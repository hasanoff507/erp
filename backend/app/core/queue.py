"""``JobQueue`` port and its SAQ adapter (23 §4).

Every job's first argument is the tenant id (23 §4 "Worker/scheduler'da tenant
konteksti"); :func:`tenant_job` enforces it and runs the job body inside
``tenant_transaction``.
"""

from __future__ import annotations

import functools
from collections.abc import Awaitable, Callable
from typing import Any, Concatenate, Protocol
from uuid import UUID

from saq import Queue
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.session import Database, TenantContextError, tenant_transaction


class JobQueue(Protocol):
    async def enqueue(self, job: str, tenant_id: UUID, **kwargs: Any) -> str | None: ...


class SaqJobQueue:
    def __init__(self, queue: Queue) -> None:
        self._queue = queue

    async def enqueue(self, job: str, tenant_id: UUID, **kwargs: Any) -> str | None:
        if not isinstance(tenant_id, UUID):
            raise TenantContextError("jobs are always enqueued for one tenant")
        queued = await self._queue.enqueue(job, tenant_id=str(tenant_id), **kwargs)
        return queued.key if queued is not None else None


def make_queue(redis_url: str, name: str = "default") -> Queue:
    return Queue.from_url(redis_url, name=name)


def _parse_tenant(raw: object) -> UUID:
    if isinstance(raw, UUID):
        return raw
    if isinstance(raw, str):
        try:
            return UUID(raw)
        except ValueError as exc:
            raise TenantContextError(f"invalid tenant_id: {raw!r}") from exc
    raise TenantContextError("job called without tenant_id")


JobBody = Callable[Concatenate[AsyncSession, ...], Awaitable[Any]]


def tenant_job(func: JobBody) -> Callable[..., Awaitable[Any]]:
    """Wrap a job body ``(session, **kwargs)`` as a SAQ function ``(ctx, *, tenant_id, **kwargs)``.

    A job without a valid ``tenant_id`` fails before touching the database.
    """

    @functools.wraps(func)
    async def wrapper(ctx: dict[str, Any], *, tenant_id: object = None, **kwargs: Any) -> Any:
        tid = _parse_tenant(tenant_id)
        db: Database = ctx["db"]
        async with db.session_factory() as session, tenant_transaction(session, tid):
            return await func(session, **kwargs)

    return wrapper
