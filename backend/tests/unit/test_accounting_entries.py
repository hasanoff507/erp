"""Ledger line validation, storno twin and the business calendar (13 §1, §5.1–§5.3, 16 §8)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from app.modules.accounting.domain.calendar import (
    business_date,
    business_today,
    day_end,
    day_start,
    first_open_date,
    is_closed,
    month_start,
    next_month,
    period_label,
)
from app.modules.accounting.domain.entries import (
    LedgerLine,
    PostingError,
    VatMove,
    checked_line,
    checked_vat,
    swapped,
)

BRANCH = uuid4()


def line(dt: str = "9120", kt: str = "2910", amount: str = "980000.004") -> LedgerLine:
    return LedgerLine(date(2026, 10, 17), BRANCH, dt, kt, Decimal(amount), {"product_id": "p"})


def test_checked_line_quantizes_and_validates() -> None:
    checked = checked_line(line())
    assert checked is not None and checked.amount == Decimal("980000.00")
    assert checked_line(line(amount="0.004")) is None  # rounds to 0 → skipped, never written
    with pytest.raises(PostingError, match="negative"):
        checked_line(line(amount="-1"))
    with pytest.raises(PostingError, match="account_dt == account_kt"):
        checked_line(line("2910", "2910"))
    with pytest.raises(PostingError, match="not in the chart"):
        checked_line(line("1234"))
    with pytest.raises(PostingError, match="not used"):
        checked_line(line("6710", "5010"))  # payroll — out of MVP (qaror #52)
    assert checked_line(line("2910", "0000", "1.005")).amount == Decimal("1.01")  # type: ignore[union-attr]


def test_swapped_is_the_storno_twin() -> None:
    twin = swapped(line(amount="5"), date(2026, 11, 2), {"recost_job_id": "j"})
    assert (twin.account_dt, twin.account_kt, twin.amount, twin.entry_date) == (
        "2910", "9120", Decimal("5"), date(2026, 11, 2),
    )  # fmt: skip
    assert twin.analytics == {"product_id": "p", "recost_job_id": "j"}


def test_vat_move_period_and_validation() -> None:
    move = VatMove(date(2026, 10, 17), "output", Decimal("107142.857"), Decimal("12857.143"))
    assert move.period == date(2026, 10, 1)
    checked = checked_vat(move)
    assert checked is not None and (checked.base_amount, checked.vat_amount) == (
        Decimal("107142.86"), Decimal("12857.14"),
    )  # fmt: skip
    assert checked_vat(VatMove(date(2026, 10, 1), "input", Decimal(0), Decimal(0))) is None
    with pytest.raises(PostingError):
        checked_vat(VatMove(date(2026, 10, 1), "other", Decimal(1), Decimal(1)))  # type: ignore[arg-type]


def test_tashkent_calendar() -> None:
    late_utc = datetime(2026, 10, 16, 20, 30, tzinfo=UTC)  # 01:30 on 17 Oct in Tashkent (UTC+5)
    assert business_date(late_utc) == date(2026, 10, 17)
    assert business_today(late_utc) == date(2026, 10, 17)
    assert day_start(date(2026, 10, 17)) == datetime(2026, 10, 16, 19, 0, tzinfo=UTC)
    assert day_end(date(2026, 9, 30)) == datetime(2026, 9, 30, 18, 59, 59, 999999, tzinfo=UTC)
    with pytest.raises(ValueError, match="aware"):
        business_date(datetime(2026, 1, 1))  # noqa: DTZ001
    assert month_start(date(2026, 12, 31)) == date(2026, 12, 1)
    assert next_month(date(2026, 12, 5)) == date(2027, 1, 1)
    assert period_label(date(2026, 3, 9)) == "2026-03"


def test_period_rules_closing_is_oldest_first() -> None:
    assert not is_closed(date(2026, 10, 5), None)
    closed = date(2026, 9, 1)
    assert is_closed(date(2026, 9, 30), closed) and is_closed(date(2026, 1, 1), closed)
    assert not is_closed(date(2026, 10, 1), closed)
    assert first_open_date(date(2026, 9, 15), closed) == date(2026, 10, 1)  # storno of a closed-period doc
    assert first_open_date(date(2026, 10, 15), closed) == date(2026, 10, 15)
