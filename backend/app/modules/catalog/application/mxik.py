"""MXIK search/lookup with cache and retry (19 §1 "MXIK qidiruv", 21 §7).

* fresh cache hit → answered from the cache, no external call;
* otherwise the classifier is called with ``base, cap, max_attempts`` backoff
  (21 §7: 5 s / 30 s / 3); on success the cache is refreshed;
* after the last failed attempt the last known (stale) cache entry is returned
  with ``source="stale_cache"`` — never a hard error, the user may type the
  code by hand (21 §7 "Xato UX").
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import asdict
from typing import Any, TypeVar

import structlog

from app.core.error_codes import ErrorCode
from app.core.errors import AppError, ErrorDetail
from app.modules.catalog.application.ports import MxikCachePort, MxikCatalogPort, MxikUnavailableError
from app.modules.catalog.domain.mxik import MxikCandidate, MxikLookup
from app.modules.catalog.domain.products import is_valid_mxik

log = structlog.get_logger(__name__)

T = TypeVar("T")
MAX_SEARCH_LIMIT = 20


def _candidates(payload: Any) -> tuple[MxikCandidate, ...]:
    return tuple(MxikCandidate(**item) for item in payload)


class MxikService:
    def __init__(
        self,
        port: MxikCatalogPort,
        cache: MxikCachePort,
        *,
        retry_base_s: float = 5.0,
        retry_cap_s: float = 30.0,
        max_attempts: int = 3,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._port = port
        self._cache = cache
        self._base = retry_base_s
        self._cap = retry_cap_s
        self._attempts = max(1, max_attempts)
        self._sleep = sleep

    async def search(self, query: str, limit: int) -> MxikLookup:
        query = " ".join(query.split()).lower()
        limit = max(1, min(limit, MAX_SEARCH_LIMIT))
        if not query:
            return MxikLookup((), "live")
        key = f"q:{limit}:{query}"
        return await self._cached(key, lambda: self._port.search(query, limit))

    async def get(self, code: str) -> MxikLookup:
        if not is_valid_mxik(code):
            raise AppError(
                ErrorCode.MXIK_CODE_INVALID,
                details=[ErrorDetail(field="code", message_key="validation.mxik_format")],
            )

        async def fetch() -> list[MxikCandidate]:
            found = await self._port.get(code)
            return [found] if found is not None else []

        result = await self._cached(f"code:{code}", fetch)
        if not result.items and result.source != "stale_cache":
            raise AppError(ErrorCode.NOT_FOUND, params={"resource": "mxik_code"})
        return result

    async def _cached(self, key: str, fetch: Callable[[], Awaitable[list[MxikCandidate]]]) -> MxikLookup:
        cached = await self._cache.get(key)
        if cached is not None and cached[1]:
            return MxikLookup(_candidates(cached[0]), "cache")
        try:
            items = await self._retrying(fetch)
        except MxikUnavailableError:
            log.warning("mxik_unavailable", key=key, stale=cached is not None)
            return MxikLookup(_candidates(cached[0]) if cached else (), "stale_cache")
        await self._cache.put(key, [asdict(c) for c in items])
        return MxikLookup(tuple(items), "live")

    async def _retrying(self, fetch: Callable[[], Awaitable[T]]) -> T:
        delay = self._base
        for attempt in range(1, self._attempts + 1):
            try:
                return await fetch()
            except MxikUnavailableError:
                if attempt == self._attempts:
                    raise
                await self._sleep(min(delay, self._cap))
                delay *= 2
        raise MxikUnavailableError("unreachable")  # pragma: no cover
