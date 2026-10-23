"""Pure receipt / posting arithmetic of the sales slice (18 §4.4–§4.5, 13 §2.1–§2.5, 16 §6/§8, 21 §1)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from app.modules.integrations.fiscal.domain.rules import (
    is_blocked,
    ofd_backoff,
    offline_stage,
    payment_form,
    qr_url,
)
from app.modules.returns.domain.refund import refund_line, split_refund
from app.modules.sales.domain.calc import (
    CalcError,
    allocate_largest,
    allocate_last,
    check_line,
    discount_pct,
    fiscal_shares,
    marking_code_valid,
)
from app.modules.sales.domain.posting import LineAmounts, Part, document_ledger

D = Decimal


def test_qt_m10_06_vat_formula() -> None:
    math = check_line(D("1.000"), D("3000.0000"), D("12.00"), D("0"), D("3000.00"), D("321.43"))
    assert math.vat == D("321.43") and math.net == D("2678.57")


def test_line_math_mismatch_and_negative_price() -> None:
    with pytest.raises(CalcError) as caught:
        check_line(D("1.000"), D("3000.0000"), D("12.00"), D("0"), D("3000.00"), D("321.42"))
    assert caught.value.message_key == "validation.vat_amount_mismatch"
    with pytest.raises(CalcError) as negative:
        check_line(D("1.000"), D("3000.0000"), D("12.00"), D("3600.00"), D("0.00"), D("0.00"))
    assert negative.value.field == "discount_amount"


def test_discount_pct_server_side() -> None:
    assert discount_pct(D("600.00"), D("10000.00")) == D("6.00")
    assert discount_pct(D("0"), D("0")) == D("0.00")


def test_allocations() -> None:
    assert allocate_last(D("10714.29"), [D("40000"), D("30000"), D("30000")]) == [
        D("4285.72"), D("3214.29"), D("3214.28")
    ]  # fmt: skip
    assert allocate_largest(D("10.00"), [D("1"), D("1"), D("1")]) == [D("3.33"), D("3.33"), D("3.34")]
    assert sum(allocate_largest(D("100.01"), [D("3"), D("7")])) == D("100.01")


def test_fiscal_shares_mixed_receipt() -> None:
    shares = fiscal_shares(
        [D("60000.00"), D("40000.00")], [D("3.000"), D("2.000")], [D("12.00")] * 2, D("70000.00")
    )
    assert [s.amount for s in shares] == [D("42000.00"), D("28000.00")]
    assert [s.qty for s in shares] == [D("2.100"), D("1.400")]
    assert shares[0].vat == D("4500.00")
    full = fiscal_shares([D("12000.00")], [D("1.000")], [D("12.00")], D("12000.00"))
    assert full[0].amount == D("12000.00") and full[0].qty == D("1.000")


def test_qt_m01_10_ledger_split_by_payment() -> None:
    lines, _ = document_ledger(
        kind="sale", entry_date=date(2026, 10, 17), branch_id=uuid4(),
        parts=[Part("cash", D("40000.00")), Part("card", D("30000.00")), Part("debt", D("30000.00"))],
        lines=[LineAmounts(uuid4(), D("100000.00"), D("10714.29"), D("12.00"))], vat_payer=True,
    )  # fmt: skip
    got = {(x.account_dt, x.account_kt): x.amount for x in lines}
    assert got == {
        ("5010", "9020"): D("35714.28"), ("5010", "6410"): D("4285.72"),
        ("5710", "9020"): D("26785.71"), ("5710", "6410"): D("3214.29"),
        ("4010", "9020"): D("26785.72"), ("4010", "6410"): D("3214.28"),
    }  # fmt: skip


def test_turnover_regime_no_vat_rows() -> None:
    lines, vat = document_ledger(
        kind="sale", entry_date=date(2026, 10, 17), branch_id=uuid4(), parts=[Part("cash", D("12000.00"))],
        lines=[LineAmounts(uuid4(), D("12000.00"), D("1285.71"), D("12.00"))], vat_payer=False,
    )  # fmt: skip
    assert [(x.account_dt, x.account_kt, x.amount) for x in lines] == [("5010", "9020", D("12000.00"))]
    assert vat == []


def test_refund_line_and_split() -> None:
    assert refund_line(D("1000.00"), D("3.000"), D("1.000"), D("0"), D("0")) == D("333.00")
    assert refund_line(D("1000.00"), D("3.000"), D("1.000"), D("2.000"), D("666.00")) == D("334.00")
    with pytest.raises(ValueError, match="outside"):
        refund_line(D("1000.00"), D("3.000"), D("2.000"), D("2.000"), D("666.00"))
    split = split_refund(D("24000.00"), D("14000.00"), "cash")
    assert (split.debt_part, split.money_part) == (D("14000.00"), D("10000.00"))
    assert split_refund(D("5000.00"), D("0"), "debt_adjustment").debt_part == D("5000.00")


def test_payment_form() -> None:
    assert payment_form(["cash"]) == "cash"
    assert payment_form(["card", "debt"]) == "card"
    assert payment_form(["uzqr"]) == "qr" and payment_form(["click", "payme"]) == "qr"
    assert payment_form(["cash", "card"]) == "mixed"
    with pytest.raises(ValueError, match="non-debt"):
        payment_form(["debt"])


def test_48h_stages() -> None:
    t0 = datetime(2026, 10, 1, tzinfo=UTC)
    assert offline_stage(t0, t0 + timedelta(hours=23, minutes=59)) is None
    assert offline_stage(t0, t0 + timedelta(hours=24)) == 24
    assert offline_stage(t0, t0 + timedelta(hours=41)) == 40
    assert offline_stage(t0, t0 + timedelta(hours=47)) == 46
    assert not is_blocked(t0, t0 + timedelta(hours=47, minutes=59)) and is_blocked(
        t0, t0 + timedelta(hours=48)
    )
    assert ofd_backoff(1, late=False) == timedelta(seconds=30) and ofd_backoff(10, late=False) == timedelta(
        minutes=15
    )
    assert ofd_backoff(3, late=True) == timedelta(minutes=2)


def test_qr_and_marking_format() -> None:
    url = qr_url("ZZ000000000001", 5, datetime(2026, 10, 17, 9, 5, 1, tzinfo=UTC), "123456789012")
    assert url == "https://ofd.soliq.uz/check?t=ZZ000000000001&r=5&c=20261017090501&s=123456789012"
    assert marking_code_valid("0104600000000001215abcdefgh\x1d93AbCd")
    assert not marking_code_valid("short") and not marking_code_valid(" 0104600000000001215abcdefgh")
