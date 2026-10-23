"""``sale.draft_voided`` (18 §5) and ``receipt.reprinted`` (18 §6) — audit-only POS events (15 §6.1).

Neither touches a register or creates a fiscal receipt. ``sale.draft_voided`` → ``audit_log``
``action='sale.draft_voided'``, ``entity='sales'``, ``entity_id`` NULL (the draft never became a sale),
``after = {draft_ref, voided_lines, whole_receipt, reason, shift_id, cash_register_id, client_event_id}``
(``shift_id`` — the register's open shift, used by the Z-report ``voided_count``). ``receipt.reprinted``
→ one audit row per event (``entity='fiscal_receipts'``), unlimited copies, answer ``copy_label="NUSXA"``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit
from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from app.modules.sales.application.payloads import DraftVoidedPayload, ReceiptReprintedPayload, parse
from app.modules.sales.application.ports import SalesRepository
from app.modules.sync.application.handlers import EventContext, HandlerResult

COPY_LABEL = "NUSXA"


class DraftVoidedHandler:
    def __init__(self, repo: SalesRepository) -> None:
        self._repo = repo

    async def __call__(self, s: AsyncSession, ctx: EventContext, payload: Mapping[str, Any]) -> HandlerResult:
        p = parse(DraftVoidedPayload, payload)
        shift_id: UUID | None = None
        if ctx.cash_register_id is not None:
            shift_id = await self._repo.open_shift_of(s, ctx.cash_register_id)
        await record_audit(
            s, tenant_id=ctx.tenant_id, user_id=ctx.actor_user_id, action="sale.draft_voided", entity="sales",
            device_id=ctx.device_id,
            after={
                "draft_ref": p.draft_ref, "voided_lines": p.voided_lines,
                "whole_receipt": p.voided_lines is None,
                "reason": p.reason, "shift_id": str(shift_id) if shift_id else None,
                "cash_register_id": str(ctx.cash_register_id) if ctx.cash_register_id else None,
                "client_event_id": str(ctx.client_event_id), "created_at": ctx.created_at.isoformat(),
            },
        )  # fmt: skip
        return HandlerResult(server={"status": "accepted"})


class ReceiptReprintedHandler:
    def __init__(self, repo: SalesRepository) -> None:
        self._repo = repo

    async def __call__(self, s: AsyncSession, ctx: EventContext, payload: Mapping[str, Any]) -> HandlerResult:
        p = parse(ReceiptReprintedPayload, payload)
        found = await self._repo.fiscal_receipt_ref(s, p.fiscal_receipt_id)
        if found is None:
            raise AppError(
                ErrorCode.DEPENDENCY_NOT_SYNCED,
                params={"entity": "fiscal_receipts", "id": str(p.fiscal_receipt_id)},
            )
        sale_id, kind = found
        await record_audit(
            s, tenant_id=ctx.tenant_id, user_id=ctx.actor_user_id, action="receipt.reprinted",
            entity="fiscal_receipts", entity_id=p.fiscal_receipt_id, device_id=ctx.device_id,
            after={
                "kind": kind, "sale_id": str(p.sale_id or sale_id) if (p.sale_id or sale_id) else None,
                "reason": p.reason, "client_event_id": str(ctx.client_event_id), "copy_label": COPY_LABEL,
            },
        )  # fmt: skip
        return HandlerResult(server={"status": "accepted", "copy_label": COPY_LABEL})
