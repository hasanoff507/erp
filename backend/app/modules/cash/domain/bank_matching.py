"""Statement line → (method, branch, RRN registry) recognition (20 #55g, 21 §9.2). Pure Python.

* **method** — by the payer and ``НазначениеПлатежа`` keywords: provider names first (Click / Payme / Uzum),
  then UzQR, then cash collection (inkassa), then card acquiring (also: the payer's INN is the INN of an
  acquirer bank linked to a card terminal — ``card_terminals.acquirer_counterparty_id``);
* **branch** — a terminal / merchant identifier (``card_terminals.tid`` / ``mid``) found in the purpose,
  else the request ``branch_id`` (or the only branch);
* **RRN registry** — an acquirer line that lists the transaction RRNs (``RRN: 000000000001, 000000000002``)
  is matched to integrated card purchases by ``card_terminal_transactions.rrn``; a terminal-less card
  payment (``card_entry_mode='manual'``) has no RRN and is never matched this way — only by amount and date.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Final
from uuid import UUID

_PROVIDERS: Final[tuple[tuple[str, tuple[str, ...]], ...]] = (
    ("click", ("click",)),
    ("payme", ("payme",)),
    ("uzum", ("uzum",)),
)
_UZQR: Final = ("uzqr", "qr-код", "qr код", "qr kod", "qr-kod", "qr to'lov", "по qr")
_COLLECTION: Final = (
    "инкасс",
    "inkass",
    "сдача выручки",
    "сдача наличн",
    "naqd pul topshir",
    "tushumni topshir",
)
_CARD: Final = (
    "эквайр", "ekvayr", "ekvayer", "acquir", "пластик", "plastik", "uzcard", "humo", "visa", "mastercard",
    "карт", "karta", "pos-терминал", "pos terminal", "терминал",
)  # fmt: skip
_RRN = re.compile(r"\bRRN\b[\s:№#=]*((?:[0-9A-Za-z]{6,32}[\s,;]*)+)", re.IGNORECASE)
_TOKEN = re.compile(r"[0-9A-Za-z]{6,32}")
_IDENT = re.compile(r"[0-9A-Za-z]{1,20}")


def detect_method(
    purpose: str, payer_name: str | None, payer_inn: str | None, acquirer_inns: Iterable[str]
) -> str | None:
    text = f"{payer_name or ''} {purpose}".lower()
    for method, words in _PROVIDERS:
        if any(w in text for w in words):
            return method
    if any(w in text for w in _UZQR):
        return "uzqr"
    if any(w in text for w in _COLLECTION):
        return "collection"
    if payer_inn and payer_inn in set(acquirer_inns):
        return "card"
    if any(w in text for w in _CARD):
        return "card"
    return None


def detect_branches(purpose: str, terminal_ids: Mapping[str, UUID]) -> set[UUID]:
    """Branches whose terminal TID/MID (case-insensitive, whole token) occurs in the purpose."""
    tokens = {t.upper() for t in _IDENT.findall(purpose)}
    return {branch for ident, branch in terminal_ids.items() if ident.upper() in tokens}


def detect_terminals(purpose: str, terminal_ids: Mapping[str, UUID]) -> set[str]:
    """TID/MID identifiers (as registered) that occur as whole tokens in the purpose."""
    tokens = {t.upper() for t in _IDENT.findall(purpose)}
    return {ident for ident in terminal_ids if ident.upper() in tokens}


@dataclass(frozen=True, slots=True)
class Batch:
    """An open terminal settlement batch (``card_terminal_settlements``, no bank settlement yet)."""

    id: UUID
    business_date: date
    net_total: Decimal


@dataclass(frozen=True, slots=True)
class BatchMatch:
    gross: Decimal
    settled_from: date
    settled_to: date
    batch_ids: tuple[UUID, ...]


def match_batches(batches: Sequence[Batch], credit: Decimal, tolerance: Decimal) -> BatchMatch | None:
    """13 §2.18a without an RRN registry: the terminal's open batches (TID from the statement purpose), oldest
    first (``business_date``, ``id``) — the smallest prefix with ``Σ net_total ≥ credit`` and
    ``(Σ − credit) / Σ ≤ tolerance`` (the acquirer commission); ``None`` when no prefix fits."""
    total = Decimal("0.00")
    taken: list[Batch] = []
    for batch in sorted(batches, key=lambda b: (b.business_date, b.id)):
        if batch.net_total <= 0:
            continue
        total += batch.net_total
        taken.append(batch)
        if total >= credit:
            if (total - credit) / total <= tolerance:
                return BatchMatch(total, taken[0].business_date, taken[-1].business_date,
                                  tuple(b.id for b in taken))  # fmt: skip
            return None
    return None


def rrn_registry(purpose: str) -> tuple[str, ...]:
    """RRNs listed after an ``RRN`` keyword (order kept, duplicates dropped); tokens need a digit."""
    found: list[str] = []
    for m in _RRN.finditer(purpose):
        for token in _TOKEN.findall(m.group(1)):
            if any(c.isdigit() for c in token) and token.upper() != "RRN":
                found.append(token)
    return tuple(dict.fromkeys(found))
