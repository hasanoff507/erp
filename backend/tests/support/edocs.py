"""Helpers for the e-documents tests (Bosqich 5, b5-edocs: e-invoices, e-TTN, powers of attorney, E-IMZO).

The app runs with the fake e-invoice operator, the fake E-IMZO verifier (``ERP_EIMZO_VERIFIER=fake``) and the
fake FM. Workers (signed-document outbox, e-TTN outbox, operator poll) are driven directly with one shared
:class:`FakeEInvoiceAdapter`, so a test decides what the "operator" answers.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping, Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from redis.asyncio import Redis

from app.core.db.base import uuid7
from app.core.db.session import Database
from app.modules.access.domain.permissions import SystemRole
from app.modules.integrations.einvoice.application.ports import IncomingInvoice
from app.modules.integrations.einvoice.wiring import (
    FakeEInvoiceAdapter,
    doc_outbox_service,
    ettn_outbox_service,
    fake_pkcs7,
    inbox_poller,
)
from tests.conftest import MigratedDb
from tests.support.catalog import Env, Shop, catalog_app, catalog_settings
from tests.support.inventory import err, execute, rows, scalar

API = "/api/v1"
EI = f"{API}/einvoices"
ETTN = f"{API}/ettn-documents"
POA = f"{API}/powers-of-attorney"
ROLES = (
    SystemRole.OWNER,
    SystemRole.ACCOUNTANT,
    SystemRole.STOREKEEPER,
    SystemRole.MANAGER,
    SystemRole.CASHIER,
)

__all__ = [
    "API",
    "EI",
    "ETTN",
    "POA",
    "ROLES",
    "Env",
    "Shop",
    "edocs_env_fixture",
    "err",
    "execute",
    "incoming",
    "poll",
    "rows",
    "run_docs",
    "run_ettn",
    "scalar",
    "sign",
]


@pytest.fixture(name="env")
async def edocs_env_fixture(
    oauth_platform: None,
    app_db: Database,
    clean_redis: Redis,
    migrated_db: MigratedDb,
    redis_url: str,
    tmp_path: Path,
) -> AsyncIterator[Env]:
    settings = catalog_settings(
        migrated_db, redis_url, tmp_path / "files", einvoice_provider="fake", eimzo_verifier="fake",
        fiscal_provider="fake", card_fake_terminals=True,
    )  # fmt: skip
    async with catalog_app(settings) as (app, client):
        yield Env(settings, app, client, app_db)


async def sign(
    env: Env,
    shop: Shop,
    url: str,
    *,
    role: str = "owner",
    branch: UUID | None = None,
    submit: str = "submit-signed",
    action: str | None = None,
    extra: Mapping[str, Any] | None = None,
    content: str | None = None,
    expect: int | None = None,
) -> Any:
    """``sign-challenge`` → fake E-IMZO PKCS#7 over the ``document_hash`` → ``submit``; returns the response."""
    query = f"?action={action}" if action else ""
    challenge = await env.client.post(f"{url}/sign-challenge{query}", headers=shop.h(role, branch=branch))
    assert challenge.status_code == 200, challenge.text
    body = challenge.json()
    pkcs7 = fake_pkcs7(content if content is not None else body["document_hash"])
    response = await env.client.post(
        f"{url}/{submit}",
        json={"challenge_id": body["challenge_id"], "signature_pkcs7": pkcs7, **(extra or {})},
        headers=shop.h(role, branch=branch),
    )
    if expect is not None:
        assert response.status_code == expect, response.text
    return response


async def run_docs(env: Env, shop: Shop, port: FakeEInvoiceAdapter) -> list[Any]:
    await _due_now(env, shop)
    service = doc_outbox_service(env.db.session_factory, env.settings, port)
    return await service.process_due(shop.tenant_id)


async def run_ettn(env: Env, shop: Shop, port: FakeEInvoiceAdapter) -> list[Any]:
    await _due_now(env, shop)
    service = ettn_outbox_service(env.db.session_factory, env.settings, port)
    return await service.process_due(shop.tenant_id)


async def _due_now(env: Env, shop: Shop) -> None:
    """Queued at the API's DB ``now()``; the test DB clock may step back ~1 s — make every queued job due."""
    await execute(
        env, shop.tenant_id,
        "UPDATE app.outbox_jobs SET next_run_at = now() - interval '1 hour' WHERE status IN ('queued', 'retry')",
    )  # fmt: skip


async def poll(env: Env, shop: Shop, port: FakeEInvoiceAdapter) -> Any:
    return await inbox_poller(env.db.session_factory, env.settings, port).run(
        shop.tenant_id, now=datetime(2026, 10, 1, tzinfo=UTC)
    )


def incoming(
    seller_stir: str,
    lines: Sequence[Mapping[str, Any]],
    *,
    op_id: str | None = None,
    doc_date: date = date(2026, 10, 10),
    factura_type: str = "standard",
    related: str | None = None,
    ettn: Mapping[str, Any] | None = None,
    risk_flag: str = "unknown",
    updated_at: datetime | None = None,
) -> IncomingInvoice:
    """An inbox document in the normalised ``einvoices.payload`` shape (lines: qty / net_amount / vat_amount)."""
    total = sum(
        (Decimal(ln["net_amount"]) + Decimal(ln.get("vat_amount", "0")) for ln in lines), Decimal("0")
    )
    vat = sum((Decimal(ln.get("vat_amount", "0")) for ln in lines), Decimal("0"))
    payload: dict[str, Any] = {
        "number": f"EHF-{uuid7().hex[-6:]}", "doc_date": doc_date.isoformat(),
        "seller": {"stir": seller_stir, "name": f'"Seller {seller_stir}" MChJ'},
        "lines": [{"line_no": i + 1, **dict(ln)} for i, ln in enumerate(lines)],
        "total_amount": f"{total:.2f}", "vat_amount": f"{vat:.2f}",
    }  # fmt: skip
    if ettn is not None:
        payload["ettn"] = dict(ettn)
    return IncomingInvoice(
        operator_doc_id=op_id or f"OP-{uuid7().hex}",
        factura_type=factura_type,
        related_operator_doc_id=related,
        seller_stir=seller_stir,
        doc_date=doc_date,
        status="received",
        updated_at=updated_at or datetime(2026, 10, 10, 12, tzinfo=UTC),
        payload=payload,
        risk_flag=risk_flag,  # type: ignore[arg-type]
    )
