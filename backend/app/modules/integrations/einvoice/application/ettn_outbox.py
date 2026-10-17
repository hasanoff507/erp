"""Outbox worker of ``outbox_jobs(kind='ettn_send')`` — registers outgoing e-TTNs (21 §0, §3; 19 §20).

One run = **claim → commit → call the operator → record** (the operator is never called inside a
business transaction, 23 §2.1 step 5):

1. *claim* (own transaction): ``SELECT … FOR UPDATE SKIP LOCKED`` of one due ``ettn_send`` job
   (``status IN ('queued','retry') AND next_run_at ≤ now()``, or a ``running`` job whose worker died
   ``STALE_RUNNING`` ago) → ``running``, ``attempts + 1``; the e-TTN → ``sending``. An e-TTN that is
   no longer sendable (cancelled with its transfer, already registered) closes the job as ``done``.
2. ``EInvoicePort.send_ettn(ettn_id, payload)`` — ``ettn_id`` is the operator idempotency key.
3. *record* (second transaction): ``registered`` → e-TTN ``registered`` + ``operator_doc_id``,
   ``transfers.ettn_ref = operator_doc_id``, job ``done``; a permanent failure (``auth`` /
   ``validation`` or ``ETtnResult.status='failed'``) → e-TTN and job ``failed`` + ``last_error`` +
   ``audit_log`` (21 §0: legally relevant dead letters are audited); a ``transient`` error → job
   ``retry`` with backoff (:mod:`..domain.retry`), the 24th failed try → ``failed``. If the transfer was
   cancelled while the call was in flight, the e-TTN stays ``cancelled`` and keeps the operator id
   with a note (cancel it in the operator cabinet).

Lock order (SEC-03) is the same everywhere: **transfer → outbox job → e-TTN**. Transfer cancel takes
them in that order; the record step reads ``transfer_id`` without a lock (from the claim), then
``SELECT transfers … FOR UPDATE``, the job row, then the e-TTN; the claim takes job → e-TTN (a suffix
of the same order), so the worker and a cancel never wait on each other in a cycle.

Only ``kind='ettn_send'`` rows are touched (the telegram outbox belongs to notifications).
"""

from __future__ import annotations

import random
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Protocol
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.audit import record_audit
from app.core.db.session import tenant_transaction
from app.modules.integrations.einvoice.application.ports import (
    EInvoicePort,
    EInvoiceProviderError,
    ETtnResult,
)
from app.modules.integrations.einvoice.domain.retry import exhausted, retry_delay

log = structlog.get_logger(__name__)

KIND = "ettn_send"
SENDABLE = frozenset({"pending_signature", "sending", "failed"})


@dataclass(frozen=True, slots=True)
class ClaimedJob:
    id: UUID
    payload: Mapping[str, Any]
    attempts: int


@dataclass(frozen=True, slots=True)
class EttnRow:
    id: UUID
    transfer_id: UUID | None
    status: str
    payload: Mapping[str, Any]


class EttnOutboxRepository(Protocol):
    async def claim(self, s: AsyncSession, job_id: UUID | None) -> ClaimedJob | None: ...
    async def ettn(self, s: AsyncSession, ettn_id: UUID) -> EttnRow | None: ...
    async def lock_transfer(self, s: AsyncSession, transfer_id: UUID) -> None: ...
    async def lock_job(self, s: AsyncSession, job_id: UUID) -> None: ...
    async def set_ettn(
        self,
        s: AsyncSession,
        ettn_id: UUID,
        status: str,
        *,
        operator_doc_id: str | None,
        last_error: str | None,
    ) -> None: ...
    async def set_transfer_ref(self, s: AsyncSession, transfer_id: UUID, ref: str) -> None: ...
    async def finish(
        self,
        s: AsyncSession,
        job_id: UUID,
        status: str,
        last_error: str | None,
        run_after: timedelta | None = None,
    ) -> None:
        """``run_after`` → ``next_run_at = now() + run_after`` (database clock); ``None`` keeps it."""
        ...


@dataclass(frozen=True, slots=True)
class Outcome:
    job_id: UUID
    status: str  # done | retry | failed | skipped
    ettn_status: str | None = None
    operator_doc_id: str | None = None

    def as_json(self) -> dict[str, Any]:
        return {
            "job_id": str(self.job_id),
            "status": self.status,
            "ettn_status": self.ettn_status,
            "operator_doc_id": self.operator_doc_id,
        }


