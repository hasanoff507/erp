"""Composition and public entry points of the branches module (23 §1 ``wiring.py``).

Other modules (signup provisioning, seed, the future turnover-tax settlement) import **only**
from here — never from ``branches.infrastructure``. Signatures are a cross-module contract.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db.session import Database
from app.modules.auth.application.gateway import mark_device_revoked
from app.modules.branches.application import branches as branch_services
from app.modules.branches.application import services
from app.modules.branches.application.branches import BranchesService
from app.modules.branches.application.cash_registers import CashRegistersService
from app.modules.branches.application.devices import DevicesService
from app.modules.branches.application.tenant_settings import TenantSettingsService
from app.modules.branches.domain.model import DEFAULT_ACTIVITY_TYPE, ActivityType, SettlementCategory
from app.modules.branches.domain.tax import TurnoverRate
from app.modules.branches.infrastructure.devices import SqlDeviceRepository
from app.modules.branches.infrastructure.repositories import (
    SqlBranchRepository,
    SqlCashRegisterRepository,
    SqlWarehouseRepository,
)
from app.modules.branches.infrastructure.tenant import SqlTenantSettingsRepository
from app.modules.integrations.fiscal.wiring import request_fiscal_status

__all__ = [
    "ActivityType",
    "BranchesModule",
    "SettlementCategory",
    "TurnoverRate",
    "build_branches_module",
    "ensure_default_branch",
    "ensure_default_cash_register",
    "turnover_rate_on",
]


@dataclass(frozen=True, slots=True)
class BranchesModule:
    branches: BranchesService
    cash_registers: CashRegistersService
    devices: DevicesService
    tenant_settings: TenantSettingsService


async def _integration_status(s: AsyncSession) -> Mapping[str, Any]:
    """20 #40a BO-14 integrations: the tenant_keys read model (lazy: tenant_keys → auth → branches)."""
    from app.modules.integrations.tenant_keys.wiring import integration_status

    return await integration_status(s)


def build_branches_module(db: Database, redis: Callable[[], Redis]) -> BranchesModule:
    sf = db.session_factory
    branch_repo = SqlBranchRepository()

    async def device_revoked(device_id: UUID, sids: Sequence[UUID], families: Sequence[UUID]) -> None:
        # the auth RS refuses the device's tokens at once (else DB fallback within session_check_cache_s);
        # the device's sessions/families were revoked in the DB in the same transaction — their live
        # access tokens die now through the sid/fam markers (SEC-09)
        await mark_device_revoked(redis(), device_id, sids=sids, families=families)

    return BranchesModule(
        branches=BranchesService(sf, branch_repo, SqlWarehouseRepository()),
        cash_registers=CashRegistersService(
            sf, SqlCashRegisterRepository(), branch_repo, on_fiscal_bound=request_fiscal_status
        ),
        devices=DevicesService(
            sf,
            SqlDeviceRepository(),
            device_revoked,
            pin_lookback_days=get_settings().pin_revoke_lookback_days,
        ),
        tenant_settings=TenantSettingsService(sf, SqlTenantSettingsRepository(), _integration_status),
    )


async def ensure_default_branch(
    session: AsyncSession,
    tenant_id: UUID,
    name: str,
    settlement_category: SettlementCategory,
    *,
    activity_type: ActivityType = DEFAULT_ACTIVITY_TYPE,
) -> UUID:
    """Default branch ``01`` + store-room warehouse (2920), 12 §5.2; idempotent, caller's transaction."""
    return await services.ensure_default_branch(
        SqlBranchRepository(),
        SqlWarehouseRepository(),
        session,
        tenant_id,
        name,
        settlement_category,
        activity_type=activity_type,
    )


async def ensure_default_cash_register(
    session: AsyncSession, tenant_id: UUID, branch_id: UUID, name: str = "Kassa 1"
) -> UUID:
    """The plan's included web cash register of the default branch (15 §1.5); idempotent."""
    return await services.ensure_default_cash_register(
        SqlCashRegisterRepository(), session, tenant_id, branch_id, name
    )


async def turnover_rate_on(session: AsyncSession, tenant_id: UUID, branch_id: UUID, on: date) -> TurnoverRate:
    """Settlement category and turnover-tax rate of a branch in force on ``on`` (13 §4.3)."""
    return await branch_services.turnover_rate_on(SqlBranchRepository(), session, tenant_id, branch_id, on)
