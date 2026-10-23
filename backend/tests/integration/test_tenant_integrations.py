"""Integration keys — ``PUT/DELETE /tenant/integrations/{provider}`` (20 #40d/#40e), the ``tenant_secrets`` write
path (envelope encryption, 15 §4.2), the reader other slices use and the BO-14 status (20 #40a)."""

from __future__ import annotations

from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.db.base import uuid7
from app.core.db.rls import SECURITY_DEFINER_FUNCTIONS_0028A_PAYMENTS, missing_security_definer_functions
from app.core.db.session import tenant_transaction
from app.modules.integrations.tenant_keys.wiring import integration_status, tenant_secrets
from tests.support.payments import API, PayEnv, new_keys, payments_env_fixture, put_keys
from tests.support.sales import make_pos, one, rows

pytestmark = [pytest.mark.db, pytest.mark.redis]
__all__ = ["payments_env_fixture"]


async def test_ep20_40d_put_click_stores_encrypted_and_never_echoes(env: PayEnv) -> None:
    pos = await make_pos(env)
    keys = new_keys()
    response = await put_keys(env, pos, "click", keys.click)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["provider"] == "click" and body["status"] == "connected" and body["connected_at"]
    assert keys.click["secret_key"] not in response.text
    stored = await rows(
        env.db, pos.tenant_id, "SELECT kind, ciphertext, key_version, lookup_hash FROM app.tenant_secrets"
    )
    assert len(stored) == 1 and stored[0]["kind"] == "click" and stored[0]["lookup_hash"] is None
    raw = bytes(stored[0]["ciphertext"]).decode()
    assert raw.startswith("v1.") and keys.click["secret_key"] not in raw
    async with env.db.session_factory() as s, tenant_transaction(s, pos.tenant_id):
        secret = await tenant_secrets(env.settings).get(s, pos.tenant_id, "click")
    assert secret == {"merchant_id": "1001", "service_id": "2002", "secret_key": keys.click["secret_key"]}
    confirmed = await one(env.db, pos.tenant_id,
                          "SELECT settings->'payment_providers'->'click'->>'autofiscal_off_confirmed_at' FROM app.tenants")  # fmt: skip
    assert confirmed and confirmed.endswith("Z")
    audit = await rows(env.db, pos.tenant_id,
                       "SELECT action, after FROM app.audit_log WHERE entity = 'tenant_secrets'")  # fmt: skip
    assert [a["action"] for a in audit] == ["tenant_integration.connected"]
    assert audit[0]["after"]["fields"] == ["merchant_id", "secret_key", "service_id"]
    assert keys.click["secret_key"] not in str(audit[0]["after"])
    settings = await env.client.get(f"{API}/tenant/settings", headers=pos.shop.h("owner", key=None))
    assert settings.json()["integrations"]["click"]["status"] == "connected"
    assert keys.click["secret_key"] not in settings.text


async def test_ep20_40d_validation(env: PayEnv) -> None:
    pos = await make_pos(env)
    keys = new_keys()
    cases = [
        ("bitcoin", keys.click, "provider", "validation.invalid_choice"),
        ("click", {**keys.click, "provider_autofiscal_disabled_confirmed": False}, "provider_autofiscal_disabled_confirmed",
         "validation.autofiscal_confirmation_required"),
        ("click", {k: v for k, v in keys.click.items() if k != "secret_key"}, "secret_key", "validation.required"),
        ("click", {**keys.click, "key": "x"}, "key", "validation.extra_forbidden"),
        ("click", {**keys.click, "service_id": "abc"}, "service_id", "validation.invalid_format"),
        ("crpt", {"api_key": "k", "provider_autofiscal_disabled_confirmed": True},
         "provider_autofiscal_disabled_confirmed", "validation.extra_forbidden"),
        ("uzqr", {"merchant_id": "M", "terminal_id": "T", "api_key": "k"}, "cash_register_id", "validation.required"),
        ("uzum", {**keys.uzum, "dynamic_qr_user_id": None}, "dynamic_qr_user_id", "validation.required"),
    ]  # fmt: skip
    for provider, body, field, key in cases:
        response = await put_keys(env, pos, provider, body)
        assert response.status_code == 422, (provider, response.text)
        detail = response.json()["error"]["details"][0]
        assert (detail["field"], detail["message_key"]) == (field, key), (provider, detail)
    other = await make_pos(env, "Boshqa do'kon")
    response = await put_keys(env, pos, "uzqr", {**keys.uzqr, "cash_register_id": str(other.register_id)})
    assert response.status_code == 404 and response.json()["error"]["code"] == "NOT_FOUND"
    cashier = await put_keys(env, pos, "click", keys.click, role="cashier")
    assert cashier.status_code == 403
    assert await one(env.db, pos.tenant_id, "SELECT count(*) FROM app.tenant_secrets") == 0


