"""Mandatory PII masking for everything sent to the AI provider (22 §7, 15 §5.2, qaror #61).

Personal fields (person name, phone, STIR of a sole proprietor, PINFL/JShShIR,
address) are replaced with glossary tokens such as ``mijoz A`` before the
prompt leaves the process, and restored in the answer. Card data, passwords and
PINs are never sent at all — they are removed, not tokenised.

There is deliberately no switch: no setting, tenant option or argument turns
this off (QT-AI-PII-01).
"""

from __future__ import annotations

import re
import string
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Any, Protocol

REMOVED = "[olib tashlandi]"


class PiiKind(StrEnum):
    PERSON = "person"
    PHONE = "phone"
    STIR = "stir"
    PINFL = "pinfl"
    ADDRESS = "address"
    EMAIL = "email"


_TOKEN_PREFIX: dict[PiiKind, str] = {
    PiiKind.PERSON: "mijoz",
    PiiKind.PHONE: "telefon",
    PiiKind.STIR: "STIR",
    PiiKind.PINFL: "JShShIR",
    PiiKind.ADDRESS: "manzil",
    PiiKind.EMAIL: "email",
}

# Keys are normalised first (camelCase → snake_case, lower case), see _normalise_key.

# whole keys (or key endings, e.g. ``customer_full_name``) that hold a person's name
_PERSON_NAME_KEYS = frozenset(
    {
        "full_name",
        "fio",
        "first_name",
        "last_name",
        "middle_name",
        "surname",
        "patronymic",
        "given_name",
        "family_name",
        "contact_person",
    }
)

# key parts (``_``-separated words) that mark the value as personal data → tokenised
_PII_KEY_PARTS: tuple[tuple[frozenset[str], PiiKind], ...] = (
    (frozenset({"email", "emails", "mail"}), PiiKind.EMAIL),
    (frozenset({"phone", "phones", "telefon", "mobile", "msisdn", "tel"}), PiiKind.PHONE),
    (frozenset({"pinfl", "jshshir"}), PiiKind.PINFL),
    (frozenset({"stir", "inn", "tin"}), PiiKind.STIR),
    (frozenset({"address", "addresses", "manzil"}), PiiKind.ADDRESS),
)

# a bare "name" (or ``<container>_name``) is personal only for a person-like object;
# product/warehouse names are fine to send
_PERSON_CONTAINERS = frozenset(
    {
        "counterparty",
        "customer",
        "client",
        "debtor",
        "debt",
        "creditor",
        "supplier",
        "buyer",
        "payer",
        "recipient",
        "user",
        "employee",
        "contact",
        "owner",
        "cashier",
        "courier",
        "driver",
        "person",
        "people",
        "member",
        "mijoz",
        "kontragent",
    }
)

# payload keys (normalised) that must never reach the provider in any form (22 §7)
_FORBIDDEN_KEY = re.compile(
    r"(^|_)(password|passwd|pin|pin_code|pin_hash|password_hash|pan|card|card_number|card_mask|cvv|cvc|"
    r"track|track2|rrn|approval_code|secret|token|private_key|otp|"
    r"passport|pasport|passport_series|passport_number|biometric|biometrics|fingerprint)($|_)",
)

# Uzbek mobile operator / landline area codes for numbers written without the 998 prefix
_UZ_AREA_CODES = "20|33|50|55|61|62|65|66|67|69|70|71|72|73|74|75|76|77|78|79|88|90|91|93|94|95|97|98|99"
_PHONE = re.compile(
    r"(?<!\d)(?<!\d\.)"  # not inside a longer number or after a decimal point
    r"(?:\+?998[\s\-]*\(?\d{2}\)?|\(?(?:" + _UZ_AREA_CODES + r")\)?)"
    r"[\s\-]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}"
    r"(?!\d)(?!\.\d)(?!,\d{1,2}(?!\d))"  # not followed by more digits or decimals (amounts)
)
_PINFL = re.compile(r"(?<!\d)\d{14}(?!\d)")
_STIR_LABELLED = re.compile(r"(?i)(stir|inn|инн|стир)(\W{0,5})(\d{9})(?!\d)")
_CARD = re.compile(r"(?<!\d)(?:\d[ \-]?){12,18}\d(?!\d)")
_EMAIL = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")


class TokenGlossary(Protocol):
    """Token source for one AI request (22 §7).

    The token ↔ value map lives in memory for a single AI call only
    (:class:`RequestGlossary`) and is never written to the DB, logs or
    ``ai_requests``. ``tenant_glossary`` is a vocabulary of tenant terms, not a
    PII store, and never backs this interface.
    """

    def token_for(self, kind: PiiKind, value: str) -> str: ...


class RequestGlossary:
    """Stable tokens within one AI request: the same value always gets the same token."""

    def __init__(self) -> None:
        self._by_value: dict[tuple[PiiKind, str], str] = {}
        self._counters: dict[PiiKind, int] = {}

    def token_for(self, kind: PiiKind, value: str) -> str:
        key = (kind, _normalise(value))
        token = self._by_value.get(key)
        if token is None:
            index = self._counters.get(kind, 0)
            self._counters[kind] = index + 1
            token = f"{_TOKEN_PREFIX[kind]} {_letters(index)}"
            self._by_value[key] = token
        return token


def _letters(index: int) -> str:
    letters = string.ascii_uppercase
    out = ""
    index += 1
    while index:
        index, rem = divmod(index - 1, 26)
        out = letters[rem] + out
    return out


def _normalise_key(key: str) -> str:
    """``phoneNumber`` / ``Phone-Number`` / ``PHONE_NUMBER`` → ``phone_number``."""
    snake = _CAMEL.sub("_", key.strip())
    return re.sub(r"[\s\-.]+", "_", snake).lower()


