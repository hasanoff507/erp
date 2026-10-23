"""The posting toolkit and the journal (13 §5.1–§5.3, 23 §2.3, 20 #9 ``GET /ledger-entries``; QT-M11-01)."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

import pytest

from app.core.db.base import uuid7
from app.core.db.session import tenant_transaction
from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from app.modules.access.domain.permissions import SystemRole
from app.modules.accounting.wiring import LedgerLine, VatMove, business_today, ledger_poster
from tests.support.catalog import Env, Shop, catalog_env_fixture
from tests.support.inventory import (
    API,
    D,
    add_branch,
    add_user,
    close_period,
    err,
    issue,
    ledger,
    new_product,
    receive,
    rows,
    set_go_live,
    use_account,
)
from tests.support.ordering import TXN_ORDER

pytestmark = [pytest.mark.db, pytest.mark.redis]
__all__ = ["catalog_env_fixture"]

TODAY = business_today()


@pytest.fixture(autouse=True)
def _fresh_business_day() -> None:
    """The suite can cross midnight (Asia/Tashkent): take the business day when each test starts."""
    global TODAY
    TODAY = business_today()


LAST_MONTH = (TODAY.replace(day=1) - timedelta(days=1)).replace(day=1)


async def _post(
    env: Env, shop: Shop, doc_id: UUID, lines: list[LedgerLine], vat: list[VatMove] | None = None
) -> Any:
    async with env.db.session_factory() as s, tenant_transaction(s, shop.tenant_id):
        return await ledger_poster().post(s, shop.tenant_id, "sales", doc_id, lines, vat or [])


async def _reverse(env: Env, shop: Shop, doc_id: UUID) -> Any:
    async with env.db.session_factory() as s, tenant_transaction(s, shop.tenant_id):
        return await ledger_poster().reverse_document(s, shop.tenant_id, "sales", doc_id)


def _sale_lines(shop: Shop, day: date) -> list[LedgerLine]:
    """23 §2.2: cash sale 120000.00 incl. 12% VAT → 107142.86 + 12857.14; COGS 96500.00 (+ a zero line)."""
    b = shop.branch_id
    return [
        LedgerLine(day, b, "5010", "9020", Decimal("107142.86"), {"cash_register_id": "k"}),
        LedgerLine(day, b, "5010", "6410", Decimal("12857.14"), {"tax_type": "vat"}),
        LedgerLine(day, b, "9120", "2910", Decimal("96500.00"), {}),
        LedgerLine(day, b, "9120", "2910", Decimal("0.00"), {}),  # skipped, never written
    ]


async def test_qt_m11_01_posting_writes_double_entry_rows_and_vat(env: Env) -> None:
    shop = await env.shop("Jurnal")
    doc = uuid7()
    posted = await _post(
        env,
        shop,
        doc,
        _sale_lines(shop, TODAY),
        [VatMove(TODAY, "output", Decimal("107142.86"), Decimal("12857.14"))],
    )
    assert len(posted.ledger_ids) == 3 and len(posted.vat_ids) == 1
    entries = await ledger(env, shop, doc)
    assert [(e["account_dt"], e["account_kt"], e["amount"]) for e in entries] == [
        ("5010", "9020", D("107142.86")),
        ("5010", "6410", D("12857.14")),
        ("9120", "2910", D("96500.00")),
    ]
    assert sum(e["amount"] for e in entries if e["account_dt"] == "5010") == D("120000.00")
    [vat] = await rows(env, shop.tenant_id, "SELECT period, kind, base_amount, vat_amount FROM app.vat_moves")
    assert vat == {
        "period": TODAY.replace(day=1),
        "kind": "output",
        "base_amount": D("107142.86"),
        "vat_amount": D("12857.14"),
    }


async def test_storno_swaps_ledger_negates_vat_and_is_idempotent(env: Env) -> None:
    shop = await env.shop("Storno")
    doc = uuid7()
    await _post(
        env,
        shop,
        doc,
        _sale_lines(shop, TODAY),
        [VatMove(TODAY, "output", Decimal("100.00"), Decimal("12.00"))],
    )
    reversal = await _reverse(env, shop, doc)
    assert reversal.entry_date == TODAY and len(reversal.ledger_ids) == 3 and len(reversal.vat_ids) == 1
    entries = await ledger(env, shop, doc)
    originals, stornos = entries[:3], entries[3:]
    for orig, rev in zip(originals, stornos, strict=True):
        assert (rev["account_dt"], rev["account_kt"], rev["amount"]) == (
            orig["account_kt"],
            orig["account_dt"],
            orig["amount"],
        )
        assert rev["reversal_of_id"] == orig["id"] and rev["doc_id"] == doc and rev["entry_date"] == TODAY
        assert rev["analytics"] == orig["analytics"]
    vats = await rows(
        env,
        shop.tenant_id,
        f"SELECT id, base_amount, vat_amount, reversal_of_id FROM app.vat_moves ORDER BY {TXN_ORDER}, id",
    )
    assert [(v["base_amount"], v["vat_amount"]) for v in vats] == [
        (D("100.00"), D("12.00")),
        (D("-100.00"), D("-12.00")),
    ]
    assert vats[1]["reversal_of_id"] == vats[0]["id"]
    again = await _reverse(env, shop, doc)  # nothing live is left
    assert again.ledger_ids == [] and again.vat_ids == []


async def test_period_closed_and_storno_of_a_closed_period_document(env: Env) -> None:
    """13 §5.1: posting into a closed month (or any earlier one) → 409 PERIOD_CLOSED; 13 §5.2: cancelling a
    document of a closed month is allowed — the storno is dated in the open period."""
    shop = await env.shop("Davr")
    doc = uuid7()
    await _post(
        env, shop, doc, _sale_lines(shop, LAST_MONTH), [VatMove(LAST_MONTH, "output", D("1"), D("0.12"))]
    )
    await close_period(env, shop, LAST_MONTH)
    for day in (LAST_MONTH, LAST_MONTH - timedelta(days=40)):
        with pytest.raises(AppError) as exc:
            await _post(env, shop, uuid7(), _sale_lines(shop, day))
        assert exc.value.code is ErrorCode.PERIOD_CLOSED and exc.value.status_code == 409
        assert exc.value.params == {"period": f"{day.year:04d}-{day.month:02d}"}
    with pytest.raises(AppError):  # a VAT move alone in a closed month is refused too
        await _post(env, shop, uuid7(), [], [VatMove(LAST_MONTH, "input", D("1"), D("1"))])
    reversal = await _reverse(env, shop, doc)
    assert reversal.entry_date == TODAY
    stornos = [e for e in await ledger(env, shop, doc) if e["reversal_of_id"]]
    assert {e["entry_date"] for e in stornos} == {TODAY}
    periods = await rows(
        env, shop.tenant_id, "SELECT period FROM app.vat_moves WHERE reversal_of_id IS NOT NULL"
    )
    assert periods == [{"period": TODAY.replace(day=1)}]


async def test_reverse_specific_entries(env: Env) -> None:
    shop = await env.shop("Aniq storno")
    doc = uuid7()
    await _post(env, shop, doc, _sale_lines(shop, TODAY))
    async with env.db.session_factory() as s, tenant_transaction(s, shop.tenant_id):
        poster = ledger_poster()
        cogs = await poster.doc_entries(s, "sales", doc, analytics={}, live_only=True)
        target = [e for e in cogs if e.account_dt == "9120"]
        ids = await poster.reverse_entries(
            s, shop.tenant_id, target, on=TODAY, extra_analytics={"recost_job_id": "j"}
        )
        assert len(ids) == 1
        live = await poster.doc_entries(s, "sales", doc, live_only=True)
        assert {e.account_dt for e in live} == {"5010"}
        reversal = await poster.doc_entries(s, "sales", doc, analytics={"recost_job_id": "j"})
        with pytest.raises(ValueError, match="never reversed again"):
            await poster.reverse_entries(s, shop.tenant_id, reversal, on=TODAY)


async def test_ledger_entries_api_filters_scope_cursor_and_doc_number(env: Env) -> None:
    shop = await env.shop("Jurnal API", SystemRole.OWNER, SystemRole.CASHIER)
    branch_b, wh_b = await add_branch(env, shop, "02", "Sergeli")
    await add_user(env, shop, "accountant_a", SystemRole.ACCOUNTANT, (shop.branch_id,))
    await set_go_live(env, shop, TODAY.replace(day=1))
    wh = await use_account(env, shop, "2910")
    p = await new_product(env, shop)
    opening = await env.client.post(
        f"{API}/stock-openings",
        json={"warehouse_id": str(wh), "doc_date": str(TODAY), "lines": [{"product_id": str(p), "qty": "2.000", "unit_cost": "500.0000"}]},
        headers=shop.h(),
    )  # fmt: skip
    posted = (
        await env.client.post(f"{API}/stock-openings/{opening.json()['id']}/post", headers=shop.h())
    ).json()
    await issue(env, shop, wh, p, "1.000", account_dt="9430")
    await receive(env, shop, wh_b, p, "1.000", "700.00")  # stock only (the helper writes no ledger)
    await issue(env, shop, wh_b, p, "1.000", account_dt="9430")  # branch B: 700.00
    url = f"{API}/ledger-entries"

    async def get(role: str = "owner", **params: Any) -> Any:
        return await env.client.get(url, params=params, headers=shop.h(role, key=None))

    body = (await get()).json()
    assert len(body["items"]) == 3 and body["next_cursor"] is None
    by_doc = {i["doc_type"]: i for i in body["items"]}
    assert by_doc["stock_openings"]["doc_number"] == posted["number"]
    assert by_doc["stock_openings"] | {"id": None, "doc_id": None, "analytics": None} == {
        "id": None, "entry_date": str(TODAY.replace(day=1) - timedelta(days=1)), "account_dt": "2910",
        "account_kt": "0000", "amount": "1000.00", "branch_id": str(shop.branch_id), "doc_type": "stock_openings",
        "doc_id": None, "doc_number": posted["number"], "analytics": None, "reversal_of_id": None,
    }  # fmt: skip
    assert [i["account_kt"] for i in (await get(account_kt="0000")).json()["items"]] == ["0000"]
    assert len((await get(account_dt="9430")).json()["items"]) == 2
    assert len((await get(doc_type="write_offs", branch_id=str(branch_b))).json()["items"]) == 1
    assert (await get(entry_date__gte=str(TODAY + timedelta(days=1)))).json()["items"] == []
    assert len((await get(entry_date__lte=str(TODAY - timedelta(days=1)))).json()["items"]) >= 1
    first = (await get(limit=2)).json()
    rest = (await get(limit=2, cursor=first["next_cursor"])).json()
    assert len(first["items"]) == 2 and len(rest["items"]) == 1 and rest["next_cursor"] is None
    assert {i["id"] for i in first["items"]}.isdisjoint({i["id"] for i in rest["items"]})
    # a branch-restricted accountant sees only own-branch rows; another branch → 403
    own = (await get("accountant_a")).json()["items"]
    assert {i["branch_id"] for i in own} == {str(shop.branch_id)} and len(own) == 2
    denied = await get("accountant_a", branch_id=str(branch_b))
    assert denied.status_code == 403 and err(denied) == "BRANCH_SCOPE_DENIED"
    no_perm = await get("cashier")
    assert no_perm.status_code == 403 and err(no_perm) == "PERMISSION_DENIED"
    bad_cursor = await get(cursor="!!")
    assert bad_cursor.status_code == 422
    bad_range = await get(entry_date__gte=str(TODAY), entry_date__lte=str(TODAY - timedelta(days=1)))
    assert bad_range.status_code == 422
    assert (await get(account_dt="12")).status_code == 422
