"""Pure price resolution (19 §4, QT-M09-01/QT-M09-09 unit half; reused by POS in Bosqich 3)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from app.core.db.base import uuid7
from app.modules.pricing.domain.resolution import (
    PriceRecord,
    change_pct,
    effective_price,
    series_history,
    within_limit,
)

P = uuid7()
B1, B2 = uuid7(), uuid7()


def _at(day: int, hour: int = 0) -> datetime:
    return datetime(2026, 10, day, hour, tzinfo=UTC)


def rec(price: str, day: int, branch: UUID | None = None, hour: int = 0) -> PriceRecord:
    return PriceRecord(
        id=uuid7(), product_id=P, branch_id=branch, price=Decimal(price), valid_from=_at(day, hour)
    )


def test_qt_m09_01_new_price_takes_effect_from_valid_from_old_kept_in_history() -> None:
    old, new = rec("12000.0000", 1), rec("13000.0000", 16, hour=9)
    records = [old, new]
    assert effective_price(records, product_id=P, branch_id=None, at=_at(16, 8)) == Decimal("12000.0000")
    assert effective_price(records, product_id=P, branch_id=None, at=_at(16, 9)) == Decimal("13000.0000")
    history = series_history(records)
    assert [h.record.price for h in history] == [Decimal("13000.0000"), Decimal("12000.0000")]
    assert history[0].valid_to is None and history[1].valid_to == new.valid_from


def test_qt_m09_09_promo_price_ends_automatically() -> None:
    """Promo 10 000 valid 2026-10-10 … 2026-10-14; the regular 12 000 applies again from 10-15."""
    records = [rec("12000.0000", 1), rec("10000.0000", 10), rec("12000.0000", 15)]
    assert effective_price(records, product_id=P, branch_id=None, at=_at(14, 23)) == Decimal("10000.0000")
    assert effective_price(records, product_id=P, branch_id=None, at=_at(15, 9)) == Decimal("12000.0000")
    history = series_history(records)
    assert history[1].record.price == Decimal("10000.0000") and history[1].valid_to == _at(15)


def test_branch_price_overrides_global_and_future_rows_wait() -> None:
    records = [rec("12000.0000", 1), rec("11500.0000", 5, B1), rec("9000.0000", 20, B2)]
    assert effective_price(records, product_id=P, branch_id=B1, at=_at(16)) == Decimal("11500.0000")
    assert effective_price(records, product_id=P, branch_id=B2, at=_at(16)) == Decimal("12000.0000")
    assert effective_price(records, product_id=P, branch_id=B2, at=_at(21)) == Decimal("9000.0000")
    assert effective_price(records, product_id=P, branch_id=None, at=_at(16)) == Decimal("12000.0000")
    assert effective_price(records, product_id=uuid7(), branch_id=None, at=_at(16)) is None
    assert effective_price([rec("1.0000", 30)], product_id=P, branch_id=None, at=_at(16)) is None


def test_same_valid_from_later_row_wins() -> None:
    first, second = rec("100.0000", 1), rec("200.0000", 1)
    assert effective_price([second, first], product_id=P, branch_id=None, at=_at(2)) == Decimal("200.0000")


def test_change_pct_and_limit() -> None:
    assert change_pct(Decimal("12000"), Decimal("13000")) == Decimal("8.3333")
    assert change_pct(Decimal("12000"), Decimal("10800")) == Decimal("10.0000")
    assert change_pct(None, Decimal("5")) is None and change_pct(Decimal("0"), Decimal("5")) is None
    assert within_limit(Decimal("10.0000"), Decimal("10.00"))
    assert not within_limit(Decimal("10.0001"), Decimal("10.00"))
    assert within_limit(Decimal("90"), None) and within_limit(None, Decimal("0"))
    assert _at(1) + timedelta(days=1) == _at(2)
