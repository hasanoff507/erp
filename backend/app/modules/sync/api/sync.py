"""``POST /sync/push`` and ``GET /sync/pull`` (16 §3, 18 §2/§17). Tag ``sync`` (17 §11).

No ``Idempotency-Key`` on push (dedupe = ``client_event_id``); cookie-authenticated calls need
``X-CSRF-Token`` (enforced by the auth gateway, 15 §1.3). A ``sync.drain`` token (14 §16.4) opens push
only — and skips the subscription gate, the drain rules apply per event.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from app.core.auth.dependencies import (
    SCOPE_SYNC_DRAIN,
    auth_gateway,
    authenticate,
    require_subscription_ok,
)
from app.core.auth.principal import Principal
from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from app.modules.sync.application.module import SyncModule
from app.modules.sync.application.push import EventIn, OutboxStateIn

router = APIRouter(tags=["sync"])


def _module(request: Request) -> SyncModule:
    module: SyncModule | None = getattr(request.app.state, "sync", None)
    if module is None:
        raise RuntimeError("sync module is not configured (app.state.sync)")
    return module


async def push_principal(request: Request) -> Principal:
    """Normal token → subscription gate (403 SUBSCRIPTION_RESTRICTED); drain token → no gate here."""
    principal = await authenticate(request, allow_sync_drain=True)
    if not principal.has_scope(SCOPE_SYNC_DRAIN):
        status = await auth_gateway(request).subscription_status(principal.tenant_id)
        if status in ("restricted", "closed"):
            raise AppError(
                ErrorCode.SUBSCRIPTION_RESTRICTED,
                params={"tenant_id": str(principal.tenant_id), "status": status},
            )
    return principal


PushActor = Annotated[Principal, Depends(push_principal)]
PullActor = Annotated[Principal, Depends(require_subscription_ok)]


# --- schemas -------------------------------------------------------------------------------------
class SyncEventEnvelope(BaseModel):
    """18 §2.1."""

    model_config = ConfigDict(extra="forbid")

    client_event_id: UUID
    device_id: UUID
    seq: int = Field(ge=0)
    type: str = Field(min_length=1, max_length=64)
    created_at: AwareDatetime
    actor_user_id: UUID
    payload: dict[str, Any]


class OutboxState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pending_count: int = Field(ge=0)
    oldest_pending_created_at: AwareDatetime | None


class SyncPushRequest(BaseModel):
    """18 §2.6 — ``outbox_state`` is required (16 §3.1)."""

    model_config = ConfigDict(extra="forbid")

    device_id: UUID
    events: list[SyncEventEnvelope]
    outbox_state: OutboxState


class ErrorDetailOut(BaseModel):
    field: str
    message_key: str


class PushResultEntry(BaseModel):
    """18 §2.2 (+ ``params``/``details`` of the error for client-side i18n)."""

    client_event_id: UUID
    status: Literal["accepted", "rejected", "duplicate"]
    server: dict[str, Any] | None
    error_code: str | None
    message: str | None
    retryable: bool
    warnings: list[str]
    params: dict[str, Any] = Field(default_factory=dict)
    details: list[ErrorDetailOut] = Field(default_factory=list)


class SyncPushResponse(BaseModel):
    results: list[PushResultEntry]


class PullDevice(BaseModel):
    id: UUID
    branch_id: UUID
    cash_register_id: UUID | None


class SyncPullResponse(BaseModel):
    """16 §3.2 — delta scopes are row arrays, snapshot scopes objects (``null`` = unchanged).
    Exact row shapes: ``.claude-scratch/b3/contracts/sync-pull.md`` / 16 §3.2."""

    cursor: str
    has_more: bool
    server_time: datetime
    device: PullDevice
    catalog: list[dict[str, Any]] | None = None
    barcodes: list[dict[str, Any]] | None = None
    prices: list[dict[str, Any]] | None = None
    customers: list[dict[str, Any]] | None = None
    stock: list[dict[str, Any]] | None = None
    marking_codes: list[dict[str, Any]] | None = None
    fiscal: list[dict[str, Any]] | None = None
    permissions: dict[str, Any] | None = None
    limits: dict[str, Any] | None = None
    shift: dict[str, Any] | None = None
    settings: dict[str, Any] | None = None


# --- routes --------------------------------------------------------------------------------------
@router.post("/sync/push", operation_id="sync_push_events", response_model=SyncPushResponse)
async def push_events(request: Request, body: SyncPushRequest, actor: PushActor) -> dict[str, Any]:
    events = [
        EventIn(
            client_event_id=e.client_event_id,
            device_id=e.device_id,
            seq=e.seq,
            type=e.type,
            created_at=e.created_at,
            actor_user_id=e.actor_user_id,
            payload=e.payload,
        )
        for e in body.events
    ]
    state = OutboxStateIn(body.outbox_state.pending_count, body.outbox_state.oldest_pending_created_at)
    ip = request.client.host if request.client else None
    return await _module(request).push.push(actor, body.device_id, events, state, ip=ip)


@router.get(
    "/sync/pull",
    operation_id="sync_pull_changes",
    response_model=SyncPullResponse,
    response_model_exclude_unset=True,
)
async def pull_changes(
    request: Request,
    actor: PullActor,
    scope: Annotated[str | None, Query(max_length=256)] = None,
    cursor: Annotated[str | None, Query(max_length=8192)] = None,
    page_size: Annotated[int | None, Query(ge=1)] = None,
) -> dict[str, Any]:
    return await _module(request).pull.pull(actor, scope, cursor, page_size)
