"""``require_agent_capability(kind)`` (23 §3 "1C agent API"): an agent route of a device-service family
answers ``409 AGENT_CAPABILITY_DISABLED`` until the agent declared the family in ``hello``."""

from __future__ import annotations

import pytest
from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.db.session import Database
from app.modules.onec_integration.api.deps import require_agent_capability
from app.modules.onec_integration.wiring import AgentPrincipal
from tests.conftest import MigratedDb
from tests.support.agent import FULL_CAPABILITIES, agent_platform, hello, pair_agent
from tests.support.branches import api, make_shop

pytestmark = [pytest.mark.db, pytest.mark.redis]


def _probe() -> APIRouter:
    router = APIRouter()

    @router.get("/onec-agent/probe/fiscal")
    async def fiscal(
        agent: AgentPrincipal = Depends(require_agent_capability("fiscal.status")),  # noqa: B008
    ) -> dict[str, str]:
        return {"agent_id": str(agent.agent_id)}

    return router


async def test_onec_agent_require_agent_capability(
    oauth_platform: None,
    migrated_db: MigratedDb,
    redis_url: str,
    clean_redis: Redis,
    migrator_engine: AsyncEngine,
    app_db: Database,
    admin_engine: AsyncEngine,
) -> None:
    await agent_platform(migrator_engine)
    async with api(migrated_db, redis_url, _probe()) as (_, client):
        fx = await pair_agent(client, await make_shop(app_db, client), admin_engine)
        before = await client.get("/api/v1/onec-agent/probe/fiscal", headers=fx.headers())
        assert before.status_code == 409 and before.json()["error"]["code"] == "AGENT_CAPABILITY_DISABLED"
        assert before.json()["error"]["params"]["family"] == "fiscal"
        await hello(client, fx, FULL_CAPABILITIES)
        after = await client.get("/api/v1/onec-agent/probe/fiscal", headers=fx.headers())
        assert after.status_code == 200 and after.json() == {"agent_id": str(fx.agent_id)}
    with pytest.raises(ValueError, match="device-service"):
        require_agent_capability("write_object")
