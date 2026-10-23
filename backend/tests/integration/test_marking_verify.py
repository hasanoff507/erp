"""``POST /marking-codes/verify`` (18 §15; B5-EP-18#36) and ``MARKING_PRECHECK`` warn/block (qaror #62) —
US-M01-03, QT-M01-18, QT-M01-19, QT-M01-20 with ``FakeMarkingAdapter`` (B5-DoD-01 marking part)."""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from app.core.db.base import uuid7
from app.modules.integrations.marking.wiring import MarkingModule, build_marking_module
from tests.support.marking import API, code, fake_crpt_fixture, gtin, marking_env_fixture, set_precheck
from tests.support.sales import Env, Pos, make_pos, new_item, one, rows, sale_line, sale_payload, sell

pytestmark = [pytest.mark.db, pytest.mark.redis]
__all__ = ["fake_crpt_fixture", "marking_env_fixture"]

VERIFY = f"{API}/marking-codes/verify"


async def _verify(env: Env, pos: Pos, raw: str, *, role: str = "cashier", **extra: Any) -> httpx.Response:
    return await env.client.post(VERIFY, json={"code": raw, **extra}, headers=pos.shop.h(role))


async def _water(env: Env, pos: Pos) -> Any:
    return await new_item(env, pos, "Hayot suvi 1.5L", is_marked=True, marking_group_code="water_beverages",
                          price="8000.00", cost="5000.00")  # fmt: skip


async def _audits(env: Env, pos: Pos) -> list[dict[str, Any]]:
    return await rows(
        env.db, pos.tenant_id,
        "SELECT user_id, after FROM app.audit_log WHERE action = 'marking.precheck_failed' ORDER BY id",
    )  # fmt: skip


async def test_ep_18_36_verify_valid_code(env: Env, crpt: Any) -> None:
    pos = await make_pos(env)
    product = await _water(env, pos)
    raw = code("5a8pLsr>qeHnD")
    res = await _verify(env, pos, raw, product_id=str(product))
    assert res.status_code == 200, res.text
    assert res.json() == {
        "valid": True, "status": "in_stock", "warnings": [],
        "details": {"gtin": gtin(), "serial": "5a8pLsr>qeHnD", "reason": None},
    }  # fmt: skip
    assert crpt.calls == [("verify_code", raw)]  # exactly one CRPT call, GS kept as scanned
    assert await one(env.db, pos.tenant_id, "SELECT count(*) FROM app.marking_codes") == 0  # stores nothing
    assert await _audits(env, pos) == []


async def test_qt_m01_18_precheck_warn_invalid_or_timeout_sale_continues(env: Env, crpt: Any) -> None:
    pos = await make_pos(env)  # marking_precheck = 'warn' (default)
    product = await _water(env, pos)
    bad = code()
    crpt.statuses[bad] = "already_sold"
    res = await _verify(env, pos, bad)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["valid"] is False and body["details"]["reason"] == "already_sold"
    assert body["warnings"] == ["MARKING_PRECHECK_WARNING"]
    crpt.delay_s = 1.0  # CRPT does not answer within the timeout
    slow = code()
    timed = await _verify(env, pos, slow)
    assert timed.status_code == 200 and timed.json()["valid"] is None
    assert timed.json()["warnings"] == ["MARKING_PRECHECK_WARNING"]
    audits = await _audits(env, pos)
    assert [a["after"]["reason"] for a in audits] == ["already_sold", "timeout"]
    assert audits[0]["user_id"] == pos.shop.user_ids["cashier"] and audits[0]["after"]["mode"] == "warn"
    # the sale is not refused for this reason; the code goes to the OFD inside the fiscal receipt (qaror #62)
    crpt.delay_s = 0.0
    payload = sale_payload(pos, [sale_line(product, price="8000.0000", marking_code=bad)])
    sold = await sell(env, pos, payload)
    assert "MARKING_PRECHECK_WARNING" not in sold.server["warnings"]
    receipt = await one(env.db, pos.tenant_id, "SELECT payload FROM app.fiscal_receipts WHERE sale_id = :s",
                        s=payload["id"])  # fmt: skip
    assert receipt["items"][0]["marking_codes"] == [bad]
    assert [c for c, _ in crpt.calls].count("verify_code") == 2  # sale.created never calls CRPT


