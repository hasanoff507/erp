"""Branch / warehouse / cash register rules (20 #30–#40i, 12 §2.3, US-M14-03/04). Pure Python."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, date, datetime, timedelta
from typing import Final, Literal, get_args

SettlementCategory = Literal["city_100k_plus", "other", "remote_mountain"]
ActivityType = Literal["retail", "other"]
WarehouseType = Literal["store", "stock"]
InventoryAccount = Literal["2910", "2920"]
CashRegisterKind = Literal["web", "android"]
DeviceKind = Literal["web", "android", "onec_agent"]

SETTLEMENT_CATEGORIES: Final[tuple[str, ...]] = get_args(SettlementCategory)
# US-M14-04: no category chosen → the most conservative one (4%), the UI shows a "please verify" hint
DEFAULT_SETTLEMENT_CATEGORY: Final[SettlementCategory] = "city_100k_plus"
DEFAULT_ACTIVITY_TYPE: Final[ActivityType] = "retail"
DEFAULT_WAREHOUSE_TYPE: Final[WarehouseType] = "store"
DEFAULT_WAREHOUSE_NAME: Final = "Asosiy ombor"
EXTRA_REGISTER_ADDON: Final = "extra_register"
INCLUDED_REGISTERS_KEY: Final = "included_cash_registers"

# 20 #31 / 12 warehouses.inventory_account: store (savdo zali) → 2920, stock (ombor) → 2910
_INVENTORY_ACCOUNT: Final[dict[WarehouseType, InventoryAccount]] = {"store": "2920", "stock": "2910"}

# Asia/Tashkent is UTC+5 all year (no DST)
TASHKENT_OFFSET: Final = timedelta(hours=5)


def inventory_account_for(warehouse_type: WarehouseType) -> InventoryAccount:
    return _INVENTORY_ACCOUNT[warehouse_type]


def next_free_code(used: Iterable[str]) -> str | None:
    """Next free two-digit branch code ``01``…``99`` (20 #31); ``None`` when all are taken."""
    taken = set(used)
    for n in range(1, 100):
        code = f"{n:02d}"
        if code not in taken:
            return code
    return None


def tashkent_today(now: datetime | None = None) -> date:
    moment = now or datetime.now(UTC)
    return (moment.astimezone(UTC) + TASHKENT_OFFSET).date()


def month_start(day: date) -> date:
    return day.replace(day=1)


def next_month_start(day: date) -> date:
    return date(day.year + 1, 1, 1) if day.month == 12 else date(day.year, day.month + 1, 1)


def register_allowance(included: int, extra: int) -> int:
    """Active cash registers allowed: plan ``included_cash_registers`` + active ``extra_register`` qty."""
    return max(included, 0) + max(extra, 0)


def fiscal_pair_ok(agent_id: object | None, local_device_id: str | None) -> bool:
    """qaror #66: ``fiscal_agent_id`` and ``fiscal_local_device_id`` are set together or cleared together."""
    return (agent_id is None) == (local_device_id is None)
