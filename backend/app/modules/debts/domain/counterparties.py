"""Counterparty rules (11 §5, 18 §11, 19 §9) — pure Python."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Final, Literal
from uuid import UUID

CounterpartyKind = Literal["person", "company"]
COUNTERPARTY_KINDS: Final = ("person", "company")

_STIR: Final = re.compile(r"^\d{9}$")
_PHONE_SEPARATORS: Final = re.compile(r"[\s\-().]")
_UZ_PHONE: Final = re.compile(r"^\+998\d{9}$")
_E164: Final = re.compile(r"^\+[1-9]\d{7,14}$")

# fields only `debts.limit.manage` may set (18 §11.2/§11.4: "kredit limiti/doimiy chegirma — faqat ...")
LIMIT_FIELDS: Final = frozenset({"credit_limit", "standing_discount_pct"})
# "full" customer requisites (18 §11.2: STIR, bank, kredit limiti → `debts.limit.manage`)
FULL_CUSTOMER_FIELDS: Final = frozenset(
    {
        "stir",
        "legal_address",
        "bank_account",
        "bank_mfo",
        "vat_payer",
        "credit_limit",
        "standing_discount_pct",
    }
)


@dataclass(frozen=True, slots=True)
class Counterparty:
    id: UUID
    kind: str
    name: str
    phone: str | None
    stir: str | None
    legal_address: str | None
    bank_account: str | None
    bank_mfo: str | None
    vat_payer: bool | None
    is_customer: bool
    is_supplier: bool
    credit_limit: Decimal | None
    standing_discount_pct: Decimal | None
    notify_consent: bool
    notify_consent_at: datetime | None
    note: str | None
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime
    version: int


def valid_stir(value: str) -> bool:
    """STIR (INN) — exactly 9 digits (19 §9)."""
    return bool(_STIR.match(value))


def normalize_phone(raw: str) -> str | None:
    """Uzbek numbers → ``+998XXXXXXXXX``; other E.164 numbers are kept (18 §11.1); else ``None``.

    Accepted spellings: ``+998 90 123-45-67``, ``998901234567``, ``90 123 45 67`` (9 national digits).
    """
    value = _PHONE_SEPARATORS.sub("", raw or "")
    if value.isdigit():
        if len(value) == 9:
            value = "+998" + value
        elif len(value) == 12 and value.startswith("998"):
            value = "+" + value
    if _UZ_PHONE.match(value):
        return value
    if value.startswith("+998"):
        return None  # an Uzbek prefix with the wrong length is a typo, not a foreign number
    return value if _E164.match(value) else None


def search_digits(query: str) -> str | None:
    """Digits of a search query when it looks like (part of) a phone/STIR, else ``None``."""
    compact = _PHONE_SEPARATORS.sub("", query).removeprefix("+")
    return compact if len(compact) >= 3 and compact.isdigit() else None
