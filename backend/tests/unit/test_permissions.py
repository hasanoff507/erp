"""Default role matrix (15 §2.1–§2.3)."""

from __future__ import annotations

from decimal import Decimal

from app.modules.access.domain.permissions import (
    DEFAULT_MATRIX,
    PERMISSION_CODES,
    PERMISSIONS,
    TENANT_PERMISSION_CODES,
    SystemRole,
)


def test_catalog_codes_are_unique_and_well_formed() -> None:
    codes = [p.code for p in PERMISSIONS]
    assert len(codes) == len(set(codes))
    assert all(c == c.lower() and "." in c for c in codes)


def test_matrix_only_uses_catalog_codes() -> None:
    for role, perms in DEFAULT_MATRIX.items():
        assert set(perms) <= PERMISSION_CODES, role


def test_owner_is_superset_without_limits_qaror_28() -> None:
    owner = DEFAULT_MATRIX[SystemRole.OWNER]
    assert set(owner) == set(TENANT_PERMISSION_CODES)
    assert "platform.admin" not in owner
    assert all(limit is None for limit in owner.values())
    for role, perms in DEFAULT_MATRIX.items():
        assert set(perms) <= set(owner), role


def test_owner_only_codes_stay_with_owner() -> None:
    owner_only = {p.code for p in PERMISSIONS if p.owner_only}
    assert owner_only == {"debts.forgive", "settings.tenant", "billing.manage"}
    for role, perms in DEFAULT_MATRIX.items():
        if role is not SystemRole.OWNER:
            assert not owner_only & set(perms), role


def test_cashier_default_limits_qaror_23() -> None:
    cashier = DEFAULT_MATRIX[SystemRole.CASHIER]
    assert cashier["discount.give"] == Decimal("5.00")
    assert cashier["returns.approve"] == Decimal("100000.00")
    assert cashier["cash.withdraw"] == Decimal("50000.00")
    assert cashier["sales.void"] is None


def test_owner_exclusive_codes_match_15_2_2() -> None:
    others: set[str] = set()
    for role, perms in DEFAULT_MATRIX.items():
        if role is not SystemRole.OWNER:
            others |= set(perms)
    # ticked only in the Egasi column of 15 §2.2
    assert set(TENANT_PERMISSION_CODES) - others == {
        "debts.forgive", "prices.approve", "settings.users", "settings.branches", "settings.tenant",
        "expenses.approve", "billing.manage", "notifications.manage", "onec.settings.manage",
    }  # fmt: skip


def test_matrix_sizes_match_15_2_2() -> None:
    sizes = {role: len(perms) for role, perms in DEFAULT_MATRIX.items()}
    assert sizes == {
        SystemRole.OWNER: 67,
        SystemRole.MANAGER: 42,
        SystemRole.CASHIER: 13,
        SystemRole.STOREKEEPER: 11,
        SystemRole.ACCOUNTANT: 29,
    }
