"""MXIK adapters (21 §7): tasnif.soliq.uz over HTTP, a dev/test fake, and the Redis cache.

tasnif.soliq.uz has no official API; the public endpoints behind the web UI
(also used by community SDKs) are called. Base URL and paths are settings
(``ERP_MXIK_BASE_URL``) so a change on their side is a config fix. Parsing is
defensive: unknown shapes yield no candidates instead of an exception.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from decimal import Decimal, InvalidOperation
from typing import Any, Final

import httpx
from redis.asyncio import Redis

from app.modules.catalog.application.ports import MxikUnavailableError
from app.modules.catalog.domain.mxik import MxikCandidate
from app.modules.catalog.domain.products import is_valid_mxik

DEFAULT_BASE_URL: Final = "https://tasnif.soliq.uz/api/cls-api"
SEARCH_PATH: Final = "/elasticsearch/search"
LOOKUP_PATH: Final = "/mxik/get/by-mxik"

_CODE_KEYS = ("mxikCode", "mxik_code", "code", "classCode")
_NAME_KEYS = ("name", "mxikName", "fullName", "nameUz", "name_uz", "nameLatin")
_VAT_KEYS = ("vat", "vatPercent", "vat_rate", "nds", "vatRate")


def _first(item: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        value = item.get(key)
        if value not in (None, ""):
            return value
    return None


def _vat_hint(raw: Any) -> str | None:
    if raw is None or isinstance(raw, bool):
        return None
    try:
        return str(Decimal(str(raw)).quantize(Decimal("0.01")))
    except InvalidOperation:
        return None


def parse_candidates(payload: Any) -> list[MxikCandidate]:
    """``{"data": [...]}`` / ``{"data": {"content": [...]}}`` / ``[...]`` / one object → candidates."""
    items: Any = payload
    for _ in range(3):
        if isinstance(items, dict) and not _first(items, _CODE_KEYS):
            items = items.get("data", items.get("content", items.get("items")))
        else:
            break
    if isinstance(items, dict):
        items = [items]
    if not isinstance(items, list):
        return []
    out: list[MxikCandidate] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        code = str(_first(item, _CODE_KEYS) or "")
        if not is_valid_mxik(code):
            continue
        out.append(
            MxikCandidate(
                code=code,
                name=str(_first(item, _NAME_KEYS) or code),
                vat_hint=_vat_hint(_first(item, _VAT_KEYS)),
            )
        )
    return out


class TasnifMxikAdapter:
    """``MxikCatalogPort`` over HTTP. Network errors/timeouts/5xx → ``MxikUnavailableError``.

    One short-lived client per call: lookups are rare (cached) and nothing is left open at shutdown.
    """

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        *,
        timeout_s: float = 5.0,
        lang: str = "uz",
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_s
        self._lang = lang
        self._transport = transport

    async def _get(self, path: str, params: dict[str, Any]) -> Any:
        try:
            async with httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout,
                transport=self._transport,
                headers={"Accept": "application/json"},
            ) as client:
                response = await client.get(path, params=params)
        except httpx.HTTPError as exc:
            raise MxikUnavailableError(str(exc)) from exc
        if response.status_code == 404:
            return None
        if response.status_code >= 400:
            raise MxikUnavailableError(f"tasnif.soliq.uz HTTP {response.status_code}")
        try:
            return response.json()
        except ValueError as exc:
            raise MxikUnavailableError("tasnif.soliq.uz returned non-JSON") from exc

    async def search(self, query: str, limit: int) -> list[MxikCandidate]:
        payload = await self._get(
            SEARCH_PATH, {"search": query, "size": limit, "page": 0, "lang": self._lang}
        )
        return parse_candidates(payload)[:limit]

    async def get(self, code: str) -> MxikCandidate | None:
        payload = await self._get(LOOKUP_PATH, {"mxikCode": code, "lang": self._lang})
        for candidate in parse_candidates(payload):
            if candidate.code == code:
                return candidate
        return None


# dev/test only (ERP_MXIK_PROVIDER=fake, refused in staging/prod by wiring) — qaror #34
FAKE_MXIK: Final[tuple[MxikCandidate, ...]] = (
    MxikCandidate("02202001001000000", "Gazlangan ichimliklar (Coca-Cola 1.5L)", "12.00"),
    MxikCandidate("02202001002000000", "Gazlangan ichimliklar (Pepsi 1L)", "12.00"),
    MxikCandidate("02201001001000000", "Ichimlik suvi", "12.00"),
    MxikCandidate("10201001001000000", "Mol go'shti", "12.00"),
    MxikCandidate("10701001001000000", "Non", "0.00"),
)


class FakeMxikAdapter:
    def __init__(self, items: tuple[MxikCandidate, ...] = FAKE_MXIK) -> None:
        self._items = items

    async def search(self, query: str, limit: int) -> list[MxikCandidate]:
        q = query.lower()
        return [c for c in self._items if q in c.name.lower() or c.code.startswith(q)][:limit]

    async def get(self, code: str) -> MxikCandidate | None:
        return next((c for c in self._items if c.code == code), None)


class RedisMxikCache:
    """Platform-wide cache: ``mxik:<key>`` → ``{"at": epoch, "items": [...]}``.

    Kept for ``ttl_s`` (stale fallback, 21 §7), considered fresh for ``fresh_s``.
    """

    def __init__(
        self,
        redis: Callable[[], Redis],
        *,
        fresh_s: int,
        ttl_s: int,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._redis = redis
        self._fresh = fresh_s
        self._ttl = ttl_s
        self._clock = clock

    async def get(self, key: str) -> tuple[Any, bool] | None:
        raw = await self._redis().get(f"mxik:{key}")
        if raw is None:
            return None
        try:
            data = json.loads(raw)
        except ValueError:
            return None
        return data["items"], self._clock() - float(data["at"]) < self._fresh

    async def put(self, key: str, payload: Any) -> None:
        body = json.dumps({"at": self._clock(), "items": payload}, ensure_ascii=False)
        await self._redis().set(f"mxik:{key}", body, ex=self._ttl)
