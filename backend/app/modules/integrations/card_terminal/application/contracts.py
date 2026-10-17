"""Cross-module card-terminal contract (qaror #71/#64, 21 §9.2/§9.4, 18 §2.7/§16a) — B3 coordination file.

Owner: card slice. Consumers (sale/return posting, shift close; later debt payments) obtain an instance
via ``app.modules.integrations.card_terminal.wiring.card_payments(settings)`` and call it inside their
posting transaction (the session ``s`` of the event / request). Payment-row validation of 18 §4.1
(which columns may be set for ``card_entry_mode='integrated'|'manual'``, ``validation.card_*`` keys) stays
with the document owner; everything about the terminal transaction and the manual-card policy is here.
No PAN/track/CVV ever crosses this boundary.

Rules a consumer relies on:

* ``link_result`` never rejects a document because the server row differs from the device's
  ``card_result`` (16 §2.1 — the sale already happened): it returns ``RecordedCardTx.mismatch`` and the
  caller adds ``warnings=["CARD_TRANSACTION_MISMATCH"]`` + ``SyncExceptionRow(kind='card_result_mismatch',
  details=mismatch)``. It raises only for a malformed ``card_result`` (``VALIDATION_ERROR``) or an unknown /
  foreign terminal (``VALIDATION_ERROR``). An ``attempt_id`` already linked to *another* document is accepted
  too: the original link stays, ``RecordedCardTx.id`` is a duplicate transaction row of this document (its
  payment row can reference it — ``uq_sale_payments_card_tx``) and
  ``mismatch.reason='linked_to_other_document'``
  (16 §2.1, 18 §4.1; REST ``POST /card-terminal-transactions`` keeps its 409).
* ``authorize_manual`` applies ``tenants.settings.card_manual_fallback`` (only on a register with an active
  bound terminal), calls ``ApprovalGate(kind='card_manual_entry')``, links a manager-resolved ``unknown``
  attempt (``manual_reason='unknown_result'``) to the document and writes audit ``card.manual_entry``.
  Online it raises ``CARD_MANUAL_NOT_ALLOWED`` / ``CARD_MANUAL_APPROVAL_REQUIRED``; offline it never
  rejects — ``ManualAuthorization.offline_violation`` tells the caller to add
  ``SyncExceptionRow(kind='approval_limit_exceeded_offline')``.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.access.application.approval_gate import ApprovalOutcome, ApprovalRefIn

ManualPolicy = Literal["standalone", "allow", "manager_approval", "forbid"]
ManualReason = Literal["standalone_terminal", "terminal_offline", "terminal_error", "unknown_result"]
CardDocType = Literal["sales", "returns", "debt_payments"]
CardTxKind = Literal["purchase", "refund", "void"]


@dataclass(frozen=True, slots=True)
class RecordedCardTx:
    """Values the document copies onto its payment row (card details only from the terminal result)."""

    id: UUID  # card_terminal_transactions.id = attempt_id → payment.card_terminal_transaction_id
    card_terminal_id: UUID
    card_type: str | None  # never None for an approved purchase (terminal → BIN table → 'unknown')
    card_type_source: str | None  # terminal | bin_table
    card_mask: str | None
    rrn: str | None
    approval_code: str | None
    card_scheme: str | None
    tid: str | None  # → sale_payments.terminal_ref (18 §4.1)
    # server row ≠ device result (amount, duplicate tid+rrn, status) — the caller records
    # warnings CARD_TRANSACTION_MISMATCH + sync_exceptions(kind='card_result_mismatch', details=mismatch)
    mismatch: Mapping[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class ManualAuthorization:
    policy: ManualPolicy
    approval: (
        ApprovalOutcome | None
    )  # None when no approval was needed (standalone / allow / requester holds the right)
    # offline event accepted although the policy was not met (forbid / missing approval) — the caller adds
    # SyncExceptionRow(kind='approval_limit_exceeded_offline', details=details)
    offline_violation: bool = False
    details: Mapping[str, Any] = field(default_factory=dict)
    linked_transaction_id: UUID | None = None  # unknown_result: the manager-resolved attempt now linked
    # SEC-02 (15 §2.3a): online local_pin approver not PIN-bound to the pushing session — still accepted; the
    # caller adds SyncExceptionRow(kind='actor_unverified', details=unverified_details)
    approver_unverified: bool = False
    unverified_details: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SettlementInput:
    """One ``shift.closed.card_settlements[]`` item / ``POST /card-terminal-settlements`` body (18 §16a.6)."""

    id: UUID
    card_terminal_id: UUID
    shift_id: UUID | None
    batch_no: str | None
    business_date: date
    settled_at: datetime
    purchase_count: int
    purchase_total: Decimal
    refund_count: int
    refund_total: Decimal
    failed: bool = False  # the terminal could not settle → status='failed'
    terminal_response: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SettlementRecorded:
    id: UUID
    card_terminal_id: UUID
    status: str  # matched | mismatch | failed
    net_total: Decimal
    expected_total: Decimal
    variance: Decimal


class CardPayments(Protocol):
    async def manual_policy(self, s: AsyncSession, *, cash_register_id: UUID) -> ManualPolicy:
        """``standalone`` — no active terminal bound to the register (manual card always allowed, no
        approval, ``manual_reason='standalone_terminal'``); otherwise
        ``tenants.settings.card_manual_fallback`` (default ``manager_approval``)."""
        ...

    async def authorize_manual(
        self,
        s: AsyncSession,
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
        """Policy + approval for one ``card_entry_mode='manual'`` payment (18 §4.1, 21 §9.2).

        * no active terminal on the register → allowed, no approval; ``manual_reason`` other than
          ``standalone_terminal`` → online ``VALIDATION_ERROR`` (``validation.card_manual_reason_mismatch``),
          offline accepted;
        * active terminal: ``standalone_terminal`` → online ``VALIDATION_ERROR`` (same key), offline treated
          like the other reasons; ``unknown_result`` → approval always needed (the manager's resolution),
          the policy value does not apply; otherwise ``forbid`` → ``CARD_MANUAL_NOT_ALLOWED``, ``allow`` → no
          approval, ``manager_approval`` → ``ApprovalGate.require(kind='card_manual_entry',
          permission='card.manual_entry.approve')`` (missing → ``CARD_MANUAL_APPROVAL_REQUIRED``).
        Sync handlers pass ``approver_bound=ctx.actor_bound`` and ``session_user_id`` (SEC-02).
        ``line_id`` → ``doc_approvals.line_id`` (``sale_payments.id``; NULL for returns/debt payments).
        Writes audit ``card.manual_entry`` (entity = ``doc_type``/``doc_id``)."""
        ...

    async def link_result(
        self,
        s: AsyncSession,
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
        """Validate a ``CardResult`` (18 §2.7, raw JSON as received) and upsert ``card_terminal_transactions``
        by ``attempt_id`` (a replay with identical content is a no-op), link it to the document
        (``doc_type``/``doc_id``), derive ``card_type`` (terminal → ``platform.card_bin_rules`` → ``unknown``;
        BIN only in memory). ``status != approved`` or ``resolved_by='manager'`` → ``VALIDATION_ERROR``
        (``validation.card_result_required``). Differences (amount ≠ ``expected_amount``, duplicate tid+rrn,
        final state already different) → ``RecordedCardTx.mismatch`` — never a rejection. An approved
        ``void`` marks its original purchase ``voided``."""
        ...

    async def assert_shift_resolved(self, s: AsyncSession, *, shift_id: UUID) -> None:
        """``CARD_OUTCOME_UNKNOWN`` when a ``pending``/``unknown`` attempt of the shift exists (18 §3.2)."""
        ...

    async def record_settlements(
        self,
        s: AsyncSession,
        *,
        tenant_id: UUID,
        branch_id: UUID,
        settlements: Sequence[SettlementInput],
        actor_user_id: UUID | None,
        device_id: UUID | None,
        client_event_id: UUID | None,
    ) -> list[SettlementRecorded]:
        """Insert ``card_terminal_settlements`` (idempotent by ``id``), compute ``expected_*`` from the
        terminal's approved purchases/refunds not yet in a batch, stamp their ``settlement_id``, set
        ``matched``/``mismatch``/``failed``; mismatch → audit ``card.settlement.mismatch`` + M18 to the Owner
        (18 §16a.6, QT-M16-08). Used by the REST endpoint."""
        ...

    async def record_shift_settlements(
        self,
        s: AsyncSession,
        *,
        tenant_id: UUID,
        branch_id: UUID,
        shift_id: UUID,
        device_id: UUID | None,
        actor_user_id: UUID,
        client_event_id: UUID | None,
        items: Sequence[Mapping[str, Any]],
    ) -> list[SettlementRecorded]:
        """``shift.closed.card_settlements[]`` (18 §3.2) as raw JSON: validates every item
        (``VALIDATION_ERROR`` with ``card_settlements[i].<field>``), then :meth:`record_settlements`.
        The result feeds ``z_report.card_settlements``."""
        ...
