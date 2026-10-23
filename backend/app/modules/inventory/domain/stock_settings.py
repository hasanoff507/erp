"""Stock settings (19 §17 ``/stock-settings``): weight-barcode templates, expiry / low-stock warnings.

Stored as ``tenants.settings`` JSONB keys (no own table): ``weight_barcode_templates``,
``low_stock_check_enabled``, ``expiry_warning_days``. Pure Python — no I/O.

Template rule (EAN-13 ``PP CCCCC VVVVV K``): 2-digit prefix 20–29, item (PLU) code, value, check digit —
so ``item_code_len + value_len = 10``; a prefix may belong to one template only.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final

# 19 §17 / 11 tenants.settings: 22 = weight in grams (3 decimals → kg), 21 = amount in so'm
DEFAULT_WEIGHT_TEMPLATES: Final[tuple[dict[str, Any], ...]] = (
    {"prefixes": ["22"], "item_code_len": 5, "value_len": 5, "value_kind": "WEIGHT", "decimals": 3,
     "enabled": True},
    {"prefixes": ["21"], "item_code_len": 5, "value_len": 5, "value_kind": "AMOUNT", "decimals": 0,
     "enabled": True},
)  # fmt: skip
DEFAULT_EXPIRY_WARNING_DAYS: Final = 7
DEFAULT_LOW_STOCK_CHECK: Final = True
EAN13_PAYLOAD_DIGITS: Final = 10  # 13 − 2 (prefix) − 1 (check digit)
SETTINGS_KEYS: Final = ("weight_barcode_templates", "low_stock_check_enabled", "expiry_warning_days")


@dataclass(frozen=True, slots=True)
class FieldProblem:
    field: str
    message_key: str


def default_templates() -> list[dict[str, Any]]:
    return [dict(t, prefixes=list(t["prefixes"])) for t in DEFAULT_WEIGHT_TEMPLATES]


def stock_settings_view(stored: Mapping[str, Any]) -> dict[str, Any]:
    """The ``/stock-settings`` body from stored ``tenants.settings`` (defaults for missing keys)."""
    templates = stored.get("weight_barcode_templates")
    days = stored.get("expiry_warning_days")
    low = stored.get("low_stock_check_enabled")
    return {
        "weight_barcode_templates": [dict(t) for t in templates]
        if isinstance(templates, list) and templates
        else default_templates(),
        "low_stock_check_enabled": low if isinstance(low, bool) else DEFAULT_LOW_STOCK_CHECK,
        "expiry_warning_days": days
        if isinstance(days, int) and not isinstance(days, bool) and days >= 0
        else DEFAULT_EXPIRY_WARNING_DAYS,
    }


def template_problems(templates: Sequence[Mapping[str, Any]]) -> list[FieldProblem]:
    """Cross-field rules the request schema cannot express (shape/ranges are checked by the API)."""
    problems: list[FieldProblem] = []
    seen: set[str] = set()
    for i, template in enumerate(templates):
        if int(template["item_code_len"]) + int(template["value_len"]) != EAN13_PAYLOAD_DIGITS:
            problems.append(
                FieldProblem(f"weight_barcode_templates[{i}].value_len", "validation.weight_template_length")
            )
        for j, prefix in enumerate(template["prefixes"]):
            if prefix in seen:
                problems.append(
                    FieldProblem(
                        f"weight_barcode_templates[{i}].prefixes[{j}]", "validation.weight_prefix_duplicate"
                    )
                )
            seen.add(prefix)
    return problems
