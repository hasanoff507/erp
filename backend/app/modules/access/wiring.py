"""Composition and public entry points of the access module (23 §1 ``wiring.py``).

Other modules (signup provisioning, seed) import **only** from here — never
from ``access.infrastructure``. Signatures are a cross-module contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.session import Database
from app.modules.access.application import provisioning
from app.modules.access.application.roles import RolesService
from app.modules.access.domain.permissions import SystemRole
from app.modules.access.infrastructure.repositories import SqlRoleRepository

__all__ = ["AccessModule", "build_access_module", "provision_system_roles"]


@dataclass(frozen=True, slots=True)
class AccessModule:
    roles: RolesService


def build_access_module(db: Database) -> AccessModule:
    return AccessModule(roles=RolesService(db.session_factory, SqlRoleRepository()))


async def provision_system_roles(session: AsyncSession, tenant_id: UUID) -> dict[SystemRole, UUID]:
    """Create the 5 system roles and their ``role_permissions`` in the caller's transaction; idempotent."""
    return await provisioning.provision_system_roles(SqlRoleRepository(), session, tenant_id)
