"""Goods receipt / supplier return posting rules (13 §2.6–§2.8, §2.16, §2.20, §4.3, §5.3) — pure domain."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.core.db.base import uuid7
from app.modules.accounting.domain.entries import VatMove
from app.modules.purchasing.domain.receipts import (
    ReceiptLine,
    ReceiptPosting,
    discrepant_products,
    line_net,
    line_vat,
    lot_amount,
    receipt_posting,
    remaining_by_product,
    vat_deferred,
)
from app.modules.purchasing.domain.supplier_returns import (
    add_months,
    invoice_amount,
    return_entries,
    reverse_sale_required,
    vat_share,
)

D = Decimal
DAY = date(2026, 10, 17)
BRANCH, SUPPLIER, WH = uuid7(), uuid7(), uuid7()


def _line(qty: str, cost: str, rate: str = "12.00") -> ReceiptLine:
    q, c = D(qty), D(cost)
    return ReceiptLine(
        id=uuid7(), line_no=1, product_id=uuid7(), qty=q, cost=c, vat_rate=D(rate),
        vat_amount=line_vat(line_net(q, c), D(rate)),
    )  # fmt: skip


def _post(
    lines: list[ReceiptLine], **kw: object
) -> tuple[list[tuple[str, str, Decimal]], list[VatMove], Decimal]:
    args: dict[str, object] = {
        "regime": "vat", "kind": "purchase", "paid_immediately": False, "risk_flag": None, "advance": D("0.00"),
        "entry_date": DAY, "branch_id": BRANCH, "inv_acct": "2910", "supplier_id": SUPPLIER, "warehouse_id": WH,
    }  # fmt: skip
    args.update(kw)
    plan = receipt_posting([(ln, uuid7()) for ln in lines], **args)  # type: ignore[arg-type]
    return [(x.account_dt, x.account_kt, x.amount) for x in plan.ledger], plan.vat, plan.payable


def test_line_amounts_round_half_up_per_line() -> None:
    assert line_net(D("100.000"), D("10000.0000")) == D("1000000.00")
    assert line_vat(D("1000000.00"), D("12.00")) == D("120000.00")
    assert line_net(D("1.500"), D("1.2345")) == D("1.85")  # 1.85175
    assert line_vat(D("1.85"), D("12.00")) == D("0.22")  # 0.222
    assert line_net(D("3.000"), D("33333.3333")) == D("100000.00")  # 99999.9999
    assert line_vat(D("0.04"), D("12.00")) == D("0.00")  # 0.0048
    assert line_vat(D("0.05"), D("12.00")) == D("0.01")  # 0.006


def test_qt_m07_03_vat_purchase_on_credit() -> None:
    ledger, vat, payable = _post([_line("100.000", "10000.0000")])
    assert ledger == [("2910", "6010", D("1000000.00")), ("4410", "6010", D("120000.00"))]
    assert sum(a for _, kt, a in ledger if kt == "6010") == D("1120000.00")
    assert [(v.kind, v.base_amount, v.vat_amount) for v in vat] == [
        ("input", D("1000000.00"), D("120000.00"))
    ]
    assert payable == D("1120000.00")


def test_stock_line_analytics() -> None:
    line, lot = _line("1.000", "100.0000"), uuid7()
    plan = receipt_posting(
        [(line, lot)], regime="vat", kind="purchase", paid_immediately=False, risk_flag=None, advance=D("0"),
        entry_date=DAY, branch_id=BRANCH, inv_acct="2920", supplier_id=SUPPLIER, warehouse_id=WH,
    )  # fmt: skip
    assert plan.ledger[0].analytics == {
        "product_id": str(line.product_id), "warehouse_id": str(WH), "counterparty_id": str(SUPPLIER),
        "line_id": str(line.id), "lot_id": str(lot),
    }  # fmt: skip
    assert plan.ledger[1].analytics == {"tax_type": "vat", "counterparty_id": str(SUPPLIER)}


def _plan(lines: list[ReceiptLine], **kw: object) -> ReceiptPosting:
    args: dict[str, object] = {
        "regime": "vat", "kind": "purchase", "paid_immediately": False, "risk_flag": None, "advance": D("0.00"),
        "entry_date": DAY, "branch_id": BRANCH, "inv_acct": "2910", "supplier_id": SUPPLIER, "warehouse_id": WH,
    }  # fmt: skip
    args.update(kw)
    return receipt_posting([(ln, uuid7()) for ln in lines], **args)  # type: ignore[arg-type]


def test_qt_m07_04_09_red_or_unknown_einvoice_defers_vat_credit_only() -> None:
    """13 §2.8: 4410 is always posted (Kt 6010 = the gross payable); only ``vat_moves`` wait."""
    einvoice = uuid7()
    for flag in ("red", "unknown"):
        plan = _plan([_line("100.000", "10000.0000")], risk_flag=flag, einvoice_id=einvoice)
        rows = [(x.account_dt, x.account_kt, x.amount) for x in plan.ledger]
        assert rows == [("2910", "6010", D("1000000.00")), ("4410", "6010", D("120000.00"))]
        assert sum(x.amount for x in plan.ledger if x.account_kt == "6010") == D("1120000.00")
        assert plan.payable == D("1120000.00")  # ledger 6010 = debt register gross
        assert plan.ledger[1].analytics == {
            "tax_type": "vat", "counterparty_id": str(SUPPLIER), "einvoice_id": str(einvoice),
            "vat_credit": "deferred",
        }  # fmt: skip
        assert plan.vat == []
    plan = _plan([_line("100.000", "10000.0000")], risk_flag="green", einvoice_id=einvoice)
    assert plan.ledger[1].analytics == {
        "tax_type": "vat",
        "counterparty_id": str(SUPPLIER),
        "einvoice_id": str(einvoice),
    }
    assert [(v.kind, v.base_amount, v.vat_amount, v.einvoice_id) for v in plan.vat] == [
        ("input", D("1000000.00"), D("120000.00"), einvoice)
    ]
    plan = _plan([_line("100.000", "10000.0000")], risk_flag="red", paid_immediately=True)
    assert "vat_credit" not in plan.ledger[1].analytics and len(plan.vat) == 1  # paid at once
    assert vat_deferred("red", paid_immediately=True) is False  # paid at once → credit allowed
    assert vat_deferred(None, paid_immediately=False) is False  # manual receipt without an e-invoice


def test_red_einvoice_advance_offset_covers_gross() -> None:
    """Red, unpaid, 4310 advance 1,200,000.00 → Dt 6010 / Kt 4310 = 1,120,000.00 (VAT included)."""
    plan = _plan([_line("100.000", "10000.0000")], risk_flag="red", advance=D("1200000.00"))
    rows = [(x.account_dt, x.account_kt, x.amount) for x in plan.ledger]
    assert rows[-1] == ("6010", "4310", D("1120000.00"))
    assert plan.advance_offset == D("1120000.00") and plan.payable == D("1120000.00")
    # ACC-05: the offset fully covers the receipt → the whole deferred credit is released at posting
    assert [(v.kind, v.base_amount, v.vat_amount) for v in plan.vat] == [
        ("input", D("1000000.00"), D("120000.00"))
    ]


def test_2_7_zero_rate_lines_and_mixed_base() -> None:
    ledger, vat, payable = _post([_line("10.000", "5000.0000", "0.00")])
    assert ledger == [("2910", "6010", D("50000.00"))] and vat == [] and payable == D("50000.00")
    ledger, vat, payable = _post([_line("10.000", "5000.0000", "0.00"), _line("2.000", "1000.0000")])
    assert ledger == [
        ("2910", "6010", D("50000.00")),
        ("2910", "6010", D("2000.00")),
        ("4410", "6010", D("240.00")),
    ]
    assert [(v.base_amount, v.vat_amount) for v in vat] == [(D("2000.00"), D("240.00"))]  # taxed lines only
    assert payable == D("52240.00")


def test_2_8_paid_immediately_credits_bank_without_debt() -> None:
    ledger, vat, payable = _post([_line("100.000", "10000.0000")], paid_immediately=True)
    assert ledger == [("2910", "5110", D("1000000.00")), ("4410", "5110", D("120000.00"))]
    assert len(vat) == 1 and payable == D("0.00")


def test_4_3_turnover_regime_vat_in_lot_cost() -> None:
    line = _line("100.000", "10000.0000")
    ledger, vat, payable = _post([line], regime="turnover")
    assert ledger == [("2910", "6010", D("1120000.00"))] and vat == [] and payable == D("1120000.00")
    assert lot_amount(line, regime="turnover", kind="purchase") == D("1120000.00")
    assert lot_amount(line, regime="vat", kind="purchase") == D("1000000.00")


def test_2_6a_gratuitous() -> None:
    line = ReceiptLine(uuid7(), 1, uuid7(), D("5.000"), D("2000.0000"), D("12.00"), D("0.00"))
    ledger, vat, payable = _post([line], kind="gratuitous")
    assert ledger == [("2910", "8530", D("10000.00"))] and vat == [] and payable == D("0.00")
    assert lot_amount(line, regime="turnover", kind="gratuitous") == D("10000.00")


def test_2_16_advance_offset_example() -> None:
    """13 §2.16: advance 200000.00, next receipt 500000.00 (0%) → Dt 6010 / Kt 4310 200000.00."""
    ledger, _, payable = _post([_line("1.000", "500000.0000", "0.00")], advance=D("200000.00"))
    assert ledger == [("2910", "6010", D("500000.00")), ("6010", "4310", D("200000.00"))]
    assert payable == D("500000.00")  # the debt register already holds the advance as −200000.00
    ledger, _, _ = _post([_line("1.000", "100000.0000", "0.00")], advance=D("200000.00"))
    assert ledger[-1] == ("6010", "4310", D("100000.00"))  # min(advance, invoice)
    ledger, _, _ = _post([_line("1.000", "100000.0000")], advance=D("500000.00"), risk_flag="red")
    assert ledger[-1] == ("6010", "4310", D("112000.00"))  # capped by the 6010 credit (incl. deferred VAT)
    ledger, _, _ = _post([_line("1.000", "100000.0000")], advance=D("500000.00"), paid_immediately=True)
    assert all(kt != "4310" for _, kt, _ in ledger)


def test_qt_m07_08_bonus_units_in_line_cost() -> None:
    line = _line("11.000", "10909.0909", "0.00")  # 10 paid + 1 bonus, invoice 120000.00
    assert line.net == D("120000.00")
    assert lot_amount(line, regime="vat", kind="purchase") == D("120000.00")


def test_discrepancy_against_po_remaining() -> None:
    a, b, c = uuid7(), uuid7(), uuid7()
    remaining = remaining_by_product({a: D("50.000"), b: D("10.000")}, {b: D("4.000")})
    assert remaining == {a: D("50.000"), b: D("6.000")}
    assert discrepant_products([(a, D("48.000")), (b, D("6.000"))], remaining) == {a}
    assert discrepant_products([(a, D("20.000")), (a, D("30.000"))], remaining) == set()  # split lines
    assert discrepant_products([(c, D("1.000"))], remaining) == {c}  # not on the PO


def test_2_20_vat_share_takes_remainder_on_last_return() -> None:
    assert vat_share(D("1200.00"), D("10.000"), D("4.000"), D("0.000"), D("0.00")) == D("480.00")
    assert vat_share(D("1200.00"), D("10.000"), D("6.000"), D("4.000"), D("480.00")) == D("720.00")
    shares, done_qty, done_vat = [], D("0.000"), D("0.00")
    for _ in range(3):
        share = vat_share(D("100.00"), D("3.000"), D("1.000"), done_qty, done_vat)
        shares.append(share)
        done_qty, done_vat = done_qty + 1, done_vat + share
    assert shares == [D("33.33"), D("33.33"), D("33.34")] and sum(shares) == D("100.00")


def test_2_20_invoice_amount_by_regime() -> None:
    assert invoice_amount(D("4.000"), D("1000.0000"), D("480.00"), regime="vat") == D("4000.00")
    assert invoice_amount(D("4.000"), D("1000.0000"), D("480.00"), regime="turnover") == D("4480.00")


def test_2_20_ledger_rows() -> None:
    analytics = {"stock_cost": True, "line_id": str(uuid7())}

    def rows(invoice: str, book: str) -> list[tuple[str, str, Decimal]]:
        out = return_entries(
            invoice=D(invoice), book=D(book), inv_acct="2910", entry_date=DAY, branch_id=BRANCH,
            cost_analytics=analytics, supplier_id=SUPPLIER,
        )  # fmt: skip
        return [(x.account_dt, x.account_kt, x.amount) for x in out]

    assert rows("4000.00", "4000.00") == [("6010", "2910", D("4000.00"))]  # FIFO: invoice = book
    assert rows("10000.00", "7500.00") == [
        ("6010", "2910", D("7500.00")),
        ("6010", "9390", D("2500.00")),
    ]  # 3a
    assert rows("5000.00", "7500.00") == [
        ("6010", "2910", D("5000.00")),
        ("9430", "2910", D("2500.00")),
    ]  # 3b


def test_2_20_twelve_month_rule() -> None:
    assert reverse_sale_required(date(2025, 10, 17), date(2026, 10, 17)) is False
    assert reverse_sale_required(date(2025, 10, 17), date(2026, 10, 18)) is True
    assert add_months(date(2024, 2, 29), 12) == date(2025, 2, 28)
    assert add_months(date(2025, 1, 31), 1) == date(2025, 2, 28)
