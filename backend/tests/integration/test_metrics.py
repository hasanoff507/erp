"""/metrics against real PostgreSQL + Redis (23 §8, 25 §5): HTTP series and SAQ queue depth."""

from __future__ import annotations

from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr

from app.core.config import Settings
from app.core.queue import make_queue
from app.main import create_app
from tests.conftest import MigratedDb

pytestmark = pytest.mark.db

TOKEN = "t" * 40


def _value(body: str, name: str, **labels: str) -> float | None:
    for line in body.splitlines():
        if line.startswith(f"{name}{{") and all(f'{k}="{v}"' in line for k, v in labels.items()):
            return float(line.rsplit(" ", 1)[1])
    return None


async def test_metrics_report_requests_pool_and_queue_depth(migrated_db: MigratedDb, redis_url: str) -> None:
    queue_name = f"metrics-{uuid4().hex[:8]}"
    queue = make_queue(redis_url, queue_name)
    try:
        for _ in range(2):
            await queue.enqueue("noop_for_metrics", tenant_id=str(uuid4()))
        settings = Settings(
            _env_file=None,
            environment="test",
            database_url=SecretStr(migrated_db.app_url),
            redis_url=SecretStr(redis_url),
            log_json=False,
            queue_name=queue_name,
            metrics_enabled=True,
            metrics_token=SecretStr(TOKEN),
        )
        app = create_app(settings)
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                assert (await client.get("/health/ready")).status_code == 200
                assert (await client.get("/metrics")).status_code == 401
                r = await client.get("/metrics", headers={"Authorization": f"Bearer {TOKEN}"})
    finally:
        await queue.redis.delete(*(f"saq:{queue_name}:{s}" for s in ("queued", "incomplete")))
        await queue.disconnect()
    assert r.status_code == 200
    body = r.text
    assert (_value(body, "erp_http_requests_total", route="/health/ready", status="200") or 0) >= 1
    assert _value(body, "erp_queue_jobs", queue=queue_name, state="queued") == 2.0
    assert _value(body, "erp_queue_jobs", queue=queue_name, state="active") == 0.0
    # the readiness probe used a pooled connection: the api pool is visible
    assert _value(body, "erp_db_pool_connections", pool="api", state="size") is not None
