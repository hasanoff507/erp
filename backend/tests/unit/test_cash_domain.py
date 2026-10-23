"""Pure rules of the cash slice: 13 §2.18 movement lines, 13 §2.19 variance, approval grants (15 §2.3)."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

import pytest

from app.modules.access.domain.approvals import KIND_MISSING_CODE, PERMISSION_BY_KIND, UserGrant
from app.modules.cash.domain.movements import MovementInput, ledger_entry, owner_account, signed, validate
from app.modules.cash.domain.shifts import expected_cash, variance_entry

REG = UUID("00000000-0000-7000-8000-000000000001")
SHIFT = UUID("00000000-0000-7000-8000-000000000002")
BRANCH = UUID("00000000-0000-7000-8000-000000000003")
CP = UUID("00000000-0000-7000-8000-000000000004")


def mv(**over: object) -> MovementInput:
    base: dict[str, object] = {
        "cash_register_id": REG, "shift_id": SHIFT, "direction": "out", "reason": "other",
        "amount": Decimal("40000.00"), "account": None, "counterparty_id": None, "employee_id": None,
        "comment": "x",
    }  # fmt: skip
    base.update(over)
    return MovementInput(**base)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("over", "dt", "kt"),
    [
        ({"reason": "collection", "comment": None}, "5710", "5010"),
        ({"reason": "deposit", "direction": "in", "comment": None}, "5010", "5110"),
        ({"reason": "owner_withdrawal", "counterparty_id": CP, "comment": None}, "4890", "5010"),
        ({}, "9430", "5010"),
        ({"direction": "in"}, "5010", "9390"),
        ({"account": "6310", "counterparty_id": CP}, "6310", "5010"),
    ],
)
def test_qt_m16_01_ledger_lines_13_2_18(over: dict[str, object], dt: str, kt: str) -> None:
    m = mv(**over)
    assert validate(m, sole_proprietor=False) == []
    entry = ledger_entry(m, owner_acct=owner_account("llc", None), branch_id=BRANCH)
    assert (entry.account_dt, entry.account_kt) == (dt, kt)
    assert entry.analytics["cash_register_id"] == str(REG)


def test_owner_account_by_legal_form_and_setting() -> None:
    assert owner_account("llc", None) == "4890"
    assert owner_account("sole_proprietor", None) == "8720"
    assert owner_account("llc", "8720") == "8720"
    assert owner_account("jsc", "9999") == "4890"


def test_reason_direction_and_conditional_fields() -> None:
    assert [v.field for v in validate(mv(reason="deposit"), sole_proprietor=False)] == ["direction"]
    assert [
        v.field
        for v in validate(mv(reason="collection", direction="in", comment=None), sole_proprietor=False)
    ] == ["direction"]
    assert [v.field for v in validate(mv(reason="collection", account="9430"), sole_proprietor=False)] == [
        "account"
    ]
    assert [v.field for v in validate(mv(reason="owner_withdrawal"), sole_proprietor=False)] == [
        "counterparty_id"
    ]
    assert validate(mv(reason="owner_withdrawal"), sole_proprietor=True) == []
    assert [v.field for v in validate(mv(account="4730"), sole_proprietor=False)] == ["employee_id"]
    assert [v.field for v in validate(mv(comment=" "), sole_proprietor=False)] == ["comment"]
    assert [v.field for v in validate(mv(amount=Decimal("0")), sole_proprietor=False)] == ["amount"]
    assert signed("out", Decimal("5.00")) == Decimal("-5.00")


def test_variance_entries_13_2_19() -> None:
    cashier = UUID("00000000-0000-7000-8000-000000000009")
    assert expected_cash(Decimal("200000"), Decimal("360000")) == Decimal("560000.00")
    short = variance_entry(Decimal("-20000.00"), cashier_id=cashier, cash_register_id=REG, shift_id=SHIFT)
    assert short is not None and (short.account_dt, short.account_kt, short.amount) == (
        "4730",
        "5010",
        Decimal("20000.00"),
    )
    assert short.analytics["employee_id"] == str(cashier)
    over = variance_entry(Decimal("5000.00"), cashier_id=cashier, cash_register_id=REG, shift_id=SHIFT)
    assert over is not None and (over.account_dt, over.account_kt) == ("5010", "9390")
    assert variance_entry(Decimal("0.00"), cashier_id=cashier, cash_register_id=REG, shift_id=SHIFT) is None


def test_user_grant_and_kind_maps() -> None:
    cashier = UserGrant(True, False, (), (Decimal("50000"),))
    assert cashier.covers(Decimal("50000")) and not cashier.covers(Decimal("50001"))
    manager = UserGrant(True, False, (str(BRANCH),), (Decimal("10"), None))
    assert manager.limit is None and manager.in_branch(str(BRANCH)) and not manager.in_branch("other")
    owner = UserGrant(True, True, (), ())
    assert owner.holds and owner.covers(Decimal("1e12"))
    blocked = UserGrant(False, True, (), ())
    assert not blocked.holds
    assert set(PERMISSION_BY_KIND) == set(KIND_MISSING_CODE)
    assert PERMISSION_BY_KIND["cash_withdrawal_over_limit"] == "cash.withdraw"
