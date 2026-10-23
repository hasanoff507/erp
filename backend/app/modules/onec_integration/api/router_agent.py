"""Agent channel ``/api/v1/onec-agent/*`` — A-01, A-03…A-10 (33 §9.3; contracts/agent-wire.md).

Bearer ``aud=urn:erp:onec-agent`` only; no CSRF, no ``Idempotency-Key`` (dedupe by ``lease_id`` /
``client_log_id``, 23 §3); tenant/agent never from the body. Request bodies ignore unknown members (the
protocol grows additively, ``X-Agent-Protocol``). OpenAPI tag ``onec``.
"""

from __future__ import annotations

import zlib
from collections.abc import Callable, Coroutine
from typing import Annotated, Any, Final, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import JSONResponse, Response
from fastapi.routing import APIRoute
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from app.modules.onec_integration.api.deps import (
    Agent,
    AgentSession,
    onec_agents,
    require_agent_protocol,
    require_agent_subscription,
)
from app.modules.onec_integration.wiring import AgentPrincipal

MAX_DECODED_BYTES: Final = 10 * 1024 * 1024  # 33 §9.1: request ≤ 10 MB


class GzipRequest(Request):
    """33 §9.1: bodies over 16 KB arrive with ``Content-Encoding: gzip`` — decoded here (bounded)."""

    async def body(self) -> bytes:
        if not hasattr(self, "_body"):
            raw = await super().body()
            if self.headers.get("content-encoding", "").lower() == "gzip":
                decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
                try:
                    decoded = decoder.decompress(raw, MAX_DECODED_BYTES + 1)
                except zlib.error as exc:
                    raise AppError(ErrorCode.VALIDATION_ERROR, params={"reason": "gzip"}) from exc
                if len(decoded) > MAX_DECODED_BYTES or decoder.unconsumed_tail:
                    raise AppError(ErrorCode.FILE_TOO_LARGE, params={"max_bytes": MAX_DECODED_BYTES})
                raw = decoded
            self._body = raw
        return self._body


class GzipRoute(APIRoute):
    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        original = super().get_route_handler()

        async def handler(request: Request) -> Response:
            wrapped = GzipRequest(request.scope, request.receive)
            if wrapped.headers.get("content-encoding", "").lower() == "gzip":
                await wrapped.body()  # decoded once; JSON and multipart parsing read the cached body
            return await original(wrapped)

        return handler


router = APIRouter(prefix="/onec-agent", tags=["onec"], route_class=GzipRoute)

Gated = Annotated[AgentPrincipal, Depends(require_agent_protocol)]
Subscription = Annotated[str, Depends(require_agent_subscription)]


class _AgentBody(BaseModel):
    model_config = ConfigDict(extra="ignore")


class HelloIn(_AgentBody):
    agent_version: str | None = Field(default=None, max_length=32)
    protocol: int | None = None
    os_version: str | None = Field(default=None, max_length=128)
    machine_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    pc_name: str | None = Field(default=None, min_length=1, max_length=64)
    worker_bits: list[Literal[32, 64]] | None = Field(default=None, max_length=2)
    platforms: list[dict[str, Any]] | None = Field(default=None, max_length=16)
    bases: list[dict[str, Any]] | None = Field(default=None, max_length=64)
    task_keyset_version: int | None = None
    busy_base_ids: list[UUID] | None = None
    results_outbox_pending: int | None = None
    capabilities: dict[str, Any] | None = None
    clock: str | None = Field(default=None, max_length=40)


class PollIn(_AgentBody):
    ready_base_ids: list[UUID] = Field(default_factory=list, max_length=64)
    busy_base_ids: list[UUID] = Field(default_factory=list, max_length=64)
    agent_level_busy: bool = False
    max_tasks: int = Field(default=1, ge=0)
    wait_s: int = Field(default=25, ge=0)


class Progress(_AgentBody):
    stage: str | None = Field(default=None, max_length=32)
    pct: int | None = Field(default=None, ge=0, le=100)
    message: str | None = Field(default=None, max_length=500)


class HeartbeatIn(_AgentBody):
    lease_id: UUID
    progress: Progress | None = None


class ResultIn(_AgentBody):
    lease_id: UUID
    attempt: int = Field(ge=1)
    outcome: Literal["done", "failed", "unknown"]
    data: dict[str, Any] = Field(default_factory=dict)
    error: dict[str, Any] | None = None
    started_at: str | None = Field(default=None, max_length=40)
    finished_at: str | None = Field(default=None, max_length=40)
    duration_ms: int | None = Field(default=None, ge=0, le=2**31 - 1)
    worker_bits: Literal[32, 64] | None = None


class LogEntry(_AgentBody):
    client_log_id: UUID
    at: AwareDatetime
    level: Literal["debug", "info", "warn", "error"]
    code: str | None = Field(default=None, max_length=100)
    message: str = Field(max_length=16000)
    base_id: UUID | None = None
    task_id: UUID | None = None
    context: dict[str, Any] | None = None


