"""Async engine, session factory and the tenant transaction (23 §1, 32 §4.1).

Every transaction is opened through :func:`tenant_transaction`. Sessions are
created with ``autobegin=False``, so a query outside of it fails instead of
silently running without a tenant context.

The unit of work is also where a write request's ``Idempotency-Key`` is
journalled (23 §3): if the route staged its response, the ``idempotency_keys``
row is inserted in the same transaction, right before COMMIT.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any
from uuid import UUID

from fastapi import Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.context import (
    IdempotencyConflictError,
    idempotency_var,
    tenant_id_var,
    unit_of_work_var,
    user_id_var,
)

if TYPE_CHECKING:
    from app.core.config import Settings

TENANT_KEY = "tenant_id"
USER_KEY = "user_id"

_SET_TENANT = text("SELECT set_config('app.tenant_id', :tid, true)")
_SET_USER = text("SELECT set_config('app.user_id', :uid, true)")
_JOURNAL_IDEMPOTENCY = text(
    "INSERT INTO app.idempotency_keys (tenant_id, key, request_hash, response_status, response_body) "
    "VALUES (:tenant_id, :key, :request_hash, :status, CAST(:body AS jsonb)) "
    "ON CONFLICT (tenant_id, key) DO NOTHING RETURNING 1"
)


class TenantContextError(RuntimeError):
    """Raised when tenant-scoped work is attempted without a tenant id."""


def make_engine(url: str, *, pool_size: int = 10, max_overflow: int = 10, echo: bool = False) -> AsyncEngine:
    return create_async_engine(
        url,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_pre_ping=True,
        echo=echo,
        # bound parameters (PII, tokens, hashes) never reach exception messages or logs
        hide_parameters=True,
    )


def make_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, autobegin=False)


class Database:
    """Owns the engine and the session factory for one process."""

    def __init__(self, engine: AsyncEngine) -> None:
        self.engine = engine
        self.session_factory = make_session_factory(engine)

    @classmethod
    def from_settings(cls, settings: Settings) -> Database:
        engine = make_engine(
            settings.database_url.get_secret_value(),
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            echo=settings.db_echo,
        )
        return cls(engine)

    async def dispose(self) -> None:
        await self.engine.dispose()


@asynccontextmanager
async def tenant_transaction(
    session: AsyncSession, tenant_id: UUID, *, user_id: UUID | None = None
) -> AsyncIterator[AsyncSession]:
    """Open the one transaction that tenant-scoped work may run in.

    ``set_config(..., true)`` is transaction-local, so the value disappears on
    commit/rollback and cannot leak to the next user of a pooled connection.
    """
    if not isinstance(tenant_id, UUID):
        raise TenantContextError("tenant_transaction requires a tenant_id (UUID)")
    async with session.begin():
        session.info[TENANT_KEY] = tenant_id
        session.info[USER_KEY] = user_id
        tenant_token = tenant_id_var.set(tenant_id)
        user_token = user_id_var.set(user_id) if user_id is not None else None
        unit_of_work = object()
        uow_token = unit_of_work_var.set(unit_of_work)
        try:
            await session.execute(_SET_TENANT, {"tid": str(tenant_id)})
            if user_id is not None:
                await session.execute(_SET_USER, {"uid": str(user_id)})
            yield session
            await _journal_idempotency(session, tenant_id, unit_of_work)
        finally:
            session.info.pop(TENANT_KEY, None)
            session.info.pop(USER_KEY, None)
            unit_of_work_var.reset(uow_token)
            tenant_id_var.reset(tenant_token)
            if user_token is not None:
                user_id_var.reset(user_token)


async def _journal_idempotency(session: AsyncSession, tenant_id: UUID, unit_of_work: object) -> None:
    """Insert the staged ``idempotency_keys`` row in this transaction, before COMMIT (23 §3).

    ``PRIMARY KEY (tenant_id, key)`` is the last guard: if a duplicate request
    committed first (lock TTL expired), this transaction is rolled back and the
    middleware replays the stored response instead.
    """
    pending = idempotency_var.get()
    if pending is None or pending.recorded or pending.unit_of_work is not unit_of_work:
        return
    if pending.tenant_id != tenant_id:
        raise RuntimeError("stage_response() inside another tenant's transaction")
    params = {
        "tenant_id": tenant_id,
        "key": pending.key,
        "request_hash": pending.request_hash,
        "status": pending.status,
        "body": json.dumps(pending.body),
    }
    if (await session.execute(_JOURNAL_IDEMPOTENCY, params)).first() is None:
        raise IdempotencyConflictError(pending.key)
    pending.recorded = True


@asynccontextmanager
async def unscoped_transaction(session: AsyncSession) -> AsyncIterator[AsyncSession]:
    """Transaction without a tenant, only for SECURITY DEFINER calls (12 §4.5).

    Login, scheduler fan-out (``list_active_tenant_ids``) and webhooks resolve
    the tenant this way; any direct read of a tenant table returns zero rows
    because RLS is fail-closed.
    """
    async with session.begin():
        session.info[TENANT_KEY] = None
        try:
            yield session
        finally:
            session.info.pop(TENANT_KEY, None)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    db: Database = request.app.state.db
    async with db.session_factory() as session:
        yield session


def session_tenant_id(session: AsyncSession) -> UUID | None:
    value: Any = session.info.get(TENANT_KEY)
    return value if isinstance(value, UUID) else None
