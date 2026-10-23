"""Money rules (01 #26, 32 §3) against the shared vectors used by web too."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from app.core.money import (
    from_tiyin,
    line_total,
    money,
    money_str,
    price_str,
    qty_str,
    to_decimal,
    to_tiyin,
    vat_from_gross,
)

VECTORS = Path(__file__).resolve().parents[3] / "shared" / "money-vectors.json"


def _vectors() -> dict[str, Any]:
    if not VECTORS.exists():
        pytest.skip("shared/money-vectors.json not available")
    data: dict[str, Any] = json.loads(VECTORS.read_text(encoding="utf-8"))
    return data


def test_line_total_vectors() -> None:
    for case in _vectors()["line_total"]["cases"]:
        assert money_str(line_total(case["qty"], case["unit_price"], case["discount"])) == case["expected"], (
            case
        )


def test_vat_vectors() -> None:
    for case in _vectors()["vat_from_gross"]["cases"]:
        assert money_str(vat_from_gross(case["amount"], case["rate"])) == case["expected"], case


def test_23_2_2_example() -> None:
    # 23 §2.2: 10 kg x 12 000, VAT 12% included -> 12 857,14 / net 107 142,86
    total = line_total("10", "12000")
    vat = vat_from_gross(total, "12")
    assert (money_str(total), money_str(vat), money_str(total - vat)) == (
        "120000.00",
        "12857.14",
        "107142.86",
    )


def test_half_up_not_bankers() -> None:
    assert money("0.125") == Decimal("0.13")
    assert money("-0.125") == Decimal("-0.13")


@pytest.mark.parametrize("bad", [0.1, 1.0, True])
def test_float_and_bool_are_rejected(bad: object) -> None:
    with pytest.raises(TypeError):
        to_decimal(bad)  # type: ignore[arg-type]


@pytest.mark.parametrize("bad", ["abc", "NaN", "Infinity"])
def test_non_finite_rejected(bad: str) -> None:
    with pytest.raises(ValueError, match="decimal"):
        to_decimal(bad)


def test_tiyin_round_trip() -> None:
    assert to_tiyin("120000.00") == 12_000_000
    assert from_tiyin(12_000_001) == Decimal("120000.01")
    with pytest.raises(ValueError, match="2 decimal"):
        to_tiyin("1.005")


def test_transport_formats() -> None:
    assert (money_str("5"), qty_str("10.5"), price_str("8333.33333")) == ("5.00", "10.500", "8333.3333")
