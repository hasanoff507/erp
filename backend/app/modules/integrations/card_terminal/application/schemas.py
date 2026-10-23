"""``CardResult`` (18 §2.7) — the terminal result as it reaches the server (events and REST).

Money is a decimal string here (``Money``); the port DTOs use tiyin. ``card_type``/``card_type_source``
come from the device (terminal value, or the device's BIN-table lookup); when an approved purchase
arrives without them the server fills ``unknown``/``bin_table`` (the BIN never reaches the server).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints, ValidationError, model_validator

from app.core.error_codes import ErrorCode
from app.core.errors import AppError, ErrorDetail
from app.core.money import MoneyStr
from app.modules.integrations.card_terminal.application.ports import (
    CardScheme,
    CardTxResult,
    CardTypeValue,
    EntryMode,
    TxKind,
)
from app.modules.integrations.card_terminal.domain.model import (
    CARD_SCHEMES,
    CARD_TYPES,
    ENTRY_MODES,
    decline_code_of,
    normalize_mask,
    tx_status_of,
)

Rrn = Annotated[str, StringConstraints(pattern=r"^[0-9A-Za-z]{6,32}$")]
ApprovalCode = Annotated[str, StringConstraints(pattern=r"^[0-9A-Za-z]{1,12}$")]
Mask = Annotated[str, StringConstraints(pattern=r"^[0-9]{4}\*+[0-9]{4}$")]
ShortText = Annotated[str, StringConstraints(max_length=64)]
LongText = Annotated[str, StringConstraints(max_length=500)]
ResultStatus = Literal["approved", "declined", "unknown", "voided"]
ResolvedBy = Literal["auto", "status_query", "manager"]


class CardResultIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attempt_id: UUID
    card_terminal_id: UUID
    kind: TxKind
    original_attempt_id: UUID | None = None
    status: ResultStatus
    amount: MoneyStr
    approval_code: ApprovalCode | None = None
    rrn: Rrn | None = None
    stan: ShortText | None = None
    card_mask: Mask | None = None
    card_scheme: CardScheme | None = None
    card_type: CardTypeValue | None = None
    card_type_source: Literal["terminal", "bin_table"] | None = None
    entry_mode: EntryMode | None = None
    tid: Annotated[str, StringConstraints(pattern=r"^[0-9A-Za-z]{1,16}$")] | None = None
    mid: Annotated[str, StringConstraints(pattern=r"^[0-9A-Za-z]{1,20}$")] | None = None
    acquirer: ShortText | None = None
    tx_at: datetime | None = None
    resolved_by: ResolvedBy
    decline_code: ShortText | None = None
    decline_message: LongText | None = None
    slip_text: Annotated[str, StringConstraints(max_length=4000)] | None = None

    @model_validator(mode="after")
    def _rules(self) -> CardResultIn:
        if self.kind == "void" and self.original_attempt_id is None:
            raise ValueError("original_attempt_id is required for void")
        if self.kind == "purchase" and self.original_attempt_id is not None:
            raise ValueError("original_attempt_id is not allowed for purchase")
        if self.status == "voided" and self.kind != "purchase":
            raise ValueError("only a purchase can be voided")
        if self.resolved_by == "manager":
            details = (self.rrn, self.card_mask, self.approval_code, self.card_type, self.card_type_source)
            if any(v is not None for v in details):
                raise ValueError("manager resolution carries no card details")
            if self.status not in ("approved", "declined"):
                raise ValueError("manager resolution is approved or declined")
        elif self.status in ("approved", "voided") and self.kind != "void":
            if self.rrn is None or self.card_mask is None:
                raise ValueError("rrn and card_mask are required for an approved result")
        if self.card_type_source is not None and self.card_type is None:
            raise ValueError("card_type_source requires card_type")
        return self


def parse_card_result(raw: Any, field: str = "card_result") -> CardResultIn:
    """Raw JSON (event payload) → :class:`CardResultIn`; failures → ``VALIDATION_ERROR`` with ``field``."""
    if isinstance(raw, CardResultIn):
        return raw
    try:
        return CardResultIn.model_validate(raw)
    except ValidationError as exc:
        details = [
            ErrorDetail(
                field=".".join([field, *(str(p) for p in err["loc"])]) if err["loc"] else field,
                message_key="validation.card_result_invalid",
            )
            for err in exc.errors()
        ]
        raise AppError(ErrorCode.VALIDATION_ERROR, details=details) from None


_ALNUM = re.compile(r"[^0-9A-Za-z]")
_SHORT = ("stan", "acquirer", "decline_code")
_LIMITS = {"decline_message": 500, "slip_text": 4000}
_ENUMS: dict[str, frozenset[str]] = {
    "card_type": CARD_TYPES,
    "card_type_source": frozenset({"terminal", "bin_table"}),
    "entry_mode": ENTRY_MODES,
}
_IDENT_MAX = {"rrn": (6, 32), "tid": (1, 16), "mid": (1, 20), "approval_code": (1, 12)}


def lenient_card_result(raw: Any) -> tuple[dict[str, Any], list[str]]:
    """SYNC-05 (16 §2.1 — a paid sale is never rejected for the terminal's data format): event-mode clean-up
    of a ``CardResult`` that failed the strict schema. Identifiers lose separators (``RRN 1234-5678`` →
    ``12345678``), a mask is normalised to 4+4, free text is truncated, unknown enums become ``null``
    (an unknown scheme → ``other``), unknown keys are dropped. Returns the cleaned object and the names of the
    fields that were changed; the caller keeps the raw object in ``terminal_response`` and reports
    ``card_result_mismatch{reason:'malformed_result'}``. Required values that cannot be recovered (an approved
    purchase without a usable RRN/mask) still fail the strict parse afterwards."""
    if not isinstance(raw, Mapping):
        return {}, ["card_result"]
    out: dict[str, Any] = {}
    changed: list[str] = []
    allowed = set(CardResultIn.model_fields)
    for key, value in raw.items():
        if key not in allowed:
            changed.append(str(key))
            continue
        out[key] = value
    for key, (low, high) in _IDENT_MAX.items():
        value = out.get(key)
        if value is None:
            continue
        cleaned = _ALNUM.sub("", str(value))
        if cleaned != value:
            changed.append(key)
        out[key] = cleaned if low <= len(cleaned) <= high else None
        if out[key] is None and key not in changed:
            changed.append(key)
    if out.get("card_mask") is not None:
        norm = normalize_mask(str(out["card_mask"]))
        value = None if norm is None else norm.mask
        if value != out["card_mask"]:
            changed.append("card_mask")
        out["card_mask"] = value
    for key in _SHORT:
        if isinstance(out.get(key), str) and len(out[key]) > 64:
            out[key] = out[key][:64]
            changed.append(key)
    for key, limit in _LIMITS.items():
        if isinstance(out.get(key), str) and len(out[key]) > limit:
            out[key] = out[key][:limit]
            changed.append(key)
    scheme = out.get("card_scheme")
    if scheme is not None and scheme not in CARD_SCHEMES:
        lowered = str(scheme).strip().lower()
        out["card_scheme"] = lowered if lowered in CARD_SCHEMES else ("other" if lowered else None)
        changed.append("card_scheme")
    for key, values in _ENUMS.items():
        if out.get(key) is not None and out[key] not in values:
            out[key] = None
            changed.append(key)
    if out.get("card_type") is None and out.get("card_type_source") is not None:
        out["card_type_source"] = None
        changed.append("card_type_source")
    if out.get("tx_at") is not None and not isinstance(out["tx_at"], datetime):
        try:
            datetime.fromisoformat(str(out["tx_at"]).replace("Z", "+00:00"))
        except ValueError:
            out["tx_at"] = None
            changed.append("tx_at")
    return out, list(dict.fromkeys(changed))


def tiyin_to_money(value: int) -> str:
    sign = "-" if value < 0 else ""
    whole, frac = divmod(abs(value), 100)
    return f"{sign}{whole}.{frac:02d}"


def card_result_from_port(
    result: CardTxResult,
    *,
    card_terminal_id: UUID,
    requested_amount_tiyin: int,
    resolved_by: Literal["auto", "status_query"],
    bin_rule_type: str | None = None,
    original_attempt_id: UUID | None = None,
) -> dict[str, Any]:
    """Adapter ``CardTxResult`` → ``CardResult`` JSON (Python adapters: tests, the future cloud adapter).

    Mirrors the web client mapper: status map, 4+4 mask, ``card_type`` terminal → BIN rule → unknown.
    ``bin_rule_type`` is the BIN-table answer for the BIN of the raw mask (memory only)."""
    status = tx_status_of(result.status)
    norm = normalize_mask(result.card_mask)
    card_type: str | None = None
    source: str | None = None
    if status == "approved" and result.kind == "purchase":
        if result.card_type is not None:
            card_type, source = result.card_type, "terminal"
        else:
            card_type = bin_rule_type if bin_rule_type in ("personal", "corporate", "social") else "unknown"
            source = "bin_table"
    amount = result.amount_tiyin if result.amount_tiyin is not None else requested_amount_tiyin
    return {
        "attempt_id": str(result.attempt_id),
        "card_terminal_id": str(card_terminal_id),
        "kind": result.kind,
        "original_attempt_id": None if original_attempt_id is None else str(original_attempt_id),
        "status": status,
        "amount": tiyin_to_money(amount),
        "approval_code": result.approval_code,
        "rrn": result.rrn,
        "stan": result.stan,
        "card_mask": None if norm is None else norm.mask,
        "card_scheme": result.card_scheme,
        "card_type": card_type,
        "card_type_source": source,
        "entry_mode": result.entry_mode,
        "tid": result.tid,
        "mid": result.mid,
        "acquirer": result.acquirer,
        "tx_at": None if result.tx_at is None else result.tx_at.isoformat(),
        "resolved_by": resolved_by,
        "decline_code": decline_code_of(result.status, result.decline_code),
        "decline_message": result.decline_message,
        "slip_text": result.slip_text,
    }


__all__ = [
    "CardResultIn",
    "card_result_from_port",
    "lenient_card_result",
    "parse_card_result",
    "tiyin_to_money",
]
