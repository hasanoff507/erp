"""Helpers for the marking tests (B5-T07): GS1 DataMatrix test codes, the fake CRPT, the marking outbox/monitor
with an explicit clock, and a posted goods receipt with marked lines."""

from __future__ import annotations

import secrets
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from redis.asyncio import Redis

from app.core.db.session import Database
from app.modules.integrations.marking.domain.gs1 import GS, check_digit
from app.modules.integrations.marking.wiring import (
    acceptance_monitor,
    fake_marking_adapter,
    marking_outbox_service,
)
from tests.conftest import MigratedDb
from tests.support.catalog import catalog_app, catalog_settings
from tests.support.sales import Env, Pos, execute, reset_fake_fm, rows

API = "/api/v1"


def gtin(body: str = "0478006900004") -> str:
    """GTIN-14 from 13 digits + the GS1 check digit."""
    return body + str(check_digit(body))


def code(serial: str | None = None, *, gtin_body: str = "0478006900004", tail: str = "dGVz",
         expiry: str | None = None) -> str:  # fmt: skip
    """An Asl belgisi unit code: (01) GTIN (21) serial <GS> [(17) expiry] (93) crypto tail."""
    serial = serial or secrets.token_hex(6)
    middle = f"17{expiry}" if expiry else ""
    return f"01{gtin(gtin_body)}21{serial}{GS}{middle}93{tail}"


@pytest.fixture(name="crpt")
def fake_crpt_fixture() -> Iterator[Any]:
    fake = fake_marking_adapter()
    fake.reset()
    yield fake
    fake.reset()


class Clock:
    def __init__(self, at: datetime) -> None:
        self.at = at

    def __call__(self) -> datetime:
        return self.at


async def run_outbox(env: Env, tenant_id: UUID, clock: Clock | None = None) -> list[Any]:
    """Drain the tenant's marking outbox (jobs made due now — the test DB clock may step back ~1 s)."""
    await execute(
        env.db, tenant_id,
        "UPDATE app.outbox_jobs SET next_run_at = now() - interval '1 hour' WHERE kind LIKE 'marking_%' "
        "AND status IN ('queued', 'retry')",
    )  # fmt: skip
    service = marking_outbox_service(env.db.session_factory, env.settings, clock=clock)
    return await service.process_due(tenant_id)


async def run_monitor(env: Env, tenant_id: UUID, now: datetime) -> Any:
    return await acceptance_monitor(env.db.session_factory).run(tenant_id, now)


async def jobs(env: Env, tenant_id: UUID, kind: str) -> list[dict[str, Any]]:
    return await rows(
        env.db, tenant_id,
        "SELECT id, status, attempts, payload, idempotency_key, last_error FROM app.outbox_jobs WHERE kind = :k "
        "ORDER BY id",
        k=kind,
    )  # fmt: skip


async def events(env: Env, tenant_id: UUID, kind: str) -> list[dict[str, Any]]:
    found = await rows(
        env.db, tenant_id,
        "SELECT payload, idempotency_key FROM app.outbox_jobs WHERE kind = 'telegram' "
        "AND payload ->> 'event' = :k ORDER BY id",
        k=kind,
    )  # fmt: skip
    return [r["payload"] for r in found]


async def set_precheck(env: Env, pos: Pos, mode: str) -> None:
    await execute(
        env.db, pos.tenant_id,
        "UPDATE app.tenants SET settings = settings || jsonb_build_object('marking_precheck', CAST(:m AS text))",
        m=mode,
    )  # fmt: skip


async def receive_marked(
    env: Env, pos: Pos, product_id: UUID, codes: list[str], *, doc_date: date, cost: str = "5000.0000"
) -> dict[str, Any]:
    """A posted goods receipt (19 §8) of ``codes`` (one unit each) into the shop's sale warehouse."""
    from tests.support.purchasing import create_supplier, gr_line, posted_receipt

    supplier = await create_supplier(
        env.client, pos.shop, "Hayot Suv MChJ", stir=f"3{secrets.randbelow(10**8):08d}"
    )
    line = gr_line(product_id, f"{len(codes)}.000", cost, marking_codes=codes)
    return await posted_receipt(
        env.client, pos.shop, supplier["id"], pos.warehouse_id, [line], doc_date=doc_date
    )


def at(raw: str) -> datetime:
    return datetime.fromisoformat(raw).astimezone(UTC)


@pytest.fixture(name="env")
async def marking_env_fixture(
    oauth_platform: None,
    app_db: Database,
    clean_redis: Redis,
    migrated_db: MigratedDb,
    redis_url: str,
    tmp_path: Path,
) -> AsyncIterator[Env]:
    """The sales test app (fake FM, fake card terminals) with ``ERP_MARKING_PROVIDER=fake``."""
    reset_fake_fm()
    fake_marking_adapter().reset()
    settings = catalog_settings(
        migrated_db, redis_url, tmp_path / "files", fiscal_provider="fake", card_fake_terminals=True,
        marking_provider="fake", marking_verify_timeout_s=0.3, einvoice_provider="fake",
    )  # fmt: skip
    async with catalog_app(settings) as (app, client):
        yield Env(settings, app, client, app_db)
    reset_fake_fm()
    fake_marking_adapter().reset()
