"""MXIK search/lookup (19 §1, 21 §7): real tasnif adapter over httpx MockTransport, real Redis cache."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from redis.asyncio import Redis

from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from app.modules.catalog.application.mxik import MxikService
from app.modules.catalog.domain.mxik import MxikCandidate
from app.modules.catalog.infrastructure.mxik import (
    LOOKUP_PATH,
    SEARCH_PATH,
    RedisMxikCache,
    TasnifMxikAdapter,
    parse_candidates,
)
from app.modules.catalog.wiring import build_catalog_module, build_mxik_port
from tests.support.catalog import Env, catalog_env_fixture

pytestmark = [pytest.mark.redis]
__all__ = ["catalog_env_fixture"]

COLA = {"mxikCode": "02202001001000000", "name": "Gazlangan ichimlik", "vat": 12}


class Tasnif:
    """A local stand-in for tasnif.soliq.uz behind httpx.MockTransport; ``down`` simulates an outage."""

    def __init__(self) -> None:
        self.down = False
        self.calls: list[httpx.Request] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        if self.down:
            raise httpx.ConnectError("tasnif.soliq.uz unreachable", request=request)
        if request.url.path.endswith(SEARCH_PATH):
            q = request.url.params["search"]
            hits = [COLA] if q in "gazlangan ichimlik" else []
            return httpx.Response(200, json={"success": True, "data": hits})
        if request.url.path.endswith(LOOKUP_PATH):
            code = request.url.params["mxikCode"]
            return httpx.Response(200, json={"data": COLA} if code == COLA["mxikCode"] else {"data": None})
        return httpx.Response(404)


def make_service(fake: Tasnif, redis: Redis, *, fresh_s: int = 3600) -> MxikService:
    adapter = TasnifMxikAdapter(
        "https://tasnif.test/api/cls-api", transport=httpx.MockTransport(fake.handler)
    )
    cache = RedisMxikCache(lambda: redis, fresh_s=fresh_s, ttl_s=3600)
    return MxikService(adapter, cache, retry_base_s=0.0, retry_cap_s=0.0, max_attempts=3)


async def test_tasnif_adapter_search_get_and_cache(clean_redis: Redis) -> None:
    fake = Tasnif()
    service = make_service(fake, clean_redis)
    found = await service.search("Gazlangan", 20)
    assert found.source == "live"
    assert found.items == (MxikCandidate("02202001001000000", "Gazlangan ichimlik", "12.00"),)
    assert fake.calls[0].url.params["lang"] == "uz" and fake.calls[0].url.params["size"] == "20"
    again = await service.search("  gazlangan ", 20)
    assert again.source == "cache" and again.items == found.items and len(fake.calls) == 1
    got = await service.get("02202001001000000")
    assert got.source == "live" and got.items[0].vat_hint == "12.00"
    with pytest.raises(AppError) as missing:
        await service.get("99999999999999999")
    assert missing.value.code is ErrorCode.NOT_FOUND and missing.value.params == {"resource": "mxik_code"}
    with pytest.raises(AppError) as invalid:
        await service.get("12345")
    assert invalid.value.code is ErrorCode.MXIK_CODE_INVALID


async def test_outage_retries_then_serves_stale_cache(clean_redis: Redis) -> None:
    fake = Tasnif()
    warm = make_service(fake, clean_redis, fresh_s=0)  # everything is immediately stale
    assert (await warm.get("02202001001000000")).source == "live"
    fake.down = True
    calls_before = len(fake.calls)
    stale = await warm.get("02202001001000000")
    assert stale.source == "stale_cache" and stale.items[0].code == "02202001001000000"
    assert len(fake.calls) - calls_before == 3  # 21 §7: max_attempts=3
    nothing = await warm.search("hech narsa", 5)
    assert nothing.source == "stale_cache" and nothing.items == ()  # no hard error (19 §1)
    unknown = await warm.get("11111111111111111")
    assert unknown.source == "stale_cache" and unknown.items == ()


def test_parse_candidates_tolerates_shapes() -> None:
    assert parse_candidates({"data": {"content": [COLA, {"code": "bad"}]}})[0].code == COLA["mxikCode"]
    assert parse_candidates([{"mxik_code": "10701001001000000", "nameUz": "Non", "vatPercent": "0"}]) == [
        MxikCandidate("10701001001000000", "Non", "0.00")
    ]
    assert parse_candidates(None) == [] and parse_candidates("x") == []


async def test_mxik_endpoints_with_dev_fake(env: Env) -> None:
    shop = await env.shop("MXIK")
    h = shop.h(key=None)
    found = await env.client.get("/api/v1/mxik-codes", params={"query": "coca", "limit": 5}, headers=h)
    assert found.status_code == 200, found.text
    body: dict[str, Any] = found.json()
    assert list(body) == ["items"] and body["items"][0]["code"] == "02202001001000000"
    one = await env.client.get("/api/v1/mxik-codes/02202001001000000", headers=h)
    assert one.status_code == 200 and one.json()["items"][0]["vat_hint"] == "12.00"
    assert one.json()["source"] in ("live", "cache")
    bad = await env.client.get("/api/v1/mxik-codes/12", headers=h)
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "MXIK_CODE_INVALID"
    missing = await env.client.get("/api/v1/mxik-codes/99999999999999999", headers=h)
    assert missing.status_code == 404 and missing.json()["error"]["params"] == {"resource": "mxik_code"}
    too_many = await env.client.get("/api/v1/mxik-codes", params={"query": "a", "limit": 21}, headers=h)
    assert too_many.status_code == 422
    # MXIK is platform data: cached in Redis, never in a tenant table
    assert json.loads(await env.app.state.redis.get("mxik:code:02202001001000000"))["items"]


def test_fake_provider_is_refused_in_production(env: Env) -> None:
    prod = env.settings.model_copy(update={"environment": "prod"})
    with pytest.raises(RuntimeError, match="qaror #34"):
        build_mxik_port(prod)
    real = build_mxik_port(env.settings.model_copy(update={"mxik_provider": "tasnif"}))
    assert isinstance(real, TasnifMxikAdapter)
    assert build_catalog_module(env.settings, env.db, lambda: env.app.state.redis).mxik is not None
