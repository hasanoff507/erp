"""Tenant settings — BO-14 Bosqich 1 part (20 #40a/#40b/#40c/#40h), QT-M17-08 (settings part). Real PG + Redis."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import timedelta

import httpx
import pytest
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.db.session import Database
from app.modules.access.domain.permissions import SystemRole
from app.modules.branches.domain.model import next_month_start, tashkent_today
from tests.conftest import MigratedDb
from tests.support.branches import add_member, api, audit_rows, ensure_current_terms, make_shop, scalar

pytestmark = [pytest.mark.db, pytest.mark.redis]


@pytest.fixture
async def client(
    oauth_platform: None, migrated_db: MigratedDb, redis_url: str, clean_redis: Redis
) -> AsyncIterator[httpx.AsyncClient]:
    async with api(migrated_db, redis_url) as (_, c):
        yield c


async def test_get_settings_defaults(client: httpx.AsyncClient, app_db: Database) -> None:
    shop = await make_shop(app_db, client, "Mega Market")
    r = await client.get("/api/v1/tenant/settings", headers=shop.owner.headers())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["name"] == "Mega Market" and body["legal_form"] == "llc" and body["version"] == 1
    assert body["go_live_date"] is None and body["accepted_terms_version"] is None
    assert body["settings"] == {
        "bank_account": None, "bank_mfo": None, "supplier_overpay_policy": "warn",
        "vat_diff_tolerance_amount": "1000.00", "marking_precheck": "warn", "discount_posting": "gross_9050",
        "owner_withdrawal_account": "4890", "payment_org_commission_account": "9430",
        "turnover_tax_account": "9430", "negative_stock_policy": "allow", "ai_training_consent": False,
        "ai_cross_border_enabled": False, "card_manual_fallback": "manager_approval",
        "fiscal_policy": {"debt_receipt_split": "single", "credit_sale_receipt": "none"},
    }  # fmt: skip
    assert body["tax_regime"] == {"current": None, "history": []}
    assert body["integrations"]["ofd"] == {"status": "not_connected"}
    assert body["integrations"]["crpt"] == {"status": "not_connected", "key_last4": None}
    assert body["integrations"]["uzqr"] == {
        "status": "not_connected",
        "connected_at": None,
        "cash_register_ids": [],
    }


async def test_patch_settings_merges_and_audits(
    client: httpx.AsyncClient, app_db: Database, admin_engine: AsyncEngine
) -> None:
    shop = await make_shop(app_db, client)
    h = shop.owner.headers
    r = await client.patch(
        "/api/v1/tenant/settings",
        json={
            "name": "Yangi nom", "legal_form": "sole_proprietor",
            "settings": {"marking_precheck": "block", "bank_account": "2020" + "0" * 16, "bank_mfo": "00450",
                         "fiscal_policy": {"credit_sale_receipt": "credit_type"}},
            "version": 1,
        },
        headers=h(write=True),
    )  # fmt: skip
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["name"] == "Yangi nom" and body["version"] == 2
    assert body["settings"]["marking_precheck"] == "block"
    assert body["settings"]["owner_withdrawal_account"] == "8720"  # default follows legal_form (13 §2.18)
    assert body["settings"]["fiscal_policy"] == {
        "debt_receipt_split": "single",
        "credit_sale_receipt": "credit_type",
    }
    assert "tax_regime" not in body

    # merge: a later partial update keeps earlier keys
    r2 = await client.patch(
        "/api/v1/tenant/settings",
        json={
            "settings": {"fiscal_policy": {"debt_receipt_split": "per_sale"}, "bank_mfo": None},
            "version": 2,
        },
        headers=h(write=True),
    )
    assert r2.status_code == 200, r2.text
    s = r2.json()["settings"]
    assert s["fiscal_policy"] == {"debt_receipt_split": "per_sale", "credit_sale_receipt": "credit_type"}
    assert (
        s["marking_precheck"] == "block" and s["bank_mfo"] is None and s["bank_account"] == "2020" + "0" * 16
    )

    stale = await client.patch(
        "/api/v1/tenant/settings", json={"name": "Eski", "version": 1}, headers=h(write=True)
    )
    assert stale.status_code == 409 and stale.json()["error"]["params"]["current_version"] == 3
    audit = await audit_rows(admin_engine, shop.tenant_id, "tenant_settings_updated")
    assert len(audit) == 2
    assert (
        "settings.marking_precheck" in audit[0]["after"]["changed"]
        and "legal_form" in audit[0]["after"]["changed"]
    )


@pytest.mark.parametrize(
    "body",
    [
        {"settings": {"bank_account": "123"}},
        {"settings": {"bank_account": "1" * 21}},
        {"settings": {"vat_diff_tolerance_amount": "-1.00"}},
        {"settings": {"vat_diff_tolerance_amount": "10"}},
        {"settings": {"marking_precheck": "strict"}},
        {"settings": {"marking_precheck": None}},
        {"settings": {"negative_stock_policy": "forbid"}},
        {"settings": {"fiscal_policy": {"debt_receipt_split": "never"}}},
        {"settings": {"unknown_key": True}},
        {"legal_form": "ooo"},
        {"name": "A"},
    ],
)
async def test_patch_settings_validation(
    client: httpx.AsyncClient, app_db: Database, body: dict[str, object]
) -> None:
    shop = await make_shop(app_db, client)
    r = await client.patch(
        "/api/v1/tenant/settings", json={**body, "version": 1}, headers=shop.owner.headers(write=True)
    )
    assert r.status_code == 422, (body, r.text)
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_qt_m17_08_consent_and_terms_fields_are_not_patchable(
    client: httpx.AsyncClient, app_db: Database, admin_engine: AsyncEngine
) -> None:
    """QT-M17-08 (settings part): PATCH cannot touch accepted_terms_* / ai_cross_border_enabled / go_live_date;
    the AI cross-border consent changes only via POST /tenant/consents (owner)."""
    shop = await make_shop(app_db, client)
    h = shop.owner.headers
    for body in (
        {"settings": {"ai_cross_border_enabled": True}, "version": 1},
        {"ai_cross_border_enabled": True, "version": 1},
        {"accepted_terms_version": "v9", "version": 1},
        {"accepted_terms_at": "2026-10-01T00:00:00Z", "version": 1},
        {"go_live_date": "2026-10-01", "version": 1},
    ):
        r = await client.patch("/api/v1/tenant/settings", json=body, headers=h(write=True))
        assert r.status_code == 422, (body, r.text)
    assert (await client.get("/api/v1/tenant/settings", headers=h())).json()["settings"][
        "ai_cross_border_enabled"
    ] is False

    current = await ensure_current_terms(admin_engine)
    wrong = await client.post(
        "/api/v1/tenant/consents",
        json={"purpose": "ai_cross_border", "terms_version": "v0-old", "accepted": True},
        headers=h(write=True),
    )
    assert wrong.status_code == 422
    assert wrong.json()["error"]["params"] == {"current_version": current}
    assert wrong.json()["error"]["details"] == [
        {"field": "terms_version", "message_key": "validation.terms_version_not_current"}
    ]
    bad_purpose = await client.post(
        "/api/v1/tenant/consents", json={"purpose": "marketing", "terms_version": current, "accepted": True},
        headers=h(write=True),
    )  # fmt: skip
    assert bad_purpose.status_code == 422

    given = await client.post(
        "/api/v1/tenant/consents",
        json={"purpose": "ai_cross_border", "terms_version": current, "accepted": True},
        headers=h(write=True),
    )
    assert given.status_code == 201, given.text
    assert (
        given.json()["accepted"] is True
        and given.json()["ai_cross_border_enabled"] is True
        and given.json()["at"]
    )
    settings = (await client.get("/api/v1/tenant/settings", headers=h())).json()
    assert settings["settings"]["ai_cross_border_enabled"] is True

    withdrawn = await client.post(
        "/api/v1/tenant/consents",
        json={"purpose": "ai_cross_border", "terms_version": current, "accepted": False},
        headers=h(write=True),
    )
    assert withdrawn.status_code == 201 and withdrawn.json()["ai_cross_border_enabled"] is False
    rows = await scalar(
        app_db, shop.tenant_id, "SELECT count(*) FROM app.consents WHERE tenant_id = :t AND user_id = :u",
        t=shop.tenant_id, u=shop.owner.user_id,
    )  # fmt: skip
    assert rows == 2  # append-only trail: given + withdrawn
    audit = await audit_rows(admin_engine, shop.tenant_id, "consent.ai_cross_border_changed")
    assert [a["after"]["ai_cross_border_enabled"] for a in audit] == [True, False]

    # only the owner: a manager cannot give the consent
    manager = await add_member(app_db, client, shop, SystemRole.MANAGER)
    denied = await client.post(
        "/api/v1/tenant/consents",
        json={"purpose": "ai_cross_border", "terms_version": current, "accepted": True},
        headers=manager.headers(write=True),
    )
    assert denied.status_code == 403 and denied.json()["error"]["code"] == "OWNER_ONLY"


async def test_owner_only_and_accountant_tolerance_exception(
    client: httpx.AsyncClient, app_db: Database
) -> None:
    """20 #40b: settings.tenant is the owner's; vat_diff_tolerance_amount alone — tax.compare.review too (qaror #50)."""
    shop = await make_shop(app_db, client)
    accountant = await add_member(app_db, client, shop, SystemRole.ACCOUNTANT)
    get = await client.get("/api/v1/tenant/settings", headers=accountant.headers())
    assert get.status_code == 403 and get.json()["error"]["code"] == "OWNER_ONLY"
    ok = await client.patch(
        "/api/v1/tenant/settings",
        json={"settings": {"vat_diff_tolerance_amount": "2500.00"}, "version": 1},
        headers=accountant.headers(write=True),
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["settings"]["vat_diff_tolerance_amount"] == "2500.00"
    more = await client.patch(
        "/api/v1/tenant/settings",
        json={"settings": {"vat_diff_tolerance_amount": "3000.00", "marking_precheck": "off"}, "version": 2},
        headers=accountant.headers(write=True),
    )
    assert more.status_code == 403 and more.json()["error"]["code"] == "OWNER_ONLY"
    cashier = await add_member(app_db, client, shop, SystemRole.CASHIER)
    tolerance_only = await client.patch(
        "/api/v1/tenant/settings",
        json={"settings": {"vat_diff_tolerance_amount": "1.00"}, "version": 2},
        headers=cashier.headers(write=True),
    )
    assert tolerance_only.status_code == 403


async def test_tax_regime_from_next_month_only(
    client: httpx.AsyncClient, app_db: Database, admin_engine: AsyncEngine
) -> None:
    shop = await make_shop(app_db, client)
    h = shop.owner.headers
    nxt = next_month_start(tashkent_today())
    for wrong in (tashkent_today(), nxt + timedelta(days=1), next_month_start(nxt)):
        r = await client.post(
            "/api/v1/tenant/tax-regimes",
            json={"regime": "vat", "valid_from": wrong.isoformat()},
            headers=h(write=True),
        )
        assert r.status_code == 422, wrong
        assert r.json()["error"]["details"][0]["field"] == "valid_from"
    ok = await client.post(
        "/api/v1/tenant/tax-regimes",
        json={"regime": "vat", "valid_from": nxt.isoformat()},
        headers=h(write=True),
    )
    assert ok.status_code == 201, ok.text
    assert ok.json() == {"regime": "vat", "valid_from": nxt.isoformat()}
    changed_mind = await client.post(
        "/api/v1/tenant/tax-regimes",
        json={"regime": "turnover", "valid_from": nxt.isoformat()},
        headers=h(write=True),
    )
    assert changed_mind.status_code == 201
    block = (await client.get("/api/v1/tenant/settings", headers=h())).json()["tax_regime"]
    assert block == {"current": None, "history": [{"regime": "turnover", "valid_from": nxt.isoformat()}]}
    assert len(await audit_rows(admin_engine, shop.tenant_id, "tax_regime_change_scheduled")) == 2