async def test_ep20_40d_40e_replace_and_disconnect(env: PayEnv) -> None:
    pos = await make_pos(env)
    keys = new_keys()
    assert (await put_keys(env, pos, "payme", keys.payme)).status_code == 200
    rotated = {**keys.payme, "key": keys.payme["key"] + "-2", "test_mode": True}
    assert (await put_keys(env, pos, "payme", rotated)).status_code == 200
    row = await rows(env.db, pos.tenant_id, "SELECT rotated_at FROM app.tenant_secrets WHERE kind = 'payme'")
    assert len(row) == 1 and row[0]["rotated_at"] is not None
    async with env.db.session_factory() as s, tenant_transaction(s, pos.tenant_id):
        secret = await tenant_secrets(env.settings).get(s, pos.tenant_id, "payme")
    assert secret is not None and secret["key"] == rotated["key"] and secret["test_mode"] == "true"
    register = str(pos.register_id)
    assert (await put_keys(env, pos, "uzqr", {**keys.uzqr, "cash_register_id": register})).status_code == 200
    deleted = await env.client.delete(f"{API}/tenant/integrations/uzqr?cash_register_id={register}",
                                      headers=pos.shop.h("owner"))  # fmt: skip
    assert deleted.status_code == 204
    again = await env.client.delete(f"{API}/tenant/integrations/uzqr?cash_register_id={register}",
                                    headers=pos.shop.h("owner"))  # fmt: skip
    assert again.status_code == 404
    actions = await rows(env.db, pos.tenant_id,
                         "SELECT action FROM app.audit_log WHERE entity = 'tenant_secrets' ORDER BY id")  # fmt: skip
    assert [a["action"] for a in actions] == [
        "tenant_integration.connected", "tenant_integration.updated", "tenant_integration.connected",
        "tenant_integration.disconnected",
    ]  # fmt: skip


async def test_ep20_40d_payme_key_of_another_tenant_is_refused(env: PayEnv) -> None:
    first, second = await make_pos(env), await make_pos(env, "Ikkinchi do'kon")
    keys = new_keys()
    assert (await put_keys(env, first, "payme", keys.payme)).status_code == 200
    response = await put_keys(env, second, "payme", keys.payme)
    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["message_key"] == "validation.integration_key_in_use"


async def test_bo14_integration_status_read_model(env: PayEnv) -> None:
    pos = await make_pos(env)
    assert (await put_keys(env, pos, "crpt", {"api_key": "crpt-key-123456789"})).status_code == 200
    assert (await put_keys(env, pos, "didox", {"login": "123456789", "password": "p"})).status_code == 200
    reader = tenant_secrets(env.settings)
    async with env.db.session_factory() as s, tenant_transaction(s, pos.tenant_id):
        await reader.record_result(s, pos.tenant_id, "crpt", error="401 unauthorized")
        status = await integration_status(s)
    assert status["crpt"]["status"] == "connected" and status["crpt"]["key_last4"] == "6789"
    assert status["crpt"]["last_error"] == "401 unauthorized" and status["crpt"]["last_error_at"]
    assert status["didox"]["status"] == "connected" and status["click"]["status"] == "not_connected"
    async with env.db.session_factory() as s, tenant_transaction(s, pos.tenant_id):
        await reader.record_result(s, pos.tenant_id, "crpt")
        status = await integration_status(s)
    assert status["crpt"]["last_error"] is None and status["crpt"]["last_ok_at"]
    assert "crpt-key" not in str(status)


async def test_tenant_secret_bound_to_its_row(env: PayEnv) -> None:
    """A ciphertext copied to another tenant's row does not decrypt (aad binding, 15 §4.2)."""
    a, b = await make_pos(env), await make_pos(env, "B do'kon")
    assert (await put_keys(env, a, "crpt", {"api_key": "secret-a"})).status_code == 200
    assert (await put_keys(env, b, "crpt", {"api_key": "secret-b"})).status_code == 200
    stolen = await one(env.db, a.tenant_id, "SELECT ciphertext FROM app.tenant_secrets")
    await rows(env.db, b.tenant_id, "UPDATE app.tenant_secrets SET ciphertext = :c", c=stolen)
    async with env.db.session_factory() as s, tenant_transaction(s, b.tenant_id):
        assert await tenant_secrets(env.settings).get(s, b.tenant_id, "crpt") is None


async def test_payments_tenant_by_credential_function_exists(migrator_engine: AsyncEngine) -> None:
    async with migrator_engine.connect() as conn:
        assert await missing_security_definer_functions(conn, SECURITY_DEFINER_FUNCTIONS_0028A_PAYMENTS) == []


def _uuid(value: object) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))


async def test_tenant_secrets_rls_isolation(env: PayEnv) -> None:
    a, b = await make_pos(env), await make_pos(env, "C do'kon")
    assert (await put_keys(env, a, "crpt", {"api_key": "only-a"})).status_code == 200
    assert await one(env.db, b.tenant_id, "SELECT count(*) FROM app.tenant_secrets") == 0
    async with env.db.session_factory() as s, tenant_transaction(s, b.tenant_id):
        assert await tenant_secrets(env.settings).get(s, b.tenant_id, "crpt") is None
    assert _uuid(uuid7())
