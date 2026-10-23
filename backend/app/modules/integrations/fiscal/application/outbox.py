"""``outbox_jobs(kind='ofd_send')`` worker and the 48 h monitor (21 §0, §1; 16 §6; qaror #43).

**OFD send** (server-side providers: ``fake`` in B3, ``partner_cloud`` later) — one run =
claim → commit → call the provider → record (the provider is never called inside a business
transaction, 23 §2.1):

1. *claim* (own transaction): the receipt's due job → ``running``; the receipt → ``sent`` (handed to the
   provider). A receipt that is already ``fiscalized`` closes the job as ``done``.
2. ``FiscalPort.register_sale`` / ``register_refund`` / ``close_shift`` (``fiscal_receipts.id`` is the
   provider idempotency key).
3. *record*: success → ``fiscalized`` + FM requisites (``fm_terminal_id``, ``fm_receipt_seq``,
   ``fiscal_sign``, ``qr_url``, ``fiscal_at``, ``sent_at``); an OFD ack in the result → ``ofd_acked_at``
   and the sale's marking codes ``pending_verification → sold`` (16 §7). ``transient`` → receipt back to
   ``pending``, job ``retry`` (30 s × 2ⁿ, cap 15 min; every 2 min once the receipt is 40 h old — never
   given up inside the 48 h window); ``auth``/``validation`` → receipt and job ``failed`` + audit
   ``fiscal.send_failed`` (BO-14 "Qayta urinish" → :meth:`FiscalReceiptQueries.retry`).

**Monitor** (cron ``fiscal_unacked_monitor``, every 5 min): per register the oldest receipt with
``ofd_acked_at IS NULL``; at 24 / 40 / 46 / 48 h one M18 event ``offline_48h`` per (receipt, stage);
the 48 h block start / end is audited (``fiscal.offline_48h_blocked`` / ``fiscal.offline_48h_unblocked``)
and ``cash_registers.last_unacked_receipt_at`` mirrors the oldest unacked receipt.
"""

from __future__ import annotations

import base64
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Final, Protocol
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.audit import record_audit
from app.core.db.session import tenant_transaction
from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from app.core.idempotency import stage_response
from app.core.permissions import BranchScope
from app.modules.integrations.fiscal.application.ports import (
    CashRegisterRef,
    ClaimedJob,
    FiscalPort,
    FiscalProviderError,
    FiscalReceiptPayload,
    FiscalRepository,
    FiscalResult,
    ReceiptFilter,
    ReceiptRow,
    RefundInfo,
)
from app.modules.integrations.fiscal.application.service import FiscalServiceImpl
from app.modules.integrations.fiscal.domain.rules import (
    OFD_LATE_AFTER,
    is_blocked,
    ofd_backoff,
    offline_stage,
)

log = structlog.get_logger(__name__)

NOTIFY_KIND: Final = "offline_48h"


class EventRecorderPort(Protocol):
    async def record_event(
        self, s: AsyncSession, tenant_id: UUID, kind: str, payload: Mapping[str, Any], dedupe_key: str
    ) -> bool: ...


@dataclass(frozen=True, slots=True)
class SendOutcome:
    receipt_id: UUID | None
    status: str  # done | retry | failed | skipped
    receipt_status: str | None = None

    def as_json(self) -> dict[str, Any]:
        return {
            "receipt_id": str(self.receipt_id) if self.receipt_id else None,
            "status": self.status,
            "receipt_status": self.receipt_status,
        }


def _ts(value: datetime | None) -> str | None:
    return None if value is None else value.astimezone(UTC).isoformat().replace("+00:00", "Z")


