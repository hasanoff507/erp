"""Cloud print rules and printer wire formats (24 §6.1, 12 ``cloud_printers``/``print_jobs``). Pure Python.

* The job raster is the web client's 1-bit image (``web/packages/shared/lib/src/printer/bitmap.ts``): rows of
  ``ceil(width/8)`` bytes, most significant bit = leftmost dot, bit set = black.
* **Star CloudPRNT** (HTTP polling; Star Micronics "CloudPRNT Protocol Guide" and the reference server
  ``ExampleServers/php_queue/cloudprnt.php`` of github.com/star-micronics/cloudprnt-sdk): the printer POSTs a
  JSON status (``printerMAC``, ``statusCode`` …) and gets ``{"jobReady", "mediaTypes", "jobToken"}``; it
  then GETs the job (``?mac=&type=&token=``) and confirms with DELETE (``?mac=&code=&token=``, or GET with
  ``&delete``). ``code`` starting with ``2`` = printed; ``520`` = download timeout (job stays queued).
  We offer ``image/png`` (1-bit grayscale PNG built here).
* **Epson Server Direct Print** (Seiko Epson "Server Direct Print User's Manual" and its sample program): the
  printer POSTs ``application/x-www-form-urlencoded`` ``ConnectionType=GetRequest`` and receives a
  ``<PrintRequestInfo>`` document with one ``<ePOSPrint>`` per job (ePOS-Print XML ``<image>`` raster,
  ``<printjobid>``); results come back as ``ConnectionType=SetResponse`` with ``ResponseFile`` =
  ``<PrintResponseInfo Version="1.00|2.00">``.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
import struct
import zlib
from dataclasses import dataclass
from typing import Final, Literal
from xml.etree import ElementTree as ET

Protocol = Literal["star_cloudprnt", "epson_sdp"]
JobKind = Literal["receipt", "test", "label"]
JobStatus = Literal["queued", "printing", "done", "failed"]

PROTOCOLS: Final = frozenset({"star_cloudprnt", "epson_sdp"})
MAX_WIDTH_DOTS: Final = 1024
MAX_HEIGHT_DOTS: Final = 20000
MAX_RASTER_BYTES: Final = 600_000  # keeps the JSON body (base64) under the 1 MB API limit
JOB_TTL_MINUTES: Final = 30  # a receipt not picked up by then is not printed any more ('expired')
UNCONFIRMED_MINUTES: Final = 5  # a job handed out and never confirmed → failed, not re-sent
ONLINE_WITHIN_S: Final = 60  # printers poll every few seconds (CloudPRNT default 5 s)
STAR_MEDIA_TYPE: Final = "image/png"
EPOS_NS: Final = "http://www.epson-pos.com/schemas/2011/03/epos-print"
MAX_SDP_RESPONSE_BYTES: Final = 64 * 1024
_INVERT: Final = bytes(255 - b for b in range(256))


class RasterError(ValueError):
    """The submitted raster does not match its declared size."""


def new_secret() -> str:
    """32 random bytes, base64url without padding — shown once, only the SHA-256 is stored."""
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode("ascii")


def secret_hash(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def row_bytes(width_dots: int) -> int:
    return (width_dots + 7) // 8


def decode_raster(width_dots: int, height_dots: int, data_base64: str) -> bytes:
    """Base64 → raw bytes, checked against ``ceil(width/8) * height`` and the size cap."""
    if not 8 <= width_dots <= MAX_WIDTH_DOTS or not 1 <= height_dots <= MAX_HEIGHT_DOTS:
        raise RasterError("dimensions")
    expected = row_bytes(width_dots) * height_dots
    if expected > MAX_RASTER_BYTES:
        raise RasterError("too_large")
    try:
        data = base64.b64decode(data_base64, validate=True)
    except (ValueError, TypeError):
        raise RasterError("base64") from None
    if len(data) != expected:
        raise RasterError("length")
    return data


def raster_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _png_chunk(tag: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", len(payload)) + tag + payload + struct.pack(">I", zlib.crc32(tag + payload))


def raster_to_png(width_dots: int, height_dots: int, data: bytes) -> bytes:
    """1-bit grayscale PNG (bit depth 1, colour type 0). PNG uses 0 = black, so the bits are inverted."""
    stride = row_bytes(width_dots)
    inverted = data.translate(_INVERT)  # padding bits are 0 in the raster → 1 (white) in the PNG
    raw = bytearray()
    for y in range(height_dots):
        raw.append(0)  # filter: none
        raw.extend(inverted[y * stride : (y + 1) * stride])
    header = struct.pack(">IIBBBBB", width_dots, height_dots, 1, 0, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", header)
        + _png_chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + _png_chunk(b"IEND", b"")
    )


# --- Star CloudPRNT ----------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class StarDelete:
    printed: bool
    retry: bool  # 520 download timeout — the job goes back to the queue
    code: str


def star_delete_outcome(code: str | None) -> StarDelete:
    """``code`` of the CloudPRNT DELETE (e.g. ``200 OK``, ``520 …``): 2xx printed; 520 retry; else failed."""
    value = (code or "").strip()
    head = value[:3]
    return StarDelete(printed=value.startswith("2"), retry=head == "520", code=value[:100] or "unknown")


def star_poll_response(job_id: str | None) -> dict[str, object]:
    if job_id is None:
        return {"jobReady": False}
    return {"jobReady": True, "mediaTypes": [STAR_MEDIA_TYPE], "jobToken": job_id}


# --- Epson Server Direct Print -----------------------------------------------------------------------


def epos_print_request(jobs: list[tuple[str, int, int, bytes]]) -> str:
    """``<PrintRequestInfo Version="2.00">``, one ``<ePOSPrint>`` per job ``(id, width, height, data)``."""
    root = ET.Element("PrintRequestInfo", {"Version": "2.00"})
    for job_id, width, height, data in jobs:
        epos = ET.SubElement(root, "ePOSPrint")
        params = ET.SubElement(epos, "Parameter")
        ET.SubElement(params, "devid").text = "local_printer"
        ET.SubElement(params, "timeout").text = "10000"
        ET.SubElement(params, "printjobid").text = job_id
        print_data = ET.SubElement(epos, "PrintData")
        doc = ET.SubElement(print_data, "epos-print", {"xmlns": EPOS_NS})
        image = ET.SubElement(
            doc, "image", {"width": str(width), "height": str(height), "color": "color_1", "mode": "mono"}
        )
        image.text = base64.b64encode(data).decode("ascii")
        ET.SubElement(doc, "feed", {"line": "3"})
        ET.SubElement(doc, "cut", {"type": "feed"})
    body = ET.tostring(root, encoding="unicode")
    return '<?xml version="1.0" encoding="utf-8"?>' + body


@dataclass(frozen=True, slots=True)
class SdpResult:
    printjobid: str | None  # Version 2.00; None in 1.00 (results follow the order of the request)
    success: bool
    code: str


class SdpResponseError(ValueError):
    """``ResponseFile`` is not a ``PrintResponseInfo`` document we can read."""


def parse_sdp_response(xml_text: str) -> list[SdpResult]:
    """``PrintResponseInfo`` Version 1.00 (``<response success code>``) and 2.00
    (``<ePOSPrint><Parameter><printjobid/></Parameter><PrintResponse><response …/></PrintResponse>``)."""
    if len(xml_text.encode("utf-8")) > MAX_SDP_RESPONSE_BYTES or "<!DOCTYPE" in xml_text.upper():
        raise SdpResponseError("rejected")
    try:
        root = ET.fromstring(xml_text)  # noqa: S314 -- no DTD (checked above), size-capped
    except ET.ParseError:
        raise SdpResponseError("xml") from None
    if _local(root.tag) != "PrintResponseInfo":
        raise SdpResponseError("root")
    out: list[SdpResult] = []
    for child in root:
        name = _local(child.tag)
        if name == "response":
            out.append(_result(None, child))
        elif name == "ePOSPrint":
            job_id = None
            response = None
            for part in child.iter():
                tag = _local(part.tag)
                if tag == "printjobid" and part.text:
                    job_id = part.text.strip()
                elif tag == "response":
                    response = part
            if response is not None:
                out.append(_result(job_id, response))
    return out


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _result(job_id: str | None, element: ET.Element) -> SdpResult:
    success = (element.get("success") or "").strip().lower() == "true"
    return SdpResult(job_id, success, (element.get("code") or "").strip()[:100])
