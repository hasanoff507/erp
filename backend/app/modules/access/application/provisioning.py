"""System roles and the default permission matrix for a new tenant (15 §1.5, 12 §5.2).

The rest of signup (tenant, subscription, owner membership, cash register,
valuation method) belongs to M17 signup (Bosqich 1); this is the part the
seed and signup share.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.access.domain.permissions import DEFAULT_MATRIX, SYSTEM_ROLE_NAMES, SystemRole
from app.modules.access.infrastructure import repositories


async def provision_system_roles(session: AsyncSession, tenant_id: UUID) -> dict[SystemRole, UUID]:
    """Create the 5 system roles and their ``role_permissions``; idempotent."""
    role_ids: dict[SystemRole, UUID] = {}
    for role in SystemRole:
        role_id = await repositories.upsert_system_role(
            session, tenant_id, role.value, SYSTEM_ROLE_NAMES[role]
        )
        await repositories.grant_permissions(session, tenant_id, role_id, DEFAULT_MATRIX[role])
        role_ids[role] = role_id
    return role_ids
