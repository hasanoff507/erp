"""Composition of the payments slice (23 §1 ``wiring.py``; 18 §16, 21 §9).

Public entry points: :func:`build_payments_module` (``app.state.payments``), :func:`checkout_expiry`
(cron job) and :func:`uzqr_port` (``ERP_UZQR_PROVIDER``: ``stub`` — real POS API ⛔ 26 #49;
``fake`` — never in prod).
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.db.session import Database
from app.modules.integrations.payments.application.checkouts import CheckoutExpirySweep, CheckoutService
from app.modules.integrations.payments.application.ports import UzqrPort, UzumQrPort
from app.modules.integrations.payments.application.webhooks import (
    ClickWebhook,
    PaymeWebhook,
    UzqrWebhook,
    UzumWebhook,
)
from app.modules.integrations.payments.infrastructure.sql import SqlCheckoutRepository, SqlTenantLookup
from app.modules.integrations.payments.infrastructure.uzqr import FakeUzqrAdapter, UzqrStubAdapter
from app.modules.integrations.payments.infrastructure.uzum_qr import UzumDynamicQrClient
from app.modules.integrations.tenant_keys.wiring import tenant_secrets

PAYMENTS_CHECKOUT_EXPIRE_JOB = "payments_checkout_expire"  # SAQ job: one tenant's expired pending checkouts

__all__ = [
    "PAYMENTS_CHECKOUT_EXPIRE_JOB",
    "FakeUzqrAdapter",
    "PaymentsModule",
    "build_payments_module",
    "checkout_expiry",
    "uzqr_port",
]


@dataclass(slots=True)
class PaymentsModule:
    checkouts: CheckoutService
    click: ClickWebhook
    payme: PaymeWebhook
    uzum: UzumWebhook
    uzqr: UzqrWebhook
    webhook_rate_per_min: int


def uzqr_port(settings: Settings) -> UzqrPort:
    """Dynamic UzQR (21 §9.1): the stub until the POS API arrives (26 #49); the fake only outside prod."""
    if settings.uzqr_provider == "fake":
        if settings.environment == "prod":
            raise RuntimeError("FakeUzqrAdapter is not allowed in prod (21 §9.1)")
        return FakeUzqrAdapter()
    return UzqrStubAdapter()


def build_payments_module(
    settings: Settings,
    db: Database,
    *,
    uzqr: UzqrPort | None = None,
    uzum_transport: httpx.AsyncBaseTransport | None = None,
) -> PaymentsModule:
    sf = db.session_factory
    repo = SqlCheckoutRepository()
    lookup = SqlTenantLookup(sf)
    secrets = tenant_secrets(settings)
    port = uzqr or uzqr_port(settings)
    uzum_qr: UzumQrPort = UzumDynamicQrClient(
        settings.uzum_dynamic_qr_base_url,
        timeout_s=settings.payments_http_timeout_s,
        transport=uzum_transport,
    )
    checkouts = CheckoutService(
        sf, repo, secrets, port, uzum_qr, ttl_s=settings.payments_checkout_ttl_s,
        click_url=settings.click_pay_url,
        payme_url=settings.payme_checkout_url, payme_test_url=settings.payme_test_checkout_url,
    )  # fmt: skip
    return PaymentsModule(
        checkouts=checkouts,
        click=ClickWebhook(sf, repo, lookup, secrets),
        payme=PaymeWebhook(sf, repo, lookup, secrets),
        uzum=UzumWebhook(sf, repo, lookup, secrets),
        uzqr=UzqrWebhook(sf, repo, lookup, secrets, port),
        webhook_rate_per_min=settings.payments_webhook_rate_per_min,
    )


def checkout_expiry(session_factory: async_sessionmaker[AsyncSession]) -> CheckoutExpirySweep:
    return CheckoutExpirySweep(session_factory, SqlCheckoutRepository())
