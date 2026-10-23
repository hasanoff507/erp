"""``GET/PATCH /stock-settings`` (19 §17; US-M09-06 weight barcodes, US-M01-07) and its effect on the POS
``settings`` pull scope (16 §1 — a template change forces devices to re-read)."""

from __future__ import annotations

from typing import Any

import pytest

from app.modules.access.domain.permissions import SystemRole
from tests.support.sync import API, SyncEnv, pos_device, pull_ok, rows, sync_env_fixture

pytestmark = [pytest.mark.db, pytest.mark.redis]
__all__ = ["sync_env_fixture"]

URL = f"{API}/stock-settings"
DEFAULTS = [
    {"prefixes": ["22"], "item_code_len": 5, "value_len": 5, "value_kind": "WEIGHT", "decimals": 3,
     "enabled": True},
    {"prefixes": ["21"], "item_code_len": 5, "value_len": 5, "value_kind": "AMOUNT", "decimals": 0,
     "enabled": True},
]  # fmt: skip
CUSTOM = [
    {"prefixes": ["27", "28"], "item_code_len": 4, "value_len": 6, "value_kind": "WEIGHT", "decimals": 3,
     "enabled": True},
    {"prefixes": ["21"], "item_code_len": 5, "value_len": 5, "value_kind": "AMOUNT", "decimals": 0,
     "enabled": False},
]  # fmt: skip


def _err(response: Any) -> str:
    code: str = response.json()["error"]["code"]
    return code


def _fields(response: Any) -> list[tuple[str, str]]:
    return [(d["field"], d["message_key"]) for d in response.json()["error"].get("details", [])]


async def test_get_defaults_and_permissions(env: SyncEnv) -> None:
    shop = await env.shop("Tarozi", SystemRole.OWNER, SystemRole.CASHIER, SystemRole.STOREKEEPER)
    got = await env.client.get(URL, headers=shop.h("cashier", key=None))  # stock.view is enough to read
    assert got.status_code == 200, got.text
    body = got.json()
    assert body["weight_barcode_templates"] == DEFAULTS
    assert (body["low_stock_check_enabled"], body["expiry_warning_days"]) == (True, 7)
    assert isinstance(body["version"], int)

    denied = await env.client.patch(
        URL, json={"expiry_warning_days": 3, "version": body["version"]}, headers=shop.h("cashier")
    )
    assert denied.status_code == 403 and _err(denied) == "PERMISSION_DENIED"  # catalog.manage only
    ok = await env.client.patch(
        URL, json={"expiry_warning_days": 3, "version": body["version"]}, headers=shop.h("storekeeper")
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["expiry_warning_days"] == 3 and ok.json()["version"] == body["version"] + 1


async def test_qt_m09_06_patch_templates_audit_version_conflict_and_pull(env: SyncEnv) -> None:
    shop = await env.shop("Go'sht do'koni")
    pos = await pos_device(env, shop)
    first = await pull_ok(env, pos, scope="settings")
    old_version = first["settings"]["weight_barcode_version"]
    assert first["settings"]["weight_barcode_templates"] == DEFAULTS

    current = (await env.client.get(URL, headers=shop.h(key=None))).json()
    patched = await env.client.patch(
        URL,
        json={
            "weight_barcode_templates": CUSTOM,
            "low_stock_check_enabled": False,
            "version": current["version"],
        },
        headers=shop.h(),
    )
    assert patched.status_code == 200, patched.text
    body = patched.json()
    assert body["weight_barcode_templates"] == CUSTOM and body["low_stock_check_enabled"] is False
    assert body["expiry_warning_days"] == 7 and body["version"] == current["version"] + 1

    # stored in tenants.settings (other keys kept), tenants.version bumped
    [tenant] = await rows(env.db, shop.tenant_id, "SELECT settings, version FROM app.tenants")
    assert tenant["settings"]["weight_barcode_templates"] == CUSTOM
    assert tenant["settings"]["low_stock_check_enabled"] is False and tenant["version"] == body["version"]
    [audit] = await rows(
        env.db,
        shop.tenant_id,
        "SELECT before, after FROM app.audit_log WHERE action = 'stock_settings.updated'",
    )
    assert audit["before"]["weight_barcode_templates"] == DEFAULTS
    assert audit["after"]["changed"] == ["low_stock_check_enabled", "weight_barcode_templates"]

    # the POS sees the new templates and a new weight_barcode_version on its next pull
    again = await pull_ok(env, pos, scope="settings", cursor=first["cursor"])
    assert again["settings"] is not None
    assert again["settings"]["weight_barcode_templates"] == CUSTOM
    assert again["settings"]["weight_barcode_version"] != old_version

    # stale version → 409 VERSION_CONFLICT with the server version
    stale = await env.client.patch(
        URL, json={"expiry_warning_days": 10, "version": current["version"]}, headers=shop.h()
    )
    assert stale.status_code == 409 and _err(stale) == "VERSION_CONFLICT"
    assert stale.json()["error"]["params"]["current_version"] == body["version"]

    # the same values again: no write, no new audit row, version unchanged
    same = await env.client.patch(
        URL, json={"weight_barcode_templates": CUSTOM, "version": body["version"]}, headers=shop.h()
    )
    assert same.status_code == 200 and same.json()["version"] == body["version"]
    audits = await rows(
        env.db, shop.tenant_id, "SELECT id FROM app.audit_log WHERE action = 'stock_settings.updated'"
    )
    assert len(audits) == 1


async def test_template_validation(env: SyncEnv) -> None:
    shop = await env.shop("Validatsiya")
    version = (await env.client.get(URL, headers=shop.h(key=None))).json()["version"]

    async def patch(templates: list[dict[str, Any]]) -> Any:
        return await env.client.patch(
            URL, json={"weight_barcode_templates": templates, "version": version}, headers=shop.h()
        )

    base = dict(DEFAULTS[0])
    bad_prefix = await patch([{**base, "prefixes": ["19"]}])
    assert bad_prefix.status_code == 422 and _err(bad_prefix) == "VALIDATION_ERROR"
    assert (await patch([{**base, "prefixes": []}])).status_code == 422
    assert (await patch([{**base, "item_code_len": 7}])).status_code == 422
    assert (await patch([{**base, "decimals": 4}])).status_code == 422
    assert (await patch([{**base, "value_kind": "COUNT"}])).status_code == 422
    assert (await patch([{**base, "extra": 1}])).status_code == 422

    length = await patch([{**base, "item_code_len": 6, "value_len": 5}])
    assert length.status_code == 422
    assert _fields(length) == [("weight_barcode_templates[0].value_len", "validation.weight_template_length")]
    dup = await patch([base, {**DEFAULTS[1], "prefixes": ["21", "22"]}])
    assert dup.status_code == 422
    assert _fields(dup) == [("weight_barcode_templates[1].prefixes[1]", "validation.weight_prefix_duplicate")]
    days = await env.client.patch(URL, json={"expiry_warning_days": -1, "version": version}, headers=shop.h())
    assert days.status_code == 422
    unchanged = (await env.client.get(URL, headers=shop.h(key=None))).json()
    assert unchanged["version"] == version and unchanged["weight_barcode_templates"] == DEFAULTS
