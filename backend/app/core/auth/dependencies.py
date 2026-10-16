"""Resource Server dependencies (23 §3 order: CSRF → auth → subscription → branch → permission → tx).

The implementation of :class:`AuthGateway` lives in ``app/modules/auth`` and
is published on ``app.state.auth`` by the composition root.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

import structlog
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.ports import AuthGateway
from app.core.auth.principal import Principal
from app.core.db.session import Database, tenant_transaction
from app.core.error_codes import ErrorCode
from app.core.errors import AppError

# 14 §16.4: a sync.drain token opens only POST /sync/push (Bosqich 3); everything else is 403
SCOPE_SYNC_DRAIN = "sync.drain"
LOCKED_SUBSCRIPTION_STATES = frozenset({"restricted", "closed"})


def auth_gateway(request: Request) -> AuthGateway:
    gateway: AuthGateway | None = getattr(request.app.state, "auth", None)
    if gateway is None:
        raise RuntimeError("auth gateway is not configured (app.state.auth)")
    return gateway


async def authenticate(request: Request, *, allow_sync_drain: bool = False) -> Principal:
    cached: Principal | None = getattr(request.state, "principal", None)
    principal = cached or await auth_gateway(request).authenticate(request)
    if cached is None:
        request.state.principal = principal
        structlog.contextvars.bind_contextvars(
            tenant_id=str(principal.tenant_id), user_id=str(principal.user_id)
        )
    if principal.has_scope(SCOPE_SYNC_DRAIN) and not allow_sync_drain:
        raise AppError(ErrorCode.PERMISSION_DENIED, params={"reason": "sync_drain_only"})
    return principal


async def current_principal(request: Request) -> Principal:
    """Authenticated caller; does **not** check the subscription (``/auth/*`` style routes)."""
    return await authenticate(request)


async def require_subscription_ok(
    request: Request, principal: Annotated[Principal, Depends(current_principal)]
) -> Principal:
    """14 §16.1.1: ``restricted``/``closed`` tenant → ``403 SUBSCRIPTION_RESTRICTED``."""
    status = await auth_gateway(request).subscription_status(principal.tenant_id)
    if status in LOCKED_SUBSCRIPTION_STATES:
        raise AppError(
            ErrorCode.SUBSCRIPTION_RESTRICTED,
            params={"tenant_id": str(principal.tenant_id), "status": status},
        )
    return principal


async def tenant_session(
    request: Request, principal: Annotated[Principal, Depends(require_subscription_ok)]
) -> AsyncIterator[AsyncSession]:
    """One ``tenant_transaction`` for the request, tenant taken from the token — never the body.

    Use it through :data:`TenantSession`: the ``scope="function"`` commit happens
    before the response is sent, so a failed commit is never reported as success
    (and never stored by the idempotency journal).
    """
    db: Database = request.app.state.db
    async with (
        db.session_factory() as session,
        tenant_transaction(session, principal.tenant_id, user_id=principal.user_id),
    ):
        yield session


TenantSession = Annotated[AsyncSession, Depends(tenant_session, scope="function")]
