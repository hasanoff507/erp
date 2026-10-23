"""``GET /auth/terms`` + ``seed terms`` — the SPA reads the current Terms version before signup (qaror #61)."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from scripts.seed import publish_terms
from tests.conftest import MigratedDb
from tests.support.auth import auth_settings, running_app

pytestmark = [pytest.mark.db, pytest.mark.redis]

SHA_A = "a" * 64
SHA_B = "b" * 64


async def test_publish_terms_switches_the_current_version_and_endpoint_lists_it(
    migrated_db: MigratedDb, redis_url: str, migrator_engine: AsyncEngine, seeded: None
) -> None:
    await publish_terms(
        migrator_engine,
        kind="privacy",
        version="privacy-t1",
        text_url="https://erp.test/p1",
        text_sha256=SHA_A,
    )
    await publish_terms(
        migrator_engine,
        kind="privacy",
        version="privacy-t2",
        text_url="https://erp.test/p2",
        text_sha256=SHA_B,
    )
    async with running_app(auth_settings(migrated_db, redis_url)) as (_, client):
        response = await client.get("/auth/terms")
    assert response.status_code == 200
    items = response.json()["items"]
    privacy = [item for item in items if item["kind"] == "privacy"]
    assert [p["version"] for p in privacy] == ["privacy-t2"]  # only one current version per kind
    assert privacy[0]["text_url"] == "https://erp.test/p2"
    assert privacy[0]["text_sha256"] == SHA_B
    assert [i["kind"] for i in items] == sorted(i["kind"] for i in items)
