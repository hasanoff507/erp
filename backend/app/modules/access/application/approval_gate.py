"""Cross-module approval contract (18 §2.4, 15 §2.3, 12 §2.5a) — Bosqich 3 coordination file.

Owner: cash/approvals slice (it also builds ``/approval-requests`` and BO-16 backend). Consumers
(sale discounts, returns, cash withdrawals, manual card entry, card ``unknown`` resolution) obtain an
instance via ``app.modules.access.wiring.approval_gate()`` and call :meth:`ApprovalGate.require` inside
their posting transaction, before writing registers.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Literal, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

ApprovalKind = Literal[
    "discount_over_limit",
    "return_over_limit",
    "return_no_receipt",
    "debt_over_limit",
    "cash_withdrawal_over_limit",
    "price_change",
    "expense_over_limit",
    "write_off_over_limit",
    "card_manual_entry",
]


@dataclass(frozen=True, slots=True)
class ApprovalRefIn:
    """The ``ApprovalRef`` object of 18 §2.4 as received in an event/request."""

    mode: Literal["local_pin", "remote_request"]
    approved_by: UUID | None = None
    pin_verified_locally: bool | None = None
    approval_request_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class ApprovalOutcome:
    """``required`` — the requester's own limit did not cover the value (an approval was applied).

    ``doc_approval_id`` — the ``doc_approvals`` row written (None when not required).
    ``offline_limit_exceeded`` — offline ``local_pin`` approver whose own limit does not cover the value:
    the event is still accepted and the caller adds a ``SyncExceptionRow(kind=
    'approval_limit_exceeded_offline')`` (16 §5); online the same case raises instead.
    """

    required: bool
    doc_approval_id: UUID | None = None
    offline_limit_exceeded: bool = False
    details: Mapping[str, Any] = field(default_factory=dict)
    # online ``local_pin`` whose ``approved_by`` is not PIN-bound to the device session (SEC-02, 15 §2.3a):
    # still accepted; the caller adds ``SyncExceptionRow(kind='actor_unverified')`` with these details
    approver_unverified: bool = False
    unverified_details: Mapping[str, Any] = field(default_factory=dict)


class ApprovalGate(Protocol):
    async def require(
        self,
        s: AsyncSession,
        *,
        tenant_id: UUID,
        branch_id: UUID,
        kind: ApprovalKind,
        permission: str,
        requested_by: UUID,
        value: Decimal | None,
        approval: ApprovalRefIn | None,
        doc_type: str,
        doc_id: UUID,
        offline: bool,
        always_required: bool = False,
        line_id: UUID | None = None,
        missing_code: str | None = None,
        approver_bound: Callable[[UUID], Awaitable[bool]] | None = None,
    ) -> ApprovalOutcome:
        """Check ``requested_by``'s ``role_permissions.limit_value`` for ``permission`` against ``value``.

        ``permission`` is the requester's own code (``discount.give``, ``returns.approve``,
        ``cash.withdraw``, ``card.manual_entry.approve`` …); the approver is always checked against the
        kind's code of 15 §2.3 (``app.modules.access.domain.approvals.PERMISSION_BY_KIND`` — e.g.
        ``discount.approve``).

        Within the limit (and not ``always_required``, e.g. ``return_no_receipt``) → no approval needed.
        Otherwise ``approval`` must be valid: ``local_pin`` — approver active in the tenant/branch,
        holds ``permission`` with a limit covering ``value``; ``remote_request`` — ``approved``, not
        consumed/expired, same kind/branch, ``requested_value`` ≥ ``value`` → becomes ``consumed``.
        Writes the ``doc_approvals`` row. Errors: missing approval → the kind's ``*_LIMIT_EXCEEDED`` /
        ``APPROVAL_REQUIRED`` code (18 §18), approver lacks right/limit → ``APPROVAL_INVALID``,
        consumed/rejected/expired request → ``APPROVAL_REQUEST_ALREADY_RESOLVED``. Owner bypass per
        QT-PERM-01 (owner's own action needs no approval).

        ``line_id`` → ``doc_approvals.line_id`` (discount — ``sale_lines.id``; card manual entry —
        ``sale_payments.id``). ``approver_bound`` — ``EventContext.actor_bound`` of the pushing session:
        for an online (``offline=False``) ``local_pin`` approval whose ``approved_by`` is not bound, the
        outcome carries ``approver_unverified`` (detect, never reject —
        F-6). ``missing_code`` overrides the error raised when ``approval`` is missing
        (e.g. ``"APPROVAL_REQUIRED"`` for an expired-goods return, 18 §7.1); default per kind:
        ``KIND_MISSING_CODE``. ``value`` is in the permission's unit (so'm or percent, 15 §2.1).
        """
        ...
