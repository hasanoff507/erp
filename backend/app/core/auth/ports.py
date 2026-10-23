"""What the core RS dependencies need from the auth module (23 §1: implemented in ``modules/auth``)."""

from __future__ import annotations

from decimal import Decimal
from typing import Protocol
from uuid import UUID

from starlette.requests import Request

from app.core.auth.principal import Principal


class AuthGateway(Protocol):
    async def authenticate(self, request: Request) -> Principal:
        """Bearer JWT or BFF cookie → verified principal; raises ``AppError`` (401/403)."""
        ...

    async def peek_tenant(self, request: Request) -> UUID | None:
        """Cheap, side-effect free tenant lookup for the idempotency middleware."""
        ...

    async def subscription_status(self, tenant_id: UUID) -> str: ...

    async def permission_limits(self, principal: Principal, code: str) -> list[Decimal | None]:
        """``limit_value`` of every active role granting ``code``; empty = not granted."""
        ...

    async def branch_ids(self, principal: Principal) -> tuple[UUID, ...] | None:
        """Current ``memberships.branch_ids`` (empty = all branches); ``None`` = no active membership."""
        ...
