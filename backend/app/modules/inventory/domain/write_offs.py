"""Write-offs (19 §15, 13 §2.12, §4.3, US-M04-06). Pure Python.

Cost line of every line — ``Dt`` :func:`cost_account` ``/ Kt inv_acct`` = the issue cost:

==============================================  =======================================
``reason``                                       ``Dt``
==============================================  =======================================
``expired``/``damaged``/``expired_return``/      ``9430``; ``4730`` when
``other``                                        ``write_offs.responsible_user_id`` (analytics
                                                 ``employee_id``)
``gift`` + ``gift_kind='promo_justified'``       ``9410`` (no VAT)
``gift`` + ``gift_kind='other'``                 ``9430`` + VAT ``Dt 9430 / Kt 6410``
==============================================  =======================================

Gift VAT (13 §2.12, SK 248-modda 3-qism 2-band): ``market_value = ROUND_HALF_UP(retail price
(VAT included) / (1 + rate/100) × qty, 2)``, ``vat = ROUND_HALF_UP(market_value × rate / 100, 2)``,
``vat_moves(kind='output', base_amount=market_value)`` — only for a VAT-regime tenant (13 §4.3) and
``rate > 0``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Final, Literal
from uuid import UUID

from app.core.money import HUNDRED, money, qty, to_decimal
from app.modules.inventory.domain.costing import (
    ZERO_MONEY,
    LotView,
    Method,
    fifo_order,
    plan_issue,
)

Reason = Literal["expired", "damaged", "gift", "expired_return", "other"]
GiftKind = Literal["promo_justified", "other"]
REASONS: Final = ("expired", "damaged", "gift", "expired_return", "other")
MANUAL_REASONS: Final = ("expired", "damaged", "gift", "other")  # expired_return — only from returns
LOSS_ACCOUNT: Final = "9430"
EMPLOYEE_ACCOUNT: Final = "4730"
PROMO_ACCOUNT: Final = "9410"
VAT_ACCOUNT: Final = "6410"


def cost_account(reason: str, gift_kind: str | None, responsible_user_id: UUID | None) -> str:
    """``Dt`` of the cost line (13 §2.12)."""
    if reason == "gift":
        return PROMO_ACCOUNT if gift_kind == "promo_justified" else LOSS_ACCOUNT
    return EMPLOYEE_ACCOUNT if responsible_user_id is not None else LOSS_ACCOUNT


def gift_needs_vat(reason: str, gift_kind: str | None) -> bool:
    return reason == "gift" and gift_kind == "other"


@dataclass(frozen=True, slots=True)
class GiftVat:
    market_value: Decimal
    vat: Decimal


def gift_vat(retail_price: Decimal, rate_pct: Decimal, quantity: Decimal) -> GiftVat:
    """Market value without VAT and its VAT (13 §2.12, rounding 13 §5.3)."""
    rate = to_decimal(rate_pct)
    if rate < 0:
        raise ValueError("VAT rate cannot be negative")
    market = money(to_decimal(retail_price) * qty(quantity) / (1 + rate / HUNDRED))
    return GiftVat(market, money(market * rate / HUNDRED))


# --- read-only cost estimate for the approval limit (19 §15) -----------------------------------
@dataclass(frozen=True, slots=True)
class EstimateLine:
    key: tuple[UUID, UUID]
    quantity: Decimal
    lot_id: UUID | None
    from_blocked: bool


@dataclass(frozen=True, slots=True)
class KeyState:
    """What the estimate needs of one (warehouse, product): open lots, AVECO ``avg_cost``, an estimate
    unit cost for the uncovered (pending) part."""

    lots: list[LotView]
    avg_cost: Decimal | None
    pending_unit_cost: Decimal


@dataclass(frozen=True, slots=True)
class Estimate:
    total: Decimal
    covered: list[Decimal]  # per line, what the lots give
    uncovered: list[Decimal]  # per line, the pending (negative-stock) part


def estimate_cost(
    method: Method, lines: Sequence[EstimateLine], states: dict[tuple[UUID, UUID], KeyState]
) -> Estimate:
    """Total issue cost of ``lines`` taken one after another (same allocation rules as the toolkit:
    FIFO piece cost ``qty × lot.unit_cost``, AVECO ``covered × avg_cost``, the uncovered rest at the
    pending estimate). Residual-value rounding of a last-unit-out issue is ignored — it is an estimate
    to compare with ``stock.writeoff.limit_value`` before anything is issued."""
    lots = {key: {lot.id: lot for lot in st.lots} for key, st in states.items()}
    total = ZERO_MONEY
    covered: list[Decimal] = []
    uncovered: list[Decimal] = []
    for ln in lines:
        st = states[ln.key]
        views = fifo_order(list(lots[ln.key].values()))
        plan = plan_issue(views, ln.quantity, lot_id=ln.lot_id, from_blocked=ln.from_blocked)
        if method == "fifo":
            total += sum((money(q * lot.unit_cost) for lot, q in plan.pieces), ZERO_MONEY)
        else:
            total += money(plan.covered * (st.avg_cost or Decimal("0")))
        total += money(plan.uncovered * st.pending_unit_cost)
        covered.append(plan.covered)
        uncovered.append(plan.uncovered)
        for lot, q in plan.pieces:
            lots[ln.key][lot.id] = LotView(
                lot.id,
                lot.received_at,
                lot.qty_left - q,
                lot.blocked_qty - q if ln.from_blocked else lot.blocked_qty,
                lot.unit_cost,
            )
    return Estimate(money(total), covered, uncovered)
