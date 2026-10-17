"""``card_terminal_transactions`` writer (18 §16a.3/§16a.4, 16 §2.1, 21 §9.4; qaror #71).

One core — :meth:`TxWriter.apply` — serves both entry points:

* ``POST /card-terminal-transactions`` (online POS): upsert by ``id = attempt_id`` (a replay with the same
  content is a no-op); ``status`` only moves forward; a final state that differs from the stored one →
  ``409 CARD_TRANSACTION_MISMATCH`` + ``sync_exceptions(kind='card_result_mismatch')`` (written in its own
  transaction, the request's own transaction rolls back). A new ``purchase`` on a terminal with an
  unresolved ``unknown`` → ``CARD_OUTCOME_UNKNOWN``; a second ``pending`` → ``CARD_TERMINAL_BUSY``.
  ``resolved_by='manager'`` — the manager closes an ``unknown`` attempt by looking at the terminal slip
  (``card_manual_approval``, ``card.manual_entry.approve``); nothing about the card is written.
* document events (``sale.created`` / ``return.created`` through :class:`CardPaymentsService`): the same
  upsert, but a difference never rejects the document — it is reported as ``mismatch``.

Audit (15 §6.1): ``card.purchase.approved|declined|unknown``, ``card.refund``, ``card.void.auto``,
``card.void.failed``, ``card.outcome.resolved_manual`` — ``after`` holds mask/RRN/approval code/scheme/amount
only (never a PAN).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.audit import record_audit
from app.core.auth.principal import Principal
from app.core.db.base import uuid7
from app.core.db.session import tenant_transaction
from app.core.error_codes import ErrorCode
from app.core.errors import AppError, ErrorDetail
from app.core.idempotency import stage_response
from app.core.money import money, money_str
from app.core.permissions import BranchScope
from app.modules.access.application.approval_gate import ApprovalGate, ApprovalRefIn
from app.modules.integrations.card_terminal.application.ports import CardRepository, TerminalRow, TxRow
from app.modules.integrations.card_terminal.application.schemas import CardResultIn
from app.modules.integrations.card_terminal.domain.model import FINAL, can_transition

ENTITY = "card_terminal_transactions"
APPROVE_PERMISSION = "card.manual_entry.approve"
KIND_PERMISSIONS: Mapping[str, tuple[str, ...]] = {
    "purchase": ("sales.create", "debts.payment.accept"),
    "refund": ("returns.create",),
    "void": ("sales.void", "returns.create"),
}
READ_PERMISSIONS: tuple[str, ...] = ("sales.create", "returns.create", "debts.payment.accept")
Mode = Literal["rest", "event"]


def invalid(field_name: str, key: str) -> AppError:
    return AppError(ErrorCode.VALIDATION_ERROR, details=[ErrorDetail(field=field_name, message_key=key)])


def iso(value: datetime | None) -> str | None:
    return None if value is None else value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def tx_json(tx: TxRow) -> dict[str, Any]:
    """18 §16a.3 response; with ``resolved_by='manager'`` the card details are null by construction."""
    return {
        "id": str(tx.id),
        "card_terminal_id": str(tx.card_terminal_id),
        "status": tx.status,
        "kind": tx.kind,
        "amount": money_str(tx.amount),
        "approved_amount": None if tx.approved_amount is None else money_str(tx.approved_amount),
        "approval_code": tx.approval_code,
        "rrn": tx.rrn,
        "card_mask": tx.card_mask,
        "card_scheme": tx.card_scheme,
        "card_type": tx.card_type,
        "card_type_source": tx.card_type_source,
        "tid": tx.tid,
        "decline_code": tx.decline_code,
        "decline_message": tx.decline_message,
        "doc_type": tx.doc_type,
        "doc_id": None if tx.doc_id is None else str(tx.doc_id),
        "resolved_by": tx.resolved_by,
        "updated_at": iso(tx.updated_at),
    }


class MismatchError(Exception):
    """Internal signal: the REST request differs from the stored row (409 after the rollback)."""

    def __init__(
        self, tx_id: UUID, details: Mapping[str, Any], device_id: UUID | None, client_event_id: UUID | None
    ) -> None:
        super().__init__(str(tx_id))
        self.tx_id = tx_id
        self.details = details
        self.device_id = device_id
        self.client_event_id = client_event_id


@dataclass(slots=True)
class Applied:
    tx: TxRow
    created: bool
    mismatch: dict[str, Any] | None = None
    audit: list[tuple[str, dict[str, Any]]] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class Attempt:
    """What the caller knows about the attempt besides the terminal result."""

    id: UUID
    kind: str
    amount: Decimal  # requested amount
    original_id: UUID | None
    cash_register_id: UUID | None
    shift_id: UUID | None
    device_id: UUID | None
    client_event_id: UUID | None
    requested_at: datetime


def _audit_after(tx_amount: Decimal, result: CardResultIn | None, status: str) -> dict[str, Any]:
    after: dict[str, Any] = {"status": status, "amount": money_str(tx_amount)}
    if result is not None:
        after.update(
            {
                "card_mask": result.card_mask, "rrn": result.rrn, "approval_code": result.approval_code,
                "card_scheme": result.card_scheme, "decline_code": result.decline_code,
                "resolved_by": result.resolved_by,
            }
        )  # fmt: skip
    return after


def _audit_action(kind: str, status: str, doc_type: str | None) -> str | None:
    if kind == "purchase":
        return {"approved": "card.purchase.approved", "declined": "card.purchase.declined",
                "unknown": "card.purchase.unknown"}.get(status)  # fmt: skip
    if kind == "refund":
        return "card.refund" if status == "approved" else None
    if status == "approved":  # void
        return "card.refund" if doc_type == "returns" else "card.void.auto"
    if status == "declined":
        return "card.void.failed"
    return None


class TxWriter:
    """Shared upsert used by the REST service and :class:`CardPaymentsService`."""

    def __init__(self, repo: CardRepository) -> None:
        self._repo = repo

    async def apply(
        self,
        s: AsyncSession,
        *,
        tenant_id: UUID,
        actor: UUID,
        terminal: TerminalRow,
        attempt: Attempt,
        result: CardResultIn | None,
        mode: Mode,
        doc: tuple[str, UUID] | None = None,
    ) -> Applied:
        target = result.status if result is not None else "pending"
        existing = await self._repo.tx(s, attempt.id, lock=True)
        if existing is None:
            applied = await self._insert(s, tenant_id, actor, terminal, attempt, result, target, mode, doc)
        else:
            applied = await self._update(s, existing, terminal, attempt, result, target, doc)
        if doc is not None:
            await self._link(s, applied, doc, attempt.client_event_id)
        await self._after_void(s, applied, result)
        for action, after in applied.audit:
            await record_audit(
                s, tenant_id=tenant_id, user_id=actor, action=action, entity=ENTITY, entity_id=applied.tx.id,
                after=after, device_id=attempt.device_id,
            )  # fmt: skip
        return applied

    def _result_values(self, result: CardResultIn, target: str) -> dict[str, Any]:
        card_type, source = result.card_type, result.card_type_source
        if target in ("approved", "voided") and result.kind == "purchase" and result.resolved_by != "manager":
            if card_type is None:  # the device had no BIN rule / no BIN: 21 §9.4 fallback
                card_type, source = "unknown", "bin_table"
            elif source is None:
                source = "terminal"
        response = result.model_dump(mode="json", exclude={"slip_text"})
        return {
            "status": target,
            "approved_amount": money(result.amount) if target in ("approved", "voided") else None,
            "approval_code": result.approval_code, "rrn": result.rrn, "stan": result.stan,
            "card_mask": result.card_mask, "card_scheme": result.card_scheme, "card_type": card_type,
            "card_type_source": source, "entry_mode": result.entry_mode, "tid": result.tid, "mid": result.mid,
            "acquirer": result.acquirer,
            "decline_code": result.decline_code if target == "declined" else None,
            "decline_message": result.decline_message if target == "declined" else None,
            "resolved_by": result.resolved_by if target != "unknown" else None,
            "terminal_response": response, "slip_text": result.slip_text, "tx_at": result.tx_at,
            "resolved_at": datetime.now(UTC) if target in FINAL else None,
        }  # fmt: skip

    async def _insert(
        self,
        s: AsyncSession,
        tenant_id: UUID,
        actor: UUID,
        terminal: TerminalRow,
        attempt: Attempt,
        result: CardResultIn | None,
        target: str,
        mode: Mode,
        doc: tuple[str, UUID] | None,
    ) -> Applied:
        if mode == "rest" and attempt.kind == "purchase":
            others = await self._repo.unresolved_on_terminal(s, terminal.id, attempt.id)
            if "unknown" in others:
                raise AppError(ErrorCode.CARD_OUTCOME_UNKNOWN, params={"card_terminal_id": str(terminal.id)})
            if "pending" in others and target == "pending":
                raise AppError(ErrorCode.CARD_TERMINAL_BUSY, params={"card_terminal_id": str(terminal.id)})
        if attempt.original_id is not None and await self._repo.tx(s, attempt.original_id) is None:
            if mode == "rest":
                raise AppError(ErrorCode.NOT_FOUND, params={"resource": "card_terminal_transaction"})
            raise invalid("card_result.original_attempt_id", "validation.card_original_not_found")
        values: dict[str, Any] = {
            "id": attempt.id, "tenant_id": tenant_id, "branch_id": terminal.branch_id,
            "card_terminal_id": terminal.id, "cash_register_id": attempt.cash_register_id,
            "shift_id": attempt.shift_id, "device_id": attempt.device_id, "kind": attempt.kind,
            "original_transaction_id": attempt.original_id, "amount": money(attempt.amount),
            "client_event_id": attempt.client_event_id, "requested_at": attempt.requested_at,
            "created_by": actor, "status": target,
        }  # fmt: skip
        mismatch: dict[str, Any] | None = None
        if result is not None:
            values.update(self._result_values(result, target))
            if target in ("approved", "voided") and attempt.kind == "purchase" and result.tid and result.rrn:
                taken = await self._repo.rrn_taken(s, result.tid, result.rrn, attempt.id)
                if taken is not None:
                    mismatch = {"reason": "duplicate_rrn", "existing_id": str(taken), "tid": result.tid,
                                "rrn": result.rrn}  # fmt: skip
                    if mode == "rest":
                        raise MismatchError(attempt.id, mismatch, attempt.device_id, attempt.client_event_id)
                    values["tid"] = None  # kept in terminal_response; uq_ctt_purchase_rrn stays intact
        await self._repo.insert_tx(s, values)
        tx = await self._repo.tx(s, attempt.id)
        assert tx is not None
        applied = Applied(tx, created=True, mismatch=mismatch)
        action = _audit_action(attempt.kind, target, None if doc is None else doc[0])
        if action is not None and result is not None and result.resolved_by != "manager":
            applied.audit.append((action, _audit_after(tx.amount, result, target)))
        return applied

    async def _update(
        self,
        s: AsyncSession,
        existing: TxRow,
        terminal: TerminalRow,
        attempt: Attempt,
        result: CardResultIn | None,
        target: str,
        doc: tuple[str, UUID] | None,
    ) -> Applied:
        if (
            existing.card_terminal_id != terminal.id
            or existing.kind != attempt.kind
            or (existing.original_transaction_id or attempt.original_id)
            != (attempt.original_id or existing.original_transaction_id)
        ):
            return Applied(existing, created=False, mismatch={
                "reason": "attempt_conflict", "server": {"card_terminal_id": str(existing.card_terminal_id),
                                                          "kind": existing.kind},
                "device": {"card_terminal_id": str(terminal.id), "kind": attempt.kind}})  # fmt: skip
        if result is None:  # a repeated "pending" announcement
            if existing.status == "pending":
                return Applied(existing, created=False)
            return Applied(existing, created=False, mismatch={"reason": "state_conflict",
                                                              "server_status": existing.status,
                                                              "device_status": "pending"})  # fmt: skip
        if existing.status == target:
            differs = self._differs(existing, result) if target in FINAL else None
            return Applied(existing, created=False, mismatch=differs)
        if not can_transition(existing.status, target):
            return Applied(existing, created=False, mismatch={
                "reason": "state_conflict", "server_status": existing.status,
                "device_status": target})  # fmt: skip
        values = self._result_values(result, target)
        if existing.cash_register_id is None and attempt.cash_register_id is not None:
            values["cash_register_id"] = attempt.cash_register_id
        if existing.shift_id is None and attempt.shift_id is not None:
            values["shift_id"] = attempt.shift_id
        if existing.client_event_id is None and attempt.client_event_id is not None:
            values["client_event_id"] = attempt.client_event_id
        mismatch: dict[str, Any] | None = None
        if target == "approved" and existing.kind == "purchase" and result.tid and result.rrn:
            taken = await self._repo.rrn_taken(s, result.tid, result.rrn, existing.id)
            if taken is not None:
                mismatch = {"reason": "duplicate_rrn", "existing_id": str(taken), "tid": result.tid,
                            "rrn": result.rrn}  # fmt: skip
                values["tid"] = None
        await self._repo.update_tx(s, existing.id, values)
        tx = await self._repo.tx(s, existing.id)
        assert tx is not None
        applied = Applied(tx, created=False, mismatch=mismatch)
        action = _audit_action(existing.kind, target, existing.doc_type or (None if doc is None else doc[0]))
        if action is not None and result.resolved_by != "manager":
            applied.audit.append((action, _audit_after(tx.amount, result, target)))
        return applied

    @staticmethod
    def _differs(existing: TxRow, result: CardResultIn) -> dict[str, Any] | None:
        if result.resolved_by == "manager" or existing.resolved_by == "manager":
            same = existing.resolved_by == result.resolved_by
            return None if same else {"reason": "result_differs", "field": "resolved_by"}
        pairs = {
            "rrn": (existing.rrn, result.rrn),
            "approval_code": (existing.approval_code, result.approval_code),
            "card_mask": (existing.card_mask, result.card_mask),
        }
        if existing.status in ("approved", "voided") and existing.approved_amount is not None:
            pairs["amount"] = (money_str(existing.approved_amount), money_str(money(result.amount)))
        diff = {k: {"server": a, "device": b} for k, (a, b) in pairs.items() if a != b and b is not None}
        return {"reason": "result_differs", "fields": diff} if diff else None

    async def _link(
        self, s: AsyncSession, applied: Applied, doc: tuple[str, UUID], client_event_id: UUID | None
    ) -> None:
        """Link the attempt to its document (event mode only — REST never passes ``doc``).

        Already linked to ANOTHER document (device bug, re-created document): the event is still accepted
        (16 §2.1, 18 §4.1). The original link stays; this document gets a duplicate row (new id, ``tid``
        NULL so ``uq_ctt_purchase_rrn`` holds, ``terminal_response.duplicate_of`` = the attempt, excluded
        from settlement totals) so its payment row can reference a transaction of its own
        (``uq_sale_payments_card_tx``), and the caller records ``card_result_mismatch``."""
        tx = applied.tx
        if tx.doc_id is not None and (tx.doc_type, tx.doc_id) != doc:
            duplicate = uuid7()
            await self._repo.clone_tx(s, tx.id, duplicate, doc=doc, client_event_id=client_event_id)
            cloned = await self._repo.tx(s, duplicate)
            assert cloned is not None
            reason = {
                "reason": "linked_to_other_document", "attempt_id": str(tx.id),
                "existing_doc_type": tx.doc_type, "existing_doc_id": str(tx.doc_id),
                "duplicate_id": str(duplicate),
            }  # fmt: skip
            applied.mismatch = reason if applied.mismatch is None else {**applied.mismatch, **reason}
            applied.tx = cloned
            return
        if tx.doc_id is None:
            await self._repo.update_tx(s, tx.id, {"doc_type": doc[0], "doc_id": doc[1]})
            refreshed = await self._repo.tx(s, tx.id)
            assert refreshed is not None
            applied.tx = refreshed

    async def _after_void(self, s: AsyncSession, applied: Applied, result: CardResultIn | None) -> None:
        """An approved ``void`` marks its original purchase ``voided`` (18 §16a.3)."""
        tx = applied.tx
        if tx.kind != "void" or tx.status != "approved" or tx.original_transaction_id is None:
            return
        original = await self._repo.tx(s, tx.original_transaction_id, lock=True)
        if original is not None and original.kind == "purchase" and original.status == "approved":
            await self._repo.update_tx(s, original.id, {"status": "voided"})


@dataclass(frozen=True, slots=True)
class RecordInput:
    """``POST /card-terminal-transactions`` body (18 §16a.3)."""

    id: UUID
    card_terminal_id: UUID
    cash_register_id: UUID | None
    shift_id: UUID | None
    kind: str
    original_transaction_id: UUID | None
    amount: Decimal
    client_event_id: UUID | None
    requested_at: datetime
    status: str | None
    result: CardResultIn | None
    card_manual_approval: ApprovalRefIn | None


class CardTransactionService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        repo: CardRepository,
        gate: ApprovalGate,
    ) -> None:
        self._sf = session_factory
        self._repo = repo
        self._gate = gate
        self._writer = TxWriter(repo)

    async def get(self, actor: Principal, scope: BranchScope, tx_id: UUID) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            tx = await self._repo.tx(s, tx_id)
            if tx is None or (scope.allowed and tx.branch_id not in scope.allowed):
                raise AppError(ErrorCode.NOT_FOUND, params={"resource": "card_terminal_transaction"})
        return tx_json(tx)

    async def record(
        self,
        actor: Principal,
        scope: BranchScope,
        data: RecordInput,
        *,
        may_approve: bool,
        ip: str | None,
    ) -> tuple[dict[str, Any], int]:
        _check_input(data)
        try:
            async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
                terminal = await self._terminal(s, scope, data)
                attempt = Attempt(
                    id=data.id, kind=data.kind, amount=data.amount, original_id=data.original_transaction_id,
                    cash_register_id=data.cash_register_id, shift_id=data.shift_id, device_id=actor.device_id,
                    client_event_id=data.client_event_id, requested_at=data.requested_at,
                )  # fmt: skip
                if data.result is not None and data.result.resolved_by == "manager":
                    applied = await self._manager(
                        s, actor, terminal, attempt, data, may_approve=may_approve, ip=ip
                    )
                else:
                    if data.result is None and terminal.adapter == "cloud":
                        # CloudTerminalAdapter needs a vendor cloud API (21 §9.4) — none is wired yet
                        raise AppError(ErrorCode.CARD_TERMINAL_UNREACHABLE, params={"adapter": "cloud"})
                    applied = await self._writer.apply(
                        s, tenant_id=actor.tenant_id, actor=actor.user_id, terminal=terminal, attempt=attempt,
                        result=data.result, mode="rest",
                    )  # fmt: skip
                if applied.mismatch is not None:
                    raise MismatchError(data.id, applied.mismatch, actor.device_id, data.client_event_id)
                status = 201 if applied.created else 200
                body = tx_json(applied.tx)
                stage_response(body, status)
        except MismatchError as exc:
            await self._report_mismatch(actor, exc)
            raise AppError(
                ErrorCode.CARD_TRANSACTION_MISMATCH, params={"attempt_id": str(exc.tx_id)}, details=[]
            ) from None
        return body, status

    async def _terminal(self, s: AsyncSession, scope: BranchScope, data: RecordInput) -> TerminalRow:
        terminal = await self._repo.terminal(s, data.card_terminal_id, lock=True)
        if terminal is None or (scope.allowed and terminal.branch_id not in scope.allowed):
            raise AppError(ErrorCode.NOT_FOUND, params={"resource": "card_terminal"})
        if scope.current is not None and terminal.branch_id != scope.current:
            raise invalid("card_terminal_id", "validation.card_terminal_not_in_branch")
        if data.cash_register_id is not None and terminal.cash_register_id not in (
            None,
            data.cash_register_id,
        ):
            raise invalid("card_terminal_id", "validation.card_terminal_other_register")
        is_new = await self._repo.tx(s, data.id) is None
        if is_new and terminal.status != "active" and data.kind == "purchase" and data.result is None:
            raise invalid("card_terminal_id", "validation.card_terminal_inactive")
        return terminal

    async def _manager(
        self,
        s: AsyncSession,
        actor: Principal,
        terminal: TerminalRow,
        attempt: Attempt,
        data: RecordInput,
        *,
        may_approve: bool,
        ip: str | None,
    ) -> Applied:
        """18 §16a.4 step 3: the manager confirms "passed / not passed" from the terminal slip."""
        result = data.result
        assert result is not None
        approval = data.card_manual_approval
        if approval is None and not may_approve:
            raise AppError(ErrorCode.PERMISSION_DENIED, params={"permission": APPROVE_PERMISSION})
        existing = await self._repo.tx(s, data.id, lock=True)
        if existing is not None and existing.status not in ("pending", "unknown"):
            if existing.status == result.status and existing.resolved_by == "manager":
                return Applied(existing, created=False)  # replay
            return Applied(existing, created=False, mismatch={
                "reason": "state_conflict", "server_status": existing.status,
                "device_status": result.status})  # fmt: skip
        doc = await self._repo.doc_by_client_event(s, data.client_event_id) if data.client_event_id else None
        resolver = actor.user_id
        if doc is None:  # the document (if any) has not consumed the approval yet
            try:
                await self._gate.require(
                    s, tenant_id=actor.tenant_id, branch_id=terminal.branch_id, kind="card_manual_entry",
                    permission=APPROVE_PERMISSION, requested_by=actor.user_id, value=money(data.amount),
                    approval=approval, doc_type=ENTITY, doc_id=data.id, offline=False,
                )  # fmt: skip
            except AppError as exc:
                if approval is None:
                    raise AppError(
                        ErrorCode.PERMISSION_DENIED, params={"permission": APPROVE_PERMISSION}
                    ) from exc
                raise
        if approval is not None:
            if approval.mode == "local_pin" and approval.approved_by is not None:
                resolver = approval.approved_by
            elif approval.approval_request_id is not None:
                resolver = (
                    await self._repo.approval_request_resolver(s, approval.approval_request_id) or resolver
                )
        approved = result.status == "approved"
        now = datetime.now(UTC)
        values: dict[str, Any] = {
            "status": result.status, "resolved_by": "manager", "resolved_by_user_id": resolver,
            "resolved_at": now,
            "approved_amount": money(data.amount) if approved else None,
            "decline_code": None if approved else "not_found",
            "decline_message": None if approved else result.decline_message,
            "terminal_response": {"resolved_by": "manager", "status": result.status},
        }  # fmt: skip
        if doc is not None:
            values.update({"doc_type": doc[0], "doc_id": doc[1]})
        if existing is None:
            values.update({
                "id": data.id, "tenant_id": actor.tenant_id, "branch_id": terminal.branch_id,
                "card_terminal_id": terminal.id, "cash_register_id": data.cash_register_id,
                "shift_id": data.shift_id, "device_id": actor.device_id, "kind": data.kind,
                "original_transaction_id": data.original_transaction_id, "amount": money(data.amount),
                "client_event_id": data.client_event_id, "requested_at": data.requested_at,
                "created_by": actor.user_id,
            })  # fmt: skip
            await self._repo.insert_tx(s, values)
        else:
            if existing.client_event_id is None and data.client_event_id is not None:
                values["client_event_id"] = data.client_event_id
            await self._repo.update_tx(s, existing.id, values)
        tx = await self._repo.tx(s, data.id)
        assert tx is not None
        await record_audit(
            s, tenant_id=actor.tenant_id, user_id=actor.user_id, action="card.outcome.resolved_manual",
            entity=ENTITY, entity_id=tx.id, ip=ip, device_id=actor.device_id,
            before=None if existing is None else {"status": existing.status},
            after={"status": tx.status, "amount": money_str(tx.amount), "approved_by": str(resolver)},
        )  # fmt: skip
        return Applied(tx, created=existing is None)

    async def _report_mismatch(self, actor: Principal, exc: MismatchError) -> None:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            await self._repo.insert_sync_exception(
                s, kind="card_result_mismatch", device_id=exc.device_id, client_event_id=exc.client_event_id,
                doc_type=ENTITY, doc_id=exc.tx_id, details=exc.details,
            )  # fmt: skip


def _check_input(data: RecordInput) -> None:
    if data.amount <= 0:
        raise invalid("amount", "validation.positive")
    if data.kind == "void" and data.original_transaction_id is None:
        raise invalid("original_transaction_id", "validation.required")
    if data.kind == "purchase" and data.original_transaction_id is not None:
        raise invalid("original_transaction_id", "validation.not_allowed")
    if data.result is None:
        if data.status != "pending":
            raise invalid("status", "validation.card_status_pending_required")
        if data.card_manual_approval is not None:
            raise invalid("card_manual_approval", "validation.not_allowed")
        return
    r = data.result
    if r.attempt_id != data.id:
        raise invalid("result.attempt_id", "validation.card_attempt_id_mismatch")
    if r.card_terminal_id != data.card_terminal_id:
        raise invalid("result.card_terminal_id", "validation.card_terminal_mismatch")
    if r.kind != data.kind:
        raise invalid("result.kind", "validation.card_kind_mismatch")
    if r.original_attempt_id is not None and r.original_attempt_id != data.original_transaction_id:
        raise invalid("result.original_attempt_id", "validation.card_original_mismatch")
    if data.status is not None and data.status != r.status:
        raise invalid("status", "validation.card_status_mismatch")
    if r.resolved_by == "manager":
        if r.amount != money_str(money(data.amount)) and r.status == "approved":
            raise invalid("result.amount", "validation.card_manager_amount")
    elif data.card_manual_approval is not None:
        raise invalid("card_manual_approval", "validation.not_allowed")
