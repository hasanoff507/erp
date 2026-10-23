"""Composition of the cash module (23 §1 ``wiring.py``).

Public entry points for other modules:

* :func:`shift_guard` → :class:`~app.modules.cash.application.contracts.ShiftGuard` (sales/returns posting);
* :func:`sync_handlers` → ``shift.opened`` / ``shift.closed`` / ``cash_movement.created`` (collected by sync);
* :func:`build_cash_module` → the REST services published on ``app.state.cash``;
* :func:`build_approvals` → the BO-16 queue (``/approval-requests``, owned with this slice) with the
  ``cash_movements`` hook (approving a back-office over-limit withdrawal posts its draft).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db.session import Database, session_tenant_id
from app.modules.access.wiring import (
    ApprovalRefIn,
    ApprovalRequestService,
    approval_gate,
    approval_request_service,
)
from app.modules.accounting.wiring import ledger_poster
from app.modules.auth.wiring import pin_verifier
from app.modules.cash.application.bank_import import BankStatementImportService, ImportLimits
from app.modules.cash.application.bank_settlements import BankSettlementService
from app.modules.cash.application.contracts import OpenShift, ShiftGuard
from app.modules.cash.application.module import CashModule
from app.modules.cash.application.movements import CashMovementService
from app.modules.cash.application.shift_guard import ShiftGuardService
from app.modules.cash.application.shifts import ShiftService
from app.modules.cash.application.sync_events import CashSyncHandlers
from app.modules.cash.infrastructure.bank_settlements_sql import (
    BankStatementFileStore,
    SqlBankSettlementRepository,
)
from app.modules.cash.infrastructure.cash_sql import SqlCashRepository
from app.modules.debts.wiring import debt_register
from app.modules.expenses.wiring import approval_hook as expense_approval_hook
from app.modules.integrations.card_terminal.wiring import card_payments
from app.modules.integrations.fiscal.wiring import fiscal_service
from app.modules.notifications.wiring import event_recorder
from app.modules.pricing.wiring import price_change_service

__all__ = [
    "CashModule",
    "OpenShift",
    "ShiftGuard",
    "build_approvals",
    "build_cash_module",
    "shift_guard",
    "sync_handlers",
]


def shift_guard() -> ShiftGuardService:
    return ShiftGuardService(SqlCashRepository(), ledger_poster())


def _services(settings: Settings, db: Database) -> tuple[ShiftService, CashMovementService]:
    repo = SqlCashRepository()
    shifts = ShiftService(
        db.session_factory,
        repo,
        ledger_poster(),
        event_recorder(),
        fiscal_service(settings),
        card_payments(settings),
    )
    movements = CashMovementService(
        db.session_factory,
        repo,
        ledger_poster(),
        approval_gate(),
        ShiftGuardService(repo, ledger_poster()),
        event_recorder(),
        approval_ttl_minutes=settings.approval_ttl_minutes,
        debts=debt_register(),
    )
    return shifts, movements


def build_cash_module(settings: Settings, db: Database) -> CashModule:
    shifts, movements = _services(settings, db)
    bank, imports = _bank_services(settings, db)
    return CashModule(shifts=shifts, movements=movements, bank_settlements=bank, bank_imports=imports)


def _bank_services(
    settings: Settings, db: Database
) -> tuple[BankSettlementService, BankStatementImportService]:
    """BO-24 bank settlements (qaror #42): REST service + 1CClientBankExchange import (20 #55a–#55h)."""
    repo = SqlBankSettlementRepository()
    bank = BankSettlementService(db.session_factory, repo, ledger_poster())
    imports = BankStatementImportService(
        db.session_factory,
        repo,
        bank,
        BankStatementFileStore(settings.file_storage_dir),
        ImportLimits(max_bytes=settings.import_max_bytes, max_lines=settings.import_max_rows),
    )
    return bank, imports


def sync_handlers(settings: Settings, db: Database) -> Mapping[str, Any]:
    shifts, movements = _services(settings, db)
    handlers = CashSyncHandlers(shifts, movements)
    return {
        "shift.opened": handlers.shift_opened,
        "shift.closed": handlers.shift_closed,
        "cash_movement.created": handlers.cash_movement_created,
    }


def build_approvals(
    settings: Settings, db: Database, cash: CashModule, redis: Callable[[], Redis]
) -> ApprovalRequestService:
    """``/approval-requests`` service: PIN step-up through ``auth.wiring.pin_verifier`` (lockout, audit)
    and the ``cash_movements`` hook."""
    pins = pin_verifier(settings, db, redis)

    gate = approval_gate()
    prices = price_change_service(db.session_factory)

    async def price_hook(s: AsyncSession, row: Any, decision: str, user_id: UUID) -> None:
        """18 §10: approve posts the linked ``price_changes`` (request consumed), reject → ``rejected``."""
        tenant_id = session_tenant_id(s)
        if row.linked_doc_id is None or tenant_id is None:
            return
        if decision == "approved":
            await gate.require(
                s,
                tenant_id=tenant_id,
                branch_id=row.branch_id,
                kind="price_change",
                permission="prices.approve",
                requested_by=row.requested_by,
                value=row.requested_value,
                approval=ApprovalRefIn(mode="remote_request", approval_request_id=row.id),
                doc_type="price_changes",
                doc_id=row.linked_doc_id,
                offline=False,
            )
        await prices.resolve_approval(
            s, tenant_id=tenant_id, doc_id=row.linked_doc_id, decision=decision, resolver_id=user_id
        )

    async def cash_hook(s: AsyncSession, row: Any, decision: str, user_id: UUID) -> None:
        del user_id
        tenant_id = session_tenant_id(s)
        if decision == "approved" and row.linked_doc_id is not None and tenant_id is not None:
            await cash.movements.post_approved(s, tenant_id, row.linked_doc_id, row.id)

    hooks: dict[str, Any] = {
        "cash_movements": cash_hook,
        "price_changes": price_hook,
        "expenses": expense_approval_hook(settings, db),  # B4: expense_over_limit (20 #43)
    }
    return approval_request_service(
        db,
        pins,
        ttl_minutes=settings.approval_ttl_minutes,
        hooks=hooks,
    )
