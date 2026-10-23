""":class:`CardPayments` implementation — card rules inside a document posting
(18 §4.1/§7.1, 16 §2.1, 21 §9.2).

Runs in the caller's session (the sync event or REST transaction). See ``application/contracts.py``.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.core.audit import record_audit
from app.core.error_codes import ErrorCode
from app.core.errors import AppError, ErrorDetail
from app.core.money import MoneyStr, money, money_str
from app.modules.access.application.approval_gate import ApprovalGate, ApprovalOutcome, ApprovalRefIn
from app.modules.integrations.card_terminal.application.contracts import (
    CardDocType,
    CardTxKind,
    ManualAuthorization,
    ManualPolicy,
    ManualReason,
    RecordedCardTx,
    SettlementInput,
    SettlementRecorded,
)
from app.modules.integrations.card_terminal.application.ports import CardRepository
from app.modules.integrations.card_terminal.application.schemas import parse_card_result
from app.modules.integrations.card_terminal.application.settlements import SettlementWriter
from app.modules.integrations.card_terminal.application.transactions import (
    APPROVE_PERMISSION,
    Attempt,
    TxWriter,
    invalid,
)

_POLICIES: frozenset[str] = frozenset({"allow", "manager_approval", "forbid"})
DEFAULT_POLICY = "manager_approval"  # 12 tenants.settings: key absent → manager_approval


class _SettlementItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    card_terminal_id: UUID
    batch_no: str | None = Field(default=None, max_length=32)
    business_date: str | None = None
    settled_at: datetime
    purchase_count: int = Field(ge=0)
    purchase_total: MoneyStr
    refund_count: int = Field(default=0, ge=0)
    refund_total: MoneyStr = "0.00"
    status: str | None = None
    terminal_response: dict[str, Any] = Field(default_factory=dict)
    shift_id: UUID | None = None


class CardPaymentsService:
    def __init__(self, repo: CardRepository, gate: ApprovalGate, settlements: SettlementWriter) -> None:
        self._repo = repo
        self._gate = gate
        self._writer = TxWriter(repo)
        self._settlements = settlements

    async def manual_policy(self, s: Any, *, cash_register_id: UUID) -> ManualPolicy:
        if await self._repo.active_terminal_count(s, cash_register_id) == 0:
            return "standalone"
        value = await self._repo.manual_fallback_setting(s)
        return value if value in _POLICIES else DEFAULT_POLICY  # type: ignore[return-value]

    async def authorize_manual(
        self,
        s: Any,
        *,
        tenant_id: UUID,
        branch_id: UUID,
        cash_register_id: UUID,
        manual_reason: ManualReason,
        amount: Decimal,
        approval: ApprovalRefIn | None,
        requested_by: UUID,
        doc_type: CardDocType,
        doc_id: UUID,
        client_event_id: UUID | None,
        device_id: UUID | None,
        offline: bool,
        line_id: UUID | None = None,
        approver_bound: Callable[[UUID], Awaitable[bool]] | None = None,
        session_user_id: UUID | None = None,
    ) -> ManualAuthorization:
        policy = await self.manual_policy(s, cash_register_id=cash_register_id)
        details: dict[str, Any] = {
            "manual_reason": manual_reason,
            "policy": policy,
            "amount": money_str(money(amount)),
        }
        reason_ok = (manual_reason == "standalone_terminal") == (policy == "standalone")
        if not reason_ok and not offline:
            raise invalid("manual_reason", "validation.card_manual_reason_mismatch")
        outcome: ApprovalOutcome | None = None
        violation = False
        linked: UUID | None = None
        resolved = (
            await self._manager_resolved(s, client_event_id) if manual_reason == "unknown_result" else []
        )
        needs_approval = policy != "standalone" and (
            manual_reason == "unknown_result" or policy == "manager_approval"
        )
        if policy == "forbid" and manual_reason != "unknown_result":
            if not offline:
                raise AppError(ErrorCode.CARD_MANUAL_NOT_ALLOWED, params={"policy": policy})
            violation = True
            details["violation"] = "card_manual_not_allowed"
        elif needs_approval and not (resolved and approval is not None):
            # unknown_result whose manager resolution already reached the server: the approval was checked
            # (and a remote request consumed) by POST /card-terminal-transactions — not re-consumed here
            try:
                outcome = await self._gate.require(
                    s, tenant_id=tenant_id, branch_id=branch_id, kind="card_manual_entry",
                    permission=APPROVE_PERMISSION, requested_by=requested_by, value=money(amount),
                    approval=approval, doc_type=doc_type, doc_id=doc_id, offline=offline, line_id=line_id,
                    approver_bound=approver_bound,
                    missing_code=ErrorCode.CARD_MANUAL_APPROVAL_REQUIRED.value,
                )  # fmt: skip
            except AppError as exc:
                if not offline:
                    raise
                violation = True
                details["violation"] = exc.code.value
            if outcome is not None and outcome.offline_limit_exceeded:
                violation = True
                details["violation"] = "approval_limit_exceeded_offline"
        for tx in resolved:
            if tx.doc_id is None:
                await self._repo.update_tx(s, tx.id, {"doc_type": doc_type, "doc_id": doc_id})
                linked = tx.id
            elif (tx.doc_type, tx.doc_id) == (doc_type, doc_id):
                linked = tx.id
        approver = None if approval is None else approval.approved_by
        await record_audit(
            s, tenant_id=tenant_id, user_id=requested_by, action="card.manual_entry", entity=doc_type,
            entity_id=doc_id, device_id=device_id,
            after={**details, "approved_by": None if approver is None else str(approver),
                   "approval_mode": None if approval is None else approval.mode, "offline": offline},
        )  # fmt: skip
        return ManualAuthorization(
            policy=policy,
            approval=outcome if outcome is not None and outcome.required else None,
            offline_violation=violation,
            details=details,
            linked_transaction_id=linked,
            approver_unverified=outcome is not None and outcome.approver_unverified,
            unverified_details=(
                {
                    **outcome.unverified_details,
                    "session_user_id": None if session_user_id is None else str(session_user_id),
                }
                if outcome is not None and outcome.approver_unverified
                else {}
            ),
        )

    async def _manager_resolved(self, s: Any, client_event_id: UUID | None) -> list[Any]:
        if client_event_id is None:
            return []
        return list(await self._repo.manager_resolved_by_event(s, client_event_id))

    async def link_result(
        self,
        s: Any,
        *,
        tenant_id: UUID,
        branch_id: UUID,
        cash_register_id: UUID,
        shift_id: UUID | None,
        card_result: Mapping[str, Any],
        expected_amount: Decimal,
        kind: CardTxKind,
        doc_type: CardDocType,
        doc_id: UUID,
        client_event_id: UUID | None,
        actor_user_id: UUID,
        device_id: UUID | None,
    ) -> RecordedCardTx:
        result = parse_card_result(card_result)
        if result.status != "approved" or result.resolved_by == "manager":
            raise invalid("card_result.status", "validation.card_result_required")
        if result.kind != kind:
            raise invalid("card_result.kind", "validation.card_kind_mismatch")
        terminal = await self._repo.terminal(s, result.card_terminal_id, lock=True)
        if terminal is None or terminal.branch_id != branch_id:
            raise invalid("card_result.card_terminal_id", "validation.card_terminal_not_found")
        attempt = Attempt(
            id=result.attempt_id, kind=kind, amount=money(expected_amount),
            original_id=result.original_attempt_id,
            cash_register_id=cash_register_id, shift_id=shift_id, device_id=device_id,
            client_event_id=client_event_id, requested_at=result.tx_at or datetime.now(UTC),
        )  # fmt: skip
        applied = await self._writer.apply(
            s, tenant_id=tenant_id, actor=actor_user_id, terminal=terminal, attempt=attempt, result=result,
            mode="event", doc=(doc_type, doc_id),
        )  # fmt: skip
        mismatch = dict(applied.mismatch) if applied.mismatch else None
        if money(result.amount) != money(expected_amount):
            amount_diff = {"reason": "amount", "card_result_amount": result.amount,
                           "payment_amount": money_str(money(expected_amount))}  # fmt: skip
            mismatch = amount_diff if mismatch is None else {**mismatch, "amount": amount_diff}
        tx = applied.tx
        if mismatch is not None:
            mismatch.setdefault("attempt_id", str(tx.id))
        # the payment row carries what the device reported (registers follow the event, 16 §2.1);
        # card_type is the server-derived value (terminal → BIN table → unknown)
        card_type = tx.card_type if tx.status in ("approved", "voided") and tx.card_type else result.card_type
        source = tx.card_type_source if card_type == tx.card_type else result.card_type_source
        if kind == "purchase" and card_type is None:
            card_type, source = "unknown", "bin_table"
        return RecordedCardTx(
            id=tx.id,
            card_terminal_id=tx.card_terminal_id,
            card_type=card_type if kind == "purchase" else result.card_type,
            card_type_source=source
            if kind == "purchase"
            else (result.card_type_source if result.card_type else None),
            card_mask=result.card_mask,
            rrn=result.rrn,
            approval_code=result.approval_code,
            card_scheme=result.card_scheme,
            tid=result.tid,
            mismatch=mismatch,
        )

    async def assert_shift_resolved(self, s: Any, *, shift_id: UUID) -> None:
        count = await self._repo.unresolved_in_shift(s, shift_id)
        if count:
            raise AppError(
                ErrorCode.CARD_OUTCOME_UNKNOWN, params={"shift_id": str(shift_id), "unresolved": count}
            )

    async def record_settlements(
        self,
        s: Any,
        *,
        tenant_id: UUID,
        branch_id: UUID,
        settlements: Sequence[SettlementInput],
        actor_user_id: UUID | None,
        device_id: UUID | None,
        client_event_id: UUID | None,
    ) -> list[SettlementRecorded]:
        return [
            await self._settlements.record(
                s,
                tenant_id=tenant_id,
                branch_id=branch_id,
                item=item,
                actor_user_id=actor_user_id,
                device_id=device_id,
                client_event_id=client_event_id if len(settlements) == 1 else None,
            )
            for item in settlements
        ]

    async def record_shift_settlements(
        self,
        s: Any,
        *,
        tenant_id: UUID,
        branch_id: UUID,
        shift_id: UUID,
        device_id: UUID | None,
        actor_user_id: UUID,
        client_event_id: UUID | None,
        items: Sequence[Mapping[str, Any]],
    ) -> list[SettlementRecorded]:
        parsed: list[SettlementInput] = []
        for index, raw in enumerate(items):
            try:
                item = _SettlementItem.model_validate(raw)
            except ValidationError as exc:
                raise AppError(
                    ErrorCode.VALIDATION_ERROR,
                    details=[
                        ErrorDetail(
                            field=".".join([f"card_settlements[{index}]", *(str(p) for p in e["loc"])]),
                            message_key="validation.card_settlement_invalid",
                        )
                        for e in exc.errors()
                    ],
                ) from None
            business = item.business_date
            parsed.append(
                SettlementInput(
                    id=item.id,
                    card_terminal_id=item.card_terminal_id,
                    shift_id=shift_id,
                    batch_no=item.batch_no,
                    business_date=datetime.fromisoformat(business).date()
                    if business
                    else item.settled_at.date(),
                    settled_at=item.settled_at,
                    purchase_count=item.purchase_count,
                    purchase_total=money(item.purchase_total),
                    refund_count=item.refund_count,
                    refund_total=money(item.refund_total),
                    failed=item.status == "failed",
                    terminal_response=item.terminal_response,
                )
            )
        return await self.record_settlements(
            s, tenant_id=tenant_id, branch_id=branch_id, settlements=parsed, actor_user_id=actor_user_id,
            device_id=device_id, client_event_id=client_event_id,
        )  # fmt: skip
