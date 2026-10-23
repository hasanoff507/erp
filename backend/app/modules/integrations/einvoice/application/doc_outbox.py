"""Outbox worker of the signed e-documents (21 §0, §2, §3, §6): ``outbox_jobs`` kinds ``einvoice_send``,
``einvoice_accept`` (accept or reject of an incoming EHF), ``poa_send`` and ``ettn_accept``.

Same shape as the ``ettn_send`` worker (:mod:`.ettn_outbox`): **claim → commit → call the operator →
record**; the operator is never called inside a business transaction (23 §2.1 step 5). The document's
newest stored E-IMZO signature (``edoc_signatures``) goes with the call. Errors follow 21 §0: ``transient`` →
``retry`` with backoff (1 min × 2, cap 1 h, 24 tries → ``failed``), ``auth``/``validation`` → ``failed`` +
``audit_log`` (``edoc.send_failed``); a power of attorney becomes ``failed`` with ``last_error`` (re-sign →
``sending``). Lock order: outbox job → document (the API takes the same order).

Recording an **accepted** incoming EHF also accepts its combined e-TTN (19 §19) and, for an *additional*
EHF linked to a posted supplier return, writes the 13 §2.20 VAT row
(:meth:`VatCredit.adjust_supplier_return`).
"""

from __future__ import annotations

import random
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Final, Protocol
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.audit import record_audit
from app.core.db.session import tenant_transaction
from app.modules.accounting.domain.calendar import business_today
from app.modules.integrations.einvoice.application.common import (
    EINVOICE_ACCEPT,
    EINVOICE_SEND,
    ETTN_ACCEPT,
    POA_SEND,
)
from app.modules.integrations.einvoice.application.ports import (
    EInvoicePortProvider,
    EInvoiceProviderError,
    Pkcs7Signature,
)
from app.modules.integrations.einvoice.application.records import EDocsRepository, StoredSignature
from app.modules.integrations.einvoice.application.vat_credit import VatCredit
from app.modules.integrations.einvoice.domain.documents import EINVOICE_REJECTABLE, ETTN_RESPONDABLE
from app.modules.integrations.einvoice.domain.retry import exhausted, retry_delay

log = structlog.get_logger(__name__)

KINDS: Final = (EINVOICE_SEND, EINVOICE_ACCEPT, POA_SEND, ETTN_ACCEPT)


@dataclass(frozen=True, slots=True)
class DocJob:
    id: UUID
    kind: str
    payload: Mapping[str, Any]
    attempts: int


