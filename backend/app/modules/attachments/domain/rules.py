"""Attachment upload rules (17 §12; 12 ``attachments``). Pure Python.

* uploadable ``kind`` → the module permission the uploader needs (any one of them);
  the other ``attachments.kind`` values (``export``, ``label_pdf``, ``billing_invoice``, ``einvoice``,
  ``onec_diagnostics``, ``other``) are written by the server itself and are not uploaded here;
* per kind the accepted content types; per content type the size limit (image 10 MB, PDF 20 MB,
  Excel/CSV 10 MB) — over it ``413 FILE_TOO_LARGE``, another type ``415 UNSUPPORTED_FILE_TYPE``;
* the declared type must match the file's magic bytes (a renamed file is refused — 415);
* the time-limited download URL: ``HMAC-SHA256(key, "{tenant}:{id}:{exp}")`` (stand-in for the S3
  presigned URL of 23 §7 while files live on the shared volume).
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Final

MB: Final = 1024 * 1024
JPEG: Final = "image/jpeg"
PNG: Final = "image/png"
PDF: Final = "application/pdf"
XLSX: Final = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
XLS: Final = "application/vnd.ms-excel"
CSV: Final = "text/csv"
ZIP: Final = "application/zip"  # server-written only (onec_diagnostics, A-07) — never uploadable here

MAX_BYTES: Final[dict[str, int]] = {
    JPEG: 10 * MB,
    PNG: 10 * MB,
    PDF: 20 * MB,
    XLSX: 10 * MB,
    XLS: 10 * MB,
    CSV: 10 * MB,
}
UPLOAD_LIMIT: Final = max(MAX_BYTES.values())

UPLOAD_PERMISSIONS: Final[dict[str, tuple[str, ...]]] = {
    "expense_receipt": ("expenses.create",),
    "ocr_source": ("ai.ocr.use",),
    "state_report": ("tax.compare.review",),
    "import": ("catalog.manage", "stock.opening.manage", "bank_settlements.manage"),
}
# SEC-02 (17 §12): a bank statement is read only with the bank-settlement right, not the other import rights
BANK_STATEMENT_READ: Final[tuple[str, ...]] = ("bank_settlements.manage",)
# server-written kinds readable through GET /attachments/{id} (no upload path): kind → read rights
SERVER_KIND_READ: Final[dict[str, tuple[str, ...]]] = {
    "onec_diagnostics": ("onec.settings.manage",),  # Do'kon agenti diagnostics package (33 W-07/A-07, BO-14)
}
CONTENT_TYPES: Final[dict[str, frozenset[str]]] = {
    "expense_receipt": frozenset({JPEG, PNG, PDF}),
    "ocr_source": frozenset({JPEG, PNG, PDF}),
    "state_report": frozenset({PDF, XLSX, XLS}),
    "import": frozenset({XLSX, CSV}),
}
EXTENSIONS: Final[dict[str, str]] = {
    JPEG: "jpg",
    PNG: "png",
    PDF: "pdf",
    XLSX: "xlsx",
    XLS: "xls",
    CSV: "csv",
    ZIP: "zip",
}
URL_TTL_S: Final = 15 * 60  # 17 §12: signed URL lives 15 minutes


def normalize_type(content_type: str | None) -> str:
    return (content_type or "").split(";", 1)[0].strip().lower()


def matches_magic(content_type: str, content: bytes) -> bool:
    """The bytes really are what the declared type says (no executable/HTML behind a .jpg)."""
    if content_type == JPEG:
        return content.startswith(b"\xff\xd8\xff")
    if content_type == PNG:
        return content.startswith(b"\x89PNG\r\n\x1a\n")
    if content_type == PDF:
        return content.startswith(b"%PDF-")
    if content_type == XLSX:
        return content.startswith(b"PK\x03\x04")
    if content_type == XLS:
        # Legacy BIFF workbooks are OLE Compound File containers.
        return content.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")
    if content_type == CSV:
        return b"\x00" not in content[:4096]
    return False


def url_signature(key: bytes, tenant_id: str, attachment_id: str, expires: int) -> str:
    message = f"{tenant_id}:{attachment_id}:{expires}".encode()
    return hmac.new(key, message, hashlib.sha256).hexdigest()


def signature_ok(
    key: bytes, tenant_id: str, attachment_id: str, expires: int, signature: str, now: int
) -> bool:
    if expires < now:
        return False
    return hmac.compare_digest(url_signature(key, tenant_id, attachment_id, expires), signature)
