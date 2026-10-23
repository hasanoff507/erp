"""B4 fix round FX-supplier-tax — pure domain: ACC-05 (advance offset releases the deferred VAT credit,
13 §2.6/§2.8/§2.16) and ACC-06 (regime sub-ranges of a transition month, 13 §4.3)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.core.db.base import uuid7
from app.modules.accounting.domain.entries import VatMove
from app.modules.purchasing.domain.receipts import ReceiptLine, line_net, line_vat, receipt_posting
from app.modules.vat.application.vat import split_regimes

D = Decimal
DAY = date(2026, 10, 17)
BRANCH, SUPPLIER, WH, EINVOICE = uuid7(), uuid7(), uuid7(), uuid7()


def _line(qty: str, cost: str) -> ReceiptLine:
    q, c = D(qty), D(cost)
    return ReceiptLine(
        id=uuid7(), line_no=1, product_id=uuid7(), qty=q, cost=c, vat_rate=D("12.00"),
        vat_amount=line_vat(line_net(q, c), D("12.00")),
    )  # fmt: skip


def _post(
    advance: str, risk_flag: str | None = "red"
) -> tuple[list[tuple[str, str, Decimal]], list[VatMove]]:
    plan = receipt_posting(
        [(_line("1.000", "1000000.0000"), uuid7())], regime="vat", kind="purchase", paid_immediately=False,
        risk_flag=risk_flag, advance=D(advance), entry_date=DAY, branch_id=BRANCH, inv_acct="2910",
        supplier_id=SUPPLIER, warehouse_id=WH, einvoice_id=EINVOICE,
    )  # fmt: skip
    return [(x.account_dt, x.account_kt, x.amount) for x in plan.ledger], plan.vat


def test_acc05_full_advance_releases_whole_deferred_credit() -> None:
    ledger, vat = _post("2000000.00")
    assert ledger == [
        ("2910", "6010", D("1000000.00")),
        ("4410", "6010", D("120000.00")),
        ("6010", "4310", D("1120000.00")),
    ]
    assert vat == [VatMove(DAY, "input", D("1000000.00"), D("120000.00"), EINVOICE)]


def test_acc05_partial_advance_releases_proportional_share() -> None:
    ledger, vat = _post("400000.00")
    assert ledger[-1] == ("6010", "4310", D("400000.00"))
    # 120 000 x 400 000 / 1 120 000 = 42 857.142… ; 1 000 000 x 400 000 / 1 120 000 = 357 142.857…
    assert vat == [VatMove(DAY, "input", D("357142.86"), D("42857.14"), EINVOICE)]


def test_acc05_no_advance_keeps_credit_deferred_and_green_unchanged() -> None:
    assert _post("0.00")[1] == []
    _, vat = _post("400000.00", risk_flag="green")  # not deferred: the full credit at posting, once
    assert vat == [VatMove(DAY, "input", D("1000000.00"), D("120000.00"), EINVOICE)]


def test_acc06_split_regimes() -> None:
    sep, end = date(2026, 9, 1), date(2026, 9, 30)
    assert split_regimes([], sep, end) == [(sep, end, "vat")]
    turnover = [(date(2026, 1, 1), "turnover")]
    assert split_regimes(turnover, sep, end) == [(sep, end, "turnover")]
    to_vat = [*turnover, (date(2026, 9, 15), "vat")]
    assert split_regimes(to_vat, sep, end) == [
        (sep, date(2026, 9, 14), "turnover"),
        (date(2026, 9, 15), end, "vat"),
    ]
    # a change on the 1st replaces the regime for the whole month; a repeated regime row merges
    assert split_regimes([*turnover, (sep, "vat")], sep, end) == [(sep, end, "vat")]
    assert split_regimes([*turnover, (date(2026, 9, 10), "turnover")], sep, end) == [(sep, end, "turnover")]
