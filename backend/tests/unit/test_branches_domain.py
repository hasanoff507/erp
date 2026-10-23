"""Pure rules of the branches module: codes, warehouse accounts, tax history, tenant settings."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from app.modules.access.domain.descriptions import PERMISSION_DESCRIPTIONS
from app.modules.access.domain.permissions import PERMISSION_CODES
from app.modules.access.domain.roles import PermissionEntry, validate_permission_set
from app.modules.branches.domain.model import (
    fiscal_pair_ok,
    inventory_account_for,
    month_start,
    next_free_code,
    next_month_start,
    register_allowance,
    tashkent_today,
)
from app.modules.branches.domain.tax import (
    RateRow,
    TaxSetting,
    rate_in_force,
    setting_in_force,
    turnover_rate_code,
)
from app.modules.branches.domain.tenant_settings import effective_settings, merge_settings

RATES = {
    "retail_city_100k_plus": [RateRow(date(2026, 1, 1), Decimal("4.00"))],
    "retail_other": [RateRow(date(2026, 1, 1), Decimal("2.00"))],
    "retail_remote_mountain": [RateRow(date(2026, 1, 1), Decimal("1.00"))],
}


def test_next_free_two_digit_code() -> None:
    assert next_free_code([]) == "01"
    assert next_free_code(["01"]) == "02"
    assert next_free_code(["01", "02", "04", "A1"]) == "03"
    assert next_free_code([f"{n:02d}" for n in range(1, 100)]) is None


def test_inventory_account_from_warehouse_type() -> None:
    assert inventory_account_for("store") == "2920"
    assert inventory_account_for("stock") == "2910"


def test_tashkent_day_and_months() -> None:
    assert tashkent_today(datetime(2026, 10, 31, 19, 30, tzinfo=UTC)) == date(2026, 11, 1)  # UTC+5
    assert tashkent_today(datetime(2026, 10, 31, 18, 59, tzinfo=UTC)) == date(2026, 10, 31)
    assert month_start(date(2026, 10, 17)) == date(2026, 10, 1)
    assert next_month_start(date(2026, 10, 17)) == date(2026, 11, 1)
    assert next_month_start(date(2026, 12, 31)) == date(2027, 1, 1)


def test_register_allowance_and_fiscal_pair() -> None:
    assert register_allowance(1, 0) == 1
    assert register_allowance(1, 2) == 3
    assert fiscal_pair_ok(None, None) and fiscal_pair_ok("agent", "fm-1")
    assert not fiscal_pair_ok("agent", None) and not fiscal_pair_ok(None, "fm-1")


def test_qt_m14_05_old_category_applies_before_valid_from() -> None:
    """QT-M14-05: other → city_100k_plus from 2026-11-01; October 2026 is taxed with the old 2%."""
    history = [
        TaxSetting(date(2026, 3, 1), "other", "retail"),
        TaxSetting(date(2026, 11, 1), "city_100k_plus", "retail"),
    ]
    october = setting_in_force(history, date(2026, 10, 31))
    november = setting_in_force(history, date(2026, 11, 1))
    assert october is not None and november is not None
    assert october.settlement_category == "other"
    assert november.settlement_category == "city_100k_plus"
    code = turnover_rate_code(october.settlement_category, october.activity_type)
    assert code == "retail_other"
    assert rate_in_force(RATES[code], date(2026, 10, 15)) == Decimal("2.00")
    assert setting_in_force(history, date(2026, 2, 28)) is None


@pytest.mark.parametrize(
    ("category", "activity", "legal_form", "code"),
    [
        ("city_100k_plus", "retail", "llc", "retail_city_100k_plus"),  # QT-M14-04 (4%)
        ("other", "retail", "llc", "retail_other"),  # QT-M14-03 (2%)
        ("remote_mountain", "retail", "jsc", "retail_remote_mountain"),
        ("other", "other", "llc", "general"),
        ("other", "retail", "sole_proprietor", "sole_proprietor"),
    ],
)
def test_turnover_rate_code(category: str, activity: str, legal_form: str, code: str) -> None:
    assert turnover_rate_code(category, activity, legal_form) == code


def test_rate_in_force_uses_latest_valid_from() -> None:
    rows = [RateRow(date(2026, 1, 1), Decimal("4.00")), RateRow(date(2027, 1, 1), Decimal("3.00"))]
    assert rate_in_force(rows, date(2026, 12, 31)) == Decimal("4.00")
    assert rate_in_force(rows, date(2027, 1, 1)) == Decimal("3.00")
    assert rate_in_force(rows, date(2025, 12, 31)) is None


def test_tenant_settings_defaults_and_merge() -> None:
    eff = effective_settings({}, "llc")
    assert eff["owner_withdrawal_account"] == "4890" and eff["vat_diff_tolerance_amount"] == "1000.00"
    assert effective_settings({}, "sole_proprietor")["owner_withdrawal_account"] == "8720"
    assert (
        effective_settings({"owner_withdrawal_account": "4890"}, "sole_proprietor")[
            "owner_withdrawal_account"
        ]
        == "4890"
    )
    assert "weight_barcode_templates" not in effective_settings({"weight_barcode_templates": []}, "llc")
    stored = {"fiscal_policy": {"debt_receipt_split": "per_sale"}, "weight_barcode_templates": [1]}
    merged = merge_settings(
        stored, {"fiscal_policy": {"credit_sale_receipt": "credit_type"}, "marking_precheck": "off"}
    )
    assert merged == {
        "fiscal_policy": {"debt_receipt_split": "per_sale", "credit_sale_receipt": "credit_type"},
        "weight_barcode_templates": [1],  # keys owned by other screens are kept
        "marking_precheck": "off",
    }
    assert stored["fiscal_policy"] == {"debt_receipt_split": "per_sale"}  # not mutated


def test_permission_set_rules_and_descriptions() -> None:
    assert set(PERMISSION_DESCRIPTIONS) == set(PERMISSION_CODES)
    ok = [PermissionEntry("discount.give", Decimal("8.00")), PermissionEntry("sales.create", None)]
    assert validate_permission_set(ok) == []
    problems = validate_permission_set(
        [
            PermissionEntry("cash.withdraw", Decimal("1000000")),  # so'm limit: no upper bound
            PermissionEntry("prices.approve", Decimal("101")),  # percent
            PermissionEntry("billing.manage", None),  # owner only
        ]
    )
    assert [(p.field, p.message_key) for p in problems] == [
        ("permissions[1].limit_value", "validation.max_value"),
        ("permissions[2].code", "validation.owner_only_permission"),
    ]
