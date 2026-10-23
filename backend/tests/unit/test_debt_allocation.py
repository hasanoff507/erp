"""Debt payment allocation + ``debt_settlement`` receipt lines (18 §12.2, 13 §2.14, 16 §1) — shared vectors.

The same file (``shared/debt-allocation-vectors.json``) drives the web twin ``@shared/lib/debt-allocation``
(32 §6.3, QT-M08-16: TS and Python give the same result).
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from app.shared.debt_allocation import OpenDoc, OpenLine, allocate, allocate_json

VECTORS = Path(__file__).resolve().parents[3] / "shared" / "debt-allocation-vectors.json"
D = Decimal


def _cases() -> list[dict[str, Any]]:
    if not VECTORS.exists():
        pytest.skip("shared/debt-allocation-vectors.json not available")
    data: dict[str, Any] = json.loads(VECTORS.read_text(encoding="utf-8"))
    cases: list[dict[str, Any]] = data["cases"]
    return cases


def test_vectors_reproduce_exactly() -> None:
    cases = _cases()
    assert len(cases) >= 10
    for case in cases:
        got = allocate_json(case["amount"], case["open_docs"], fiscal=case["fiscal"])
        assert got == case["expected"], case["name"]


def test_receipt_total_always_equals_the_money_received() -> None:
    for case in _cases():
        got = allocate_json(case["amount"], case["open_docs"], fiscal=case["fiscal"])
        allocated = sum((D(a["amount"]) for a in got["allocations"]), D("0.00"))
        assert allocated + D(got["unallocated_amount"]) == D(case["amount"]), case["name"]
        if case["fiscal"]:
            assert sum((D(ln["amount"]) for ln in got["fiscal_lines"]), D("0.00")) == D(case["amount"]), case[
                "name"
            ]
        else:
            assert got["fiscal_lines"] == []


def _sale(
    doc_id: str, doc_date: str, open_amount: str, *lines: tuple[str, str], due: str | None = None
) -> OpenDoc:
    return OpenDoc(
        "sales", doc_id, doc_date, due, D(open_amount),
        tuple(OpenLine(f"{doc_id}-{i}", None, D(q), D(t), D("12.00"), D("0.00")) for i, (q, t) in enumerate(lines)),
    )  # fmt: skip


def test_qt_m08_11_payment_allocated_oldest_first() -> None:
    """QT-M08-11: old 100 000 + new 200 000, payment 100 000 → the old one is closed, the new one untouched."""
    old = _sale("a", "2026-09-01", "100000.00", ("1.000", "100000.00"))
    new = _sale("b", "2026-10-01", "200000.00", ("1.000", "200000.00"))
    result = allocate(D("100000.00"), [new, old])
    assert [(a.target_doc_id, a.amount) for a in result.allocations] == [("a", D("100000.00"))]
    assert result.unallocated_amount == D("0.00")


def test_qt_m08_06_07_example_31_receipt_lines_only_from_s1() -> None:
    """31 «Misol — QT-M08-06/07»: S1 200 000 + S2 100 000, payment 150 000 → S1 75 %, S2 not on the receipt."""
    s1 = _sale("s1", "2026-09-01", "200000.00", ("4.000", "120000.00"), ("1.000", "80000.00"))
    s2 = _sale("s2", "2026-09-15", "100000.00", ("1.000", "100000.00"))
    result = allocate(D("150000.00"), [s2, s1])
    assert [(a.target_doc_id, a.amount) for a in result.allocations] == [("s1", D("150000.00"))]
    assert {ln.sale_id for ln in result.fiscal_lines} == {"s1"}
    assert [(ln.qty, ln.amount) for ln in result.fiscal_lines] == [
        (D("3.000"), D("90000.00")),
        (D("0.750"), D("60000.00")),
    ]


def test_writeoff_comes_after_every_open_debt() -> None:
    w = OpenDoc("debt_writeoffs", "w", "2020-01-01", None, D("10.00"))
    s = _sale("s", "2026-09-01", "5.00", ("1.000", "5.00"))
    result = allocate(D("12.00"), [w, s])
    assert [(a.target_doc_type, a.amount) for a in result.allocations] == [
        ("sales", D("5.00")),
        ("debt_writeoffs", D("7.00")),
    ]


def test_invalid_input() -> None:
    with pytest.raises(ValueError, match="positive"):
        allocate(D("0.00"), [])
    with pytest.raises(ValueError, match="doc_type"):
        allocate(D("1.00"), [OpenDoc("returns", "x", "2026-01-01", None, D("1.00"))])


def _vector(name: str) -> dict[str, Any]:
    return next(c for c in _cases() if c["name"] == name)


def test_acc01_returned_line_excluded_from_debt_receipt() -> None:
    """ACC-01 (R1 repro): A 60 000 + B 40 000 on debt, B returned, payment 60 000 → one line A 60 000.00 with
    A's qty and marking code; nothing on B (vector ``returned_line_debt_sale`` — the TS twin runs it too)."""
    case = _vector("returned_line_debt_sale")
    got = allocate_json(case["amount"], case["open_docs"], fiscal=True)
    assert got == case["expected"]
    a_line = case["open_docs"][0]["lines"][0]
    assert [
        (ln["sale_line_id"], ln["qty"], ln["amount"], ln["marking_code"]) for ln in got["fiscal_lines"]
    ] == [(a_line["sale_line_id"], a_line["qty"], "60000.00", a_line["marking_code"])]
    # without the returned fields the old formula split the money 60/40 over A and B
    plain = [{**case["open_docs"][0], "lines": [
        {k: v for k, v in ln.items() if not k.startswith("returned_")} for ln in case["open_docs"][0]["lines"]
    ]}]  # fmt: skip
    assert len(allocate_json(case["amount"], plain)["fiscal_lines"]) == 2