class DocJobRepository(Protocol):
    async def claim(self, s: AsyncSession, kinds: tuple[str, ...], job_id: UUID | None) -> DocJob | None: ...
    async def lock_job(self, s: AsyncSession, job_id: UUID) -> None: ...
    async def finish(
        self,
        s: AsyncSession,
        job_id: UUID,
        status: str,
        last_error: str | None,
        run_after: timedelta | None = None,
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class DocOutcome:
    job_id: UUID
    kind: str
    status: str  # done | retry | failed | skipped
    doc_status: str | None = None

    def as_json(self) -> dict[str, Any]:
        return {
            "job_id": str(self.job_id),
            "kind": self.kind,
            "status": self.status,
            "doc_status": self.doc_status,
        }


@dataclass(frozen=True, slots=True)
class _Prepared:
    entity: str
    doc_id: UUID
    operator_doc_id: str | None
    signature: StoredSignature | None
    payload: Mapping[str, Any]


def _pkcs7(sig: StoredSignature | None) -> Pkcs7Signature | None:
    return None if sig is None else Pkcs7Signature(sig.signature_pkcs7, sig.certificate_serial)


def _uuid(payload: Mapping[str, Any], key: str) -> UUID | None:
    try:
        return UUID(str(payload[key]))
    except (KeyError, ValueError):
        return None


class DocOutboxService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        jobs: DocJobRepository,
        docs: EDocsRepository,
        ports: EInvoicePortProvider,
        vat: VatCredit,
        *,
        rand: Callable[[], float] = random.random,
    ) -> None:
        self._sf = session_factory
        self._jobs = jobs
        self._docs = docs
        self._ports = ports
        self._vat = vat
        self._rand = rand

    async def process_due(self, tenant_id: UUID, *, limit: int = 50) -> list[DocOutcome]:
        out: list[DocOutcome] = []
        while len(out) < limit:
            outcome = await self.run(tenant_id)
            if outcome is None:
                break
            out.append(outcome)
        return out

    async def run(self, tenant_id: UUID, job_id: UUID | None = None) -> DocOutcome | None:
        async with self._sf() as s, tenant_transaction(s, tenant_id):
            job = await self._jobs.claim(s, KINDS, job_id)
            if job is None:
                return None
            prepared, skip = await self._prepare(s, job)
            if prepared is None:
                await self._jobs.finish(s, job.id, "done", skip)
                return DocOutcome(job.id, job.kind, "skipped")
        try:
            port = await self._ports.for_tenant(tenant_id)
            result = await self._call(port, job, prepared)
        except EInvoiceProviderError as exc:
            if exc.kind == "transient":
                return await self._transient(tenant_id, job, prepared, str(exc))
            return await self._failed(tenant_id, job, prepared, f"{exc.kind}: {exc}")
        except Exception as exc:  # network stack / adapter bug → transient (21 §0)
            log.warning("edoc_send_error", job_id=str(job.id), exc_info=True)
            return await self._transient(tenant_id, job, prepared, f"{type(exc).__name__}: {exc}")
        return await self._record(tenant_id, job, prepared, result)

    # --- claim ----------------------------------------------------------------------------------------
    async def _prepare(self, s: AsyncSession, job: DocJob) -> tuple[_Prepared | None, str | None]:
        if job.kind in (EINVOICE_SEND, EINVOICE_ACCEPT):
            doc_id = _uuid(job.payload, "einvoice_id")
            e = await self._docs.einvoice(s, doc_id) if doc_id else None
            if e is None:
                return None, "e-invoice not found"
            action = job.payload.get("action", "accept")
            ok = (
                (e.direction == "out" and e.status == "signed")
                if job.kind == EINVOICE_SEND
                else (
                    e.direction == "in"
                    and (e.status == "signed" if action == "accept" else e.status in EINVOICE_REJECTABLE)
                )
            )
            if not ok:
                return None, f"e-invoice is {e.status}; nothing to send"
            sig = await self._docs.latest_signature(s, "einvoices", e.id, "sign")
            if sig is None and not (job.kind == EINVOICE_ACCEPT and action == "reject"):
                return None, "no E-IMZO signature"
            return _Prepared("einvoices", e.id, e.operator_doc_id, sig, e.payload), None
        if job.kind == POA_SEND:
            doc_id = _uuid(job.payload, "poa_id")
            p = await self._docs.poa(s, doc_id) if doc_id else None
            if p is None or p.status != "sending":
                return None, "power of attorney is not sending"
            sig = await self._docs.latest_signature(s, "powers_of_attorney", p.id, "sign")
            if sig is None:
                return None, "no E-IMZO signature"
            body = {
                "supplier_stir": p.supplier_stir,
                "employee_user_id": str(p.employee_user_id),
                "employee_name": p.employee_name,
                "doc_date": p.doc_date.isoformat(),
                "valid_from": p.valid_from.isoformat(),
                "valid_to": p.valid_to.isoformat(),
            }
            return _Prepared("powers_of_attorney", p.id, p.operator_doc_id, sig, body), None
        doc_id = _uuid(job.payload, "ettn_id")
        x = await self._docs.ettn(s, doc_id) if doc_id else None
        if x is None or x.status not in ETTN_RESPONDABLE[x.direction] or not x.operator_doc_id:
            return None, "e-TTN is not awaiting an answer"
        action = str(job.payload.get("action", "accept"))
        sig = await self._docs.latest_signature(s, "ettn_documents", x.id, action)
        if sig is None:
            return None, "no E-IMZO signature"
        return _Prepared("ettn_documents", x.id, x.operator_doc_id, sig, x.payload), None

    async def _call(self, port: Any, job: DocJob, p: _Prepared) -> Any:
        sig = _pkcs7(p.signature)
        if job.kind == EINVOICE_SEND:
            assert sig is not None
            return await port.send_outgoing(p.doc_id, sig, payload=p.payload)
        if job.kind == EINVOICE_ACCEPT:
            if job.payload.get("action") == "reject":
                return await port.reject_incoming(
                    p.doc_id, str(job.payload.get("reason") or ""), sig, operator_doc_id=p.operator_doc_id
                )
            assert sig is not None
            return await port.sign_and_accept(p.doc_id, sig, operator_doc_id=p.operator_doc_id)
        if job.kind == POA_SEND:
            assert sig is not None
            return await port.send_power_of_attorney(p.doc_id, sig, payload=p.payload)
        assert sig is not None
        assert p.operator_doc_id is not None
        action = "reject" if job.payload.get("action") == "reject" else "accept"
        return await port.respond_ettn(p.doc_id, p.operator_doc_id, action, sig, job.payload.get("reason"))

    # --- record ---------------------------------------------------------------------------------------
    async def _record(self, tenant_id: UUID, job: DocJob, p: _Prepared, result: Any) -> DocOutcome:
        status_ok = getattr(result, "status", None)
        error = getattr(result, "error", None)
        if job.kind == POA_SEND and status_ok != "sent":
            return await self._failed(tenant_id, job, p, f"validation: {error or 'rejected'}")
        if job.kind == EINVOICE_SEND and status_ok != "sent":
            return await self._failed(tenant_id, job, p, f"validation: {error or 'rejected'}")
        async with self._sf() as s, tenant_transaction(s, tenant_id):
            await self._jobs.lock_job(s, job.id)
            doc_status = await self._apply(s, tenant_id, job, p, result)
            await self._jobs.finish(s, job.id, "done", None)
        return DocOutcome(job.id, job.kind, "done", doc_status)

    async def _apply(self, s: AsyncSession, tenant_id: UUID, job: DocJob, p: _Prepared, result: Any) -> str:
        now = datetime.now(UTC)
        if job.kind == EINVOICE_SEND:
            e = await self._docs.einvoice(s, p.doc_id, lock=True)
            if e is None or e.status != "signed":
                return e.status if e else "missing"
            await self._docs.update_einvoice(
                s, e.id, {"status": "sent", "operator_doc_id": result.operator_doc_id}
            )
            return "sent"
        if job.kind == EINVOICE_ACCEPT:
            e = await self._docs.einvoice(s, p.doc_id, lock=True)
            if e is None:
                return "missing"
            new = "rejected" if job.payload.get("action") == "reject" else "accepted"
            if e.status in ("accepted", "rejected"):
                return e.status
            values: dict[str, Any] = {"status": new}
            if result.operator_doc_id and not e.operator_doc_id:
                values["operator_doc_id"] = result.operator_doc_id
            await self._docs.update_einvoice(s, e.id, values)
            for ettn_id in await self._docs.ettns_of_einvoice(s, e.id):  # combined EHF+TTN (19 §19)
                await self._docs.update_ettn(s, ettn_id, {"status": new})
            if (
                new == "accepted"
                and e.factura_type == "additional"
                and e.related_doc_type == "supplier_returns"
            ):
                assert e.related_doc_id is not None
                await self._vat.adjust_supplier_return(s, tenant_id, e.related_doc_id, business_today())
            await record_audit(
                s,
                tenant_id=tenant_id,
                action=f"einvoice.{new}",
                entity="einvoices",
                entity_id=e.id,
                before={"status": e.status},
                after={"status": new, "job_id": str(job.id)},
            )
            return new
        if job.kind == POA_SEND:
            poa = await self._docs.poa(s, p.doc_id, lock=True)
            if poa is None or poa.status != "sending":
                return poa.status if poa else "missing"
            await self._docs.update_poa(
                s,
                poa.id,
                {
                    "status": "sent",
                    "number": result.number,
                    "operator_doc_id": result.operator_doc_id,
                    "sent_at": now,
                    "last_error": None,
                },
            )
            return "sent"
        x = await self._docs.ettn(s, p.doc_id, lock=True)
        if x is None:
            return "missing"
        new = "rejected" if job.payload.get("action") == "reject" else "accepted"
        await self._docs.update_ettn(s, x.id, {"status": new, "last_error": None})
        await record_audit(
            s,
            tenant_id=tenant_id,
            action=f"ettn.{new}",
            entity="ettn_documents",
            entity_id=x.id,
            before={"status": x.status},
            after={"status": new, "job_id": str(job.id)},
        )
        return new

    async def _failed(self, tenant_id: UUID, job: DocJob, p: _Prepared, error: str) -> DocOutcome:
        error = error[:1000]
        doc_status: str | None = None
        async with self._sf() as s, tenant_transaction(s, tenant_id):
            await self._jobs.lock_job(s, job.id)
            if job.kind == POA_SEND:
                poa = await self._docs.poa(s, p.doc_id, lock=True)
                if poa is not None and poa.status == "sending":
                    await self._docs.update_poa(s, poa.id, {"status": "failed", "last_error": error})
                    doc_status = "failed"
            elif job.kind == ETTN_ACCEPT:
                await self._docs.update_ettn(s, p.doc_id, {"last_error": error})
            await self._jobs.finish(s, job.id, "failed", error)
            await record_audit(
                s,
                tenant_id=tenant_id,
                action="edoc.send_failed",
                entity=p.entity,
                entity_id=p.doc_id,
                after={"job_id": str(job.id), "kind": job.kind, "attempts": job.attempts, "error": error},
            )
        log.warning("edoc_send_failed", job_id=str(job.id), kind=job.kind, error=error)
        return DocOutcome(job.id, job.kind, "failed", doc_status)

    async def _transient(self, tenant_id: UUID, job: DocJob, p: _Prepared, error: str) -> DocOutcome:
        if exhausted(job.attempts):
            return await self._failed(tenant_id, job, p, f"transient, {job.attempts} attempts: {error}")
        delay = retry_delay(job.attempts, self._rand())
        async with self._sf() as s, tenant_transaction(s, tenant_id):
            await self._jobs.lock_job(s, job.id)
            await self._jobs.finish(s, job.id, "retry", error[:1000], delay)
        return DocOutcome(job.id, job.kind, "retry")
