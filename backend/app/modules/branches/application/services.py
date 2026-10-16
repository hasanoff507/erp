"""Signup provisioning of the default branch / warehouse / cash register (15 §1.5, 12 §5.2).

Public entry points (fixed signatures): ``app.modules.branches.wiring.ensure_default_branch`` and
``ensure_default_cash_register``.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.base import uuid7
from app.modules.branches.application.ports import (
    BranchRepository,
    CashRegisterRepository,
    NewBranch,
    WarehouseRepository,
)
from app.modules.branches.domain.model import (
    DEFAULT_ACTIVITY_TYPE,
    DEFAULT_WAREHOUSE_NAME,
    DEFAULT_WAREHOUSE_TYPE,
    ActivityType,
    SettlementCategory,
    inventory_account_for,
)

DEFAULT_BRANCH_CODE = "01"


async def ensure_default_branch(
    branches: BranchRepository,
    warehouses: WarehouseRepository,
    session: AsyncSession,
    tenant_id: UUID,
    name: str,
    settlement_category: SettlementCategory,
    *,
    activity_type: ActivityType = DEFAULT_ACTIVITY_TYPE,
) -> UUID:
    """Default branch ``01`` with its store-room warehouse (2920), 12 §5.2; idempotent.

    ``activity_type`` — the signup ``business_type`` (14 §20 ``/auth/signup``).
    """
    existing = await branches.default_branch_id(session, tenant_id)
    if existing is not None:
        return existing
    branch = NewBranch(
        id=uuid7(),
        code=DEFAULT_BRANCH_CODE,
        name=name,
        address=None,
        settlement_category=settlement_category,
        activity_type=activity_type,
    )
    await branches.insert_branch(session, tenant_id, branch, is_default=True)
    await warehouses.insert_warehouse(
        session,
        tenant_id,
        branch.id,
        uuid7(),
        DEFAULT_WAREHOUSE_NAME,
        DEFAULT_WAREHOUSE_TYPE,
        inventory_account_for(DEFAULT_WAREHOUSE_TYPE),
    )
    return branch.id


async def ensure_default_cash_register(
    registers: CashRegisterRepository,
    session: AsyncSession,
    tenant_id: UUID,
    branch_id: UUID,
    name: str = "Kassa 1",
) -> UUID:
    """The plan's included web cash register of the default branch (15 §1.5); idempotent."""
    existing = await registers.first_cash_register_id(session, tenant_id, branch_id)
    if existing is not None:
        return existing
    register_id = uuid7()
    await registers.insert_cash_register(session, tenant_id, register_id, branch_id, name, "web")
    return register_id