class OfdSendService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        repo: FiscalRepository,
        port: FiscalPort,
    ) -> None:
        self._sf = session_factory
        self._repo = repo
        self._port = port

    async def run(self, tenant_id: UUID, receipt_id: UUID | None = None) -> SendOutcome | None:
        """Process the job of ``receipt_id`` (or the oldest due one); ``None`` when nothing is due."""
        async with self._sf() as s, tenant_transaction(s, tenant_id):
            job_id = await self._repo.job_of(s, receipt_id) if receipt_id is not None else None
            if receipt_id is not None and job_id is None:
                return None
            job = await self._repo.claim(s, job_id)
            if job is None:
                return None
            rid = _receipt_id(job.payload)
            receipt = await self._repo.get(s, rid, lock=True) if rid else None
            if receipt is None or receipt.status == "fiscalized":
                await self._repo.finish_job(s, job.id, "done", "nothing to send")
                return SendOutcome(rid, "skipped", receipt.status if receipt else None)
            register = (
                await self._repo.register(s, receipt.cash_register_id) if receipt.cash_register_id else None
            )
            if register is None:
                await self._repo.finish_job(s, job.id, "failed", "cash register not found")
                return SendOutcome(rid, "failed", receipt.status)
            refund = await self._refund_info(s, receipt)
            await self._repo.set_status(s, receipt.id, "sent")
        doc = FiscalReceiptPayload(
            receipt.id, receipt.kind, CashRegisterRef(register.id, tenant_id, register.fiscal_module_id),
            receipt.receipt_seq, receipt.payload,
        )  # fmt: skip
        try:
            if receipt.kind == "return":
                result = await self._port.register_refund(doc, refund or RefundInfo(None, None, None, None))
            elif receipt.kind == "z_report":
                result = await self._port.close_shift(doc)
            else:
                result = await self._port.register_sale(doc)
        except FiscalProviderError as exc:
            if exc.kind == "transient":
                return await self._transient(tenant_id, job, receipt, str(exc))
            return await self._failed(tenant_id, job, receipt, f"{exc.kind}: {exc}")
        except Exception as exc:  # adapter bug / network stack → transient (21 §0)
            log.warning("ofd_send_error", receipt_id=str(receipt.id), exc_info=True)
            return await self._transient(tenant_id, job, receipt, f"{type(exc).__name__}: {exc}")
        return await self._fiscalized(tenant_id, job, receipt, result)

    async def process_due(self, tenant_id: UUID, *, limit: int = 100) -> list[SendOutcome]:
        """Cron backstop: every due ``ofd_send`` job of the tenant (retries, lost enqueues, dead workers)."""
        out: list[SendOutcome] = []
        while len(out) < limit:
            outcome = await self.run(tenant_id)
            if outcome is None:
                break
            out.append(outcome)
        return out

    async def _refund_info(self, s: AsyncSession, receipt: ReceiptRow) -> RefundInfo | None:
        if receipt.kind != "return" or receipt.return_id is None:
            return None
        original = await self._repo.original_sale_receipt(s, receipt.return_id)
        if original is None:
            return None
        return RefundInfo(
            original.fm_terminal_id, original.fm_receipt_seq, original.fiscal_at, original.fiscal_sign
        )

    async def _fiscalized(
        self, tenant_id: UUID, job: ClaimedJob, receipt: ReceiptRow, result: FiscalResult
    ) -> SendOutcome:
        async with self._sf() as s, tenant_transaction(s, tenant_id):
            await self._repo.get(s, receipt.id, lock=True)
            await self._repo.set_fiscalized(s, receipt.id, result)
            if result.ofd_acked_at is not None:
                await acknowledge(self._repo, s, receipt, result.ofd_acked_at)
            await self._repo.finish_job(s, job.id, "done", None)
        return SendOutcome(receipt.id, "done", "fiscalized")

    async def _transient(
        self, tenant_id: UUID, job: ClaimedJob, receipt: ReceiptRow, error: str
    ) -> SendOutcome:
        late = datetime.now(UTC) - receipt.created_at >= OFD_LATE_AFTER  # receipt age, not scheduling
        delay = ofd_backoff(max(job.attempts, 1), late=late)
        async with self._sf() as s, tenant_transaction(s, tenant_id):
            await self._repo.get(s, receipt.id, lock=True)
            await self._repo.set_status(s, receipt.id, "pending", attempt=True)
            await self._repo.finish_job(s, job.id, "retry", error[:1000], delay)
        return SendOutcome(receipt.id, "retry", "pending")

    async def _failed(self, tenant_id: UUID, job: ClaimedJob, receipt: ReceiptRow, error: str) -> SendOutcome:
        error = error[:1000]
        async with self._sf() as s, tenant_transaction(s, tenant_id):
            await self._repo.get(s, receipt.id, lock=True)
            await self._repo.set_status(s, receipt.id, "failed", attempt=True)
            await self._repo.finish_job(s, job.id, "failed", error)
            await record_audit(
                s, tenant_id=tenant_id, action="fiscal.send_failed", entity="fiscal_receipts",
                entity_id=receipt.id, after={"job_id": str(job.id), "attempts": job.attempts, "error": error},
            )  # fmt: skip
        log.warning("ofd_send_failed", receipt_id=str(receipt.id), error=error)
        return SendOutcome(receipt.id, "failed", "failed")