def _singular(word: str) -> str:
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    if word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def _is_person_container(parent: str | None) -> bool:
    if not parent:
        return False
    last = _normalise_key(parent).split("_")[-1]
    return last in _PERSON_CONTAINERS or _singular(last) in _PERSON_CONTAINERS


def _is_forbidden(key: str) -> bool:
    return _FORBIDDEN_KEY.search(_normalise_key(key)) is not None


def _pii_kind(key: str | None, parent: str | None) -> PiiKind | None:
    if key is None:
        return None
    norm = _normalise_key(key)
    if norm in _PERSON_NAME_KEYS or any(norm.endswith("_" + n) for n in _PERSON_NAME_KEYS):
        return PiiKind.PERSON
    parts = norm.split("_")
    for words, kind in _PII_KEY_PARTS:
        if any(part in words for part in parts):
            return kind
    if norm in {"name", "names"}:
        return PiiKind.PERSON if _is_person_container(parent) else None
    if parts[-1] in {"name", "names"} and len(parts) > 1:
        return PiiKind.PERSON if _is_person_container("_".join(parts[:-1])) else None
    return None


def _scalar_text(value: Any) -> str | None:
    """Text of a scalar that may carry PII (str, int, float, Decimal) — never bool/None."""
    if isinstance(value, str):
        return value
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int | float | Decimal):
        return str(value)
    return None


def _normalise(value: str) -> str:
    return " ".join(value.split()).casefold()


@dataclass(frozen=True, slots=True)
class PiiValue:
    """A personal value the calling code already knows about (e.g. from a tool result)."""

    kind: PiiKind
    value: str


class PiiMasker:
    """Masks one AI exchange and restores tokens in the answer."""

    def __init__(self, glossary: TokenGlossary | None = None) -> None:
        self._glossary = glossary or RequestGlossary()
        self._originals: dict[str, str] = {}  # token -> original value
        self._known: dict[str, str] = {}  # normalised original -> token

    # -- registration -------------------------------------------------------------
    def register(self, kind: PiiKind, value: str) -> str:
        value = value.strip()
        if not value:
            return value
        token = self._glossary.token_for(kind, value)
        self._originals.setdefault(token, value)
        self._known[_normalise(value)] = token
        return token

    def register_all(self, values: Iterable[PiiValue]) -> None:
        for item in values:
            self.register(item.kind, item.value)

    # -- masking ------------------------------------------------------------------
    def mask_text(self, text: str) -> str:
        # order matters: a labelled 9-digit STIR and a 14-digit PINFL are claimed before the
        # phone pattern can see them; e-mails before phones (digits in the local part)
        text = _STIR_LABELLED.sub(
            lambda m: m.group(1) + m.group(2) + self.register(PiiKind.STIR, m.group(3)), text
        )
        text = _PINFL.sub(lambda m: self.register(PiiKind.PINFL, m.group(0)), text)
        text = _EMAIL.sub(lambda m: self.register(PiiKind.EMAIL, m.group(0)), text)
        text = _PHONE.sub(lambda m: self.register(PiiKind.PHONE, m.group(0)), text)
        text = _CARD.sub(REMOVED, text)
        # known values (names, addresses) — longest first so "Aliyev Vali" wins over "Vali"
        for original in sorted(self._known, key=len, reverse=True):
            pattern = re.compile(r"(?<!\w)" + r"\s+".join(map(re.escape, original.split())) + r"(?!\w)", re.I)
            text = pattern.sub(self._known[original], text)
        return text

    def mask_payload(self, payload: Any) -> Any:
        """Mask a JSON-like structure (tool results, context objects)."""
        # first pass registers values under PII keys so they are also caught in free text
        self._collect(payload)
        return self._mask_value(payload)

    def _collect(self, value: Any, key: str | None = None, parent: str | None = None) -> None:
        if isinstance(value, Mapping):
            for k, v in value.items():
                if not _is_forbidden(str(k)):
                    self._collect(v, str(k), key)
        elif isinstance(value, list | tuple):
            for v in value:
                self._collect(v, key, parent)
        else:
            kind = _pii_kind(key, parent)
            text = _scalar_text(value)
            if kind is not None and text is not None:
                self.register(kind, text)

    def _mask_value(self, value: Any, key: str | None = None, parent: str | None = None) -> Any:
        if isinstance(value, Mapping):
            return {
                k: self._mask_value(v, str(k), key) for k, v in value.items() if not _is_forbidden(str(k))
            }
        if isinstance(value, list | tuple):
            return [self._mask_value(v, key, parent) for v in value]
        kind = _pii_kind(key, parent)
        text = _scalar_text(value)
        if kind is not None and text is not None:
            return self.register(kind, text) if text.strip() else text
        if isinstance(value, str):
            return self.mask_text(value)
        return value

    # -- unmasking ----------------------------------------------------------------
    def unmask_text(self, text: str) -> str:
        for token in sorted(self._originals, key=len, reverse=True):
            text = re.sub(r"(?<!\w)" + re.escape(token) + r"(?!\w)", self._originals[token], text, flags=re.I)
        return text

    def unmask_payload(self, value: Any) -> Any:
        if isinstance(value, Mapping):
            return {k: self.unmask_payload(v) for k, v in value.items()}
        if isinstance(value, list | tuple):
            return [self.unmask_payload(v) for v in value]
        if isinstance(value, str):
            return self.unmask_text(value)
        return value

    @property
    def tokens(self) -> Mapping[str, str]:
        return dict(self._originals)