class EttnOutboxService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        repo: EttnOutboxRepository,
        port: EInvoicePort,
        *,
        rand: Callable[[], float] = random.random,
    ) -> None:
        self._sf = session_factory
        self._repo = repo
        self._port = port
        self._rand = rand

    async def run(self, tenant_id: UUID, job_id: UUID | None = None) -> Outcome | None:
        """Process one due job (``job_id`` or the oldest due); ``None`` when nothing is due."""
        async with self._sf() as s, tenant_transaction(s, tenant_id):
            job = await self._repo.claim(s, job_id)
            if job is None:
                return None
            ettn_id = _ettn_id(job.payload)
            ettn = await self._repo.ettn(s, ettn_id) if ettn_id else None
            if ettn is None or ettn.status not in SENDABLE:
                note = "e-TTN not found" if ettn is None else f"e-TTN is {ettn.status}; nothing to send"
                await self._repo.finish(s, job.id, "done", note)
                return Outcome(job.id, "skipped", ettn.status if ettn else None)
            await self._repo.set_ettn(s, ettn.id, "sending", operator_doc_id=None, last_error=None)
        try:
            result = await self._port.send_ettn(ettn.id, ettn.payload)
        except EInvoiceProviderError as exc:
            if exc.kind == "transient":
                return await self._transient(tenant_id, job, ettn, str(exc))
            return await self._failed(tenant_id, job, ettn, f"{exc.kind}: {exc}")
        except Exception as exc:  # network stack / adapter bug → transient (21 §0)
            log.warning("ettn_send_error", job_id=str(job.id), exc_info=True)
            return await self._transient(tenant_id, job, ettn, f"{type(exc).__name__}: {exc}")
        if result.status == "registered" and result.operator_doc_id:
            return await self._registered(tenant_id, job, ettn, result)
        return await self._failed(
            tenant_id, job, ettn, f"{result.error_kind or 'validation'}: {result.error}"
        )

    async def process_due(self, tenant_id: UUID, *, limit: int = 50) -> list[Outcome]:
        """Cron backstop: drain the tenant's due ``ettn_send`` jobs (lost enqueues, retries, dead workers)."""
        out: list[Outcome] = []
        while len(out) < limit:
            outcome = await self.run(tenant_id)
            if outcome is None:
                break
            out.append(outcome)
        return out

    # --- record ---------------------------------------------------------------------------------
    async def _registered(
        self, tenant_id: UUID, job: ClaimedJob, ettn: EttnRow, result: ETtnResult
    ) -> Outcome:
        op_id = result.operator_doc_id
        assert op_id is not None
        async with self._sf() as s, tenant_transaction(s, tenant_id):
            current = await self._lock_for_record(s, job, ettn)
            if current is not None and current.status == "sending":
                await self._repo.set_ettn(s, ettn.id, "registered", operator_doc_id=op_id, last_error=None)
                if ettn.transfer_id is not None:
                    await self._repo.set_transfer_ref(s, ettn.transfer_id, op_id)
                status = "registered"
            else:  # cancelled with its transfer while the call was in flight
                status = current.status if current else "missing"
                note = (
                    f"registered at the operator ({op_id}) after the e-TTN became {status}: cancel it there"
                )
                await self._repo.set_ettn(s, ettn.id, status, operator_doc_id=op_id, last_error=note)
                log.warning("ettn_registered_after_cancel", ettn_id=str(ettn.id), operator_doc_id=op_id)
            await self._repo.finish(s, job.id, "done", None)
        return Outcome(job.id, "done", status, op_id)

    async def _lock_for_record(self, s: AsyncSession, job: ClaimedJob, ettn: EttnRow) -> EttnRow | None:
        """transfer → outbox job → e-TTN (SEC-03); ``ettn.transfer_id`` was read at claim time."""
        if ettn.transfer_id is not None:
            await self._repo.lock_transfer(s, ettn.transfer_id)
        await self._repo.lock_job(s, job.id)
        return await self._repo.ettn(s, ettn.id)

    async def _failed(self, tenant_id: UUID, job: ClaimedJob, ettn: EttnRow, error: str) -> Outcome:
        error = error[:1000]
        async with self._sf() as s, tenant_transaction(s, tenant_id):
            current = await self._lock_for_record(s, job, ettn)
            status = (
                "failed"
                if current is not None and current.status == "sending"
                else (current.status if current else "missing")
            )
            await self._repo.set_ettn(s, ettn.id, status, operator_doc_id=None, last_error=error)
            await self._repo.finish(s, job.id, "failed", error)
            await record_audit(
                s, tenant_id=tenant_id, action="ettn.send_failed", entity="ettn_documents", entity_id=ettn.id,
                after={"job_id": str(job.id), "attempts": job.attempts, "error": error},
            )  # fmt: skip
        log.warning("ettn_send_failed", job_id=str(job.id), ettn_id=str(ettn.id), error=error)
        return Outcome(job.id, "failed", status)

    async def _transient(self, tenant_id: UUID, job: ClaimedJob, ettn: EttnRow, error: str) -> Outcome:
        if exhausted(job.attempts):
            return await self._failed(tenant_id, job, ettn, f"transient, {job.attempts} attempts: {error}")
        error = error[:1000]
        delay = retry_delay(job.attempts, self._rand())
        async with self._sf() as s, tenant_transaction(s, tenant_id):
            current = await self._lock_for_record(s, job, ettn)
            if current is not None and current.status == "sending":
                await self._repo.set_ettn(s, ettn.id, "sending", operator_doc_id=None, last_error=error)
            await self._repo.finish(s, job.id, "retry", error, delay)
        return Outcome(job.id, "retry", "sending")


def _ettn_id(payload: Mapping[str, Any]) -> UUID | None:
    try:
        return UUID(str(payload["ettn_id"]))
    except (KeyError, ValueError):
        return None
