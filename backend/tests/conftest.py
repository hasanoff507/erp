"""Shared fixtures.

Real PostgreSQL 16 and Redis are used for everything under ``tests/integration``:
either the CI service containers (``ERP_TEST_PG_ADMIN_URL`` /
``ERP_TEST_REDIS_URL``) or containers started with testcontainers.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

import pytest
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.db.session import Database, make_engine
from tests.support.bootstrap import APP_PASSWORD, MIGRATOR_PASSWORD, bootstrap_database, upgrade_head


@dataclass(frozen=True)
class PgUrls:
    admin: str  # superuser, maintenance db
    host: str
    port: int

    def url(self, user: str, password: str, db: str) -> str:
        return f"postgresql+asyncpg://{user}:{password}@{self.host}:{self.port}/{db}"


def _with_asyncpg(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit(parts._replace(scheme="postgresql+asyncpg"))


@pytest.fixture(scope="session")
def pg_server() -> Iterator[PgUrls]:
    admin = os.environ.get("ERP_TEST_PG_ADMIN_URL")
    if admin:
        parts = urlsplit(admin)
        yield PgUrls(_with_asyncpg(admin), parts.hostname or "localhost", parts.port or 5432)
        return
    from testcontainers.community.postgres import PostgresContainer

    with PostgresContainer(
        "postgres:16-alpine", username="postgres", password="postgres", dbname="postgres"
    ) as pg:
        host = pg.get_container_host_ip()
        port = int(pg.get_exposed_port(5432))
        yield PgUrls(f"postgresql+asyncpg://postgres:postgres@{host}:{port}/postgres", host, port)


@pytest.fixture(scope="session")
def redis_url() -> Iterator[str]:
    url = os.environ.get("ERP_TEST_REDIS_URL")
    if url:
        yield url
        return
    from testcontainers.community.redis import RedisContainer

    with RedisContainer("redis:7-alpine") as container:
        yield f"redis://{container.get_container_host_ip()}:{container.get_exposed_port(6379)}/0"


@dataclass(frozen=True)
class MigratedDb:
    name: str
    app_url: str
    migrator_url: str
    admin_url: str


@pytest.fixture(scope="session")
async def migrated_db(pg_server: PgUrls) -> MigratedDb:
    name = "erp_test"
    await bootstrap_database(pg_server.admin, name)
    migrator_url = pg_server.url("erp_migrator", MIGRATOR_PASSWORD, name)
    await asyncio.to_thread(upgrade_head, migrator_url)
    admin_db_url = pg_server.admin.rsplit("/", 1)[0] + f"/{name}"
    return MigratedDb(name, pg_server.url("erp_app", APP_PASSWORD, name), migrator_url, admin_db_url)


@pytest.fixture(scope="session")
async def app_db(migrated_db: MigratedDb) -> AsyncIterator[Database]:
    db = Database(make_engine(migrated_db.app_url, pool_size=5, max_overflow=5))
    yield db
    await db.dispose()


@pytest.fixture(scope="session")
async def migrator_engine(migrated_db: MigratedDb) -> AsyncIterator[AsyncEngine]:
    engine = make_engine(migrated_db.migrator_url, pool_size=2, max_overflow=0)
    yield engine
    await engine.dispose()


@pytest.fixture(scope="session")
async def admin_engine(migrated_db: MigratedDb) -> AsyncIterator[AsyncEngine]:
    """Superuser on the test database — only for fixtures that must bypass RLS."""
    engine = make_engine(migrated_db.admin_url, pool_size=2, max_overflow=0)
    yield engine
    await engine.dispose()


@pytest.fixture(scope="session")
async def seeded(migrator_engine: AsyncEngine) -> None:
    from scripts.seed import seed_global

    await seed_global(migrator_engine)


@pytest.fixture
async def redis(redis_url: str) -> AsyncIterator[Redis]:
    client = Redis.from_url(redis_url, decode_responses=True)
    yield client
    await client.aclose()


@pytest.fixture
async def clean_redis(redis: Redis) -> Redis:
    await redis.flushdb()
    return redis


async def scalar(engine: AsyncEngine, sql: str, **params: object) -> object:
    async with engine.connect() as conn:
        return (await conn.execute(text(sql), params)).scalar()


@pytest.fixture(scope="session")
async def oauth_platform(seeded: None, migrator_engine: AsyncEngine) -> None:
    """Deploy-time auth setup (12 §5.1): client secrets/redirects and an active signing key."""
    from app.core.config import Settings
    from app.modules.auth.infrastructure.key_admin import configure_client, rotate_signing_key
    from app.modules.auth.wiring import build_cipher
    from tests.support.auth import ANDROID_CALLBACK, BFF_SECRET, WEB_CALLBACK

    cipher = build_cipher(Settings(_env_file=None))
    await configure_client(
        migrator_engine, cipher, "web-bff", secret=BFF_SECRET, redirect_uris=[WEB_CALLBACK]
    )
    await configure_client(migrator_engine, cipher, "android-pos", redirect_uris=[ANDROID_CALLBACK])
    await rotate_signing_key(migrator_engine, cipher)
