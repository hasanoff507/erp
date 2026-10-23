"""Outbox worker of the CRPT notices (21 §0, §4): ``marking_verify``, ``marking_accept``,
``marking_supplier_return``, ``marking_writeoff``.

One run = **claim → commit → call CRPT → record** (CRPT is never called inside a business transaction):

1. *claim* (own transaction): ``SELECT … FOR UPDATE SKIP LOCKED`` of one due job of the four kinds (or a
   ``running`` one whose worker died) → ``running``, ``attempts + 1``; the tenant's ``MarkingPort`` is
   resolved in the same transaction (``None`` — no CRPT key → transient, the job waits);
2. the port call (``doc_id`` is CRPT's idempotency key — a repeated notice is a success);
3. *record* (second transaction, the job row locked again): success → job ``done`` + ``payload.accepted_at``
   / ``crpt_doc_id`` and ``marking_codes.verified_at``; CRPT rejected the notice (or some codes) / a
   permanent error → job ``failed`` + ``last_error`` + ``audit_log`` (legally relevant dead letter, 21 §0)
   + M18 ``marking_alert``; transient → ``retry`` with backoff (base 1 min, cap 30 min) until the group
   deadline window is over (:func:`..domain.rules.exhausted`).

``marking_verify`` (offline-sold codes, 16 §7): invalid codes → ``marking.verify_failed`` audit + M18
``marking_alert`` (the sale stands — the goods are gone; the alert is for review and later correction). A code
CRPT reports ``already_sold`` after the sale's own receipt was acknowledged by the OFD is this sale itself.

A document cancelled while the call was in flight keeps the CRPT answer in the job payload and raises the same
M18 alert as a cancel after confirmation (``payload.cancelled``).
"""

from __future__ import annotations

import random
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.audit import record_audit
from app.core.db.session import tenant_transaction
from app.modules.integrations.marking.application.hooks import ALERT, EventSink, iso, parse_at
from app.modules.integrations.marking.application.ports import (
    MarkingAcceptResult,
    MarkingPort,
    MarkingPortProvider,
    MarkingProviderError,
    MarkingResult,
    NoticeJob,
)
from app.modules.integrations.marking.application.repository import MarkingRepository
from app.modules.integrations.marking.domain import rules

log = structlog.get_logger(__name__)

STALE_RUNNING_S = 600
_ENTITY = {
    rules.VERIFY: "sales",
    rules.ACCEPT: "goods_receipts",
    rules.SUPPLIER_RETURN: "supplier_returns",
    rules.WRITEOFF: "write_offs",
}


@dataclass(frozen=True, slots=True)
class Outcome:
    job_id: UUID
    kind: str
    status: str  # done | retry | failed | skipped
    detail: str | None = None

    def as_json(self) -> dict[str, Any]:
        return {"job_id": str(self.job_id), "kind": self.kind, "status": self.status, "detail": self.detail}


@dataclass(frozen=True, slots=True)
class _Answer:
    ok: bool
    crpt_doc_id: str | None = None
    bad_codes: tuple[str, ...] = ()
    reasons: Mapping[str, str] | None = None
    error: str | None = None


