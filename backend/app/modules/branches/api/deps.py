"""Module-level dependencies of the branches API."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Annotated

from fastapi import Depends, Query, Request

from app.core.auth.dependencies import auth_gateway, require_subscription_ok
from app.core.auth.principal import Principal
from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from app.core.permissions import BranchScope, PermissionGrant, current_branch_scope, require_permission

if TYPE_CHECKING:
    from app.modules.branches.wiring import BranchesModule

Actor = Annotated[Principal, Depends(require_subscription_ok)]
Scope = Annotated[BranchScope, Depends(current_branch_scope)]
Page = Annotated[int, Query(ge=1)]
Size = Annotated[int, Query(ge=1, le=200)]


def branches_module(request: Request) -> BranchesModule:
    module: BranchesModule | None = getattr(request.app.state, "branches_module", None)
    if module is None:
        raise RuntimeError("branches module is not wired (app.state.branches_module)")
    return module


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


async def has_permission(request: Request, principal: Principal, code: str) -> bool:
    """Same decision as ``require_permission`` (token scope prefix + live ``role_permissions``), no raise."""
    if not principal.has_scope(code.split(".", 1)[0]):
        return False
    return bool(await auth_gateway(request).permission_limits(principal, code))


def require_owner_permission(code: str) -> Callable[..., Awaitable[PermissionGrant]]:
    """A "faqat Egasi" code (15 §2.1): any other role gets ``403 OWNER_ONLY`` (17 §10)."""
    inner = require_permission(code)

    async def dependency(request: Request, principal: Actor) -> PermissionGrant:
        try:
            return await inner(request, principal)
        except AppError as exc:
            if exc.code is ErrorCode.PERMISSION_DENIED:
                raise AppError(ErrorCode.OWNER_ONLY, params={"permission": code}) from None
            raise

    dependency.__name__ = f"require_owner_permission_{code.replace('.', '_')}"
    return dependency
