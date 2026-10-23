"""Back-office ``/api/v1/onec-agents/*`` — Do'kon agentlari (33 §10.3 W-01…W-05, W-07, W-08; BO-14).

BFF cookie / Bearer user token, ``require_subscription_ok``, permissions ``onec.view`` /
``onec.settings.manage`` (15 §2.1), ``Idempotency-Key`` on every write (``stage_response`` inside the
route's transaction). W-06 (discover 1C bases) is Bosqich 7. OpenAPI tag ``onec``.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse, Response
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field
from redis.exceptions import RedisError

from app.core.auth.dependencies import TenantSession, require_subscription_ok
from app.core.auth.principal import Principal
from app.core.error_codes import ErrorCode
from app.core.errors import AppError, ErrorDetail
from app.core.idempotency import stage_response
from app.core.permissions import PermissionGrant, require_permission
from app.core.ratelimit import hit
from app.modules.onec_integration.api.deps import onec_agents
from app.modules.onec_integration.application.cursor import decode_cursor, encode_cursor

router = APIRouter(prefix="/onec-agents", tags=["onec"])

View = Annotated[PermissionGrant, Depends(require_permission("onec.view"))]
Manage = Annotated[PermissionGrant, Depends(require_permission("onec.settings.manage"))]
Caller = Annotated[Principal, Depends(require_subscription_ok)]

LEVELS = frozenset({"debug", "info", "warn", "error"})
PAIRING_LOOKUPS_PER_MINUTE = 10  # 14 §12: W-03 per user


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


class PairIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_code: str = Field(min_length=8, max_length=32)
    name: str | None = Field(default=None, min_length=1, max_length=100)


class RevokeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Literal["user", "key_compromised", "replaced"]
    note: str | None = Field(default=None, max_length=500)


class DiagnosticsRequestIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    include_logs_days: int = Field(default=3, ge=1, le=7)


@router.get("", operation_id="onec_list_agents")
async def list_agents(
    request: Request,
    s: TenantSession,
    _: View,
    status: Literal["active", "revoked"] | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    """W-01: the tenant's store agents (BO-14 «Do'kon agentlari»)."""
    return await onec_agents(request).agents.list_agents(s, status, page, size)


@router.get("/pairing-requests/{user_code}", operation_id="onec_get_pairing_request")
async def pairing_request(
    request: Request, user_code: str, s: TenantSession, grant: Manage, caller: Caller
) -> dict[str, Any]:
    """W-03: which computer asks to be paired (PC name, IP, OS) — 10 lookups / user / minute."""
    del grant
    try:
        state = await hit(request.app.state.redis, f"onec:rl:pairing:{caller.user_id}", 60)
    except RedisError:
        state = None
    if state is not None and state.count > PAIRING_LOOKUPS_PER_MINUTE:
        raise AppError(ErrorCode.RATE_LIMITED, headers={"Retry-After": str(state.retry_after_s)})
    return await onec_agents(request).pairing.lookup(s, user_code, caller.tenant_id, caller.user_id)


@router.post("/pair", operation_id="onec_pair_agent", status_code=201)
async def pair(
    request: Request, body: PairIn, s: TenantSession, grant: Manage, caller: Caller
) -> JSONResponse:
    """W-04: approve the device grant — ``onec_agents`` + ``devices(kind='onec_agent')``."""
    del grant
    agent = await onec_agents(request).pairing.pair(
        s, body.user_code, body.name, tenant_id=caller.tenant_id, user_id=caller.user_id, ip=_ip(request)
    )
    stage_response(agent, 201)
    return JSONResponse(agent, status_code=201)


@router.post("/pairing-requests/{user_code}/deny", operation_id="onec_deny_pairing_request", status_code=204)
async def deny(request: Request, user_code: str, s: TenantSession, grant: Manage, caller: Caller) -> Response:
    """W-04 «Rad etish»: the agent's token poll gets ``access_denied``."""
    del grant
    await onec_agents(request).pairing.deny(s, user_code, user_id=caller.user_id)
    stage_response(None, 204)
    return Response(status_code=204)


@router.get("/{agent_id}", operation_id="onec_get_agent")
async def get_agent(request: Request, agent_id: UUID, s: TenantSession, _: View) -> dict[str, Any]:
    """W-02: agent details (+ its 1C bases — Bosqich 7, always ``[]`` here)."""
    return await onec_agents(request).agents.get_agent_json(s, agent_id)


@router.post("/{agent_id}/revoke", operation_id="onec_revoke_agent")
async def revoke(
    request: Request, agent_id: UUID, body: RevokeIn, s: TenantSession, grant: Manage, caller: Caller
) -> dict[str, Any]:
    """W-05: disconnect the computer (idempotent); its token stops working at once (status cache)."""
    del grant
    agent = await onec_agents(request).agents.revoke(
        s,
        caller.tenant_id,
        agent_id,
        reason=body.reason,
        note=body.note,
        user_id=caller.user_id,
        ip=_ip(request),
    )
    stage_response(agent, 200)
    return agent


@router.post(
    "/{agent_id}/diagnostics-requests", operation_id="onec_request_agent_diagnostics", status_code=202
)
async def request_diagnostics(
    request: Request,
    agent_id: UUID,
    body: DiagnosticsRequestIn,
    s: TenantSession,
    grant: Manage,
    caller: Caller,
) -> JSONResponse:
    """W-07: a ``collect_diagnostics`` task; ``warnings: [ONEC_AGENT_OFFLINE]`` when the agent is silent."""
    del grant
    result = await onec_agents(request).agents.request_diagnostics(
        s, caller.tenant_id, agent_id, include_logs_days=body.include_logs_days, user_id=caller.user_id,
        ip=_ip(request),
    )  # fmt: skip
    stage_response(result, 202)
    return JSONResponse(result, status_code=202)


@router.get("/{agent_id}/logs", operation_id="onec_list_agent_logs")
async def agent_logs(
    request: Request,
    agent_id: UUID,
    s: TenantSession,
    _: View,
    level__in: Annotated[str | None, Query(max_length=40)] = None,
    base_id: UUID | None = None,
    at__gte: AwareDatetime | None = None,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    """W-08: agent logs ∪ server events (``diagnostics_ready``), newest first, cursor pagination."""
    levels = frozenset(v.strip() for v in level__in.split(",") if v.strip()) if level__in else None
    if levels is not None and not levels <= LEVELS:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            details=[ErrorDetail(field="level__in", message_key="validation.invalid_choice")],
        )
    if base_id is not None:  # 1C bases are Bosqich 7: every B5 row has base_id = NULL
        return {"items": [], "next_cursor": None}
    items, after = await onec_agents(request).agents.list_logs(
        s, agent_id, levels=levels, at_gte=at__gte, cursor=decode_cursor(cursor), limit=limit
    )
    return {"items": items, "next_cursor": encode_cursor(*after) if after else None}
