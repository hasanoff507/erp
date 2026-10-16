"""``TenantSettings`` keys, defaults and merge (20 M13a/M14 table, 12 ``tenants.settings``). Pure Python.

Only explicitly set keys are stored in ``tenants.settings``; defaults are applied on read, so a
default that depends on another field (``owner_withdrawal_account`` ← ``legal_form``) follows it.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Final

LEGAL_FORMS: Final = ("llc", "jsc", "private_enterprise", "sole_proprietor")
CONSENT_PURPOSES: Final = ("ai_cross_border",)
TAX_REGIMES: Final = ("vat", "turnover")

# keys PATCH /tenant/settings may write (20 #40b); ai_cross_border_enabled only via POST /tenant/consents
WRITABLE_KEYS: Final = frozenset(
    {
        "bank_account",
        "bank_mfo",
        "supplier_overpay_policy",
        "vat_diff_tolerance_amount",
        "marking_precheck",
        "discount_posting",
        "owner_withdrawal_account",
        "payment_org_commission_account",
        "turnover_tax_account",
        "negative_stock_policy",
        "ai_training_consent",
        "fiscal_policy",
        "card_manual_fallback",
    }
)

_DEFAULTS: Final[dict[str, Any]] = {
    "bank_account": None,
    "bank_mfo": None,
    "supplier_overpay_policy": "warn",  # qaror #47
    "vat_diff_tolerance_amount": "1000.00",  # qaror #50
    "marking_precheck": "warn",  # qaror #62
    "discount_posting": "gross_9050",
    "payment_org_commission_account": "9430",
    "turnover_tax_account": "9430",
    "negative_stock_policy": "allow",  # offline overselling is accepted by default (16 §5)
    "ai_training_consent": False,
    "ai_cross_border_enabled": False,  # qaror #61
    "card_manual_fallback": "manager_approval",  # qaror #71
}
_FISCAL_POLICY_DEFAULTS: Final[dict[str, str]] = {
    "debt_receipt_split": "single",
    "credit_sale_receipt": "none",
}


def default_owner_withdrawal_account(legal_form: str) -> str:
    """13 §2.18: sole proprietor → 8720, every other legal form → 4890."""
    return "8720" if legal_form == "sole_proprietor" else "4890"


def effective_settings(stored: dict[str, Any], legal_form: str) -> dict[str, Any]:
    """Stored ``tenants.settings`` + defaults, restricted to the API keys (20 TenantSettings)."""
    out: dict[str, Any] = {key: stored.get(key, default) for key, default in _DEFAULTS.items()}
    out["owner_withdrawal_account"] = stored.get(
        "owner_withdrawal_account", default_owner_withdrawal_account(legal_form)
    )
    fiscal = stored.get("fiscal_policy")
    out["fiscal_policy"] = {**_FISCAL_POLICY_DEFAULTS, **(fiscal if isinstance(fiscal, dict) else {})}
    return out


def merge_settings(stored: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    """Partial update: keys in ``patch`` replace stored ones, ``fiscal_policy`` merges one level deep."""
    merged = deepcopy(stored)
    for key, value in patch.items():
        if key == "fiscal_policy" and isinstance(value, dict):
            current = merged.get("fiscal_policy")
            merged["fiscal_policy"] = {**(current if isinstance(current, dict) else {}), **value}
        else:
            merged[key] = value
    return merged
