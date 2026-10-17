"""Shifts: ``shift.opened`` / ``shift.closed`` postings and the back-office views (18 §3, 20 #55; 13 §2.19).

``open`` (``shift.open`` — checked by sync): register of the pushing device, no other open shift on it
(``SHIFT_ALREADY_OPEN``), ``shift_no`` unique per register; ``opened_at`` = effective event time. No
posting and no ``cash_moves`` row for the opening cash (13 X-01).

``close`` (``shift.close`` — sync; ``cash.count.shift`` — here): shift locked ``FOR UPDATE``; another
device → ``SHIFT_DEVICE_MISMATCH``; not open → ``SHIFT_NOT_OPEN``; an unresolved card attempt of the
shift → ``CARD_OUTCOME_UNKNOWN`` and the event's terminal settlements — both through the card slice's
``CardPayments`` (``assert_shift_resolved``, ``record_shift_settlements``); then
``expected_cash = opening + Σ cash_moves``, variance + note rule, the 13 §2.19 variance line
(``doc_type='shifts'``), the ``z_report`` fiscal receipt (``FiscalService``, kind ``z_report`` — one per
shift, QT-SEQ-03) and, for a non-zero variance, the ``cash_variance`` notification event (M18 — recorded
only, sending is Bosqich 4).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.audit import record_audit
from app.core.auth.principal import Principal
from app.core.db.session import tenant_transaction
from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from app.core.permissions import BranchScope
from app.modules.accounting.wiring import LedgerLine, LedgerPoster, business_date, day_end, day_start
from app.modules.cash.application.common import (
    check_branch,
    decode_cursor,
    encode_cursor,
    invalid,
    m2,
    register_date,
    scope_branches,
    ts,
)
from app.modules.cash.application.ports import CashRepository, ShiftFilter, ShiftRow
from app.modules.cash.domain.shifts import expected_cash, running_totals, variance_entry, z_report
from app.modules.integrations.card_terminal.application.contracts import CardPayments
from app.modules.integrations.fiscal.application.contracts import FiscalService
from app.modules.sync.application.handlers import EventContext, SyncExceptionRow


class NotificationRecorder(Protocol):
    async def record_event(
        self, s: AsyncSession, tenant_id: UUID, kind: str, payload: Mapping[str, Any], dedupe_key: str
    ) -> bool: ...


OFFLINE_AFTER = timedelta(minutes=5)  # an event received later than this after its time was made offline


@dataclass(frozen=True, slots=True)
class OpenInput:
    id: UUID
    cash_register_id: UUID
    shift_no: int
    opening_cash: Decimal
    comment: str | None


@dataclass(frozen=True, slots=True)
class CloseInput:
    shift_id: UUID
    counted_cash: Decimal
    counted_card_total: Decimal | None
    card_settlements: Sequence[Mapping[str, Any]]
    variance_note: str | None


@dataclass(slots=True)
class CloseResult:
    server: dict[str, Any]
    sync_exceptions: list[SyncExceptionRow] = field(default_factory=list)
    after_commit: list[Callable[[], Awaitable[None]]] = field(default_factory=list)


def shift_json(row: ShiftRow) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "shift_no": row.shift_no,
        "branch_id": str(row.branch_id),
        "cash_register_id": str(row.cash_register_id),
        "device_id": str(row.device_id),
        "status": row.status,
        "opening_cash": m2(row.opening_cash),
        "opened_by": str(row.opened_by),
        "opened_at": ts(row.opened_at),
        "closed_by": None if row.closed_by is None else str(row.closed_by),
        "closed_at": ts(row.closed_at),
        "expected_cash": m2(row.expected_cash),
        "counted_cash": m2(row.counted_cash),
        "variance": m2(row.variance),
        "variance_note": row.variance_note,
        "counted_card_total": m2(row.counted_card_total),
        "comment": row.comment,
    }


class ShiftService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        repo: CashRepository,
        poster: LedgerPoster,
        notifications: NotificationRecorder,
        fiscal: FiscalService | None,
        card: CardPayments | None = None,
    ) -> None:
        self._sf = session_factory
        self._repo = repo
        self._poster = poster
        self._notify = notifications
        self._fiscal = fiscal
        self._card = card

    # --- shift.opened ---------------------------------------------------------------------------------
    async def open(self, s: AsyncSession, ctx: EventContext, body: OpenInput) -> dict[str, Any]:
        register = await self._repo.get_register(s, body.cash_register_id)
        if register is None or register.archived or register.branch_id != ctx.branch_id:
            raise invalid("cash_register_id", "validation.cash_register_unknown")
        if ctx.cash_register_id is not None and ctx.cash_register_id != body.cash_register_id:
            raise invalid("cash_register_id", "validation.cash_register_not_of_device")
        if await self._repo.open_shift_of_register(s, body.cash_register_id) is not None:
            raise AppError(
                ErrorCode.SHIFT_ALREADY_OPEN, params={"cash_register_id": str(body.cash_register_id)}
            )
        if await self._repo.shift_no_taken(s, body.cash_register_id, body.shift_no):
            raise invalid("shift_no", "validation.shift_no_taken")
        if await self._repo.get_shift(s, body.id) is not None:
            raise invalid("id", "validation.duplicate")
        await self._repo.insert_shift(
            s,
            {
                "id": body.id,
                "tenant_id": ctx.tenant_id,
                "branch_id": register.branch_id,
                "cash_register_id": body.cash_register_id,
                "device_id": ctx.device_id,
                "shift_no": body.shift_no,
                "opened_by": ctx.actor_user_id,
                "opened_at": ctx.created_at,
                "opening_cash": body.opening_cash,
                "comment": body.comment,
                "client_event_id": ctx.client_event_id,
            },
        )
        await record_audit(
            s,
            tenant_id=ctx.tenant_id,
            user_id=ctx.actor_user_id,
            action="shift_opened",
            entity="shifts",
            entity_id=body.id,
            device_id=ctx.device_id,
            after={
                "shift_no": body.shift_no,
                "opening_cash": m2(body.opening_cash),
                "cash_register_id": str(body.cash_register_id),
            },
        )
        return {"id": str(body.id), "cash_register_id": str(body.cash_register_id), "shift_no": body.shift_no}

    # --- shift.closed ---------------------------------------------------------------------------------
    async def close(self, s: AsyncSession, ctx: EventContext, body: CloseInput) -> CloseResult:
        count = await self._repo.grant(s, ctx.actor_user_id, "cash.count.shift")
        if not count.holds:
            raise AppError(ErrorCode.PERMISSION_DENIED, params={"permission": "cash.count.shift"})
        shift = await self._repo.get_shift(s, body.shift_id, lock="update")
        if shift is None:  # its shift.opened is not accepted yet — retry (16 §3.3, SYNC-06)
            raise AppError(
                ErrorCode.DEPENDENCY_NOT_SYNCED, params={"entity": "shifts", "shift_id": str(body.shift_id)}
            )
        if shift.device_id != ctx.device_id:
            raise AppError(ErrorCode.SHIFT_DEVICE_MISMATCH, params={"shift_id": str(body.shift_id)})
        if shift.status != "open":
            raise AppError(
                ErrorCode.SHIFT_NOT_OPEN, params={"shift_id": str(body.shift_id), "status": shift.status}
            )
        if self._card is not None:
            # the card slice owns both rules (qaror #71): unresolved attempt → CARD_OUTCOME_UNKNOWN,
            # terminal settlements of the event → card_terminal_settlements (matched/mismatch/failed)
            await self._card.assert_shift_resolved(s, shift_id=shift.id)
            await self._card.record_shift_settlements(
                s,
                tenant_id=ctx.tenant_id,
                branch_id=shift.branch_id,
                shift_id=shift.id,
                device_id=ctx.device_id,
                actor_user_id=ctx.actor_user_id,
                client_event_id=ctx.client_event_id,
                items=list(body.card_settlements),
            )
        elif await self._repo.unresolved_card_attempts(s, shift.id):
            raise AppError(ErrorCode.CARD_OUTCOME_UNKNOWN, params={"shift_id": str(shift.id)})
        totals = await self._repo.shift_totals(s, shift.id)
        expected = expected_cash(shift.opening_cash, totals.cash_moves_total)
        counted = body.counted_cash
        variance = counted - expected
        note = (body.variance_note or "").strip() or None
        if variance != 0 and note is None:
            raise invalid("variance_note", "validation.variance_note_required")
        card_total = body.counted_card_total if body.counted_card_total is not None else totals.card_manual
        await self._repo.close_shift(
            s,
            {
                "id": shift.id,
                "closed_by": ctx.actor_user_id,
                "closed_at": ctx.created_at,
                "expected_cash": expected,
                "counted_cash": counted,
                "variance_note": note,
                "counted_card_total": card_total,
            },
        )
        result = CloseResult(server={})
        doc_date = business_date(ctx.created_at)
        entry = variance_entry(
            variance, cashier_id=shift.opened_by, cash_register_id=shift.cash_register_id, shift_id=shift.id
        )
        if entry is not None:
            entry_date, correction = await register_date(s, self._poster, doc_date)
            analytics = dict(entry.analytics)
            if correction is not None:
                analytics["correction_of_period"] = correction
                result.sync_exceptions.append(
                    SyncExceptionRow(
                        kind="late_in_closed_period",
                        details={"period": correction, "doc_date": str(doc_date)},
                        doc_type="shifts",
                        doc_id=shift.id,
                    )
                )
            await self._poster.post(
                s,
                ctx.tenant_id,
                "shifts",
                shift.id,
                [
                    LedgerLine(
                        entry_date,
                        shift.branch_id,
                        entry.account_dt,
                        entry.account_kt,
                        entry.amount,
                        analytics,
                    )
                ],
            )
            await self._notify.record_event(
                s,
                ctx.tenant_id,
                "cash_variance",
                {
                    "shift_id": str(shift.id),
                    "shift_no": shift.shift_no,
                    "branch_id": str(shift.branch_id),
                    "cash_register_id": str(shift.cash_register_id),
                    "cashier_id": str(shift.opened_by),
                    "expected_cash": m2(expected),
                    "counted_cash": m2(counted),
                    "variance": m2(variance),
                    "kind": "shortage" if variance < 0 else "overage",
                },
                f"cash_variance:{shift.id}",
            )
        z = z_report(totals, expected=expected, counted=counted)
        fiscal: dict[str, Any] = {"status": "pending"}
        if self._fiscal is not None:
            offline = ctx.received_at - ctx.created_at > OFFLINE_AFTER
            ref = await self._fiscal.record(
                s,
                kind="z_report",
                doc_id=shift.id,
                cash_register_id=shift.cash_register_id,
                shift_id=shift.id,
                receipt_seq=None,
                payment_form=None,
                payload={
                    "shift_no": shift.shift_no,
                    "opened_at": ts(shift.opened_at),
                    "closed_at": ts(ctx.created_at),
                    "z_report": z,
                },
                fiscal_result=None,
                is_offline=offline,
                offline_since=ctx.created_at if offline else None,
                created_at=ctx.created_at,
            )
            fiscal = {"id": str(ref.id), "status": ref.status}
            service, tenant_id, receipt_id = self._fiscal, ctx.tenant_id, ref.id

            async def _enqueue() -> None:
                await service.enqueue(tenant_id, [receipt_id])

            result.after_commit.append(_enqueue)
        await record_audit(
            s,
            tenant_id=ctx.tenant_id,
            user_id=ctx.actor_user_id,
            action="shift_closed",
            entity="shifts",
            entity_id=shift.id,
            device_id=ctx.device_id,
            after={
                "expected_cash": m2(expected),
                "counted_cash": m2(counted),
                "variance": m2(variance),
                "variance_note": note,
                "counted_card_total": m2(card_total),
                "counted_card_total_server": m2(totals.card_manual),
            },
        )
        result.server = {"id": str(shift.id), "shift_no": shift.shift_no, "z_report": z, "fiscal": fiscal}
        return result

    # --- REST reads -----------------------------------------------------------------------------------
    async def list_page(
        self,
        actor: Principal,
        scope: BranchScope,
        cash_register_id: UUID | None,
        status: str | None,
        cursor: str | None,
        limit: int,
    ) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            rows = await self._repo.list_shifts(
                s,
                ShiftFilter(
                    scope_branches(scope), cash_register_id, status, decode_cursor(cursor), limit + 1
                ),
            )
        more = len(rows) > limit
        rows = rows[:limit]
        return {
            "items": [
                {
                    "id": str(r.id),
                    "shift_no": r.shift_no,
                    "cash_register_id": str(r.cash_register_id),
                    "branch_id": str(r.branch_id),
                    "status": r.status,
                    "opening_cash": m2(r.opening_cash),
                    "opened_at": ts(r.opened_at),
                    "closed_at": ts(r.closed_at),
                }
                for r in rows
            ],
            "next_cursor": encode_cursor(rows[-1].opened_at, rows[-1].id) if more and rows else None,
        }

    async def get(self, actor: Principal, scope: BranchScope, shift_id: UUID) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            row = await self._load(s, scope, shift_id)
            totals = await self._repo.shift_totals(s, row.id)
            body = shift_json(row)
            if row.status == "open":
                expected = expected_cash(row.opening_cash, totals.cash_moves_total)
                body["running_totals"] = running_totals(totals, expected=expected)
                body["z_report"] = None
            else:
                body["running_totals"] = None
                body["z_report"] = self._z(row, totals)
                body["fiscal"] = await self._fiscal_json(s, row.id)
        return body

    async def z_report(self, actor: Principal, scope: BranchScope, shift_id: UUID) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            row = await self._load(s, scope, shift_id)
            if row.status != "closed":
                raise AppError(
                    ErrorCode.DOC_INVALID_STATE,
                    params={"expected_status": "closed", "actual_status": row.status},
                )
            totals = await self._repo.shift_totals(s, row.id)
            body = {"shift_id": str(row.id), "shift_no": row.shift_no, **self._z(row, totals)}
            body["fiscal"] = await self._fiscal_json(s, row.id)
        return body

    async def cash_history(
        self, actor: Principal, scope: BranchScope, register_id: UUID, date_from: Any, date_to: Any
    ) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            register = await self._repo.get_register(s, register_id)
            if register is None:
                raise AppError(ErrorCode.NOT_FOUND, params={"resource": "cash_register"})
            check_branch(scope, register.branch_id, "cash_register")
            start = None if date_from is None else day_start(date_from)
            end = None if date_to is None else day_end(date_to)
            items = []
            for row in await self._repo.shifts_between(s, register_id, start, end):
                totals = await self._repo.shift_totals(s, row.id)
                expected = row.expected_cash
                if expected is None:
                    expected = expected_cash(row.opening_cash, totals.cash_moves_total)
                items.append(
                    {
                        "shift_id": str(row.id),
                        "shift_no": row.shift_no,
                        "status": row.status,
                        "opened_at": ts(row.opened_at),
                        "closed_at": ts(row.closed_at),
                        "opening_cash": m2(row.opening_cash),
                        "cash_sales": m2(totals.totals_by_method.get("cash", Decimal("0"))),
                        "cash_in": m2(totals.cash_in),
                        "cash_out": m2(totals.cash_out),
                        "expected_cash": m2(expected),
                        "counted_cash": m2(row.counted_cash),
                        "variance": m2(row.variance),
                        "variance_note": row.variance_note,
                        "counted_card_total": m2(row.counted_card_total),
                    }
                )
        return {"items": items}

    # --- helpers --------------------------------------------------------------------------------------
    async def _load(self, s: AsyncSession, scope: BranchScope, shift_id: UUID) -> ShiftRow:
        row = await self._repo.get_shift(s, shift_id)
        if row is None:
            raise AppError(ErrorCode.NOT_FOUND, params={"resource": "shift"})
        check_branch(scope, row.branch_id, "shift")
        return row

    @staticmethod
    def _z(row: ShiftRow, totals: Any) -> dict[str, Any]:
        expected = row.expected_cash if row.expected_cash is not None else Decimal("0.00")
        return z_report(totals, expected=expected, counted=row.counted_cash)

    async def _fiscal_json(self, s: AsyncSession, shift_id: UUID) -> dict[str, Any]:
        z = await self._repo.z_fiscal(s, shift_id)
        if z is None:
            return {"id": None, "status": "pending"}
        return {
            "id": str(z["id"]),
            "status": z["status"],
            "fiscal_sign": z["fiscal_sign"],
            "qr_url": z["qr_url"],
            "ofd_acked_at": ts(z["ofd_acked_at"]),
        }
