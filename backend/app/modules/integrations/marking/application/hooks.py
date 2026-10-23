"""Document hooks of the marking integration (contracts/marking.md; 19 §8, 21 §4, 16 §7, 18 §4.2).

Every method runs in the CALLER's tenant transaction and only writes rows (``outbox_jobs``, ``marking_codes``,
M18 events, audit): CRPT is called by :mod:`.outbox` after COMMIT (21 §0, 23 §2.1 step 5).

* goods receipt ``post`` → ``marking_accept`` with the group deadline (qaror #63);
* supplier return / write-off ``post`` → codes ``returned_to_supplier`` / ``written_off`` +
  ``marking_supplier_return`` / ``marking_writeoff``;
* cancel of those documents → codes back, an unsent notice closed, a confirmed one → M18;
* sales: an offline-sold code is verified later (``marking_verify``, 16 §7); a duplicate code on a receipt
  the FM already signed → M18 ``marking_alert`` (B3 F-5; the sync exception is the sales handler's).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit
from app.core.error_codes import ErrorCode
from app.core.errors import AppError, ErrorDetail
from app.modules.integrations.marking.application.repository import JobRow, MarkingRepository
from app.modules.integrations.marking.domain import deadline, rules

ALERT: str = "marking_alert"  # M18 kind (reports.finance.view)
DUE: str = "marking_acceptance_due"  # M18 kind (purchases.return)


class EventSink(Protocol):
    """``notifications.EventRecorder.record_event`` (contract 7)."""

    async def record_event(
        self, s: AsyncSession, tenant_id: UUID, kind: str, payload: Mapping[str, Any], dedupe_key: str
    ) -> bool: ...


@dataclass(frozen=True, slots=True)
class MarkedLine:
    """A marked line of a supplier return / write-off (``index`` → field ``lines[i].marking_codes``)."""

    index: int
    product_id: UUID
    qty: Decimal
    codes: tuple[str, ...]


def iso(at: datetime) -> str:
    return at.astimezone(UTC).isoformat().replace("+00:00", "Z")


def parse_at(raw: Any) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None


def _invalid(index: int, key: str) -> AppError:
    return AppError(
        ErrorCode.VALIDATION_ERROR,
        details=[ErrorDetail(field=f"lines[{index}].marking_codes", message_key=key)],
    )


class MarkingHooks:
    def __init__(self, repo: MarkingRepository, events: EventSink) -> None:
        self._repo = repo
        self._events = events

    # --- M07 goods receipt -------------------------------------------------------------------------
    async def on_goods_receipt_posted(
        self,
        s: AsyncSession,
        tenant_id: UUID,
        receipt_id: UUID,
        *,
        doc_date: date,
        shipped_on: date | None = None,
        actor_user_id: UUID | None = None,
    ) -> UUID | None:
        found = await self._repo.receipt_codes(s, receipt_id)
        if not found:
            return None
        start = deadline.ownership_start(doc_date, shipped_on)
        kind, due = deadline.strictest({c.deadline_kind or "3_business_days" for c in found}, start)
        payload = {
            "receipt_id": str(receipt_id),
            "codes": [c.code for c in found],
            "deadline_kind": kind,
            "ownership_at": iso(start),
            "due_at": iso(due),
        }
        job_id = await self._repo.insert_job(
            s, tenant_id, rules.ACCEPT, payload, f"{rules.ACCEPT}:{receipt_id}"
        )
        await record_audit(
            s,
            tenant_id=tenant_id,
            user_id=actor_user_id,
            action="marking.accept_queued",
            entity="goods_receipts",
            entity_id=receipt_id,
            after={"codes": len(found), "deadline_kind": kind, "due_at": iso(due)},
        )
        return job_id

    async def on_goods_receipt_cancelled(
        self, s: AsyncSession, tenant_id: UUID, receipt_id: UUID, *, actor_user_id: UUID | None = None
    ) -> None:
        await self._cancel_notice(
            s,
            tenant_id,
            f"{rules.ACCEPT}:{receipt_id}",
            receipt_id,
            actor_user_id,
            "accepted_receipt_cancelled",
        )

    async def acceptance(
        self, s: AsyncSession, receipt_id: UUID, *, now: datetime | None = None
    ) -> dict[str, Any] | None:
        """19 §8 ``marking_acceptance`` of a posted receipt (``None`` — no acceptance job)."""
        job = await self._repo.job_by_key(s, f"{rules.ACCEPT}:{receipt_id}")
        if job is None or job.payload.get("cancelled"):
            return None
        return acceptance_view(job, now or datetime.now(UTC))

    # --- supplier return / write-off -----------------------------------------------------------------
    async def on_supplier_return_posted(
        self,
        s: AsyncSession,
        tenant_id: UUID,
        return_id: UUID,
        *,
        lines: Sequence[MarkedLine],
        actor_user_id: UUID | None = None,
    ) -> UUID | None:
        return await self._move(
            s,
            tenant_id,
            return_id,
            lines,
            "returned_to_supplier",
            rules.SUPPLIER_RETURN,
            "supplier_returns",
            actor_user_id,
        )

    async def on_write_off_posted(
        self,
        s: AsyncSession,
        tenant_id: UUID,
        write_off_id: UUID,
        *,
        lines: Sequence[MarkedLine],
        actor_user_id: UUID | None = None,
    ) -> UUID | None:
        return await self._move(
            s, tenant_id, write_off_id, lines, "written_off", rules.WRITEOFF, "write_offs", actor_user_id
        )

    async def on_codes_document_cancelled(
        self, s: AsyncSession, tenant_id: UUID, doc_id: UUID, *, actor_user_id: UUID | None = None
    ) -> None:
        for status, kind in (
            ("returned_to_supplier", rules.SUPPLIER_RETURN),
            ("written_off", rules.WRITEOFF),
        ):
            if await self._repo.restore_codes(s, doc_id, status):
                await self._cancel_notice(
                    s, tenant_id, f"{kind}:{doc_id}", doc_id, actor_user_id, "crpt_notice_cancelled"
                )

    async def _move(
        self,
        s: AsyncSession,
        tenant_id: UUID,
        doc_id: UUID,
        lines: Sequence[MarkedLine],
        status: str,
        kind: str,
        entity: str,
        actor_user_id: UUID | None,
    ) -> UUID | None:
        wanted = [c for ln in lines for c in ln.codes]
        if not wanted:
            for ln in lines:
                if ln.qty > 0:
                    raise _invalid(ln.index, "validation.marking_count_mismatch")
            return None
        found = await self._repo.codes(s, wanted, lock=True)
        seen: set[str] = set()
        for ln in lines:
            if Decimal(len(ln.codes)) != ln.qty:
                raise _invalid(ln.index, "validation.marking_count_mismatch")
            for code in ln.codes:
                if code in seen:
                    raise _invalid(ln.index, "validation.marking_code_duplicate")
                seen.add(code)
                row = found.get(code)
                if row is None or row.status != "in_stock" or row.product_id != ln.product_id:
                    raise _invalid(ln.index, "validation.marking_code_not_in_stock")
        await self._repo.move_codes(s, wanted, status, doc_id)
        payload = {"doc_id": str(doc_id), "doc_type": entity, "codes": wanted}
        job_id = await self._repo.insert_job(s, tenant_id, kind, payload, f"{kind}:{doc_id}")
        await record_audit(
            s,
            tenant_id=tenant_id,
            user_id=actor_user_id,
            action=f"marking.{status}",
            entity=entity,
            entity_id=doc_id,
            after={"codes": len(wanted), "job_id": str(job_id)},
        )
        return job_id

    async def _cancel_notice(
        self,
        s: AsyncSession,
        tenant_id: UUID,
        key: str,
        doc_id: UUID,
        actor_user_id: UUID | None,
        reason: str,
    ) -> None:
        job = await self._repo.job_by_key(s, key, lock=True)
        if job is None:
            return
        if job.status == "done" and not job.payload.get("cancelled"):  # CRPT already has the notice
            await self._events.record_event(
                s,
                tenant_id,
                ALERT,
                {
                    "reason": reason,
                    "doc_id": str(doc_id),
                    "crpt_doc_id": job.payload.get("crpt_doc_id"),
                    "codes": list(_codes(job))[:20],
                },
                f"{ALERT}:{reason}:{doc_id}",
            )
        else:
            await self._repo.finish(
                s, job.id, "done", "document cancelled before the CRPT notice", patch={"cancelled": True}
            )
        await record_audit(
            s,
            tenant_id=tenant_id,
            user_id=actor_user_id,
            action="marking.notice_cancelled",
            entity="outbox_jobs",
            entity_id=job.id,
            after={"kind": job.kind, "doc_id": str(doc_id), "was": job.status},
        )

    # --- sales (16 §7, 18 §4.2) ----------------------------------------------------------------------
    async def on_offline_sale(
        self,
        s: AsyncSession,
        tenant_id: UUID,
        sale_id: UUID,
        *,
        branch_id: UUID,
        codes: Sequence[str],
        precheck_mode: str,
    ) -> UUID | None:
        """``MARKING_PRECHECK != off``: verify the offline-sold codes later (16 §7 "Internet qaytganda")."""
        if not codes or rules.mode_of(precheck_mode) == "off":
            return None
        payload = {"sale_id": str(sale_id), "branch_id": str(branch_id), "codes": list(codes)}
        return await self._repo.insert_job(s, tenant_id, rules.VERIFY, payload, f"{rules.VERIFY}:{sale_id}")

    async def on_signed_duplicate(
        self,
        s: AsyncSession,
        tenant_id: UUID,
        sale_id: UUID,
        *,
        branch_id: UUID,
        device_id: UUID | None,
        codes: Sequence[str],
    ) -> None:
        """B3 F-5: an FM-signed receipt carries a code the tenant already sold — accepted, Owner/Accountant
        alerted (M18)."""
        await self._events.record_event(
            s,
            tenant_id,
            ALERT,
            {
                "reason": "duplicate_code",
                "sale_id": str(sale_id),
                "branch_id": str(branch_id),
                "device_id": str(device_id) if device_id else None,
                "codes": sorted(codes)[:20],
            },
            f"{ALERT}:duplicate_code:{sale_id}",
        )


def _codes(job: JobRow) -> list[str]:
    raw = job.payload.get("codes")
    return [str(c) for c in raw] if isinstance(raw, list) else []


def acceptance_view(job: JobRow, now: datetime) -> dict[str, Any]:
    due = parse_at(job.payload.get("due_at"))
    kind = str(job.payload.get("deadline_kind") or "3_business_days")
    if job.status == "done":
        status = "accepted"
    elif due is not None and now >= due:
        status = "overdue"
    else:
        status = "pending"
    out: dict[str, Any] = {"status": status, "due_at": iso(due) if due else None, "deadline_kind": kind}
    return out
