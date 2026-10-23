"""E-document rules shared by e-invoices, e-TTN and powers of attorney (21 §2, §3, §5, §6) — pure Python.

* :func:`document_hash` — what the browser signs with E-IMZO (``sign-challenge`` → ``document_hash``): the
  SHA-256 (hex) of the canonical JSON (sorted keys, no spaces, UTF-8) of ``{entity, id, action, document}``.
  The signed content of the attached PKCS#7 is the ``document_hash`` string itself (ASCII), so a signature
  is bound to the document, its state and the action; a document changed after the challenge no longer
  matches (``EIMZO_SIGN_FAILED``, ``reason='document_changed'``).
* State machines (12 ``einvoices`` / ``ettn_documents`` / ``powers_of_attorney``; 19 §8a, §19, §20; 18 §14a).
* Outgoing e-invoice amounts from receipt lines (13 §2.22: no posting — amounts only).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Any, Final, Literal

from app.core.money import money

Entity = Literal["einvoices", "ettn_documents", "powers_of_attorney"]
SignAction = Literal["sign", "accept", "reject"]

ZERO: Final = Decimal("0.00")
TASHKENT: Final = timezone(timedelta(hours=5))  # Asia/Tashkent, no DST
CHALLENGE_TTL_S: Final = 600

# einvoices
EINVOICE_SIGNABLE: Final = {"in": frozenset({"received"}), "out": frozenset({"draft"})}
EINVOICE_REJECTABLE: Final = frozenset({"received", "signed"})
EINVOICE_OUT_CANCELLABLE: Final = frozenset({"draft", "signed"})
# ettn_documents
ETTN_SIGNABLE: Final = frozenset({"pending_signature", "failed"})
ETTN_RESPONDABLE: Final = {"in": frozenset({"received"}), "out": frozenset({"registered"})}
ETTN_MANUAL_BLOCKED: Final = frozenset({"registered", "accepted", "cancelled"})
# powers_of_attorney
POA_SIGNABLE: Final = frozenset({"pending_signature", "failed"})
POA_CANCELLABLE: Final = frozenset({"draft", "pending_signature"})
POA_DEFAULT_DAYS: Final = 10


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode()


def document_hash(entity: Entity, entity_id: str, action: SignAction, document: Mapping[str, Any]) -> str:
    body = {"entity": entity, "id": entity_id, "action": action, "document": dict(document)}
    return hashlib.sha256(canonical_json(body)).hexdigest()


def signed_content(doc_hash: str) -> bytes:
    """The content of the attached PKCS#7 the browser makes for a challenge (21 §5)."""
    return doc_hash.encode("ascii")


# --- amounts -------------------------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class InvoiceLine:
    """One outgoing e-invoice line (net = without VAT)."""

    name: str
    qty: Decimal
    net_amount: Decimal
    vat_rate: Decimal
    vat_amount: Decimal
    product_id: str | None = None
    mxik: str | None = None
    unit_code: str | None = None
    marking_code: str | None = None

    @property
    def total(self) -> Decimal:
        return self.net_amount + self.vat_amount


def invoice_totals(lines: Sequence[InvoiceLine]) -> tuple[Decimal, Decimal]:
    """(total incl. VAT, VAT) — sums of the rounded lines (13 §5.3)."""
    total = money(sum((ln.total for ln in lines), ZERO))
    vat = money(sum((ln.vat_amount for ln in lines), ZERO))
    return total, vat


def sale_line_net(line_total: Decimal, vat_amount: Decimal) -> Decimal:
    """A receipt line is VAT-inclusive (``line_total``): the e-invoice net is ``line_total − vat_amount``."""
    return money(line_total - vat_amount)


# --- marking acceptance deadline (19 §8, VM 833 66–67) -------------------------------------------------
def marking_due_at(dispatch_day: date, deadline_kind: str) -> datetime:
    """Acceptance deadline counted from the dispatch (e-invoice / e-TTN) date, Asia/Tashkent:
    ``72_hours`` → dispatch day 00:00 + 72 h; ``3_business_days`` → end of the 3rd Mon–Fri day after the
    dispatch day (no public-holiday calendar — conservative only on weekends)."""
    start = datetime.combine(dispatch_day, time.min, tzinfo=TASHKENT)
    if deadline_kind == "72_hours":
        return (start + timedelta(hours=72)).astimezone(UTC)
    day, counted = dispatch_day, 0
    while counted < 3:
        day += timedelta(days=1)
        if day.weekday() < 5:
            counted += 1
    return (datetime.combine(day, time.min, tzinfo=TASHKENT) + timedelta(days=1)).astimezone(UTC)


def poa_valid_to(valid_from: date) -> date:
    return valid_from + timedelta(days=POA_DEFAULT_DAYS)