async def test_qt_m01_20_precheck_block_rejects(env: Env, crpt: Any) -> None:
    pos = await make_pos(env)
    await _water(env, pos)
    await set_precheck(env, pos, "block")
    bad = code()
    crpt.statuses[bad] = "expired"
    res = await _verify(env, pos, bad)
    assert res.status_code == 409, res.text
    assert res.json()["error"]["code"] == "MARKING_VERIFY_FAILED"
    assert res.json()["error"]["params"]["reason"] == "expired"
    crpt.delay_s = 1.0
    timed = await _verify(env, pos, code())
    assert timed.status_code == 503 and timed.json()["error"]["code"] == "MARKING_VERIFY_UNAVAILABLE"
    crpt.delay_s = 0.0
    ok = await _verify(env, pos, code())
    assert ok.status_code == 200 and ok.json()["valid"] is True and ok.json()["warnings"] == []
    assert await _audits(env, pos) == []  # block refuses — nothing to audit, no sale is created
    assert await one(env.db, pos.tenant_id, "SELECT count(*) FROM app.sales") == 0


async def test_qt_m01_19_verify_local_duplicate_and_format(env: Env, crpt: Any) -> None:
    pos = await make_pos(env)
    product = await _water(env, pos)
    sold = code()
    await sell(env, pos, sale_payload(pos, [sale_line(product, price="8000.0000", marking_code=sold)]))
    for mode in ("off", "warn", "block"):  # local duplicate check runs in every mode, before CRPT
        await set_precheck(env, pos, mode)
        again = await _verify(env, pos, sold)
        assert again.status_code == 409 and again.json()["error"]["code"] == "MARKING_CODE_ALREADY_SOLD"
    bad = await _verify(env, pos, "short")
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "MARKING_CODE_INVALID"
    assert crpt.calls == []


async def test_ep_18_36_verify_product_and_permission_checks(env: Env, crpt: Any) -> None:
    pos = await make_pos(env)
    cola = await new_item(env, pos)
    plain = await _verify(env, pos, code(), product_id=str(cola))
    assert plain.status_code == 422 and plain.json()["error"]["details"][0]["message_key"] == (
        "validation.marking_code_unexpected"
    )
    missing = await _verify(env, pos, code(), product_id=str(uuid7()))
    assert missing.status_code == 422
    denied = await _verify(env, pos, code(), role="accountant")  # no sales.create
    assert denied.status_code == 403
    off = code()
    await set_precheck(env, pos, "off")
    crpt.statuses[off] = "not_found"
    info = await _verify(env, pos, off)  # off: the POS does not call; an explicit call only reports
    assert info.status_code == 200 and info.json()["valid"] is False and info.json()["warnings"] == []
    unparsed = await _verify(env, pos, "0104600000000001215abcdefgh\x1d93AbCd")  # GTIN check digit wrong
    assert unparsed.json()["valid"] is False and unparsed.json()["details"]["gtin"] is None


async def test_ep_18_36_tenant_without_crpt_key_counts_as_no_answer(env: Env, crpt: Any) -> None:
    pos = await make_pos(env)
    module: MarkingModule = env.app.state.marking
    env.app.state.marking = build_marking_module(env.settings.model_copy(update={"marking_provider": "crpt"}),
                                                 env.db)  # fmt: skip
    try:
        warn = await _verify(env, pos, code())
        assert warn.status_code == 200 and warn.json()["valid"] is None
        assert warn.json()["warnings"] == ["MARKING_PRECHECK_WARNING"]
        await set_precheck(env, pos, "block")
        block = await _verify(env, pos, code())
        assert block.status_code == 503 and block.json()["error"]["code"] == "MARKING_VERIFY_UNAVAILABLE"
    finally:
        env.app.state.marking = module
    assert crpt.calls == []
