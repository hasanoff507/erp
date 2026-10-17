"""Ports of the branches module (23 §1): application depends on these, infrastructure implements them.

Every method runs inside the caller's ``tenant_transaction`` (the session is passed in).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.branches.domain.tax import RateRow, TaxSetting


@dataclass(frozen=True, slots=True)
class BranchRow:
    id: UUID
    code: str
    name: str
    address: str | None
    is_default: bool
    settlement_category: str  # in force on the requested day (branch_tax_settings, else the branch column)
    activity_type: str
    version: int
    archived_at: datetime | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class NewBranch:
    id: UUID
    code: str
    name: str
    address: str | None
    settlement_category: str
    activity_type: str


@dataclass(frozen=True, slots=True)
class WarehouseRow:
    id: UUID
    branch_id: UUID
    name: str
    type: str
    inventory_account: str
    version: int
    archived_at: datetime | None


@dataclass(frozen=True, slots=True)
class CashRegisterRow:
    id: UUID
    branch_id: UUID
    name: str
    kind: str
    fiscal_module_id: str | None
    txkm_contract_ref: str | None
    fiscal_agent_id: UUID | None
    fiscal_local_device_id: str | None
    ofd_status: str
    fm_state: str
    last_unacked_receipt_at: datetime | None
    fm_receipts_pending: int | None
    tax_registered_at: datetime | None
    archived_at: datetime | None
    version: int


@dataclass(frozen=True, slots=True)
class DeviceRow:
    id: UUID
    kind: str
    app_version: str | None
    cash_register_id: UUID | None
    cash_register_name: str | None
    branch_id: UUID | None
    last_seen_at: datetime | None
    last_sync_at: datetime | None
    outbox_pending_count: int | None
    outbox_oldest_pending_at: datetime | None
    revoked_at: datetime | None


@dataclass(frozen=True, slots=True)
class RegisterTarget:
    cash_register_id: UUID
    cash_register_name: str
    branch_id: UUID
    branch_name: str
    archived: bool


@dataclass(frozen=True, slots=True)
class DeviceFilter:
    allowed_branches: tuple[UUID, ...]  # empty = every branch (and devices without a cash register)
    branch_id: UUID | None
    kind: str | None
    include_revoked: bool


@dataclass(frozen=True, slots=True)
class TenantRow:
    name: str
    legal_form: str
    go_live_date: date | None
    accepted_terms_version: str | None
    accepted_terms_at: datetime | None
    settings: dict[str, Any]
    version: int


@dataclass(frozen=True, slots=True)
class IntegrationRow:
    kind: str
    cash_register_id: UUID | None
    connected_at: datetime


class BranchRepository(Protocol):
    async def default_branch_id(self, session: AsyncSession, tenant_id: UUID) -> UUID | None: ...

    async def lock_tenant(self, session: AsyncSession, tenant_id: UUID) -> None:
        """Serialize branch-code / cash-register-limit decisions of one tenant (row lock on ``tenants``)."""
        ...

    async def used_codes(self, session: AsyncSession, tenant_id: UUID) -> list[str]: ...

    async def insert_branch(
        self, session: AsyncSession, tenant_id: UUID, branch: NewBranch, *, is_default: bool
    ) -> None: ...

    async def list_branches(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        allowed: tuple[UUID, ...],
        on: date,
        *,
        offset: int,
        limit: int,
    ) -> tuple[list[BranchRow], int]: ...

    async def get_branch(
        self, session: AsyncSession, tenant_id: UUID, branch_id: UUID, on: date, *, for_update: bool = False
    ) -> BranchRow | None: ...

    async def update_branch(self, session: AsyncSession, branch_id: UUID, fields: dict[str, Any]) -> int:
        """Set the given columns, ``version + 1``; returns the new version."""
        ...

    async def tax_history(self, session: AsyncSession, branch_id: UUID) -> list[TaxSetting]: ...

    async def tax_history_page(
        self, session: AsyncSession, branch_id: UUID, *, offset: int, limit: int
    ) -> tuple[list[TaxSetting], int]: ...

    async def upsert_tax_setting(
        self, session: AsyncSession, tenant_id: UUID, branch_id: UUID, setting: TaxSetting, user_id: UUID
    ) -> None: ...

    async def today_sales(self, session: AsyncSession, branch_id: UUID, on: date) -> Decimal: ...

    async def stock_value(self, session: AsyncSession, branch_id: UUID) -> Decimal: ...

    async def legal_form(self, session: AsyncSession, tenant_id: UUID) -> str: ...

    async def turnover_rates(self, session: AsyncSession, code: str) -> list[RateRow]: ...


class WarehouseRepository(Protocol):
    async def insert_warehouse(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        branch_id: UUID,
        warehouse_id: UUID,
        name: str,
        warehouse_type: str,
        inventory_account: str,
    ) -> None: ...

    async def list_warehouses(
        self, session: AsyncSession, tenant_id: UUID, branch_ids: tuple[UUID, ...] | None
    ) -> list[WarehouseRow]:
        """``branch_ids`` None = every branch."""
        ...

    async def get_warehouse(
        self, session: AsyncSession, tenant_id: UUID, warehouse_id: UUID, *, for_update: bool = False
    ) -> WarehouseRow | None: ...

    async def has_stock_moves(self, session: AsyncSession, warehouse_id: UUID) -> bool: ...

    async def update_warehouse(
        self, session: AsyncSession, warehouse_id: UUID, fields: dict[str, Any]
    ) -> int: ...


class CashRegisterRepository(Protocol):
    async def first_cash_register_id(
        self, session: AsyncSession, tenant_id: UUID, branch_id: UUID
    ) -> UUID | None: ...

    async def insert_cash_register(
        self, session: AsyncSession, tenant_id: UUID, register_id: UUID, branch_id: UUID, name: str, kind: str
    ) -> None: ...

    async def list_cash_registers(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        branch_ids: tuple[UUID, ...] | None,
        *,
        include_archived: bool,
    ) -> list[CashRegisterRow]: ...

    async def get_cash_register(
        self, session: AsyncSession, tenant_id: UUID, register_id: UUID, *, for_update: bool = False
    ) -> CashRegisterRow | None: ...

    async def active_count(self, session: AsyncSession, tenant_id: UUID) -> int: ...

    async def allowance(self, session: AsyncSession, tenant_id: UUID) -> tuple[int, int]:
        """(plan ``included_cash_registers``, active ``extra_register`` add-on quantity)."""
        ...

    async def update_cash_register(
        self, session: AsyncSession, register_id: UUID, fields: dict[str, Any]
    ) -> int: ...

    async def archive_cash_register(self, session: AsyncSession, register_id: UUID) -> datetime: ...

    async def fiscal_agent_exists(self, session: AsyncSession, agent_id: UUID) -> bool: ...


class DeviceRepository(Protocol):
    async def list_devices(
        self, session: AsyncSession, tenant_id: UUID, flt: DeviceFilter, *, offset: int, limit: int
    ) -> tuple[list[DeviceRow], int]: ...

    async def get_device(
        self, session: AsyncSession, tenant_id: UUID, device_id: UUID, *, for_update: bool = False
    ) -> DeviceRow | None: ...

    async def revoke(self, session: AsyncSession, device_id: UUID, user_id: UUID) -> datetime: ...

    async def recent_device_users(
        self, session: AsyncSession, tenant_id: UUID, device_id: UUID, since: datetime
    ) -> list[UUID]:
        """Members of the tenant who worked on the device since ``since`` (shifts, PIN/login audit)."""
        ...

    async def force_pin_reset(self, session: AsyncSession, user_id: UUID) -> None: ...

    # --- B3 device-auth ---
    async def register_target(
        self, session: AsyncSession, tenant_id: UUID, cash_register_id: UUID
    ) -> RegisterTarget | None:
        """The cash register a web device is registered to, with its branch (locked ``FOR SHARE``)."""
        ...

    async def insert_device(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        device_id: UUID,
        cash_register_id: UUID,
        kind: str,
        app_version: str | None,
    ) -> None: ...

    async def set_app_version(self, session: AsyncSession, device_id: UUID, app_version: str) -> None: ...

    async def member_elsewhere(self, session: AsyncSession, user_id: UUID, tenant_id: UUID) -> bool:
        """An active membership in another tenant (``app.auth_member_elsewhere``) — the PIN is shared."""
        ...

    async def mark_tenant_pin_reset(self, session: AsyncSession, tenant_id: UUID, user_id: UUID) -> None:
        """``memberships.pin_reset_at = now()`` — tenant-local PIN reset (16 §9)."""
        ...

    async def revoke_device_tokens(
        self, session: AsyncSession, device_id: UUID, reason: str
    ) -> tuple[list[UUID], list[UUID]]:
        """``app.auth_revoke_device``: the device's sessions and refresh families (revoked now)."""
        ...


class TenantSettingsRepository(Protocol):
    async def get_tenant(
        self, session: AsyncSession, tenant_id: UUID, *, for_update: bool = False
    ) -> TenantRow | None: ...

    async def update_tenant(self, session: AsyncSession, tenant_id: UUID, fields: dict[str, Any]) -> int: ...

    async def tax_regimes(self, session: AsyncSession, tenant_id: UUID) -> list[tuple[date, str]]: ...

    async def upsert_tax_regime(
        self, session: AsyncSession, tenant_id: UUID, valid_from: date, regime: str, user_id: UUID
    ) -> None: ...

    async def integrations(self, session: AsyncSession, tenant_id: UUID) -> list[IntegrationRow]: ...

    async def ofd_connected(self, session: AsyncSession, tenant_id: UUID) -> bool: ...

    async def current_terms_version(self, session: AsyncSession, kind: str) -> str | None: ...

    async def insert_consent(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        user_id: UUID,
        purpose: str,
        terms_version: str,
        accepted: bool,
        ip: str | None,
    ) -> datetime: ...
