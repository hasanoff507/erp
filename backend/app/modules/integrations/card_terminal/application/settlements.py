"""Terminal settlement («сверка итогов») — ``card_terminal_settlements`` (18 §16a.6, QT-M16-08; qaror #71).

``expected_count``/``expected_total`` come from the terminal's approved purchases/refunds that are not yet in
a batch (Σ purchase − Σ refund); those rows get the new ``settlement_id``. ``status``: ``failed`` when the
terminal could not settle, otherwise ``matched`` / ``mismatch`` (``variance`` is a generated column).
``mismatch`` → audit ``card.settlement.mismatch`` + M18 event for the Owner. Idempotent by ``id``.
No posting (13 §2.18a matches the bank statement later).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.audit import record_audit
from app.core.auth.principal import Principal
from app.core.db.session import tenant_transaction
from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from app.core.idempotency import stage_response
from app.core.money import money_str
from app.core.permissions import BranchScope
from app.modules.integrations.card_terminal.application.contracts import SettlementInput, SettlementRecorded
from app.modules.integrations.card_terminal.application.ports import CardRepository, SettlementRow
from app.modules.integrations.card_terminal.application.transactions import invalid
from app.modules.integrations.card_terminal.domain.model import settlement_status
from app.modules.notifications.application.outbox import EventRecorder
from app.modules.notifications.domain.events import EVENT_KINDS

ENTITY = "card_terminal_settlements"
NOTIFY_KIND = "card_settlement_mismatch"  # M18 event kind (20 #69) — recorded once the catalog has it


def settlement_json(row: SettlementRow) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "card_terminal_id": str(row.card_terminal_id),
        "status": row.status,
        "net_total": money_str(row.net_total),
        "expected_total": money_str(row.expected_total),
        "variance": money_str(row.variance),
    }


def _recorded(row: SettlementRow) -> SettlementRecorded:
    return SettlementRecorded(
        row.id, row.card_terminal_id, row.status, row.net_total, row.expected_total, row.variance
    )


class SettlementWriter:
    def __init__(self, repo: CardRepository, events: EventRecorder) -> None:
        self._repo = repo
        self._events = events

    async def record(
        self,
        s: AsyncSession,
        *,
        tenant_id: UUID,
        branch_id: UUID | None,
        item: SettlementInput,
        actor_user_id: UUID | None,
        device_id: UUID | None,
        client_event_id: UUID | None,
        ip: str | None = None,
    ) -> SettlementRecorded:
        existing = await self._repo.settlement(s, item.id)
        if existing is not None:
            return _recorded(existing)
        terminal = await self._repo.terminal(s, item.card_terminal_id, lock=True)
        if terminal is None or (branch_id is not None and terminal.branch_id != branch_id):
            raise AppError(ErrorCode.NOT_FOUND, params={"resource": "card_terminal"})
        if item.shift_id is not None and not await self._repo.shift_exists(s, item.shift_id):
            raise AppError(ErrorCode.SHIFT_NOT_OPEN, params={"shift_id": str(item.shift_id)})
        count, purchases, refunds = await self._repo.unbatched_totals(s, terminal.id)
        expected = purchases - refunds
        status = settlement_status(item.purchase_total, item.refund_total, expected, failed=item.failed)
        try:
            row = await self._repo.insert_settlement(
                s,
                {
                    "id": item.id, "tenant_id": tenant_id, "branch_id": terminal.branch_id,
                    "card_terminal_id": terminal.id, "shift_id": item.shift_id, "batch_no": item.batch_no,
                    "business_date": item.business_date, "settled_at": item.settled_at,
                    "purchase_count": item.purchase_count, "purchase_total": item.purchase_total,
                    "refund_count": item.refund_count, "refund_total": item.refund_total,
                    "expected_count": count, "expected_total": expected, "status": status,
                    "terminal_response": dict(item.terminal_response), "client_event_id": client_event_id,
                    "device_id": device_id, "created_by": actor_user_id,
                },
            )  # fmt: skip
        except Exception as exc:  # uq_cts_batch: the same batch_no reported under another id
            if "uq_cts_batch" in str(exc):
                raise invalid("batch_no", "validation.card_settlement_batch_duplicate") from None
            raise
        if status != "failed":
            await self._repo.stamp_settlement(s, terminal.id, row.id)
        if status == "mismatch":
            after = settlement_json(row) | {"purchase_total": money_str(item.purchase_total),
                                            "refund_total": money_str(item.refund_total)}  # fmt: skip
            await record_audit(
                s, tenant_id=tenant_id, user_id=actor_user_id, action="card.settlement.mismatch",
                entity=ENTITY,
                entity_id=row.id, after=after, ip=ip, device_id=device_id,
            )  # fmt: skip
            if NOTIFY_KIND in EVENT_KINDS:
                await self._events.record_event(
                    s, tenant_id, NOTIFY_KIND,
                    {"card_terminal_id": str(terminal.id), "terminal_name": terminal.name, **after},
                    f"card_settlement_mismatch:{row.id}",
                )  # fmt: skip
        return _recorded(row)


class SettlementService:
    """``POST /card-terminal-settlements`` (``shift.close``; ``id`` given by the device)."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        repo: CardRepository,
        writer: SettlementWriter,
    ) -> None:
        self._sf = session_factory
        self._repo = repo
        self._writer = writer

    async def record(
        self, actor: Principal, scope: BranchScope, item: SettlementInput, ip: str | None
    ) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            terminal = await self._repo.terminal(s, item.card_terminal_id)
            if terminal is None or (scope.allowed and terminal.branch_id not in scope.allowed):
                raise AppError(ErrorCode.NOT_FOUND, params={"resource": "card_terminal"})
            rec = await self._writer.record(
                s, tenant_id=actor.tenant_id, branch_id=None, item=item, actor_user_id=actor.user_id,
                device_id=actor.device_id, client_event_id=None, ip=ip,
            )  # fmt: skip
            body = {
                "id": str(rec.id), "card_terminal_id": str(rec.card_terminal_id), "status": rec.status,
                "net_total": money_str(rec.net_total), "expected_total": money_str(rec.expected_total),
                "variance": money_str(rec.variance),
            }  # fmt: skip
            stage_response(body, 201)
        return body
