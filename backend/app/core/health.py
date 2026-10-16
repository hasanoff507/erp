"""Health endpoints (23 §8, 17 §1): ``/health/live``, ``/health/ready`` and ``/health``.

Readiness is split into *gating* checks (PostgreSQL round-trip + Alembic
version at head, Redis) that decide the status code, and *reported* checks
that are informational only. ``GET /health`` (27 Bosqich 0 DoD) is the
liveness alias.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy import text

from app.core.db.session import Database

CheckStatus = Literal["ok", "fail"]
ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"
CHECK_TIMEOUT_S = 2.0


class HealthResponse(BaseModel):
    status: CheckStatus
    checks: dict[str, str] = {}


@dataclass
class ReadinessProbe:
    gating: dict[str, Callable[[], Awaitable[str]]] = field(default_factory=dict)
    reported: dict[str, Callable[[], Awaitable[str]]] = field(default_factory=dict)

    async def run(self) -> tuple[bool, dict[str, str]]:
        results: dict[str, str] = {}
        ok = True
        for name, check in self.gating.items():
            status = await _guard(check)
            results[name] = status
            ok = ok and status == "ok"
        for name, check in self.reported.items():
            results[name] = await _guard(check)
        return ok, results


async def _guard(check: Callable[[], Awaitable[str]]) -> str:
    try:
        return await asyncio.wait_for(check(), timeout=CHECK_TIMEOUT_S)
    except Exception as exc:  # health must report, not raise
        return f"fail: {type(exc).__name__}"


def alembic_head() -> str | None:
    script = ScriptDirectory.from_config(Config(str(ALEMBIC_INI)))
    return script.get_current_head()


def postgres_check(db: Database, expected_head: str | None) -> Callable[[], Awaitable[str]]:
    async def check() -> str:
        async with db.engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            if expected_head is None:
                return "ok"
            version = (await conn.execute(text("SELECT version_num FROM public.alembic_version"))).scalar()
            await conn.rollback()
        return "ok" if version == expected_head else f"fail: schema {version} != {expected_head}"

    return check


def redis_check(redis: Redis) -> Callable[[], Awaitable[str]]:
    async def check() -> str:
        await redis.ping()
        return "ok"

    return check


router = APIRouter(tags=["health"])


@router.get("/health", operation_id="health_get", response_model=HealthResponse)
@router.get("/health/live", operation_id="health_live", response_model=HealthResponse)
async def live() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get(
    "/health/ready",
    operation_id="health_ready",
    response_model=HealthResponse,
    responses={503: {"model": HealthResponse}},
)
async def ready(request: Request) -> JSONResponse:
    probe: ReadinessProbe = request.app.state.readiness
    ok, checks = await probe.run()
    body = HealthResponse(status="ok" if ok else "fail", checks=checks)
    return JSONResponse(body.model_dump(), status_code=200 if ok else 503)
