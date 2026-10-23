"""SQL for ``app.branches`` / ``branch_tax_settings`` / ``warehouses`` / ``cash_registers`` (12 §2.3).

Everything runs inside the caller's tenant transaction (RLS + explicit ``tenant_id`` filters).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Final
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.base import uuid7
from app.modules.branches.application.ports import BranchRow, CashRegisterRow, NewBranch, WarehouseRow
from app.modules.branches.domain.model import EXTRA_REGISTER_ADDON, INCLUDED_REGISTERS_KEY
from app.modules.branches.domain.tax import RateRow, TaxSetting

# --- branches -----------------------------------------------------------------------------------

_DEFAULT_BRANCH = text("SELECT id FROM app.branches WHERE tenant_id = :tenant_id AND code = '01'")
_LOCK_TENANT = text("SELECT id FROM app.tenants WHERE id = :tenant_id FOR UPDATE")
_USED_CODES = text("SELECT code FROM app.branches WHERE tenant_id = :tenant_id")
_INSERT_BRANCH = text(
    "INSERT INTO app.branches "
    "(id, tenant_id, code, name, address, is_default, settlement_category, activity_type) "
    "VALUES (:id, :tenant_id, :code, :name, :address, :is_default, :settlement_category, :activity_type)"
)
# settlement_category / activity_type in force on :on — branch_tax_settings history, else the branch columns
_BRANCH_SELECT: Final = (
    "SELECT b.id, b.code, b.name, b.address, b.is_default, "
    "COALESCE(t.settlement_category, b.settlement_category) AS settlement_category, "
    "COALESCE(t.activity_type, b.activity_type) AS activity_type, b.version, b.archived_at, b.created_at "
    "FROM app.branches b LEFT JOIN LATERAL ("
    "  SELECT ts.settlement_category, ts.activity_type FROM app.branch_tax_settings ts "
    "  WHERE ts.branch_id = b.id AND ts.valid_from <= :on ORDER BY ts.valid_from DESC LIMIT 1"
    ") t ON true "
)
_SCOPE: Final = "(cardinality(CAST(:allowed AS uuid[])) = 0 OR b.id = ANY(CAST(:allowed AS uuid[])))"
_LIST_BRANCHES = text(
    _BRANCH_SELECT + f"WHERE b.tenant_id = :tenant_id AND b.archived_at IS NULL AND {_SCOPE} "
    "ORDER BY b.is_default DESC, b.code, b.id OFFSET :offset LIMIT :limit"
)
_COUNT_BRANCHES = text(
    "SELECT count(*) FROM app.branches b WHERE b.tenant_id = :tenant_id AND b.archived_at IS NULL AND "  # noqa: S608
    + _SCOPE
)
_GET_BRANCH = text(_BRANCH_SELECT + "WHERE b.tenant_id = :tenant_id AND b.id = :id")
_GET_BRANCH_FOR_UPDATE = text(
    _BRANCH_SELECT + "WHERE b.tenant_id = :tenant_id AND b.id = :id FOR UPDATE OF b"
)
_BRANCH_COLUMNS: Final = frozenset({"name", "address", "settlement_category", "activity_type"})
_TAX_HISTORY = text(
    "SELECT valid_from, settlement_category, activity_type FROM app.branch_tax_settings "
    "WHERE branch_id = :branch_id ORDER BY valid_from"
)
_TAX_HISTORY_PAGE = text(
    "SELECT valid_from, settlement_category, activity_type, count(*) OVER () AS total "
    "FROM app.branch_tax_settings WHERE branch_id = :branch_id "
    "ORDER BY valid_from DESC OFFSET :offset LIMIT :limit"
)
_TAX_HISTORY_COUNT = text("SELECT count(*) FROM app.branch_tax_settings WHERE branch_id = :branch_id")
_UPSERT_TAX_SETTING = text(
    "INSERT INTO app.branch_tax_settings "
    "(id, tenant_id, branch_id, valid_from, settlement_category, activity_type, created_by) "
    "VALUES (:id, :tenant_id, :branch_id, :valid_from, :settlement_category, :activity_type, :created_by) "
    "ON CONFLICT (branch_id, valid_from) DO UPDATE SET settlement_category = EXCLUDED.settlement_category, "
    "activity_type = EXCLUDED.activity_type, created_by = EXCLUDED.created_by, created_at = now()"
)
_TODAY_SALES = text(
    "SELECT COALESCE(sum(total_amount), 0) FROM app.sales "
    "WHERE branch_id = :branch_id AND doc_date = :on AND status = 'posted'"
)
_STOCK_VALUE = text(
    "SELECT COALESCE(sum(sb.value), 0) FROM app.stock_balances sb "
    "JOIN app.warehouses w ON w.id = sb.warehouse_id AND w.tenant_id = sb.tenant_id "
    "WHERE w.branch_id = :branch_id"
)
_LEGAL_FORM = text("SELECT legal_form FROM app.tenants WHERE id = :tenant_id")
_TURNOVER_RATES = text("SELECT valid_from, rate_pct FROM platform.turnover_tax_rates WHERE code = :code")

# --- warehouses ---------------------------------------------------------------------------------

_INSERT_WAREHOUSE = text(
    "INSERT INTO app.warehouses (id, tenant_id, branch_id, name, type, inventory_account) "
    "VALUES (:id, :tenant_id, :branch_id, :name, :type, :inventory_account)"
)
_WAREHOUSE_SELECT: Final = (
    "SELECT id, branch_id, name, type, inventory_account, version, archived_at FROM app.warehouses "
)
_LIST_WAREHOUSES = text(
    _WAREHOUSE_SELECT + "WHERE tenant_id = :tenant_id AND archived_at IS NULL "
    "AND (CAST(:branch_ids AS uuid[]) IS NULL OR branch_id = ANY(CAST(:branch_ids AS uuid[]))) "
    "ORDER BY branch_id, created_at, id"
)
_GET_WAREHOUSE = text(_WAREHOUSE_SELECT + "WHERE tenant_id = :tenant_id AND id = :id")
_GET_WAREHOUSE_FOR_UPDATE = text(_WAREHOUSE_SELECT + "WHERE tenant_id = :tenant_id AND id = :id FOR UPDATE")
_HAS_STOCK_MOVES = text("SELECT 1 FROM app.stock_moves WHERE warehouse_id = :id LIMIT 1")
_WAREHOUSE_COLUMNS: Final = frozenset({"name", "inventory_account"})

# --- cash registers -----------------------------------------------------------------------------

_FIRST_CASH_REGISTER = text(
    "SELECT id FROM app.cash_registers WHERE tenant_id = :tenant_id AND branch_id = :branch_id "
    "AND archived_at IS NULL ORDER BY created_at, id LIMIT 1"
)
_INSERT_CASH_REGISTER = text(
    "INSERT INTO app.cash_registers (id, tenant_id, branch_id, name, kind) "
    "VALUES (:id, :tenant_id, :branch_id, :name, :kind)"
)
_REGISTER_SELECT: Final = (
    "SELECT id, branch_id, name, kind, fiscal_module_id, txkm_contract_ref, fiscal_agent_id, "
    "fiscal_local_device_id, ofd_status, fm_state, last_unacked_receipt_at, fm_receipts_pending, "
    "tax_registered_at, archived_at, version FROM app.cash_registers "
)
_LIST_REGISTERS = text(
    _REGISTER_SELECT + "WHERE tenant_id = :tenant_id "
    "AND (CAST(:include_archived AS boolean) OR archived_at IS NULL) "
    "AND (CAST(:branch_ids AS uuid[]) IS NULL OR branch_id = ANY(CAST(:branch_ids AS uuid[]))) "
    "ORDER BY branch_id, created_at, id"
)
_GET_REGISTER = text(_REGISTER_SELECT + "WHERE tenant_id = :tenant_id AND id = :id")
_GET_REGISTER_FOR_UPDATE = text(_REGISTER_SELECT + "WHERE tenant_id = :tenant_id AND id = :id FOR UPDATE")
_ACTIVE_REGISTERS = text(
    "SELECT count(*) FROM app.cash_registers WHERE tenant_id = :tenant_id AND archived_at IS NULL"
)
_INCLUDED_REGISTERS = text(
    "SELECT COALESCE((p.limits ->> :key)::int, 0) FROM app.subscriptions s "
    "JOIN platform.plans p ON p.id = s.plan_id WHERE s.tenant_id = :tenant_id"
)
_EXTRA_REGISTERS = text(
    "SELECT COALESCE(sum(quantity), 0) FROM app.tenant_addons "
    "WHERE tenant_id = :tenant_id AND addon_code = :addon AND removed_at IS NULL"
)
_ARCHIVE_REGISTER = text(
    "UPDATE app.cash_registers SET archived_at = now(), version = version + 1, updated_at = now() "
    "WHERE id = :id RETURNING archived_at"
)
_REGISTER_COLUMNS: Final = frozenset({"name", "fiscal_agent_id", "fiscal_local_device_id"})
# onec_agents arrives with the Do'kon agenti (migration 0028, Bosqich 5); until then no agent can exist
_AGENTS_TABLE = text("SELECT to_regclass('app.onec_agents') IS NOT NULL")
_AGENT_EXISTS = text("SELECT 1 FROM app.onec_agents WHERE id = :id")


def _update_sql(table: str, allowed: frozenset[str], fields: dict[str, Any]) -> Any:
    unknown = set(fields) - allowed
    if unknown or not fields:
        raise ValueError(f"cannot update {table} columns {sorted(unknown) or '(none)'}")
    assignments = ", ".join(f"{column} = :{column}" for column in sorted(fields))
    return text(
        f"UPDATE app.{table} SET {assignments}, version = version + 1, updated_at = now() "  # noqa: S608
        "WHERE id = :id RETURNING version"
    )


def _branch(row: Any) -> BranchRow:
    return BranchRow(
        id=row.id,
        code=row.code,
        name=row.name,
        address=row.address,
        is_default=row.is_default,
        settlement_category=row.settlement_category,
        activity_type=row.activity_type,
        version=row.version,
        archived_at=row.archived_at,
        created_at=row.created_at,
    )


def _warehouse(row: Any) -> WarehouseRow:
    return WarehouseRow(
        id=row.id,
        branch_id=row.branch_id,
        name=row.name,
        type=row.type,
        inventory_account=row.inventory_account,
        version=row.version,
        archived_at=row.archived_at,
    )


def _register(row: Any) -> CashRegisterRow:
    return CashRegisterRow(
        id=row.id,
        branch_id=row.branch_id,
        name=row.name,
        kind=row.kind,
        fiscal_module_id=row.fiscal_module_id,
        txkm_contract_ref=row.txkm_contract_ref,
        fiscal_agent_id=row.fiscal_agent_id,
        fiscal_local_device_id=row.fiscal_local_device_id,
        ofd_status=row.ofd_status,
        fm_state=row.fm_state,
        last_unacked_receipt_at=row.last_unacked_receipt_at,
        fm_receipts_pending=row.fm_receipts_pending,
        tax_registered_at=row.tax_registered_at,
        archived_at=row.archived_at,
        version=row.version,
    )


def _ids(values: tuple[UUID, ...] | None) -> list[str] | None:
    return None if values is None else [str(v) for v in values]


class SqlBranchRepository:
    """:class:`app.modules.branches.application.ports.BranchRepository`."""

    async def default_branch_id(self, session: AsyncSession, tenant_id: UUID) -> UUID | None:
        value: UUID | None = (
            await session.execute(_DEFAULT_BRANCH, {"tenant_id": tenant_id})
        ).scalar_one_or_none()
        return value

    async def lock_tenant(self, session: AsyncSession, tenant_id: UUID) -> None:
        await session.execute(_LOCK_TENANT, {"tenant_id": tenant_id})

    async def used_codes(self, session: AsyncSession, tenant_id: UUID) -> list[str]:
        return [r[0] for r in (await session.execute(_USED_CODES, {"tenant_id": tenant_id})).all()]

    async def insert_branch(
        self, session: AsyncSession, tenant_id: UUID, branch: NewBranch, *, is_default: bool
    ) -> None:
        await session.execute(
            _INSERT_BRANCH,
            {
                "id": branch.id,
                "tenant_id": tenant_id,
                "code": branch.code,
                "name": branch.name,
                "address": branch.address,
                "is_default": is_default,
                "settlement_category": branch.settlement_category,
                "activity_type": branch.activity_type,
            },
        )

    async def list_branches(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        allowed: tuple[UUID, ...],
        on: date,
        *,
        offset: int,
        limit: int,
    ) -> tuple[list[BranchRow], int]:
        params = {"tenant_id": tenant_id, "allowed": _ids(allowed), "on": on}
        rows = (await session.execute(_LIST_BRANCHES, {**params, "offset": offset, "limit": limit})).all()
        total = (await session.execute(_COUNT_BRANCHES, params)).scalar_one()
        return [_branch(r) for r in rows], int(total)

    async def get_branch(
        self, session: AsyncSession, tenant_id: UUID, branch_id: UUID, on: date, *, for_update: bool = False
    ) -> BranchRow | None:
        stmt = _GET_BRANCH_FOR_UPDATE if for_update else _GET_BRANCH
        row = (await session.execute(stmt, {"tenant_id": tenant_id, "id": branch_id, "on": on})).first()
        return None if row is None else _branch(row)

    async def update_branch(self, session: AsyncSession, branch_id: UUID, fields: dict[str, Any]) -> int:
        stmt = _update_sql("branches", _BRANCH_COLUMNS, fields)
        version: int = (await session.execute(stmt, {**fields, "id": branch_id})).scalar_one()
        return version

    async def tax_history(self, session: AsyncSession, branch_id: UUID) -> list[TaxSetting]:
        rows = (await session.execute(_TAX_HISTORY, {"branch_id": branch_id})).all()
        return [TaxSetting(r.valid_from, r.settlement_category, r.activity_type) for r in rows]

    async def tax_history_page(
        self, session: AsyncSession, branch_id: UUID, *, offset: int, limit: int
    ) -> tuple[list[TaxSetting], int]:
        params = {"branch_id": branch_id, "offset": offset, "limit": limit}
        rows = (await session.execute(_TAX_HISTORY_PAGE, params)).all()
        if rows:
            total = int(rows[0].total)
        else:
            total = int((await session.execute(_TAX_HISTORY_COUNT, {"branch_id": branch_id})).scalar_one())
        return [TaxSetting(r.valid_from, r.settlement_category, r.activity_type) for r in rows], total

    async def upsert_tax_setting(
        self, session: AsyncSession, tenant_id: UUID, branch_id: UUID, setting: TaxSetting, user_id: UUID
    ) -> None:
        await session.execute(
            _UPSERT_TAX_SETTING,
            {
                "id": uuid7(),
                "tenant_id": tenant_id,
                "branch_id": branch_id,
                "valid_from": setting.valid_from,
                "settlement_category": setting.settlement_category,
                "activity_type": setting.activity_type,
                "created_by": user_id,
            },
        )

    async def today_sales(self, session: AsyncSession, branch_id: UUID, on: date) -> Decimal:
        value: Decimal = (
            await session.execute(_TODAY_SALES, {"branch_id": branch_id, "on": on})
        ).scalar_one()
        return value

    async def stock_value(self, session: AsyncSession, branch_id: UUID) -> Decimal:
        value: Decimal = (await session.execute(_STOCK_VALUE, {"branch_id": branch_id})).scalar_one()
        return value

    async def legal_form(self, session: AsyncSession, tenant_id: UUID) -> str:
        value: str = (await session.execute(_LEGAL_FORM, {"tenant_id": tenant_id})).scalar_one()
        return value

    async def turnover_rates(self, session: AsyncSession, code: str) -> list[RateRow]:
        rows = (await session.execute(_TURNOVER_RATES, {"code": code})).all()
        return [RateRow(r.valid_from, r.rate_pct) for r in rows]


class SqlWarehouseRepository:
    """:class:`app.modules.branches.application.ports.WarehouseRepository`."""

    async def insert_warehouse(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        branch_id: UUID,
        warehouse_id: UUID,
        name: str,
        warehouse_type: str,
        inventory_account: str,
    ) -> None:
        await session.execute(
            _INSERT_WAREHOUSE,
            {
                "id": warehouse_id,
                "tenant_id": tenant_id,
                "branch_id": branch_id,
                "name": name,
                "type": warehouse_type,
                "inventory_account": inventory_account,
            },
        )

    async def list_warehouses(
        self, session: AsyncSession, tenant_id: UUID, branch_ids: tuple[UUID, ...] | None
    ) -> list[WarehouseRow]:
        params = {"tenant_id": tenant_id, "branch_ids": _ids(branch_ids)}
        return [_warehouse(r) for r in (await session.execute(_LIST_WAREHOUSES, params)).all()]

    async def get_warehouse(
        self, session: AsyncSession, tenant_id: UUID, warehouse_id: UUID, *, for_update: bool = False
    ) -> WarehouseRow | None:
        stmt = _GET_WAREHOUSE_FOR_UPDATE if for_update else _GET_WAREHOUSE
        row = (await session.execute(stmt, {"tenant_id": tenant_id, "id": warehouse_id})).first()
        return None if row is None else _warehouse(row)

    async def has_stock_moves(self, session: AsyncSession, warehouse_id: UUID) -> bool:
        return (await session.execute(_HAS_STOCK_MOVES, {"id": warehouse_id})).first() is not None

    async def update_warehouse(
        self, session: AsyncSession, warehouse_id: UUID, fields: dict[str, Any]
    ) -> int:
        stmt = _update_sql("warehouses", _WAREHOUSE_COLUMNS, fields)
        version: int = (await session.execute(stmt, {**fields, "id": warehouse_id})).scalar_one()
        return version


class SqlCashRegisterRepository:
    """:class:`app.modules.branches.application.ports.CashRegisterRepository`."""

    async def first_cash_register_id(
        self, session: AsyncSession, tenant_id: UUID, branch_id: UUID
    ) -> UUID | None:
        value: UUID | None = (
            await session.execute(_FIRST_CASH_REGISTER, {"tenant_id": tenant_id, "branch_id": branch_id})
        ).scalar_one_or_none()
        return value

    async def insert_cash_register(
        self, session: AsyncSession, tenant_id: UUID, register_id: UUID, branch_id: UUID, name: str, kind: str
    ) -> None:
        await session.execute(
            _INSERT_CASH_REGISTER,
            {"id": register_id, "tenant_id": tenant_id, "branch_id": branch_id, "name": name, "kind": kind},
        )

    async def list_cash_registers(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        branch_ids: tuple[UUID, ...] | None,
        *,
        include_archived: bool,
    ) -> list[CashRegisterRow]:
        params = {
            "tenant_id": tenant_id,
            "branch_ids": _ids(branch_ids),
            "include_archived": include_archived,
        }
        return [_register(r) for r in (await session.execute(_LIST_REGISTERS, params)).all()]

    async def get_cash_register(
        self, session: AsyncSession, tenant_id: UUID, register_id: UUID, *, for_update: bool = False
    ) -> CashRegisterRow | None:
        stmt = _GET_REGISTER_FOR_UPDATE if for_update else _GET_REGISTER
        row = (await session.execute(stmt, {"tenant_id": tenant_id, "id": register_id})).first()
        return None if row is None else _register(row)

    async def active_count(self, session: AsyncSession, tenant_id: UUID) -> int:
        return int((await session.execute(_ACTIVE_REGISTERS, {"tenant_id": tenant_id})).scalar_one())

    async def allowance(self, session: AsyncSession, tenant_id: UUID) -> tuple[int, int]:
        included = (
            await session.execute(
                _INCLUDED_REGISTERS, {"tenant_id": tenant_id, "key": INCLUDED_REGISTERS_KEY}
            )
        ).scalar()
        extra = (
            await session.execute(_EXTRA_REGISTERS, {"tenant_id": tenant_id, "addon": EXTRA_REGISTER_ADDON})
        ).scalar_one()
        return int(included or 0), int(extra)

    async def update_cash_register(
        self, session: AsyncSession, register_id: UUID, fields: dict[str, Any]
    ) -> int:
        stmt = _update_sql("cash_registers", _REGISTER_COLUMNS, fields)
        version: int = (await session.execute(stmt, {**fields, "id": register_id})).scalar_one()
        return version

    async def archive_cash_register(self, session: AsyncSession, register_id: UUID) -> datetime:
        value: datetime = (await session.execute(_ARCHIVE_REGISTER, {"id": register_id})).scalar_one()
        return value

    async def fiscal_agent_exists(self, session: AsyncSession, agent_id: UUID) -> bool:
        if not (await session.execute(_AGENTS_TABLE)).scalar_one():
            return False
        return (await session.execute(_AGENT_EXISTS, {"id": agent_id})).first() is not None