class MarkingOutboxService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        repo: MarkingRepository,
        ports: MarkingPortProvider,
        events: EventSink,
        *,
        clock: Callable[[], datetime] | None = None,
        rand: Callable[[], float] = random.random,
        stale_running_s: int = STALE_RUNNING_S,
    ) -> None:
        self._sf = session_factory
        self._repo = repo
        self._ports = ports
        self._events = events
        self._clock = clock or (lambda: datetime.now(UTC))
        self._rand = rand
        self._stale = stale_running_s

    async def run(self, tenant_id: UUID, job_id: UUID | None = None) -> Outcome | None:
        async with self._sf() as s, tenant_transaction(s, tenant_id):
            job = await self._repo.claim(s, job_id, self._stale)
            if job is None:
                return None
            port = await self._ports.for_tenant(s, tenant_id)
            acked = False
            if job.kind == rules.VERIFY and _uuid(job.payload.get("sale_id")) is not None:
                acked = await self._repo.sale_acked(s, _uuid(job.payload.get("sale_id")))  # type: ignore[arg-type]
        codes = _codes(job.payload)
        if not codes:
            return await self._finish(tenant_id, job, "done", "no codes", {})
        if port is None:
            return await self._transient(tenant_id, job, "CRPT API key (crpt_api_key) is not configured")
        try:
            answer = await self._call(port, job, codes, acked)
        except MarkingProviderError as exc:
            if exc.kind == "transient":
                return await self._transient(tenant_id, job, str(exc))
            return await self._failed(tenant_id, job, f"{exc.kind}: {exc}", codes)
        except Exception as exc:  # network stack / adapter bug → transient (21 §0)
            log.warning("marking_outbox_error", job_id=str(job.id), exc_info=True)
            return await self._transient(tenant_id, job, f"{type(exc).__name__}: {exc}")
        if job.kind == rules.VERIFY:
            return await self._verified(tenant_id, job, codes, answer)
        if not answer.ok:
            return await self._failed(
                tenant_id, job, answer.error or "rejected by CRPT", list(answer.bad_codes) or codes
            )
        return await self._confirmed(tenant_id, job, codes, answer)

    async def process_due(self, tenant_id: UUID, *, limit: int = 50) -> list[Outcome]:
        out: list[Outcome] = []
        while len(out) < limit:
            outcome = await self.run(tenant_id)
            if outcome is None:
                break
            out.append(outcome)
        return out

    # --- CRPT ---------------------------------------------------------------------------------------
    async def _call(self, port: MarkingPort, job: NoticeJob, codes: list[str], acked: bool) -> _Answer:
        doc_id = _uuid(
            job.payload.get("receipt_id") or job.payload.get("doc_id") or job.payload.get("sale_id")
        )
        if job.kind == rules.VERIFY:
            reasons: dict[str, str] = {}
            for code in codes:
                res = await port.verify_code(code)
                reason = res.reason or "not_found"
                if not res.valid and not (reason == "already_sold" and acked):
                    reasons[code] = reason
            return _Answer(not reasons, bad_codes=tuple(reasons), reasons=reasons)
        assert doc_id is not None, "notice job without a document id"
        notice: MarkingAcceptResult | MarkingResult
        if job.kind == rules.ACCEPT:
            notice = await port.accept(codes, doc_id)
        elif job.kind == rules.SUPPLIER_RETURN:
            notice = await port.supplier_return(codes, doc_id)
        else:
            notice = await port.write_off(codes, doc_id)
        ok = notice.status == "accepted" and not notice.rejected_codes
        return _Answer(ok, notice.crpt_doc_id, notice.rejected_codes, error=notice.error)

    # --- record -------------------------------------------------------------------------------------
    async def _confirmed(self, tenant_id: UUID, job: NoticeJob, codes: list[str], answer: _Answer) -> Outcome:
        now = self._clock()
        async with self._sf() as s, tenant_transaction(s, tenant_id):
            row = await self._repo.lock_job(s, job.id)
            cancelled = bool(row and row.payload.get("cancelled"))
            await self._repo.mark_verified(s, codes, now)
            await self._repo.finish(
                s,
                job.id,
                "done",
                None,
                patch={"accepted_at": iso(now), "crpt_doc_id": answer.crpt_doc_id},
            )
            await record_audit(
                s,
                tenant_id=tenant_id,
                action=f"marking.{job.kind.removeprefix('marking_')}_confirmed",
                entity=_ENTITY[job.kind],
                entity_id=_doc_id(job),
                after={"job_id": str(job.id), "crpt_doc_id": answer.crpt_doc_id, "codes": len(codes)},
            )
            if cancelled:
                await self._alert(s, tenant_id, job, "crpt_notice_cancelled", codes, None)
        return Outcome(job.id, job.kind, "done", answer.crpt_doc_id)

    async def _verified(self, tenant_id: UUID, job: NoticeJob, codes: list[str], answer: _Answer) -> Outcome:
        now = self._clock()
        good = [c for c in codes if c not in answer.bad_codes]
        async with self._sf() as s, tenant_transaction(s, tenant_id):
            await self._repo.lock_job(s, job.id)
            if good:
                await self._repo.mark_verified(s, good, now)
            if answer.bad_codes:
                reasons = dict(answer.reasons or {})
                await record_audit(
                    s,
                    tenant_id=tenant_id,
                    action="marking.verify_failed",
                    entity="sales",
                    entity_id=_doc_id(job),
                    after={
                        "reason": "crpt_invalid",
                        "codes": sorted(reasons)[:20],
                        "reasons": {k: reasons[k] for k in sorted(reasons)[:20]},
                    },
                )
                await self._alert(s, tenant_id, job, "verify_failed", list(answer.bad_codes), reasons)
            await self._repo.finish(
                s, job.id, "done", None, patch={"verified_at": iso(now), "invalid": sorted(answer.bad_codes)}
            )
        return Outcome(job.id, job.kind, "done", f"{len(answer.bad_codes)} invalid")

    async def _failed(self, tenant_id: UUID, job: NoticeJob, error: str, codes: Sequence[str]) -> Outcome:
        error = error[:1000]
        async with self._sf() as s, tenant_transaction(s, tenant_id):
            await self._repo.lock_job(s, job.id)
            await self._repo.finish(s, job.id, "failed", error)
            await record_audit(
                s,
                tenant_id=tenant_id,
                action=f"marking.{job.kind.removeprefix('marking_')}_failed",
                entity=_ENTITY[job.kind],
                entity_id=_doc_id(job),
                after={"job_id": str(job.id), "attempts": job.attempts, "error": error},
            )
            await self._alert(s, tenant_id, job, "crpt_rejected", list(codes), None, error=error)
        log.warning("marking_notice_failed", job_id=str(job.id), kind=job.kind, error=error)
        return Outcome(job.id, job.kind, "failed", error)

    async def _transient(self, tenant_id: UUID, job: NoticeJob, error: str) -> Outcome:
        due = parse_at(job.payload.get("due_at"))
        if rules.exhausted(job.kind, job.attempts, self._clock(), due):
            return await self._failed(
                tenant_id, job, f"transient, {job.attempts} attempts: {error}", _codes(job.payload)
            )
        return await self._finish(
            tenant_id,
            job,
            "retry",
            error[:1000],
            None,
            run_after=rules.retry_delay(job.attempts, self._rand()),
        )

    async def _finish(
        self,
        tenant_id: UUID,
        job: NoticeJob,
        status: str,
        error: str | None,
        patch: Mapping[str, Any] | None,
        *,
        run_after: Any = None,
    ) -> Outcome:
        async with self._sf() as s, tenant_transaction(s, tenant_id):
            await self._repo.lock_job(s, job.id)
            await self._repo.finish(s, job.id, status, error, run_after=run_after, patch=patch)
        return Outcome(job.id, job.kind, status, error)

    async def _alert(
        self,
        s: AsyncSession,
        tenant_id: UUID,
        job: NoticeJob,
        reason: str,
        codes: list[str],
        reasons: Mapping[str, str] | None,
        *,
        error: str | None = None,
    ) -> None:
        doc_id = _doc_id(job)
        payload: dict[str, Any] = {
            "reason": reason,
            "job_kind": job.kind,
            "doc_type": _ENTITY[job.kind],
            "doc_id": str(doc_id) if doc_id else None,
            "codes": sorted(codes)[:20],
        }
        if job.payload.get("branch_id"):
            payload["branch_id"] = str(job.payload["branch_id"])
        if reasons:
            payload["reasons"] = {k: reasons[k] for k in sorted(reasons)[:20]}
        if error:
            payload["error"] = error[:300]
        await self._events.record_event(s, tenant_id, ALERT, payload, f"{ALERT}:{reason}:{job.id}")


def _uuid(raw: Any) -> UUID | None:
    try:
        return raw if isinstance(raw, UUID) else UUID(str(raw)) if raw else None
    except ValueError:
        return None


def _doc_id(job: NoticeJob) -> UUID | None:
    return _uuid(job.payload.get("receipt_id") or job.payload.get("doc_id") or job.payload.get("sale_id"))


def _codes(payload: Mapping[str, Any]) -> list[str]:
    raw = payload.get("codes")
    return [str(c) for c in raw] if isinstance(raw, list) else []
