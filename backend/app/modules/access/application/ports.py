"""Ports of the access module (23 §1): the application layer depends on these, infrastructure implements them.

Every method runs inside the caller's ``tenant_transaction`` (the session is passed in).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True, slots=True)
class RoleRow:
    id: UUID
    name: str
    is_system: bool
    system_code: str | None
    version: int
    archived_at: datetime | None


class RoleRepository(Protocol):
    async def upsert_system_role(
        self, session: AsyncSession, tenant_id: UUID, system_code: str, name: str
    ) -> UUID: ...

    async def grant_permissions(
        self, session: AsyncSession, tenant_id: UUID, role_id: UUID, permissions: dict[str, Decimal | None]
    ) -> None:
        """Insert missing rows only (provisioning; existing rows are kept)."""
        ...

    async def list_roles(
        self, session: AsyncSession, tenant_id: UUID, *, offset: int, limit: int
    ) -> tuple[list[RoleRow], int]: ...

    async def get_role(
        self, session: AsyncSession, tenant_id: UUID, role_id: UUID, *, for_update: bool = False
    ) -> RoleRow | None: ...

    async def name_taken(
        self, session: AsyncSession, tenant_id: UUID, name: str, *, exclude_id: UUID | None = None
    ) -> bool: ...

    async def insert_role(self, session: AsyncSession, tenant_id: UUID, role_id: UUID, name: str) -> None: ...

    async def rename_role(self, session: AsyncSession, role_id: UUID, name: str) -> int:
        """New ``version``."""
        ...

    async def bump_version(self, session: AsyncSession, role_id: UUID) -> int: ...

    async def role_permissions(self, session: AsyncSession, role_id: UUID) -> dict[str, Decimal | None]: ...

    async def replace_permissions(
        self, session: AsyncSession, tenant_id: UUID, role_id: UUID, permissions: dict[str, Decimal | None]
    ) -> None:
        """Make ``role_permissions`` of the role exactly ``permissions``."""
        ...
