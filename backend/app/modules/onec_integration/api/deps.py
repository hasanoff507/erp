"""Dependencies of the agent channel (23 §3 "1C agent API", 33 §9.1–§9.2):

* :func:`current_agent` — Bearer token (``aud=urn:erp:onec-agent``, scope ``onec.agent``) →
  tenant/agent/device from the claims only; agent ``status`` from Redis (60 s), ``revoked`` →
  ``403 ONEC_AGENT_REVOKED``;
* :func:`require_agent_protocol` — ``X-Agent-Protocol: 2`` and ``X-Agent-Version ≥ min_agent_version``
  (``426 ONEC_AGENT_UPDATE_REQUIRED``; only A-01/A-03 — a lease in flight finishes, A-09 stays reachable);
* :func:`require_agent_subscription` — ``restricted``/``closed`` tenant → ``403 SUBSCRIPTION_RESTRICTED``
  (A-01/A-03 only, 33 §9.1 obuna lokauti);
* :func:`require_agent_capability` — the agent declared ``capabilities.<family>.enabled`` (23 §3);
* :func:`agent_session` — one ``tenant_transaction`` of the agent's tenant (no user).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Annotated, Final
from uuid import UUID

import structlog
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import LOCKED_SUBSCRIPTION_STATES, auth_gateway
from app.core.db.session import Database, tenant_transaction
from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from app.modules.auth.application.keys import InvalidAccessTokenError
from app.modules.auth.domain.constants import AUD_ONEC_AGENT
from app.modules.auth.domain.scopes import scope_to_set
from app.modules.auth.wiring import AuthModule
from app.modules.onec_integration.domain.capabilities import capability_enabled
from app.modules.onec_integration.domain.kinds import family_of
from app.modules.onec_integration.domain.versions import SUPPORTED_PROTOCOLS, version_lt
from app.modules.onec_integration.wiring import AgentPrincipal, OneCAgentsModule

AGENT_SCOPE: Final = "onec.agent"
CLIENT_PREFIX: Final = "onec-agent:"
_CHALLENGE: Final = {"WWW-Authenticate": 'Bearer error="invalid_token"'}


def onec_agents(request: Request) -> OneCAgentsModule:
    module: OneCAgentsModule | None = getattr(request.app.state, "onec_agents", None)
    if module is None:
        raise RuntimeError("store-agent module is not configured (app.state.onec_agents)")
    return module


def _auth(request: Request) -> AuthModule:
    module: AuthModule | None = getattr(request.app.state, "auth_module", None)
    if module is None:
        raise RuntimeError("auth module is not wired (app.state.auth_module)")
    return module


def _unauthorized(reason: str) -> AppError:
    return AppError(ErrorCode.UNAUTHORIZED, params={"reason": reason}, headers=_CHALLENGE)


async def current_agent(request: Request) -> AgentPrincipal:
    cached: AgentPrincipal | None = getattr(request.state, "agent_principal", None)
    if cached is not None:
        return cached
    header = request.headers.get("authorization") or ""
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise _unauthorized("missing_token")
    try:
        claims = await _auth(request).codec.verify(token.strip(), audience=AUD_ONEC_AGENT)
    except InvalidAccessTokenError as exc:
        raise _unauthorized(exc.reason) from exc
    client_id = str(claims.get("client_id") or "")
    try:
        tenant_id = UUID(str(claims["tenant_id"]))
        agent_id = UUID(str(claims.get("agent_id")))
        device_id = UUID(str(claims["device_id"])) if claims.get("device_id") else None
    except (KeyError, ValueError) as exc:
        raise _unauthorized("claims") from exc
    if AGENT_SCOPE not in scope_to_set(str(claims.get("scope"))) or client_id != f"{CLIENT_PREFIX}{agent_id}":
        raise _unauthorized("claims")
    status = await onec_agents(request).agents.agent_status(tenant_id, agent_id)
    if status is None:
        raise _unauthorized("unknown_agent")
    if status != "active":
        raise AppError(ErrorCode.ONEC_AGENT_REVOKED, params={"agent_id": str(agent_id)})
    principal = AgentPrincipal(
        tenant_id=tenant_id,
        agent_id=agent_id,
        device_id=device_id,
        client_id=client_id,
        agent_version=(request.headers.get("x-agent-version") or "").strip()[:32] or None,
        ip=request.client.host if request.client else None,
    )
    request.state.agent_principal = principal
    structlog.contextvars.bind_contextvars(tenant_id=str(tenant_id), agent_id=str(agent_id))
    return principal


Agent = Annotated[AgentPrincipal, Depends(current_agent)]


async def require_agent_protocol(request: Request, agent: Agent) -> AgentPrincipal:
    raw = (request.headers.get("x-agent-protocol") or "").strip()
    minimum = onec_agents(request).agents.min_agent_version
    if not raw.isdigit() or int(raw) not in SUPPORTED_PROTOCOLS or version_lt(agent.agent_version, minimum):
        raise AppError(
            ErrorCode.ONEC_AGENT_UPDATE_REQUIRED,
            params={"min_agent_version": minimum, "protocol": sorted(SUPPORTED_PROTOCOLS)},
        )
    return agent


async def require_agent_subscription(request: Request, agent: Agent) -> str:
    status = await auth_gateway(request).subscription_status(agent.tenant_id)
    if status in LOCKED_SUBSCRIPTION_STATES:
        raise AppError(
            ErrorCode.SUBSCRIPTION_RESTRICTED, params={"tenant_id": str(agent.tenant_id), "status": status}
        )
    return status


def require_agent_capability(kind: str) -> Callable[..., Awaitable[AgentPrincipal]]:
    """The agent declared the family of ``kind`` in its last ``hello`` (23 §3); else
    ``409 AGENT_CAPABILITY_DISABLED``."""
    family = family_of(kind)
    if family is None:
        raise ValueError(f"{kind!r} is not a device-service kind")

    async def dependency(request: Request, agent: Agent) -> AgentPrincipal:
        db: Database = request.app.state.db
        async with db.session_factory() as s, tenant_transaction(s, agent.tenant_id):
            view = await onec_agents(request).directory.get_agent(s, agent.tenant_id, agent.agent_id)
        if view is None or not capability_enabled(view.capabilities, family):
            raise AppError(
                ErrorCode.AGENT_CAPABILITY_DISABLED,
                params={"agent_id": str(agent.agent_id), "kind": kind, "family": family},
            )
        return agent

    dependency.__name__ = f"require_agent_capability_{family}_{uuid.uuid4().hex[:6]}"
    return dependency


async def agent_session(agent: Agent, request: Request) -> AsyncIterator[AsyncSession]:
    db: Database = request.app.state.db
    async with db.session_factory() as session, tenant_transaction(session, agent.tenant_id):
        yield session


AgentSession = Annotated[AsyncSession, Depends(agent_session, scope="function")]
