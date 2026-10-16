"""Idempotency-Key handling (23 §3, 32 §4.5, 17 §6).

* Redis ``SET NX idem:{tenant}:{key}`` — short lock; a parallel duplicate gets
  ``409 IDEMPOTENCY_IN_PROGRESS`` with ``Retry-After: 1``.
* ``app.idempotency_keys`` — durable journal (30 days); a repeat with the same
  request hash returns the stored response, a different hash gets
  ``422 IDEMPOTENCY_KEY_REUSED``.
* The journal row is written by the route's unit of work: the middleware puts
  the key and request hash into a contextvar, the route calls
  :func:`stage_response` inside its ``tenant_transaction`` and the row is
  inserted there, before COMMIT — so a crash after the business commit cannot
  leave a write without its journal row. Only a 2xx write that never stages a
  response (no business transaction) is journalled by the middleware itself.

Only back-office writes are covered; ``/sync/push`` (dedupe by
``client_event_id``) and ``/onec-agent/*`` are exempt. The tenant comes from the
auth layer through ``TenantResolver`` — never from the request body.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

import structlog
from fastapi.encoders import jsonable_encoder
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.context import IdempotencyConflictError, PendingIdempotency, idempotency_var, unit_of_work_var
from app.core.db.session import tenant_transaction
from app.core.error_codes import ErrorCode
from app.core.errors import ErrorDetail, error_response

log = structlog.get_logger(__name__)

HEADER = "idempotency-key"
WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
DEFAULT_EXEMPT_PREFIXES: tuple[str, ...] = ("/api/v1/sync/push", "/api/v1/onec-agent/")
MAX_KEY_LENGTH = 200
_CONFLICT = -1  # pseudo status: the unit of work lost the PRIMARY KEY race

TenantResolver = Callable[[Request], Awaitable[UUID | None]]


async def no_tenant(_: Request) -> UUID | None:
    """Default resolver until the auth module plugs in the real one."""
    return None


@dataclass(frozen=True, slots=True)
class StoredResponse:
    request_hash: str
    status: int
    body: Any


class IdempotencyStore(Protocol):
    async def get(self, tenant_id: UUID, key: str) -> StoredResponse | None: ...

    async def save(self, tenant_id: UUID, key: str, response: StoredResponse) -> None: ...


class PgIdempotencyStore:
    """``app.idempotency_keys`` repository; every access runs in the tenant's transaction."""

    _GET = text(
        "SELECT request_hash, response_status, response_body FROM app.idempotency_keys "
        "WHERE tenant_id = :tenant_id AND key = :key"
    )
    _SAVE = text(
        "INSERT INTO app.idempotency_keys (tenant_id, key, request_hash, response_status, response_body) "
        "VALUES (:tenant_id, :key, :request_hash, :status, CAST(:body AS jsonb)) "
        "ON CONFLICT (tenant_id, key) DO NOTHING"
    )

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get(self, tenant_id: UUID, key: str) -> StoredResponse | None:
        async with self._session_factory() as session, tenant_transaction(session, tenant_id):
            row = (await session.execute(self._GET, {"tenant_id": tenant_id, "key": key})).first()
        if row is None:
            return None
        return StoredResponse(request_hash=row[0], status=row[1], body=row[2])

    async def save(self, tenant_id: UUID, key: str, response: StoredResponse) -> None:
        params = {
            "tenant_id": tenant_id,
            "key": key,
            "request_hash": response.request_hash,
            "status": response.status,
            "body": json.dumps(response.body),
        }
        async with self._session_factory() as session, tenant_transaction(session, tenant_id):
            await session.execute(self._SAVE, params)


def stage_response(body: Any, status_code: int = 200) -> None:
    """Stage the response of the running write request for the idempotency journal.

    Call it inside the route's ``tenant_transaction`` (or ``TenantSession``)
    with the same body and status the route returns; the journal row is then
    inserted in that transaction right before COMMIT (23 §3). No-op outside an
    ``Idempotency-Key`` request.
    """
    pending = idempotency_var.get()
    if pending is None or pending.recorded:
        return
    pending.status = status_code
    pending.body = jsonable_encoder(body)
    # bound to the innermost open tenant_transaction; outside one the middleware journals after the response
    pending.unit_of_work = unit_of_work_var.get()


def request_hash(method: str, path: str, query: bytes, body: bytes) -> str:
    digest = hashlib.sha256()
    for part in (method.encode(), path.encode(), query, body):
        digest.update(len(part).to_bytes(8, "big"))
        digest.update(part)
    return digest.hexdigest()


def lock_key(tenant_id: UUID, key: str) -> str:
    return f"idem:{tenant_id}:{key}"


# compare-and-delete: only the holder of the token may release the lock. If our
# TTL expired and a duplicate took the lock over, we must not delete its lock.
_RELEASE_LOCK = (
    "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) else return 0 end"
)


