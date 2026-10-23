"""QT-M19-01 (Telegram part, 33 §13.3): W-04 pairing and W-05 revoke queue the M18 ``onec_agent_paired`` event
(``outbox_jobs(kind='telegram')``) in the same transaction."""

from __future__ import annotations

import pytest
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.db.session import Database
from tests.conftest import MigratedDb
from tests.support.agent import agent_platform, pair_agent
from tests.support.branches import api, make_shop

pytestmark = [pytest.mark.db, pytest.mark.redis]


async def test_qt_m19_01_agent_paired_telegram_event(
    oauth_platform: None,
    migrated_db: MigratedDb,
    redis_url: str,
    clean_redis: Redis,
    migrator_engine: AsyncEngine,
    app_db: Database,
    admin_engine: AsyncEngine,
) -> None:
    await agent_platform(migrator_engine)
    async with api(migrated_db, redis_url) as (_, client):
        shop = await make_shop(app_db, client)
        fx = await pair_agent(client, shop, admin_engine)
        revoked = await client.post(
            f"/api/v1/onec-agents/{fx.agent_id}/revoke",
            json={"reason": "user"},
            headers=shop.owner.headers(write=True),
        )
        assert revoked.status_code == 200, revoked.text
    async with admin_engine.connect() as conn:
        rows = (
            await conn.execute(
                text(
                    "SELECT payload FROM app.outbox_jobs WHERE tenant_id = :t AND kind = 'telegram' "
                    "AND payload->>'event' = 'onec_agent_paired' ORDER BY id"
                ),
                {"t": shop.tenant_id},
            )
        ).all()
    states = [r[0]["state"] for r in rows]
    assert states == ["connected", "disconnected"]
    assert all(r[0]["agent_id"] == str(fx.agent_id) and r[0]["name"] == "DOKON-PC" for r in rows)