async def acknowledge(repo: FiscalRepository, s: AsyncSession, receipt: ReceiptRow, at: datetime) -> None:
    """OFD ack of one receipt: ``ofd_acked_at``, the register's ``last_unacked_receipt_at`` recomputed, the
    sale's marking codes → ``sold`` (16 §6, §7; qaror #62)."""
    await repo.ack(s, receipt.id, at)
    if receipt.cash_register_id is not None:  # the device ladder reads this column (16 §6) — no monitor lag
        oldest = await repo.oldest_unacked(s, receipt.cash_register_id)
        await repo.set_last_unacked(s, receipt.cash_register_id, oldest[1] if oldest else None)
    if receipt.sale_id is not None and receipt.kind in ("sale", "debt_settlement", "credit_sale"):
        await repo.mark_codes_sold(s, receipt.sale_id)


def _receipt_id(payload: Mapping[str, Any]) -> UUID | None:
    try:
        return UUID(str(payload["fiscal_receipt_id"]))
    except (KeyError, ValueError):
        return None


# --- monitor ---------------------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class MonitorReport:
    registers: int
    events: int
    blocked: int
    unblocked: int

    def as_json(self) -> dict[str, int]:
        return {
            "registers": self.registers,
            "events": self.events,
            "blocked": self.blocked,
            "unblocked": self.unblocked,
        }


class UnackedMonitor:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        repo: FiscalRepository,
        events: EventRecorderPort,
    ) -> None:
        self._sf = session_factory
        self._repo = repo
        self._events = events

    async def run(self, tenant_id: UUID, now: datetime | None = None) -> MonitorReport:
        at = now or datetime.now(UTC)
        events = blocked = unblocked = 0
        async with self._sf() as s, tenant_transaction(s, tenant_id):
            current = {reg: (rid, created) for reg, rid, created in await self._repo.unacked_registers(s)}
            previous = dict(await self._repo.blocked_registers(s))
            for register_id in sorted(set(current) | set(previous), key=lambda u: u.int):
                prev = previous.get(register_id)
                cur = current.get(register_id)
                cur_at = cur[1] if cur else None
                if cur is not None:
                    stage = offline_stage(cur_at, at)
                    if stage is not None:
                        written = await self._events.record_event(
                            s, tenant_id, NOTIFY_KIND,
                            {"cash_register_id": str(register_id), "stage": stage, "receipt_id": str(cur[0]),
                             "oldest_unacked_at": _ts(cur_at)},
                            f"offline_48h:{register_id}:{cur[0]}:{stage}",
                        )  # fmt: skip
                        events += int(written)
                was_blocked = is_blocked(prev, at)
                now_blocked = is_blocked(cur_at, at)
                if now_blocked and not (was_blocked and prev == cur_at):
                    blocked += 1
                    await record_audit(
                        s, tenant_id=tenant_id, action="fiscal.offline_48h_blocked", entity="cash_registers",
                        entity_id=register_id, after={"oldest_unacked_at": _ts(cur_at)},
                    )  # fmt: skip
                if was_blocked and not now_blocked:
                    unblocked += 1
                    await record_audit(
                        s, tenant_id=tenant_id, action="fiscal.offline_48h_unblocked",
                        entity="cash_registers",
                        entity_id=register_id, before={"oldest_unacked_at": _ts(prev)},
                        after={"oldest_unacked_at": _ts(cur_at)},
                    )  # fmt: skip
                    await self._events.record_event(
                        s, tenant_id, NOTIFY_KIND,
                        {"cash_register_id": str(register_id), "stage": "cleared", "previous": _ts(prev)},
                        f"offline_48h:{register_id}:cleared:{_ts(prev)}",
                    )  # fmt: skip
                if prev != cur_at:
                    await self._repo.set_last_unacked(s, register_id, cur_at)
        return MonitorReport(len(current), events, blocked, unblocked)


# --- REST: GET /fiscal-receipts, retry ------------------------------------------------------------
def encode_cursor(at: datetime, rid: UUID) -> str:
    return base64.urlsafe_b64encode(f"{at.isoformat()}|{rid}".encode()).decode()


def decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode()).decode()
        at, rid = raw.split("|", 1)
        return datetime.fromisoformat(at), UUID(rid)
    except (ValueError, UnicodeDecodeError):
        raise AppError(ErrorCode.VALIDATION_ERROR, params={"field": "cursor"}) from None


def receipt_json(r: ReceiptRow) -> dict[str, Any]:
    return {
        "id": str(r.id), "sale_id": _s(r.sale_id), "debt_payment_id": _s(r.debt_payment_id),
        "return_id": _s(r.return_id), "kind": r.kind, "status": r.status, "receipt_seq": r.receipt_seq,
        "fm_terminal_id": r.fm_terminal_id, "fm_receipt_seq": r.fm_receipt_seq, "fiscal_sign": r.fiscal_sign,
        "qr_url": r.qr_url, "payment_form": r.payment_form, "delivery": r.delivery,
        "fiscal_at": _ts(r.fiscal_at), "ofd_acked_at": _ts(r.ofd_acked_at), "sent_at": _ts(r.sent_at),
        "offline_since": _ts(r.offline_since), "attempts": r.attempts,
        "cash_register_id": _s(r.cash_register_id),
        "shift_id": _s(r.shift_id), "created_at": _ts(r.created_at),
    }  # fmt: skip


def _s(value: UUID | None) -> str | None:
    return None if value is None else str(value)


def _check_scope(scope: BranchScope, r: ReceiptRow) -> None:
    if scope.current is not None and r.branch_id != scope.current:
        raise AppError(ErrorCode.NOT_FOUND, params={"resource": "fiscal_receipt"})
    if not scope.unrestricted and r.branch_id not in scope.allowed:
        raise AppError(ErrorCode.NOT_FOUND, params={"resource": "fiscal_receipt"})


class FiscalReceiptQueries:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        repo: FiscalRepository,
        service: FiscalServiceImpl,
    ) -> None:
        self._sf = session_factory
        self._repo = repo
        self._service = service

    async def list_page(
        self, tenant_id: UUID, user_id: UUID, flt: ReceiptFilter, cursor: str | None, limit: int
    ) -> dict[str, Any]:
        after = decode_cursor(cursor) if cursor else None
        async with self._sf() as s, tenant_transaction(s, tenant_id, user_id=user_id):
            rows = await self._repo.page(s, flt, after, limit + 1)
        page = rows[:limit]
        next_cursor = encode_cursor(page[-1].created_at, page[-1].id) if len(rows) > limit else None
        return {"items": [receipt_json(r) for r in page], "next_cursor": next_cursor}

    async def get(
        self, tenant_id: UUID, user_id: UUID, scope: BranchScope, receipt_id: UUID
    ) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, tenant_id, user_id=user_id):
            row = await self._repo.get(s, receipt_id)
        if row is None:
            raise AppError(ErrorCode.NOT_FOUND, params={"resource": "fiscal_receipt"})
        _check_scope(scope, row)
        return receipt_json(row)

    async def retry(
        self, tenant_id: UUID, user_id: UUID, scope: BranchScope, receipt_id: UUID, ip: str | None
    ) -> dict[str, Any]:
        """18 §14.2: the receipt's ``ofd_send`` job back to ``queued`` (a failed receipt → ``pending``)."""
        async with self._sf() as s, tenant_transaction(s, tenant_id, user_id=user_id):
            row = await self._repo.get(s, receipt_id, lock=True)
            if row is None:
                raise AppError(ErrorCode.NOT_FOUND, params={"resource": "fiscal_receipt"})
            _check_scope(scope, row)
            if row.status == "fiscalized" or not self._service.server_side:
                raise AppError(ErrorCode.DOC_INVALID_STATE, params={"status": row.status})
            job_id = await self._repo.requeue(s, receipt_id)
            if job_id is None:
                job_id = await self._repo.insert_job(s, tenant_id, receipt_id)
            if row.status == "failed":
                await self._repo.set_status(s, receipt_id, "pending")
            await record_audit(
                s, tenant_id=tenant_id, user_id=user_id, action="fiscal.retry", entity="fiscal_receipts",
                entity_id=receipt_id, before={"status": row.status}, after={"job_id": str(job_id)}, ip=ip,
            )  # fmt: skip
            body = {"status": "requeued"}
            stage_response(body, 200)
        await self._service.enqueue(tenant_id, [receipt_id])
        return body
