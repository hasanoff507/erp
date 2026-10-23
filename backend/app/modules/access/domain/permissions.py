"""Permission catalog and default role matrix (15 §2.1–§2.3, qaror #23/#28).

The catalog is code, not a table (23 §11). ``role_permissions`` rows for the
five system roles are generated from :data:`DEFAULT_MATRIX` at tenant
provisioning (12 §5.2).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Final


class LimitUnit(StrEnum):
    NONE = "none"
    PERCENT = "percent"  # discount.*, prices.approve
    AMOUNT = "amount"  # so'm


class SystemRole(StrEnum):
    OWNER = "owner"
    MANAGER = "manager"
    CASHIER = "cashier"
    STOREKEEPER = "storekeeper"
    ACCOUNTANT = "accountant"


# roles.name for the system roles (12 §5.2)
SYSTEM_ROLE_NAMES: Final[dict[SystemRole, str]] = {
    SystemRole.OWNER: "Egasi",
    SystemRole.MANAGER: "Menejer",
    SystemRole.CASHIER: "Kassir",
    SystemRole.STOREKEEPER: "Omborchi",
    SystemRole.ACCOUNTANT: "Buxgalter",
}


@dataclass(frozen=True, slots=True)
class Permission:
    code: str
    modules: str
    limit_unit: LimitUnit = LimitUnit.NONE
    owner_only: bool = False
    platform_only: bool = False


_P = Permission
_PCT = LimitUnit.PERCENT
_SUM = LimitUnit.AMOUNT

PERMISSIONS: Final[tuple[Permission, ...]] = (
    _P("sales.create", "M01"),
    _P("sales.void", "M01"),
    _P("shift.open", "M01"),
    _P("shift.close", "M01"),
    _P("cash_register.manage", "M01"),
    _P("returns.create", "M02"),
    _P("returns.approve", "M02", _SUM),
    _P("discount.give", "M03", _PCT),
    _P("discount.approve", "M03", _PCT),
    _P("discount.rule.manage", "M03"),
    _P("stock.view", "M04"),
    _P("stock.writeoff", "M04", _SUM),
    _P("stock.count.create", "M05"),
    _P("stock.count.post", "M05"),
    _P("transfer.create", "M06"),
    _P("transfer.receive", "M06"),
    _P("purchases.create", "M07"),
    _P("purchases.receive", "M07"),
    _P("purchases.post", "M07"),
    _P("purchases.pay", "M07"),
    _P("purchases.return", "M07"),
    _P("einvoice.sign", "M07, M10"),
    _P("debts.create", "M08"),
    _P("debts.approve", "M08", _SUM),
    _P("debts.forgive", "M08", owner_only=True),
    _P("debts.limit.manage", "M08"),
    _P("debts.payment.accept", "M08"),
    _P("debts.remind", "M08, AI-06"),
    _P("prices.edit", "M09"),
    _P("prices.approve", "M09", _PCT),
    _P("labels.print", "M09"),
    _P("catalog.manage", "M09"),
    _P("tax.vat.view", "M10"),
    _P("tax.compare.review", "M10"),
    _P("tax.correction.submit", "M10"),
    _P("accounting.post", "M11"),
    _P("accounting.period.close", "M11"),
    _P("stock.opening.manage", "M04, M08"),
    _P("valuation.settings.manage", "M04, M11"),
    _P("reports.sales.view", "M12"),
    _P("reports.finance.view", "M12"),
    _P("reports.export", "M12"),
    _P("settings.users", "M13"),
    _P("settings.branches", "M14"),
    _P("settings.tenant", "M13, M14", owner_only=True),
    _P("integrations.retry", "M01, M07, M10"),
    _P("einvoice.create", "M01, M08, M10"),
    _P("expenses.create", "M15"),
    _P("expenses.approve", "M15", _SUM),
    _P("cash.deposit", "M16", _SUM),
    _P("cash.withdraw", "M16", _SUM),
    _P("cash.count.shift", "M16"),
    _P("card.manual_entry.approve", "M01, M02, M08"),
    _P("devices.revoke", "M13"),
    _P("bank_settlements.manage", "M11, M16"),
    _P("billing.manage", "M17", owner_only=True),
    _P("notifications.manage", "M18"),
    _P("telegram.link", "M18"),
    _P("ai.chat.use", "AI-01"),
    _P("ai.ocr.use", "AI-03"),
    _P("onec.view", "M19"),
    _P("onec.settings.manage", "M19"),
    _P("onec.mapping.edit", "M19"),
    _P("onec.refs.create", "M19"),
    _P("onec.export.prepare", "M19"),
    _P("onec.export.approve", "M19"),
    _P("onec.export.correct", "M19"),
    _P("platform.admin", "M17/ADM-01", platform_only=True),
)

PERMISSION_CODES: Final[frozenset[str]] = frozenset(p.code for p in PERMISSIONS)
TENANT_PERMISSION_CODES: Final[tuple[str, ...]] = tuple(p.code for p in PERMISSIONS if not p.platform_only)

# value: limit_value (None = no limit). 15 §2.2; numbers only where §2.3 gives them.
_MANAGER: dict[str, Decimal | None] = dict.fromkeys(
    (
        "sales.create", "shift.open", "shift.close", "returns.create", "returns.approve", "discount.give",
        "discount.approve", "stock.count.create", "stock.count.post", "transfer.create", "transfer.receive",
        "purchases.create", "debts.create", "debts.approve", "debts.limit.manage", "debts.payment.accept",
        "debts.remind", "prices.edit", "reports.finance.view", "catalog.manage", "stock.opening.manage",
        "integrations.retry", "einvoice.create", "expenses.create", "cash.withdraw", "cash.deposit",
        "cash.count.shift", "card.manual_entry.approve", "devices.revoke", "telegram.link", "sales.void",
        "cash_register.manage", "discount.rule.manage", "stock.view", "stock.writeoff", "purchases.return",
        "labels.print", "reports.sales.view", "reports.export", "ai.chat.use", "ai.ocr.use", "onec.view",
    ),
    None,
)  # fmt: skip

_CASHIER: dict[str, Decimal | None] = {
    "sales.create": None,
    "shift.open": None,
    "shift.close": None,
    "returns.create": None,
    "returns.approve": Decimal("100000.00"),
    "discount.give": Decimal("5.00"),
    "debts.create": None,
    "debts.payment.accept": None,
    "cash.withdraw": Decimal("50000.00"),
    "cash.deposit": None,
    "cash.count.shift": None,
    "sales.void": None,
    "stock.view": None,
}

_STOREKEEPER: dict[str, Decimal | None] = dict.fromkeys(
    (
        "stock.count.create", "transfer.create", "transfer.receive", "purchases.create", "purchases.receive",
        "catalog.manage", "stock.view", "stock.writeoff", "purchases.return", "labels.print", "ai.ocr.use",
    ),
    None,
)  # fmt: skip

_ACCOUNTANT: dict[str, Decimal | None] = dict.fromkeys(
    (
        "purchases.post", "purchases.pay", "einvoice.sign", "debts.payment.accept", "debts.remind",
        "tax.vat.view", "tax.compare.review", "tax.correction.submit", "accounting.post",
        "accounting.period.close", "reports.finance.view", "stock.opening.manage",
        "valuation.settings.manage", "integrations.retry", "einvoice.create", "expenses.create",
        "stock.view", "purchases.return", "reports.sales.view", "reports.export", "ai.chat.use",
        "ai.ocr.use", "bank_settlements.manage", "onec.view", "onec.mapping.edit", "onec.refs.create",
        "onec.export.prepare", "onec.export.approve", "onec.export.correct",
    ),
    None,
)  # fmt: skip

DEFAULT_MATRIX: Final[dict[SystemRole, dict[str, Decimal | None]]] = {
    # qaror #28: owner = superset of all tenant permissions, no limits
    SystemRole.OWNER: dict.fromkeys(TENANT_PERMISSION_CODES, None),
    SystemRole.MANAGER: _MANAGER,
    SystemRole.CASHIER: _CASHIER,
    SystemRole.STOREKEEPER: _STOREKEEPER,
    SystemRole.ACCOUNTANT: _ACCOUNTANT,
}
