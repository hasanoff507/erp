"""Marking codes on supplier returns and write-offs (contract marking.md §2–§4; 21 §4; 19 §12, §15):
drafts keep the codes (``marking_codes`` = qty), ``post`` hands them to the marking hook (CRPT notice job,
codes ``returned_to_supplier`` / ``written_off``), ``cancel`` gives them back."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import pytest

from tests.support.edocs import API, ROLES, Env, Shop, edocs_env_fixture, rows
from tests.support.purchasing import (
    create_product,
    create_receipt,
    create_supplier,
    gr_line,
    post_gr,
    warehouse_of,
)

pytestmark = [pytest.mark.db, pytest.mark.redis]
__all__ = ["edocs_env_fixture"]

GS = "\x1d"
SR = f"{API}/supplier-returns"
WO = f"{API}/write-offs"


async def _stocked(env: Env, name: str) -> tuple[Shop, str, UUID, dict[str, Any], list[str]]:
    shop = await env.shop(name, *ROLES)
    supplier = (await create_supplier(env.client, shop))["id"]
    wh = await warehouse_of(env.db, shop)
    water = (
        await create_product(
            env.client, shop, "Suv 0.5L", is_marked=True, marking_group_code="water_beverages"
        )
    )["id"]
    codes = [f"0104780000000001215{i:03d}{GS}93dGVz" for i in range(3)]
    draft = await create_receipt(
        env.client, shop, supplier, wh, [gr_line(water, "3.000", "100.0000", marking_codes=codes)]
    )
    posted = await post_gr(env.client, shop, draft["id"])
    assert posted.status_code == 200, posted.text
    return shop, water, wh, posted.json(), codes


async def _status(env: Env, shop: Shop) -> dict[str, str]:
    found = await rows(env, shop.tenant_id, "SELECT code, status FROM app.marking_codes")
    return {r["code"]: r["status"] for r in found}


async def test_supplier_return_marking_codes_go_to_the_hook(env: Env) -> None:
    shop, _, _, receipt, codes = await _stocked(env, "Qaytarish kodlari")
    line = receipt["lines"][0]
    base = {"receipt_id": receipt["id"], "doc_date": receipt["doc_date"], "reason": "damaged"}
    h = shop.h("owner", branch=shop.branch_id)
    short = await env.client.post(
        SR, json={**base, "lines": [{"receipt_line_id": line["id"], "lot_id": line["lot_id"], "qty": "2.000",
                                     "marking_codes": codes[:1]}]}, headers=h,
    )  # fmt: skip
    assert short.json()["error"]["details"][0]["message_key"] == "validation.marking_count_mismatch"
    draft = await env.client.post(
        SR, json={**base, "lines": [{"receipt_line_id": line["id"], "lot_id": line["lot_id"], "qty": "2.000",
                                     "marking_codes": codes[:2]}]}, headers=shop.h("owner", branch=shop.branch_id),
    )  # fmt: skip
    assert draft.status_code == 201, draft.text
    assert draft.json()["lines"][0]["marking_codes"] == codes[:2]
    posted = await env.client.post(
        f"{SR}/{draft.json()['id']}/post", headers=shop.h("owner", branch=shop.branch_id)
    )
    assert posted.status_code == 200, posted.text
    status = await _status(env, shop)
    assert [status[c] for c in codes] == ["returned_to_supplier", "returned_to_supplier", "in_stock"]
    jobs = await rows(
        env, shop.tenant_id, "SELECT kind FROM app.outbox_jobs WHERE kind = 'marking_supplier_return'"
    )
    assert len(jobs) == 1
    cancelled = await env.client.post(
        f"{SR}/{draft.json()['id']}/cancel",
        json={"reason": "xato"},
        headers=shop.h("owner", branch=shop.branch_id),
    )
    assert cancelled.status_code == 200, cancelled.text
    assert set((await _status(env, shop)).values()) == {"in_stock"}


async def test_write_off_marking_codes_go_to_the_hook(env: Env) -> None:
    shop, water, wh, _, codes = await _stocked(env, "Hisobdan chiqarish kodlari")
    body = {"warehouse_id": str(wh), "doc_date": None, "lines": []}
    from app.modules.accounting.wiring import business_today

    body["doc_date"] = str(business_today())
    plain = await create_product(env.client, shop, "Non")
    unmarked = await env.client.post(
        WO, json={**body, "lines": [{"product_id": plain["id"], "qty": "1.000", "reason": "damaged",
                                     "marking_codes": ["X"]}]}, headers=shop.h("owner"),
    )  # fmt: skip
    assert unmarked.json()["error"]["details"][0]["message_key"] == "validation.marking_not_required"
    created = await env.client.post(
        WO, json={**body, "lines": [{"product_id": water, "qty": "1.000", "reason": "damaged",
                                     "marking_codes": [codes[2]]}]}, headers=shop.h("owner"),
    )  # fmt: skip
    assert created.status_code == 201, created.text
    posted = await env.client.post(f"{WO}/{created.json()['id']}/post", headers=shop.h("owner"))
    assert posted.status_code == 200, posted.text
    assert (await _status(env, shop))[codes[2]] == "written_off"
    assert posted.json()["lines"][0]["marking_codes"] == [codes[2]]
