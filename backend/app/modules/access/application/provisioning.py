"""System roles and the default permission matrix for a new tenant (15 §1.5, 12 §5.2).

The rest of signup (tenant, subscription, owner membership, cash register,
valuation method) belongs to M17 signup; this is the part the seed and signup
share. Public entry point: :func:`app.modules.access.wiring.provision_system_roles`.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.access.application.ports import RoleRepository
from app.modules.access.domain.permissions import DEFAULT_MATRIX, SYSTEM_ROLE_NAMES, SystemRole


async def provision_system_roles(
    repo: RoleRepository, session: AsyncSession, tenant_id: UUID
) -> dict[SystemRole, UUID]:
    """Create the 5 system roles and their ``role_permissions``; idempotent."""
    role_ids: dict[SystemRole, UUID] = {}
    for role in SystemRole:
        role_id = await repo.upsert_system_role(session, tenant_id, role.value, SYSTEM_ROLE_NAMES[role])
        await repo.grant_permissions(session, tenant_id, role_id, DEFAULT_MATRIX[role])
        role_ids[role] = role_id
    return role_ids
