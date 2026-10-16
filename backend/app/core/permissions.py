"""``require_permission`` and branch scope (15 §2, 23 §3 steps 5–6, 14 §10).

1. The token ``scope`` (permission prefixes) is the fast first filter — no DB.
2. The final decision is the live ``role_permissions`` row of an *active*
   membership (so a blocked user or a revoked role is denied immediately,
   even with a still-valid access token). Several roles → the most generous
   ``limit_value`` wins (``None`` = unlimited).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request

from app.core.auth.dependencies import auth_gateway, require_subscription_ok
from app.core.auth.principal import Principal
from app.core.error_codes import ErrorCode
from app.core.errors import AppError

BRANCH_HEADER = "x-branch-id"


@dataclass(frozen=True, slots=True)
class PermissionGrant:
    code: str
    limit_value: Decimal | None  # None = unlimited

    def allows(self, amount: Decimal) -> bool:
        return self.limit_value is None or amount <= self.limit_value


def _most_generous(limits: list[Decimal | None]) -> Decimal | None:
    if any(limit is None for limit in limits):
        return None
    return max(limit for limit in limits if limit is not None)


def require_permission(code: str) -> Callable[..., Awaitable[PermissionGrant]]:
    prefix = code.split(".", 1)[0]

    async def dependency(
        request: Request, principal: Annotated[Principal, Depends(require_subscription_ok)]
    ) -> PermissionGrant:
        if not principal.has_scope(prefix):
            raise AppError(ErrorCode.PERMISSION_DENIED, params={"permission": code})
        limits = await auth_gateway(request).permission_limits(principal, code)
        if not limits:
            raise AppError(ErrorCode.PERMISSION_DENIED, params={"permission": code})
        return PermissionGrant(code, _most_generous(limits))

    dependency.__name__ = f"require_permission_{code.replace('.', '_')}"
    return dependency


@dataclass(frozen=True, slots=True)
class BranchScope:
    """``allowed`` empty = every branch (15 §2.4); ``current`` = validated ``X-Branch-Id``."""

    allowed: tuple[UUID, ...]
    current: UUID | None

    @property
    def unrestricted(self) -> bool:
        return not self.allowed


async def current_branch_scope(
    request: Request, principal: Annotated[Principal, Depends(require_subscription_ok)]
) -> BranchScope:
    allowed = await auth_gateway(request).branch_ids(principal)
    if allowed is None:
        raise AppError(ErrorCode.PERMISSION_DENIED, params={"reason": "membership_inactive"})
    raw = request.headers.get(BRANCH_HEADER)
    current: UUID | None = None
    if raw:
        try:
            current = UUID(raw)
        except ValueError:
            raise AppError(ErrorCode.BRANCH_SCOPE_DENIED) from None
        if allowed and current not in allowed:
            raise AppError(ErrorCode.BRANCH_SCOPE_DENIED)
    return BranchScope(allowed, current)