class LogsIn(_AgentBody):
    entries: list[LogEntry] = Field(min_length=1, max_length=500)


class UnpairIn(_AgentBody):
    reason: Literal["uninstall", "user"]


@router.post("/hello", operation_id="onec_agent_hello")
async def hello(request: Request, body: HelloIn, agent: Gated, subscription: Subscription) -> dict[str, Any]:
    """A-01: agent facts and ``capabilities`` (34 §14.2) → ``onec_agents``; keyset/update offer."""
    data = body.model_dump(exclude_unset=True)
    return await onec_agents(request).agents.hello(agent, data, subscription)


@router.post("/poll", operation_id="onec_agent_poll", response_model=None)
async def poll(request: Request, body: PollIn, agent: Gated, _: Subscription) -> Response | dict[str, Any]:
    """A-03: long-poll ≤ 25 s; ``200 {tasks:[…]}`` (one signed task) or ``204``."""
    result = await onec_agents(request).agents.poll(
        agent, max_tasks=min(body.max_tasks, 4), wait_s=body.wait_s, agent_level_busy=body.agent_level_busy
    )
    if result is None:
        return Response(status_code=204)
    return result


@router.post("/tasks/{task_id}/heartbeat", operation_id="onec_agent_heartbeat")
async def heartbeat(
    request: Request, task_id: UUID, body: HeartbeatIn, agent: Agent, s: AgentSession
) -> dict[str, Any]:
    """A-04: extend the lease (``409 ONEC_TASK_LEASE_LOST`` when it is gone)."""
    progress = body.progress.model_dump(exclude_none=True) if body.progress else None
    return await onec_agents(request).tasks.heartbeat(s, agent.agent_id, task_id, body.lease_id, progress)


@router.post("/tasks/{task_id}/result", operation_id="onec_agent_result")
async def result(
    request: Request, task_id: UUID, body: ResultIn, agent: Agent, s: AgentSession
) -> dict[str, Any]:
    """A-05: idempotent by ``(task_id, lease_id)``; late results accepted (``late=true``)."""
    payload = {**body.model_dump(), "agent_version": agent.agent_version}
    ack = await onec_agents(request).tasks.accept_result(
        s, agent.tenant_id, agent.agent_id, agent.device_id, task_id, payload
    )
    return ack.as_json()


@router.post("/logs", operation_id="onec_agent_logs")
async def logs(request: Request, body: LogsIn, agent: Agent) -> dict[str, int]:
    """A-06: masked agent log entries, dedupe by ``client_log_id``."""
    entries = [e.model_dump() for e in body.entries]
    return await onec_agents(request).agents.ingest_logs(agent, entries)


@router.post("/diagnostics", operation_id="onec_agent_diagnostics", status_code=201)
async def diagnostics(
    request: Request,
    agent: Agent,
    file: Annotated[UploadFile, File()],
    task_id: Annotated[UUID, Form()],
) -> JSONResponse:
    """A-07: diagnostics zip (≤ 20 MB) of a ``collect_diagnostics`` task →
    ``attachments(kind='onec_diagnostics')``."""
    limit = onec_agents(request).diagnostics_max_bytes
    content = await file.read(limit + 1)
    if len(content) > limit:
        raise AppError(ErrorCode.FILE_TOO_LARGE, params={"max_bytes": limit})
    body = await onec_agents(request).agents.upload_diagnostics(agent, task_id, file.filename, content)
    return JSONResponse(body, status_code=201)


@router.get("/task-keys", operation_id="onec_agent_task_keys")
async def task_keys(request: Request, agent: Agent) -> dict[str, Any]:
    """A-08: the current ``task_keyset`` (signed offline by the ``agent_update`` root key)."""
    del agent
    keyset = await onec_agents(request).grants.task_keyset()
    if keyset is None:
        raise AppError(ErrorCode.NOT_FOUND, params={"resource": "task_keyset"})
    try:
        version = int(keyset.version)
    except ValueError:
        version = 0
    return {"version": version, "task_keyset": keyset.body}


@router.get("/update-manifest", operation_id="onec_agent_update_manifest")
async def update_manifest(
    request: Request, agent: Agent, channel: Annotated[Literal["stable", "pilot"], Query()] = "stable"
) -> dict[str, Any]:
    """A-09: the signed manifest of the channel (Ed25519 over the exact bytes)."""
    del agent
    manifest = await onec_agents(request).grants.update_manifest(channel)
    if manifest is None:
        raise AppError(ErrorCode.NOT_FOUND, params={"resource": "update_manifest", "channel": channel})
    return {"manifest": manifest.body, "signature": manifest.signature, "kid": manifest.kid}


@router.post("/unpair", operation_id="onec_agent_unpair", status_code=204)
async def unpair(request: Request, body: UnpairIn, agent: Agent) -> Response:
    """A-10: uninstall / «Uzish» — the agent revokes itself."""
    await onec_agents(request).agents.unpair(agent, body.reason)
    return Response(status_code=204)
