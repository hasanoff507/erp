"""SAQ enqueue adapter of the fiscal jobs (23 §4: the first job argument is the tenant id)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.core.db.session import TenantContextError
from app.core.queue import make_queue


class SaqEnqueuer:
    """A short-lived Redis connection per enqueue — the API process keeps no SAQ queue open."""

    def __init__(self, redis_url: str, queue_name: str) -> None:
        self._url = redis_url
        self._name = queue_name

    async def enqueue(self, job: str, tenant_id: UUID, **kwargs: Any) -> None:
        if not isinstance(tenant_id, UUID):
            raise TenantContextError("jobs are always enqueued for one tenant")
        queue = make_queue(self._url, self._name)
        try:
            await queue.enqueue(job, tenant_id=str(tenant_id), retries=1, timeout=300, **kwargs)
        finally:
            await queue.disconnect()
