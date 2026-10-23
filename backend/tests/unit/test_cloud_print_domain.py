"""Cloud print wire formats (B5-T04; 24 §6.1) and the SYNC-05 lenient ``CardResult`` clean-up — pure units."""

from __future__ import annotations

import base64
import zlib
from datetime import UTC, datetime

import pytest

from app.modules.integrations.card_terminal.application.schemas import lenient_card_result, parse_card_result
from app.modules.integrations.card_terminal.domain.model import (
    capability_devices,
    capability_enabled,
    tashkent_date,
)
from app.modules.integrations.cloud_print.domain.model import (
    RasterError,
    SdpResponseError,
    decode_raster,
    epos_print_request,
    parse_sdp_response,
    raster_to_png,
    secret_hash,
    star_delete_outcome,
    star_poll_response,
)


def test_b5_t04_raster_validation() -> None:
    data = bytes([0xFF, 0x80]) * 2
    assert decode_raster(9, 2, base64.b64encode(data).decode()) == data  # 9 dots → 2 bytes per row
    for width, height, payload in ((9, 3, data), (4, 2, data), (16, 2, b"\x00")):
        with pytest.raises(RasterError):
            decode_raster(width, height, base64.b64encode(payload).decode())
    with pytest.raises(RasterError):
        decode_raster(16, 2, "@@not-base64@@")
    with pytest.raises(RasterError):
        decode_raster(1024, 20000, "")  # over the size cap


def test_b5_t04_png_is_1bit_inverted() -> None:
    png = raster_to_png(9, 1, bytes([0b1010_0000, 0b1000_0000]))
    idat = png[png.index(b"IDAT") + 4 : png.index(b"IEND") - 8]
    raw = zlib.decompress(idat)
    assert raw == bytes([0, 0b0101_1111, 0b0111_1111])  # filter byte, then inverted bits; padding white


def test_b5_t04_star_cloudprnt_messages() -> None:
    assert star_poll_response(None) == {"jobReady": False}
    assert star_poll_response("j1") == {"jobReady": True, "mediaTypes": ["image/png"], "jobToken": "j1"}
    assert star_delete_outcome("200 OK").printed and not star_delete_outcome("200 OK").retry
    assert star_delete_outcome("520 Timeout").retry
    failed = star_delete_outcome("410 Paper")
    assert not failed.printed and not failed.retry and failed.code == "410 Paper"
    assert star_delete_outcome(None).code == "unknown"
    assert len(secret_hash("s")) == 64


def test_b5_t04_epson_sdp_request_and_response() -> None:
    xml = epos_print_request([("job-1", 8, 1, b"\xff")])
    assert "<printjobid>job-1</printjobid>" in xml and 'mode="mono">/w==</image>' in xml
    v2 = (
        '<PrintResponseInfo Version="2.00"><ePOSPrint><Parameter><printjobid>job-1</printjobid></Parameter>'
        '<PrintResponse><response success="true" code=""/></PrintResponse></ePOSPrint></PrintResponseInfo>'
    )
    [r] = parse_sdp_response(v2)
    assert (r.printjobid, r.success, r.code) == ("job-1", True, "")
    [r1] = parse_sdp_response('<PrintResponseInfo Version="1.00"><response success="false" code="EPTR"/>'
                              "</PrintResponseInfo>")  # fmt: skip
    assert (r1.printjobid, r1.success, r1.code) == (None, False, "EPTR")
    for bad in ("<x/>", "not xml", '<!DOCTYPE a [<!ENTITY b "c">]><PrintResponseInfo/>'):
        with pytest.raises(SdpResponseError):
            parse_sdp_response(bad)


def test_b5_t05_capabilities_and_business_date() -> None:
    caps = {
        "card_terminal": {"enabled": True, "devices": [{"local_id": "a"}, "junk"]},
        "print": {"enabled": 1},
    }
    assert capability_enabled(caps, "card_terminal") and not capability_enabled(caps, "print")
    assert not capability_enabled({}, "card_terminal")
    assert capability_devices(caps, "card_terminal") == [{"local_id": "a"}]
    assert tashkent_date(datetime(2026, 10, 17, 19, 30, tzinfo=UTC)).isoformat() == "2026-10-18"


def test_sync_05_lenient_card_result_unit() -> None:
    raw = {
        "attempt_id": "0192f000-0000-7000-8000-000000000001", "card_terminal_id": "0192f000-0000-7000-8000-000000000002",
        "kind": "purchase", "status": "approved", "amount": "100.00", "resolved_by": "auto",
        "rrn": "1234 5678-9012", "card_mask": "860031xxxxxx1234", "approval_code": "AB-12", "tid": "T-1",
        "card_scheme": "Visa", "entry_mode": "nfc", "card_type": "gold", "card_type_source": "terminal",
        "decline_message": "y" * 600, "tx_at": "yesterday", "extra": 1,
    }  # fmt: skip
    cleaned, fields = lenient_card_result(raw)
    result = parse_card_result(cleaned)
    assert (result.rrn, result.card_mask, result.approval_code, result.tid) == (
        "123456789012", "8600********1234", "AB12", "T1")  # fmt: skip
    assert result.card_scheme == "visa" and result.entry_mode is None and result.card_type is None
    assert (
        result.card_type_source is None and result.tx_at is None and len(result.decline_message or "") == 500
    )
    assert set(fields) >= {"rrn", "card_mask", "approval_code", "tid", "card_scheme", "entry_mode", "card_type",
                           "card_type_source", "decline_message", "tx_at", "extra"}  # fmt: skip
    assert lenient_card_result("x") == ({}, ["card_result"])
