"""Composition root (23 §1): build the FastAPI app and its dependencies."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis

from app.core.body_limit import MULTIPART_MARGIN, BodyLimitMiddleware
from app.core.config import Settings, get_settings
from app.core.db.session import Database
from app.core.errors import install_error_handlers
from app.core.health import ReadinessProbe, alembic_head, postgres_check, redis_check
from app.core.health import router as health_router
from app.core.idempotency import IdempotencyMiddleware, IdempotencyStore, PgIdempotencyStore, TenantResolver
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware
from app.core.telemetry import install_telemetry, observe_engine
from app.modules.access.api import approval_requests as approval_requests_api
from app.modules.access.api import roles as access_roles_api
from app.modules.access.wiring import build_access_module
from app.modules.accounting.api import ledger as accounting_ledger_api
from app.modules.accounting.wiring import build_accounting_module
from app.modules.attachments.api import router as attachments_api
from app.modules.attachments.wiring import UPLOAD_LIMIT as ATTACHMENT_UPLOAD_LIMIT
from app.modules.attachments.wiring import build_attachments
from app.modules.auth.api import admin_users as auth_admin_api
from app.modules.auth.api import bff as auth_bff_api
from app.modules.auth.api import devices as auth_devices_api
from app.modules.auth.api import oauth as auth_oauth_api
from app.modules.auth.api import signup as auth_signup_api
from app.modules.auth.wiring import build_auth_module
from app.modules.billing.api import terms as billing_terms_api
from app.modules.branches.api import branches as branches_api
from app.modules.branches.api import cash_registers as cash_registers_api
from app.modules.branches.api import devices as devices_api
from app.modules.branches.api import tenant as tenant_api
from app.modules.branches.wiring import build_branches_module
from app.modules.cash.api import bank_settlements as cash_bank_settlements_api
from app.modules.cash.api import cash_movements as cash_movements_api
from app.modules.cash.api import shifts as cash_shifts_api
from app.modules.cash.wiring import build_approvals, build_cash_module
from app.modules.catalog.api import router as catalog_api
from app.modules.catalog.wiring import build_catalog_module
from app.modules.debts.api import counterparties as debts_counterparties_api
from app.modules.debts.api import debt_docs as debts_docs_api
from app.modules.debts.wiring import build_debts_module
from app.modules.expenses.api import router as expenses_api
from app.modules.expenses.wiring import build_expenses_module
from app.modules.imports.api import router as imports_api
from app.modules.imports.wiring import build_imports_module
from app.modules.integrations.card_terminal.api import router as card_terminal_api
from app.modules.integrations.card_terminal.wiring import build_card_terminal_module
from app.modules.integrations.fiscal.api import fiscal_receipts as fiscal_receipts_api
from app.modules.inventory.api import stock as inventory_stock_api
from app.modules.inventory.api import stock_counts as inventory_stock_counts_api
from app.modules.inventory.api import transfers as inventory_transfers_api
from app.modules.inventory.api import write_offs as inventory_write_offs_api
from app.modules.inventory.wiring import build_inventory_module
from app.modules.notifications.api import router as notifications_api
from app.modules.notifications.wiring import build_notifications_module
from app.modules.pricing.api import router as pricing_api
from app.modules.pricing.wiring import build_pricing_module
from app.modules.purchasing.api import goods_receipts as purchasing_goods_receipts_api
from app.modules.purchasing.api import purchase_orders as purchasing_purchase_orders_api
from app.modules.purchasing.api import supplier_payments as purchasing_supplier_payments_api
from app.modules.purchasing.api import supplier_returns as purchasing_supplier_returns_api
from app.modules.purchasing.wiring import build_purchasing_module, build_supplier_payments
from app.modules.reports.api import reports as reports_api
from app.modules.reports.wiring import build_reports_service
from app.modules.returns.api import returns as returns_api
from app.modules.returns.wiring import build_returns_queries
from app.modules.sales.api import sales as sales_api
from app.modules.sales.wiring import build_sales_module
from app.modules.sync.api import sync as sync_api
from app.modules.sync.api import sync_exceptions as sync_exceptions_api
from app.modules.sync.wiring import build_sync_module
from app.modules.vat.api import tax_settlements as tax_settlements_api
from app.modules.vat.api import vat as vat_api
from app.modules.vat.wiring import build_tax_settlement_service, build_vat_service


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
        observe_engine("api", db.engine.sync_engine)  # erp_db_pool_connections (25 §5)
        app.state.redis = redis
        app.state.idempotency_store = PgIdempotencyStore(db.session_factory)
        auth = build_auth_module(settings, db, lambda: app.state.redis)
        app.state.auth_module = auth
        app.state.auth = auth.gateway  # core RS dependencies (app/core/auth)
        # Bosqich 1 modules
        app.state.access_module = build_access_module(db)
        app.state.branches_module = build_branches_module(db, lambda: app.state.redis)
        app.state.catalog = build_catalog_module(settings, db, lambda: app.state.redis)
        app.state.pricing = build_pricing_module(db)
        app.state.imports = build_imports_module(settings, db)
        # Bosqich 2 modules (inventory/stock-counts/transfers, purchasing, debts, accounting)
        app.state.accounting = build_accounting_module(settings, db)
        app.state.inventory = build_inventory_module(settings, db)
        app.state.debts = build_debts_module(settings, db)
        app.state.purchasing = build_purchasing_module(settings, db)
        # Bosqich 3 modules (one anchor per slice — add your app.state lines right under your anchor)
        # --- B3 device-auth ---
        # --- B3 cash ---
        app.state.cash = build_cash_module(settings, db)
        app.state.approvals = build_approvals(settings, db, app.state.cash, lambda: app.state.redis)
        app.state.vat = build_vat_service(db)
        # --- B3 sales ---
        sales_module = build_sales_module(settings, db)
        app.state.sales = sales_module
        app.state.fiscal = sales_module.fiscal
        app.state.returns = build_returns_queries(db)
        # --- B3 card ---
        app.state.card_terminal = build_card_terminal_module(settings, db)
        # --- B3 sync ---
        app.state.sync = build_sync_module(settings, db, lambda: app.state.redis)
        # --- B3 print ---
        # Bosqich 4 modules (one anchor per slice — add your app.state lines right under your anchor)
        # --- B4 debts ---
        # --- B4 supplier-tax ---
        app.state.supplier_payments = build_supplier_payments(settings, db)
        app.state.tax_settlements = build_tax_settlement_service(db)
        # --- B4 expenses ---
        app.state.expenses = build_expenses_module(settings, db)
        app.state.attachments = build_attachments(settings, db)  # 17 §12 (BO-17 receipt photo)
        # --- B4 bank ---
        # bank settlements + statement import live in app.state.cash (build_cash_module, BO-24)
        # --- B4 reports ---
        app.state.reports = build_reports_service(db)
        # --- B4 telegram ---
        app.state.notifications = build_notifications_module(settings, db, lambda: app.state.redis)
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
    # 17 §12 / SEC-13: body size cap before idempotency/routing buffer the body;
    # added before CORS, so it runs inside it and the 413 keeps the CORS headers
    app.add_middleware(
        BodyLimitMiddleware,
        upload_paths={
            f"{settings.api_prefix}/import-jobs": settings.import_max_bytes + MULTIPART_MARGIN,
            # --- B4 expenses --- (17 §12 POST /attachments, multipart: PDF ≤ 20 MB)
            f"{settings.api_prefix}/attachments": ATTACHMENT_UPLOAD_LIMIT + MULTIPART_MARGIN,
            # --- B4 bank --- (20 #55g statement import, multipart)
            f"{settings.api_prefix}/bank-settlements/imports": settings.import_max_bytes + MULTIPART_MARGIN,
        },
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
    # telemetry (23 §8): metrics middleware outermost (sees the final status), /metrics, OTel
    install_telemetry(app, settings)

    app.include_router(health_router)
    app.include_router(auth_oauth_api.router)
    app.include_router(auth_bff_api.router)
    app.include_router(auth_bff_api.api_router, prefix=settings.api_prefix)
    app.include_router(auth_admin_api.router, prefix=settings.api_prefix)
    # Bosqich 1 routers
    app.include_router(auth_signup_api.router)  # /auth/otp/*, /auth/signup, /auth/credentials, /auth/google/*
    app.include_router(billing_terms_api.router)  # /auth/terms
    for module_router in (
        access_roles_api.router, devices_api.router, branches_api.router, cash_registers_api.router,
        tenant_api.router, catalog_api.router, pricing_api.router, imports_api.router,
    ):  # fmt: skip
        app.include_router(module_router, prefix=settings.api_prefix)
    # Bosqich 2 routers
    for module_router in (
        inventory_stock_api.router, inventory_transfers_api.router, inventory_stock_counts_api.router,
        inventory_write_offs_api.router, purchasing_purchase_orders_api.router,
        purchasing_goods_receipts_api.router, purchasing_supplier_returns_api.router,
        debts_counterparties_api.router, accounting_ledger_api.router,
    ):  # fmt: skip
        app.include_router(module_router, prefix=settings.api_prefix)
    # Bosqich 3 routers (one anchor per slice — add include_router lines right under your anchor)
    # --- B3 device-auth routers ---
    app.include_router(auth_devices_api.router)  # /auth/devices/register, /auth/pin/verify (14 §7.2, §4.3)
    # --- B3 cash routers ---
    for module_router in (
        cash_shifts_api.router, cash_movements_api.router, approval_requests_api.router, vat_api.router,
    ):  # fmt: skip
        app.include_router(module_router, prefix=settings.api_prefix)
    # --- B3 sales routers ---
    app.include_router(sales_api.router, prefix=settings.api_prefix)
    app.include_router(fiscal_receipts_api.router, prefix=settings.api_prefix)
    app.include_router(returns_api.router, prefix=settings.api_prefix)
    # --- B3 card routers ---
    app.include_router(card_terminal_api.router, prefix=settings.api_prefix)
    # --- B3 sync routers ---
    app.include_router(sync_api.router, prefix=settings.api_prefix)
    app.include_router(sync_exceptions_api.router, prefix=settings.api_prefix)
    # --- B3 print routers ---
    # Bosqich 4 routers (one anchor per slice — add include_router lines right under your anchor)
    # --- B4 debts routers ---
    app.include_router(debts_docs_api.router, prefix=settings.api_prefix)
    app.include_router(debts_docs_api.reports_router, prefix=settings.api_prefix)
    # --- B4 supplier-tax routers ---
    app.include_router(purchasing_supplier_payments_api.router, prefix=settings.api_prefix)
    app.include_router(tax_settlements_api.router, prefix=settings.api_prefix)
    # --- B4 expenses routers ---
    app.include_router(expenses_api.router, prefix=settings.api_prefix)
    app.include_router(attachments_api.router, prefix=settings.api_prefix)
    # --- B4 bank routers ---
    app.include_router(cash_bank_settlements_api.router, prefix=settings.api_prefix)
    # --- B4 reports routers ---
    app.include_router(reports_api.router, prefix=settings.api_prefix)
    # --- B4 telegram routers ---
    app.include_router(notifications_api.router, prefix=settings.api_prefix)  # 20 #66–#71 + bot webhook
    return app


def app_factory() -> FastAPI:
    """uvicorn entry point: ``uvicorn app.main:app_factory --factory``."""
    return create_app()
