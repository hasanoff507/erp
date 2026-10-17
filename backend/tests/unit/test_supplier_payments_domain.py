"""Pure rules of supplier payments (13 §2.16, §2.8; qaror #47) — allocation order, debt part, VAT release."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from app.modules.purchasing.domain.supplier_payments import (
    Allocation,
    OpenDoc,
    auto_allocate,
    debt_part,
    payment_posting,
    vat_release,
)

D = Decimal


def _doc(
    n: int, day: date, outstanding: str, *, due: date | None = None, total: str | None = None
) -> OpenDoc:
    return OpenDoc("goods_receipts", UUID(int=n), f"M-{n}", day, due, D(total or outstanding), D(outstanding))


def test_13_2_16_debt_part_and_advance() -> None:
    assert debt_part(D("1000000.00"), D("800000.00")) == D("800000.00")
    assert debt_part(D("500000.00"), D("800000.00")) == D("500000.00")
    assert debt_part(D("100000.00"), D("-200000.00")) == D("0.00")  # an advance already exists


def test_auto_allocate_oldest_first_by_due_then_doc_date() -> None:
    a = _doc(3, date(2026, 10, 3), "100.00")
    b = _doc(2, date(2026, 10, 5), "100.00", due=date(2026, 10, 1))  # due date wins
    c = _doc(1, date(2026, 10, 3), "100.00")  # same date → lower id first
    got = auto_allocate([a, b, c], D("250.00"))
    assert [(x.doc.target_doc_id.int, x.amount) for x in got] == [
        (2, D("100.00")),
        (1, D("100.00")),
        (3, D("50.00")),
    ]
    assert auto_allocate([a], D("0.00")) == []


def test_vat_release_proportional_then_remainder() -> None:
    doc = OpenDoc(
        "goods_receipts", UUID(int=1), "M-1", date(2026, 10, 1), None, D("1120000.00"), D("1120000.00"),
        einvoice_id=UUID(int=9), risk_flag="red", deferred_vat=D("120000.00"), deferred_base=D("1000000.00"),
    )  # fmt: skip
    first = vat_release(Allocation(doc, D("560000.00")))
    assert first is not None and (first.base, first.vat) == (D("500000.00"), D("60000.00"))
    later = OpenDoc(
        "goods_receipts", UUID(int=1), "M-1", date(2026, 10, 1), None, D("1120000.00"), D("560000.00"),
        einvoice_id=UUID(int=9), risk_flag="red", deferred_vat=D("120000.00"), deferred_base=D("1000000.00"),
        released_vat=D("60000.00"), released_base=D("500000.00"),
    )  # fmt: skip
    closing = vat_release(Allocation(later, D("560000.00")))
    assert closing is not None and (closing.base, closing.vat) == (D("500000.00"), D("60000.00"))
    assert vat_release(Allocation(_doc(5, date(2026, 10, 1), "10.00"), D("10.00"))) is None


def test_payment_posting_lines() -> None:
    ledger, vat = payment_posting(
        method="cash", allocated=D("800000.00"), advance=D("200000.00"), entry_date=date(2026, 10, 1),
        branch_id=UUID(int=7), supplier_id=UUID(int=8), cash_register_id=UUID(int=5), shift_id=UUID(int=6),
        releases=[],
    )  # fmt: skip
    assert [(x.account_dt, x.account_kt, x.amount) for x in ledger] == [
        ("6010", "5010", D("800000.00")),
        ("4310", "5010", D("200000.00")),
    ]
    assert ledger[0].analytics["shift_id"] == str(UUID(int=6)) and vat == []
