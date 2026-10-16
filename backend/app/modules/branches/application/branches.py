"""Branches, their tax-category history and warehouses (20 #30–#35, #37, #37a; US-M14-01/03/04)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.audit import record_audit
from app.core.auth.principal import Principal
from app.core.db.base import uuid7
from app.core.db.session import tenant_transaction
from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from app.core.idempotency import stage_response
from app.core.money import money_str
from app.modules.branches.application.common import (
    archived,
    check_branch_scope,
    check_version,
    invalid,
    not_found,
    scoped_branch_ids,
)
from app.modules.branches.application.ports import (
    BranchRepository,
    BranchRow,
    NewBranch,
    WarehouseRepository,
    WarehouseRow,
)
from app.modules.branches.domain.model import (
    DEFAULT_WAREHOUSE_NAME,
    WarehouseType,
    inventory_account_for,
    month_start,
    next_free_code,
    tashkent_today,
)
from app.modules.branches.domain.tax import (
    TaxSetting,
    TurnoverRate,
    rate_in_force,
    setting_in_force,
    turnover_rate_code,
)

Clock = Callable[[], date]


@dataclass(frozen=True, slots=True)
class BranchListItem:
    id: UUID
    name: str
    code: str
    address: str | None
    is_default: bool
    settlement_category: str
    activity_type: str
    version: int


@dataclass(frozen=True, slots=True)
class BranchPage:
    items: list[BranchListItem]
    total: int
    page: int
    size: int


@dataclass(frozen=True, slots=True)
class WarehouseBrief:
    id: UUID
    type: str
    inventory_account: str


@dataclass(frozen=True, slots=True)
class BranchCreated:
    id: UUID
    name: str
    address: str | None
    code: str
    settlement_category: str
    activity_type: str
    version: int
    warehouse: WarehouseBrief


@dataclass(frozen=True, slots=True)
class BranchDetail:
    id: UUID
    name: str
    address: str | None
    is_default: bool
    settlement_category: str
    activity_type: str
    version: int
    today_sales: str
    stock_value: str


@dataclass(frozen=True, slots=True)
class BranchUpdated:
    id: UUID
    name: str
    address: str | None
    settlement_category: str
    activity_type: str
    version: int


@dataclass(frozen=True, slots=True)
class TaxSettingItem:
    valid_from: date
    settlement_category: str
    activity_type: str


@dataclass(frozen=True, slots=True)
class TaxSettingPage:
    items: list[TaxSettingItem]
    total: int
    page: int
    size: int


@dataclass(frozen=True, slots=True)
class TaxSettingCreated:
    branch_id: UUID
    valid_from: date
    settlement_category: str
    activity_type: str


@dataclass(frozen=True, slots=True)
class BranchInput:
    name: str
    address: str | None
    code: str | None
    settlement_category: str
    activity_type: str
    warehouse_type: WarehouseType


@dataclass(frozen=True, slots=True)
class BranchPatch:
    version: int
    name: str | None = None
    address: str | None = None
    address_set: bool = False  # address may be cleared with null
    settlement_category: str | None = None
    activity_type: str | None = None


@dataclass(frozen=True, slots=True)
class WarehouseView:
    id: UUID
    branch_id: UUID
    name: str
    type: str
    inventory_account: str
    version: int


@dataclass(frozen=True, slots=True)
class WarehouseUpdated:
    id: UUID
    name: str
    type: str
    inventory_account: str
    version: int


def _list_item(row: BranchRow) -> BranchListItem:
    return BranchListItem(
        id=row.id,
        name=row.name,
        code=row.code,
        address=row.address,
        is_default=row.is_default,
        settlement_category=row.settlement_category,
        activity_type=row.activity_type,
        version=row.version,
    )


def _warehouse_view(row: WarehouseRow) -> WarehouseView:
    return WarehouseView(row.id, row.branch_id, row.name, row.type, row.inventory_account, row.version)


async def turnover_rate_on(
    branches: BranchRepository, session: AsyncSession, tenant_id: UUID, branch_id: UUID, on: date
) -> TurnoverRate:
    """Category and turnover-tax rate of a branch in force on ``on`` (13 §4.3, QT-M14-05).

    History = ``branch_tax_settings``; a branch without history uses its own columns.
    """
    branch = await branches.get_branch(session, tenant_id, branch_id, on)
    if branch is None:
        raise not_found("branches")
    in_force = setting_in_force(await branches.tax_history(session, branch_id), on)
    category = in_force.settlement_category if in_force else branch.settlement_category
    activity = in_force.activity_type if in_force else branch.activity_type
    code = turnover_rate_code(category, activity, await branches.legal_form(session, tenant_id))
    rate = rate_in_force(await branches.turnover_rates(session, code), on)
    return TurnoverRate(on, category, activity, code, rate)


class BranchesService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        branches: BranchRepository,
        warehouses: WarehouseRepository,
        today: Clock = tashkent_today,
    ) -> None:
        self._sf = session_factory
        self._branches = branches
        self._warehouses = warehouses
        self._today = today

    # --- branches ------------------------------------------------------------------------------

    async def list_branches(
        self, actor: Principal, allowed: tuple[UUID, ...], page: int, size: int
    ) -> BranchPage:
        today = self._today()
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            rows, total = await self._branches.list_branches(
                s, actor.tenant_id, allowed, today, offset=(page - 1) * size, limit=size
            )
        return BranchPage([_list_item(r) for r in rows], total, page, size)

    async def create(self, actor: Principal, data: BranchInput, ip: str | None) -> BranchCreated:
        today = self._today()
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            await self._branches.lock_tenant(s, actor.tenant_id)
            used = await self._branches.used_codes(s, actor.tenant_id)
            code = data.code
            if code is not None and code in used:
                raise invalid("code", "validation.duplicate")
            code = code or next_free_code(used)
            if code is None:
                raise invalid("code", "validation.no_free_code")
            branch = NewBranch(
                id=uuid7(),
                code=code,
                name=data.name,
                address=data.address,
                settlement_category=data.settlement_category,
                activity_type=data.activity_type,
            )
            await self._branches.insert_branch(s, actor.tenant_id, branch, is_default=False)
            warehouse = WarehouseBrief(
                uuid7(), data.warehouse_type, inventory_account_for(data.warehouse_type)
            )
            await self._warehouses.insert_warehouse(
                s,
                actor.tenant_id,
                branch.id,
                warehouse.id,
                DEFAULT_WAREHOUSE_NAME,
                warehouse.type,
                warehouse.inventory_account,
            )
            # the category history starts with the branch (US-M14-04: changes apply from valid_from)
            await self._branches.upsert_tax_setting(
                s,
                actor.tenant_id,
                branch.id,
                TaxSetting(month_start(today), data.settlement_category, data.activity_type),
                actor.user_id,
            )
            result = BranchCreated(
                id=branch.id,
                name=branch.name,
                address=branch.address,
                code=code,
                settlement_category=branch.settlement_category,
                activity_type=branch.activity_type,
                version=1,
                warehouse=warehouse,
            )
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="branch.created",
                entity="branches",
                entity_id=branch.id,
                after=asdict(result),
                ip=ip,
            )
            stage_response(asdict(result), 201)
        return result

    async def get(self, actor: Principal, allowed: tuple[UUID, ...], branch_id: UUID) -> BranchDetail:
        today = self._today()
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            row = await self._branches.get_branch(s, actor.tenant_id, branch_id, today)
            if row is None or row.archived_at is not None:
                raise not_found("branches")
            check_branch_scope(allowed, branch_id)
            sales = await self._branches.today_sales(s, branch_id, today)
            stock = await self._branches.stock_value(s, branch_id)
        return BranchDetail(
            id=row.id,
            name=row.name,
            address=row.address,
            is_default=row.is_default,
            settlement_category=row.settlement_category,
            activity_type=row.activity_type,
            version=row.version,
            today_sales=money_str(sales),
            stock_value=money_str(stock),
        )

    async def update(
        self, actor: Principal, allowed: tuple[UUID, ...], branch_id: UUID, patch: BranchPatch, ip: str | None
    ) -> BranchUpdated:
        today = self._today()
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            row = await self._live_branch(s, actor.tenant_id, allowed, branch_id, today)
            check_version(row.version, patch.version)
            fields: dict[str, Any] = {}
            if patch.name is not None and patch.name != row.name:
                fields["name"] = patch.name
            if patch.address_set and patch.address != row.address:
                fields["address"] = patch.address
            category = patch.settlement_category or row.settlement_category
            activity = patch.activity_type or row.activity_type
            if (category, activity) != (row.settlement_category, row.activity_type):
                # 20 #33: upsert by (branch_id, valid_from = 1st of the current month); last change wins
                await self._write_tax_setting(
                    s, actor, row, TaxSetting(month_start(today), category, activity), ip
                )
                fields["settlement_category"] = category
                fields["activity_type"] = activity
            version = row.version
            if fields:
                version = await self._branches.update_branch(s, branch_id, fields)
                await record_audit(
                    s,
                    tenant_id=actor.tenant_id,
                    user_id=actor.user_id,
                    action="branch.updated",
                    entity="branches",
                    entity_id=branch_id,
                    before={k: getattr(row, k) for k in fields},
                    after=fields,
                    ip=ip,
                )
            result = BranchUpdated(
                id=branch_id,
                name=fields.get("name", row.name),
                address=fields.get("address", row.address),
                settlement_category=category,
                activity_type=activity,
                version=version,
            )
            stage_response(asdict(result))
        return result

    # --- tax settings (branch_tax_settings) -----------------------------------------------------

    async def tax_settings(
        self, actor: Principal, allowed: tuple[UUID, ...], branch_id: UUID, page: int, size: int
    ) -> TaxSettingPage:
        today = self._today()
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            row = await self._branches.get_branch(s, actor.tenant_id, branch_id, today)
            if row is None:
                raise not_found("branches")
            check_branch_scope(allowed, branch_id)
            items, total = await self._branches.tax_history_page(
                s, branch_id, offset=(page - 1) * size, limit=size
            )
        return TaxSettingPage(
            [TaxSettingItem(i.valid_from, i.settlement_category, i.activity_type) for i in items],
            total,
            page,
            size,
        )

    async def add_tax_setting(
        self,
        actor: Principal,
        allowed: tuple[UUID, ...],
        branch_id: UUID,
        setting: TaxSetting,
        ip: str | None,
    ) -> TaxSettingCreated:
        today = self._today()
        if setting.valid_from < month_start(today):
            # 20 #35: a past month cannot be written (earlier periods are never recalculated)
            raise invalid("valid_from", "validation.past_period")
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            row = await self._live_branch(s, actor.tenant_id, allowed, branch_id, today)
            await self._write_tax_setting(s, actor, row, setting, ip)
            history = await self._branches.tax_history(s, branch_id)
            now_in_force = setting_in_force(history, today)
            if now_in_force is not None and (
                now_in_force.settlement_category,
                now_in_force.activity_type,
            ) != (row.settlement_category, row.activity_type):
                await self._branches.update_branch(
                    s,
                    branch_id,
                    {
                        "settlement_category": now_in_force.settlement_category,
                        "activity_type": now_in_force.activity_type,
                    },
                )
            result = TaxSettingCreated(
                branch_id, setting.valid_from, setting.settlement_category, setting.activity_type
            )
            stage_response(asdict(result), 201)
        return result

    async def turnover_rate(self, actor: Principal, branch_id: UUID, on: date) -> TurnoverRate:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            return await turnover_rate_on(self._branches, s, actor.tenant_id, branch_id, on)

    # --- warehouses -----------------------------------------------------------------------------

    async def list_warehouses(
        self, actor: Principal, allowed: tuple[UUID, ...], branch_id: UUID | None
    ) -> list[WarehouseView]:
        branch_ids = scoped_branch_ids(allowed, branch_id)
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            rows = await self._warehouses.list_warehouses(s, actor.tenant_id, branch_ids)
        return [_warehouse_view(r) for r in rows]

    async def update_warehouse(
        self,
        actor: Principal,
        allowed: tuple[UUID, ...],
        warehouse_id: UUID,
        version: int,
        name: str | None,
        inventory_account: str | None,
        ip: str | None,
    ) -> WarehouseUpdated:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            row = await self._warehouses.get_warehouse(s, actor.tenant_id, warehouse_id, for_update=True)
            if row is None:
                raise not_found("warehouses")
            check_branch_scope(allowed, row.branch_id)
            if row.archived_at is not None:
                raise archived("warehouses")
            check_version(row.version, version)
            fields: dict[str, Any] = {}
            if name is not None and name != row.name:
                fields["name"] = name
            if inventory_account is not None and inventory_account != row.inventory_account:
                if await self._warehouses.has_stock_moves(s, warehouse_id):
                    raise AppError(
                        ErrorCode.WAREHOUSE_ACCOUNT_LOCKED, params={"warehouse_id": str(warehouse_id)}
                    )
                fields["inventory_account"] = inventory_account
            new_version = row.version
            if fields:
                new_version = await self._warehouses.update_warehouse(s, warehouse_id, fields)
                await record_audit(
                    s,
                    tenant_id=actor.tenant_id,
                    user_id=actor.user_id,
                    action="warehouse.updated",
                    entity="warehouses",
                    entity_id=warehouse_id,
                    before={k: getattr(row, k) for k in fields},
                    after=fields,
                    ip=ip,
                )
            result = WarehouseUpdated(
                id=warehouse_id,
                name=fields.get("name", row.name),
                type=row.type,
                inventory_account=fields.get("inventory_account", row.inventory_account),
                version=new_version,
            )
            stage_response(asdict(result))
        return result

    # --- internals ------------------------------------------------------------------------------

    async def _live_branch(
        self, s: AsyncSession, tenant_id: UUID, allowed: tuple[UUID, ...], branch_id: UUID, today: date
    ) -> BranchRow:
        row = await self._branches.get_branch(s, tenant_id, branch_id, today, for_update=True)
        if row is None:
            raise not_found("branches")
        check_branch_scope(allowed, branch_id)
        if row.archived_at is not None:
            raise archived("branches")
        return row

    async def _write_tax_setting(
        self, s: AsyncSession, actor: Principal, row: BranchRow, setting: TaxSetting, ip: str | None
    ) -> None:
        history = await self._branches.tax_history(s, row.id)
        created_month = month_start(tashkent_today(row.created_at))
        if not history and created_month < setting.valid_from:
            # a branch without history (signup's default branch): keep the old category for earlier months
            await self._branches.upsert_tax_setting(
                s,
                actor.tenant_id,
                row.id,
                TaxSetting(created_month, row.settlement_category, row.activity_type),
                actor.user_id,
            )
        before = setting_in_force(history, setting.valid_from - timedelta(days=1)) or TaxSetting(
            created_month, row.settlement_category, row.activity_type
        )
        await self._branches.upsert_tax_setting(s, actor.tenant_id, row.id, setting, actor.user_id)
        await record_audit(
            s,
            tenant_id=actor.tenant_id,
            user_id=actor.user_id,
            action="branch_tax_category_changed",
            entity="branches",
            entity_id=row.id,
            before={"settlement_category": before.settlement_category, "activity_type": before.activity_type},
            after={
                "valid_from": setting.valid_from.isoformat(),
                "settlement_category": setting.settlement_category,
                "activity_type": setting.activity_type,
            },
            ip=ip,
        )
