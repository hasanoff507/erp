"""Composition root (23 §1): build the FastAPI app and its dependencies."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis

from app.core.config import Settings, get_settings
from app.core.db.session import Database
from app.core.errors import install_error_handlers
from app.core.health import ReadinessProbe, alembic_head, postgres_check, redis_check
from app.core.health import router as health_router
from app.core.idempotency import IdempotencyMiddleware, IdempotencyStore, PgIdempotencyStore, TenantResolver
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware
from app.modules.auth.api import admin_users as auth_admin_api
from app.modules.auth.api import bff as auth_bff_api
from app.modules.auth.api import oauth as auth_oauth_api
from app.modules.auth.wiring import build_auth_module


async def _token_tenant(request: Request) -> UUID | None:
    """Idempotency tenant from the verified token/BFF session — never from the body (23 §1)."""
    gateway = getattr(request.app.state, "auth", None)
    if gateway is None:
        return None
    tenant: UUID | None = await gateway.peek_tenant(request)
    return tenant


def create_app(
    settings: Settings | None = None, *, resolve_tenant: TenantResolver = _token_tenant
) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, json=settings.log_json)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        db = Database.from_settings(settings)
        redis = Redis.from_url(settings.redis_url.get_secret_value(), decode_responses=True)
        app.state.db = db
        app.state.redis = redis
        app.state.idempotency_store = PgIdempotencyStore(db.session_factory)
        auth = build_auth_module(settings, db, lambda: app.state.redis)
        app.state.auth_module = auth
        app.state.auth = auth.gateway  # core RS dependencies (app/core/auth)
        app.state.readiness = ReadinessProbe(
            gating={"postgres": postgres_check(db, alembic_head()), "redis": redis_check(redis)},
        )
        try:
            yield
        finally:
            await redis.aclose()
            await db.dispose()

    app = FastAPI(
        title="ERP API",
        version="0.1.0",
        lifespan=lifespan,
        openapi_url=f"{settings.api_prefix}/openapi.json",
    )
    install_error_handlers(app)

    def _redis() -> Redis:
        redis: Redis = app.state.redis
        return redis

    def _store() -> IdempotencyStore:
        store: IdempotencyStore = app.state.idempotency_store
        return store

    # Starlette runs the last added middleware first: request context is outermost
    app.add_middleware(
        IdempotencyMiddleware,
        redis=_redis,
        store=_store,
        resolve_tenant=resolve_tenant,
        lock_ttl_s=settings.idempotency_lock_ttl_s,
        api_prefix=settings.api_prefix,
    )
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    app.add_middleware(RequestContextMiddleware)

    app.include_router(health_router)
    app.include_router(auth_oauth_api.router)
    app.include_router(auth_bff_api.router)
    app.include_router(auth_bff_api.api_router, prefix=settings.api_prefix)
    app.include_router(auth_admin_api.router, prefix=settings.api_prefix)
    return app


def app_factory() -> FastAPI:
    """uvicorn entry point: ``uvicorn app.main:app_factory --factory``."""
    return create_app()