async def release_lock(redis: Redis, name: str, token: str) -> bool:
    """Delete ``name`` only if it still holds ``token``; returns whether it was deleted."""
    deleted = await redis.eval(_RELEASE_LOCK, 1, name, token)
    return bool(deleted)


class IdempotencyMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        *,
        redis: Callable[[], Redis],
        store: Callable[[], IdempotencyStore],
        resolve_tenant: TenantResolver = no_tenant,
        lock_ttl_s: int = 60,
        exempt_prefixes: Sequence[str] = DEFAULT_EXEMPT_PREFIXES,
        api_prefix: str = "/api/v1",
    ) -> None:
        self.app = app
        self._redis = redis
        self._store = store
        self._resolve_tenant = resolve_tenant
        self._lock_ttl_s = lock_ttl_s
        self._exempt = tuple(exempt_prefixes)
        self._api_prefix = api_prefix

    def _applies(self, scope: Scope) -> bool:
        path: str = scope.get("path", "")
        return (
            scope["type"] == "http"
            and scope.get("method", "") in WRITE_METHODS
            and path.startswith(self._api_prefix)
            and not path.startswith(self._exempt)
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if not self._applies(scope):
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        tenant_id = await self._resolve_tenant(request)
        if tenant_id is None:
            # unauthenticated: auth rejects it further down, nothing to protect
            await self.app(scope, receive, send)
            return

        key = request.headers.get(HEADER, "").strip()
        if not key or len(key) > MAX_KEY_LENGTH:
            detail = "validation.required" if not key else "validation.max_length"
            response = error_response(
                ErrorCode.VALIDATION_ERROR,
                422,
                details=[ErrorDetail(field="Idempotency-Key", message_key=detail)],
            )
            await response(scope, receive, send)
            return

        body = await request.body()
        req_hash = request_hash(scope["method"], scope["path"], scope.get("query_string", b""), body)
        store = self._store()

        stored = await store.get(tenant_id, key)
        if stored is not None:
            await self._replay(stored, req_hash, scope, receive, send)
            return

        redis = self._redis()
        lock_name = lock_key(tenant_id, key)
        lock_token = secrets.token_hex(16)  # per-request owner token (never the request hash)
        acquired = await redis.set(lock_name, lock_token, nx=True, ex=self._lock_ttl_s)
        if not acquired:
            response = error_response(ErrorCode.IDEMPOTENCY_IN_PROGRESS, 409, headers={"Retry-After": "1"})
            await response(scope, receive, send)
            return

        try:
            # the lock may have been taken right after another request finished
            stored = await store.get(tenant_id, key)
            if stored is not None:
                await self._replay(stored, req_hash, scope, receive, send)
                return
            pending = PendingIdempotency(tenant_id=tenant_id, key=key, request_hash=req_hash)
            token = idempotency_var.set(pending)
            try:
                status, chunks = await self._run(scope, body, send)
            except IdempotencyConflictError:
                status, chunks = _CONFLICT, []
            finally:
                idempotency_var.reset(token)
            if status == _CONFLICT:
                # a duplicate committed first: our transaction rolled back, answer with its response
                stored = await store.get(tenant_id, key)
                if stored is None:
                    raise IdempotencyConflictError(key)
                await self._replay(stored, req_hash, scope, receive, send)
                return
            if 200 <= status < 300 and not pending.recorded:
                # no business transaction staged the response (e.g. a Redis-only write)
                raw = b"".join(chunks)
                await store.save(
                    tenant_id,
                    key,
                    StoredResponse(request_hash=req_hash, status=status, body=_json_or_none(raw)),
                )
        finally:
            await release_lock(redis, lock_name, lock_token)

    async def _replay(
        self, stored: StoredResponse, req_hash: str, scope: Scope, receive: Receive, send: Send
    ) -> None:
        response: Response
        if stored.request_hash != req_hash:
            response = error_response(ErrorCode.IDEMPOTENCY_KEY_REUSED, 422)
        else:
            response = _stored_to_response(stored)
        await response(scope, receive, send)

    async def _run(self, scope: Scope, body: bytes, send: Send) -> tuple[int, list[bytes]]:
        status = 500
        chunks: list[bytes] = []
        sent_body = False

        async def receive_buffered() -> Message:
            nonlocal sent_body
            if not sent_body:
                sent_body = True
                return {"type": "http.request", "body": body, "more_body": False}
            return {"type": "http.disconnect"}

        async def send_capture(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            elif message["type"] == "http.response.body":
                chunks.append(message.get("body", b""))
            await send(message)

        await self.app(scope, receive_buffered, send_capture)
        return status, chunks


def _json_or_none(raw: bytes) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except ValueError:
        return None


def _stored_to_response(stored: StoredResponse) -> Response:
    if stored.body is None:
        return Response(status_code=stored.status, headers={"Idempotent-Replayed": "true"})
    return JSONResponse(stored.body, status_code=stored.status, headers={"Idempotent-Replayed": "true"})
