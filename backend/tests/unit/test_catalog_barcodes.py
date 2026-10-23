"""Internal EAN-13 rules (US-M09-05, QT-M09-05 unit half)."""

from __future__ import annotations

import pytest

from app.modules.catalog.domain.barcodes import (
    INTERNAL_SEQ_MAX,
    INTERNAL_SEQ_MIN,
    InternalRangeExhaustedError,
    barcode_format_ok,
    ean_check_digit,
    internal_barcode,
    is_internal_barcode,
    is_valid_ean13,
    is_weight_prefixed,
)


@pytest.mark.parametrize(
    ("code", "valid"),
    [("4780000000012", False), ("4006381333931", True), ("5901234123457", True), ("5901234123458", False)],
)
def test_ean13_check_digit(code: str, valid: bool) -> None:
    assert is_valid_ean13(code) is valid
    assert ean_check_digit("400638133393") == 1


@pytest.mark.parametrize("seq", [INTERNAL_SEQ_MIN, INTERNAL_SEQ_MIN + 1, 41_234_567_890, INTERNAL_SEQ_MAX])
def test_internal_codes_are_rcn_04_ean13_outside_weight_and_gtin_ranges(seq: int) -> None:
    code = internal_barcode(seq)
    assert len(code) == 13 and code.isdigit()
    assert code.startswith("04")  # GS1 RCN 040–049
    assert is_valid_ean13(code)
    assert not is_weight_prefixed(code)  # 20–29 weight/sum prefixes
    assert is_internal_barcode(code)


def test_internal_sequence_is_unique_and_ordered() -> None:
    codes = [internal_barcode(INTERNAL_SEQ_MIN + i) for i in range(1000)]
    assert len(set(codes)) == 1000
    assert codes[0] == "0400000000008"  # 4×3 = 12 → check digit 8


def test_internal_range_is_bounded() -> None:
    with pytest.raises(InternalRangeExhaustedError):
        internal_barcode(INTERNAL_SEQ_MAX + 1)
    with pytest.raises(InternalRangeExhaustedError):
        internal_barcode(INTERNAL_SEQ_MIN - 1)


def test_manual_barcode_formats() -> None:
    assert barcode_format_ok("4780000000012", "ean")
    assert barcode_format_ok("ABC-123", "ean")
    assert not barcode_format_ok("has space", "ean")
    assert not barcode_format_ok("", "ean")
    assert barcode_format_ok(internal_barcode(INTERNAL_SEQ_MIN), "internal")
    assert not barcode_format_ok("4780000000012", "internal")
    assert not barcode_format_ok("0400000000001", "internal")  # wrong check digit
    assert is_weight_prefixed("2212345012340") and not is_weight_prefixed("4780000000012")
