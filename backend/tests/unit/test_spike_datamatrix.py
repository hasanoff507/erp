"""Bosqich 0 spike: zxing-cpp and GS1 DataMatrix with FNC1 (26 #62, OQ-064, 27 Bosqich 0).

Vectors: ``tests/fixtures/datamatrix/vectors.json`` (Asl belgisi / CRPT-like codes).
Results: ``research_notes/ochiq-savollar/spike-datamatrix.md``.

* round trip: zxing-cpp encodes the HRI form ``(01)…(21)…`` in GS1 mode, zxing-cpp
  decodes it back to the element string with GS (U+001D) separators;
* cross-check: a symbol encoded by an independent encoder (bwip-js, the browser
  label renderer of qaror #8) is decoded by zxing-cpp.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

zxingcpp = pytest.importorskip("zxingcpp")

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "datamatrix" / "vectors.json"
VECTORS: list[dict[str, Any]] = json.loads(FIXTURES.read_text(encoding="utf-8"))["vectors"]
IDS = [v["name"] for v in VECTORS]

GS = "\x1d"
# GS1 General Specifications: AIs whose length is predefined never need a GS after them
_FIXED_LENGTH_PREFIXES = {f"{n:02d}" for n in (*range(5), *range(11, 21), *range(31, 37), 41)}
# zint/zxing-cpp DataMatrix size index: 1..24 are the square ECC 200 symbols (10x10 … 144x144)
_SQUARE_VERSIONS = range(1, 25)


def element_string(ais: list[list[str]]) -> str:
    out: list[str] = []
    for i, (ai, value) in enumerate(ais):
        out.append(ai + value)
        if i < len(ais) - 1 and ai[:2] not in _FIXED_LENGTH_PREFIXES:
            out.append(GS)
    return "".join(out)


def encode_square(hri: str) -> Any:
    """Smallest square ECC 200 symbol: zxing-cpp's auto size may pick a DMRE rectangle."""
    last: Exception | None = None
    for version in _SQUARE_VERSIONS:
        try:
            return zxingcpp.create_barcode(hri, zxingcpp.BarcodeFormat.DataMatrix, gs1=True, version=version)
        except ValueError as exc:  # "Input too long for Version N"
            last = exc
    raise AssertionError(f"does not fit any square DataMatrix: {last}")


def render(matrix: list[str], *, scale: int = 4, quiet: int = 2) -> memoryview:
    """Module matrix → 8-bit grayscale image buffer (dark = 0) with a quiet zone."""
    size_y, size_x = len(matrix), len(matrix[0])
    width, height = (size_x + 2 * quiet) * scale, (size_y + 2 * quiet) * scale
    pixels = bytearray(b"\xff" * (width * height))
    for y, row in enumerate(matrix):
        for x, bit in enumerate(row):
            if bit == "1":
                for dy in range(scale):
                    start = ((y + quiet) * scale + dy) * width + (x + quiet) * scale
                    pixels[start : start + scale] = b"\x00" * scale
    return memoryview(pixels).cast("B", (height, width))


def decode(image: Any, text_mode: Any = None) -> Any:
    mode = zxingcpp.TextMode.Plain if text_mode is None else text_mode
    result = zxingcpp.read_barcode(image, formats=zxingcpp.BarcodeFormat.DataMatrix, text_mode=mode)
    assert result is not None, "no DataMatrix found"
    return result


def assert_gs1_square(result: Any, payload: str) -> None:
    assert result.format == zxingcpp.BarcodeFormat.DataMatrix
    assert result.text == payload  # FNC1 → implicit prefix, separators → GS
    assert result.content_type == zxingcpp.ContentType.GS1
    assert result.symbology_identifier == "]d2"  # ISO/IEC 15424: DataMatrix, FNC1 in first position
    rows, cols = result.extra["Version"].split("x")
    assert rows == cols, f"not a square ECC 200 symbol: {result.extra['Version']}"


@pytest.mark.parametrize("vector", VECTORS, ids=IDS)
def test_fixture_payload_is_the_gs1_element_string(vector: dict[str, Any]) -> None:
    assert vector["payload"] == element_string(vector["ais"])
    assert vector["hri"] == "".join(f"({ai}){value}" for ai, value in vector["ais"])


@pytest.mark.parametrize("vector", VECTORS, ids=IDS)
def test_zxing_round_trip_keeps_fnc1_and_gs(vector: dict[str, Any]) -> None:
    barcode = encode_square(vector["hri"])
    assert barcode.content_type == zxingcpp.ContentType.GS1
    image = barcode.to_image(scale=4)

    assert_gs1_square(decode(image), vector["payload"])
    # HRI text mode gives back the human-readable (AI) form for display
    assert decode(image, zxingcpp.TextMode.HRI).text == vector["hri"]


@pytest.mark.parametrize("vector", VECTORS, ids=IDS)
def test_zxing_decodes_symbol_from_independent_encoder(vector: dict[str, Any]) -> None:
    assert_gs1_square(decode(render(vector["bwipjs_matrix"])), vector["payload"])


def test_gs1_mode_takes_hri_input_not_raw_control_characters() -> None:
    raw = VECTORS[-1]["payload"]
    assert GS in raw
    with pytest.raises(ValueError, match="Control characters"):
        zxingcpp.create_barcode(raw, zxingcpp.BarcodeFormat.DataMatrix, gs1=True)