def test_acc01_partly_returned_line_keeps_its_remainder() -> None:
    line = OpenLine("l1", None, D("3.000"), D("300.00"), D("12.00"), D("0.00"), None, D("1.000"), D("100.00"))
    doc = OpenDoc("sales", "s", "2026-10-01", None, D("200.00"), (line,))
    result = allocate(D("200.00"), [doc])
    assert [(ln.qty, ln.amount) for ln in result.fiscal_lines] == [(D("2.000"), D("200.00"))]


def test_acc10_partial_receipts_qty_sum_equals_line_qty() -> None:
    """ACC-10: three partial payments of one line — the receipt quantities add up to exactly the line qty."""
    settled = D("0.00")
    qtys: list[Decimal] = []
    for amount in ("100.00", "100.00", "100.00"):
        line = OpenLine("l1", None, D("1.000"), D("300.00"), D("12.00"), settled)
        doc = OpenDoc("sales", "s", "2026-10-01", None, D("300.00") - settled, (line,))
        result = allocate(D(amount), [doc])
        (fl,) = result.fiscal_lines
        qtys.append(fl.qty)
        settled += fl.amount
    assert qtys == [D("0.333"), D("0.334"), D("0.333")]
    assert sum(qtys, D("0.000")) == D("1.000")
    assert _vector("three_partials_qty_sums_to_line_qty")["expected"]["fiscal_lines"][0]["qty"] == "0.334"


def test_acc02_reconcile_trims_oldest_open_debt_to_balance() -> None:
    """ACC-02: a credit on the account without a document closes the oldest debt; write-offs stay untouched."""
    from app.shared.debt_allocation import reconcile_to_balance

    old = _sale("a", "2026-09-01", "20000.00", ("1.000", "20000.00"))
    new = _sale("b", "2026-10-01", "50000.00", ("1.000", "50000.00"))
    wo = OpenDoc("debt_writeoffs", "w", "2026-01-01", None, D("7000.00"))
    got = reconcile_to_balance([new, wo, old], D("30000.00"))
    assert [(d.doc_id, d.open_amount) for d in got] == [
        ("b", D("30000.00")),
        ("w", D("7000.00")),
        ("a", D("0.00")),
    ]
    assert reconcile_to_balance([new, old], D("90000.00")) == [new, old]  # balance ≥ Σ open: unchanged
    assert [d.open_amount for d in reconcile_to_balance([new, old], D("-5.00"))] == [D("0.00"), D("0.00")]
