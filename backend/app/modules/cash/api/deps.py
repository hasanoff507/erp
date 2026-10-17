"""Shared API dependencies of the cash slice."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, Request

from app.core.auth.dependencies import auth_gateway, require_subscription_ok
from app.core.auth.principal import Principal
from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from app.modules.cash.application.module import CashModule


def require_any(*codes: str) -> Callable[..., Awaitable[str]]:
    """``code₁`` **or** ``code₂`` … (e.g. ``reports.sales.view`` or ``cash.count.shift``, 18 §3.3)."""

    async def dependency(
        request: Request, principal: Annotated[Principal, Depends(require_subscription_ok)]
    ) -> str:
        for code in codes:
            if principal.has_scope(code.split(".", 1)[0]) and await auth_gateway(request).permission_limits(
                principal, code
            ):
                return code
        raise AppError(ErrorCode.PERMISSION_DENIED, params={"permission": " | ".join(codes)})

    dependency.__name__ = "require_any_" + "_or_".join(c.replace(".", "_") for c in codes)
    return dependency


def cash_module(request: Request) -> CashModule:
    module: CashModule | None = getattr(request.app.state, "cash", None)
    if module is None:
        raise RuntimeError("cash module is not configured (app.state.cash)")
    return module


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None
