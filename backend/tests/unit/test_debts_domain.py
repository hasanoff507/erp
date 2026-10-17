"""Counterparty rules and the debt register domain (18 §11, 19 §9, 11 §7, 23 §2.1)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import pytest

from app.core.db.base import uuid7
from app.core.errors import AppError
from app.modules.debts.application.counterparties import (
    check_update_allowed,
    required_for_create,
    validate_row,
)
from app.modules.debts.domain.counterparties import Counterparty, normalize_phone, search_digits, valid_stir
from app.modules.debts.domain.register import DebtMove, lock_order, net_deltas, pending_reversals


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("+998 90 123-45-67", "+998901234567"),
        ("998901234567", "+998901234567"),
        ("90 123 45 67", "+998901234567"),
        ("(90) 123-45-67", "+998901234567"),
        ("+7 900 123 45 67", "+79001234567"),
        ("+9989012345", None),
        ("901234", None),
        ("abc", None),
        ("", None),
    ],
)
def test_normalize_phone(raw: str, expected: str | None) -> None:
    assert normalize_phone(raw) == expected


def test_stir_and_search_digits() -> None:
    assert valid_stir("301234567") and not valid_stir("30123456") and not valid_stir("3012345678")
    assert not valid_stir("30123456a")
    assert search_digits("+998 90 12") == "9989012" and search_digits("90-12") == "9012"
    assert search_digits("Mega") is None and search_digits("12") is None


def test_required_permissions_for_create() -> None:
    assert required_for_create({"is_supplier": True, "is_customer": False, "stir": "301234567"}) == {
        "purchases.create"
    }
    assert required_for_create({"is_customer": True, "phone": "+998901234567"}) == {"debts.create"}
    assert required_for_create({"is_customer": True, "stir": "301234567"}) == {"debts.limit.manage"}
    assert required_for_create({"is_supplier": True, "credit_limit": Decimal("1")}) == {
        "purchases.create",
        "debts.limit.manage",
    }
    assert required_for_create({"is_supplier": True, "is_customer": True}) == {
        "purchases.create",
        "debts.create",
    }
    assert required_for_create({}) == {"debts.limit.manage"}


def _cp(*, is_supplier: bool) -> Counterparty:
    now = datetime.now(UTC)
    return Counterparty(
        id=uuid7(), kind="company", name="X", phone=None, stir="301234567", legal_address=None,
        bank_account=None, bank_mfo=None, vat_payer=None, is_customer=not is_supplier, is_supplier=is_supplier,
        credit_limit=None, standing_discount_pct=None, notify_consent=False, notify_consent_at=None, note=None,
        archived_at=None, created_at=now, updated_at=now, version=1,
    )  # fmt: skip


def test_update_permissions() -> None:
    supplier, customer = _cp(is_supplier=True), _cp(is_supplier=False)
    check_update_allowed(customer, {"credit_limit": Decimal(1)}, frozenset({"debts.limit.manage"}))
    check_update_allowed(supplier, {"name": "Y"}, frozenset({"purchases.create"}))
    for current, changes in (
        (supplier, {"credit_limit": Decimal(1)}),
        (supplier, {"standing_discount_pct": Decimal(1)}),
        (supplier, {"is_customer": True}),
        (customer, {"name": "Y"}),
    ):
        with pytest.raises(AppError) as exc:
            check_update_allowed(current, changes, frozenset({"purchases.create", "debts.create"}))
        assert exc.value.code == "PERMISSION_DENIED"


def _row(**values: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "kind": "person", "name": " Ali ", "phone": "90 111 22 33", "stir": None, "legal_address": "  ",
        "bank_account": None, "bank_mfo": None, "vat_payer": None, "is_customer": True, "is_supplier": False,
        "credit_limit": None, "standing_discount_pct": None, "notify_consent": False, "note": None,
    }  # fmt: skip
    return base | values


def test_validate_row_normalises_and_checks() -> None:
    row = _row()
    validate_row(row)
    assert row["name"] == "Ali" and row["phone"] == "+998901112233" and row["legal_address"] is None
    supplier = _row(kind="company", stir=" 301234567 ", phone=None, is_supplier=True, is_customer=False)
    validate_row(supplier)
    assert supplier["stir"] == "301234567" and supplier["phone"] is None
    for values, field in (
        ({"name": "  "}, "name"),
        ({"phone": None}, "phone"),
        ({"kind": "company"}, "stir"),
        ({"stir": "1234"}, "stir"),
        ({"credit_limit": Decimal("-0.01")}, "credit_limit"),
        ({"standing_discount_pct": Decimal("100.01")}, "standing_discount_pct"),
        ({"is_supplier": None}, "is_supplier"),
    ):
        with pytest.raises(AppError) as exc:
            validate_row(_row(**values))
        assert exc.value.code == "VALIDATION_ERROR" and exc.value.details[0].field == field, values


def _move(cp: UUID, amount: str, reversal_of: UUID | None = None, move_id: UUID | None = None) -> DebtMove:
    return DebtMove(
        id=move_id or uuid7(), counterparty_id=cp, direction="payable", amount=Decimal(amount), due_date=None,
        limit_exceeded=False, doc_type="goods_receipts", doc_id=uuid7(), reversal_of_id=reversal_of,
        created_at=datetime.now(UTC),
    )  # fmt: skip


def test_lock_order_is_by_counterparty_then_direction() -> None:
    low = UUID("00000000-0000-7000-8000-000000000001")
    high = UUID("ffffffff-0000-7000-8000-000000000001")
    keys = [(high, "payable"), (low, "receivable"), (low, "payable"), (high, "payable")]
    assert lock_order(keys) == [(low, "payable"), (low, "receivable"), (high, "payable")]  # type: ignore[arg-type]


def test_net_deltas_and_pending_reversals() -> None:
    a, b = uuid7(), uuid7()
    assert net_deltas(
        [(a, "payable", Decimal("5")), (a, "payable", Decimal("-2")), (b, "receivable", Decimal("1"))]
    ) == {
        (a, "payable"): Decimal("3"),
        (b, "receivable"): Decimal("1"),
    }
    first, second = _move(a, "10.00"), _move(a, "5.00")
    storno = _move(a, "-10.00", reversal_of=first.id)
    assert pending_reversals([first, second, storno]) == [second]
    assert pending_reversals([storno]) == []
