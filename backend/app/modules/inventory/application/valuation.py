"""FIFO ↔ AVECO: settings API and the one-time data switch (19 §17, US-M04-05, 13 §3.1).

The method in force comes from ``valuation_method_history`` (latest ``valid_from ≤ today``). The stock
data (lots, ``avg_costs``) is *converted* exactly once when a new method takes effect — immediately
for the "no ``stock_moves`` this year" case, otherwise on 1 January (lazily by the first stock lock
of the new year, or by the daily cron, whichever comes first). The method the data currently
reflects is recorded in ``tenants.settings.stock_valuation.applied_method`` (an internal key, not
part of the ``TenantSettings`` API; written with ``version + 1`` so a concurrent settings PATCH can
never silently drop it).

Race safety: every stock transaction takes the tenant's *valuation advisory lock* before any
``stock_balances`` row — shared normally, exclusive to convert. A conversion therefore waits for all
in-flight stock transactions and blocks new ones until it commits; an operation uses the method of
the data it locked (``applied_method``), never a method the data is not in.

Conversion (no ledger entries — the register value is unchanged, 13 §3.1):

* FIFO → AVECO, per (warehouse, product): ``total_value`` = the register value of the units in lots
  (``stock_balances.value`` + pending estimates, i.e. ``Σ qty_left × unit_cost`` up to tiyin
  rounding — the register figure is used so the inventory account and ``avg_costs`` agree exactly),
  ``avg_cost = ROUND_HALF_UP(total_value / Σ qty_left, 4)``, ``qty`` = balance qty.
* AVECO → FIFO: every open lot keeps its quantity, expiry date and blocked qty and is re-priced to
  ``unit_cost = avg_cost`` of its (warehouse, product) — valuation-equivalent to the spec's "one lot
  per (warehouse, product) at avg_cost" without losing expiry/blocked data. The residue between
  ``Σ qty_left × avg_cost`` and the register value is absorbed by the last unit out (``costing``).
"""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.audit import record_audit
from app.core.auth.principal import Principal
from app.core.db.session import tenant_transaction
from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from app.core.idempotency import stage_response
from app.core.money import money, price
from app.modules.accounting.domain.calendar import business_today, day_start, year_start
from app.modules.inventory.application.ports import StockRepository
from app.modules.inventory.domain.costing import ZERO_MONEY, ZERO_QTY, AvgState, Method
from app.modules.inventory.domain.valuation import (
    DEFAULT_METHOD,
    MethodRow,
    current_row,
    decide_change,
    method_on,
    pending_row,
)


def applied_method(state: dict[str, Any] | None, history: list[MethodRow]) -> Method:
    """The method the stock data is in: the marker, else the tenant's initial method (never switched)."""
    if state and state.get("applied_method") in ("fifo", "aveco"):
        method: Method = state["applied_method"]
        return method
    if history:
        return min(history, key=lambda r: r.valid_from).method
    return DEFAULT_METHOD


class ValuationService:
    def __init__(
        self, session_factory: async_sessionmaker[AsyncSession] | None, repo: StockRepository
    ) -> None:
        self._sf = session_factory
        self._repo = repo

    # --- the stock-lock hook ----------------------------------------------------------------------
    async def ensure_applied(self, s: AsyncSession, tenant_id: UUID, today: date | None = None) -> Method:
        """Take the valuation advisory lock and return the method of the stock data (converting first
        when a new method took effect). Must run before any ``stock_balances`` lock of the txn."""
        day = today or business_today()
        history = await self._repo.method_history(s)
        tenant = await self._repo.tenant_stock(s)
        if applied_method(tenant.valuation_state, history) == method_on(history, day):
            await self._repo.advisory_lock(s, tenant_id, shared=True)
            # a conversion may have committed between the read and the lock: use the data's method
            return applied_method((await self._repo.tenant_stock(s)).valuation_state, history)
        await self._repo.advisory_lock(s, tenant_id, shared=False)
        history = await self._repo.method_history(s)
        tenant = await self._repo.tenant_stock(s)
        target = method_on(history, day)
        current = applied_method(tenant.valuation_state, history)
        if current != target:
            await self.convert(s, tenant_id, current, target)
            await self._repo.save_valuation_state(
                s, tenant_id, {**(tenant.valuation_state or {}), "applied_method": target}
            )
        return target

    async def convert(self, s: AsyncSession, tenant_id: UUID, source: Method, target: Method) -> None:
        """Re-express all stock data of the tenant in ``target`` (exclusive valuation lock held)."""
        if source == target:
            return
        balances = await self._repo.all_balances(s)
        lots = await self._repo.all_open_lots(s)
        units: dict[tuple[UUID, UUID], Any] = {}
        for lot in lots:
            key = (lot.warehouse_id, lot.product_id)
            units[key] = units.get(key, ZERO_QTY) + lot.qty_left
        if target == "aveco":
            pending = await self._repo.pending_estimates(s)
            for key, bal in balances.items():
                value = money(bal.value + pending.get(key, ZERO_MONEY))
                n = units.get(key, ZERO_QTY)
                avg = price(value / n) if n > 0 else price(0)
                await self._repo.save_avg(s, tenant_id, key, AvgState(bal.qty, avg, value))
            return
        avgs = await self._repo.all_avg(s)
        for lot in lots:
            state = avgs.get((lot.warehouse_id, lot.product_id))
            if state is not None and state.avg_cost > 0 and lot.unit_cost != state.avg_cost:
                await self._repo.set_lot_unit_cost(s, lot.id, state.avg_cost)

    # --- GET / PATCH /valuation-settings ----------------------------------------------------------
    async def settings(self, actor: Principal) -> dict[str, Any]:
        assert self._sf is not None
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            history = await self._repo.method_history(s)
        return _body(history, business_today())

    async def change(self, actor: Principal, method: Method, ip: str | None) -> dict[str, Any]:
        assert self._sf is not None
        today = business_today()
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            await self._repo.advisory_lock(s, actor.tenant_id, shared=False)  # no stock op in flight
            history = await self._repo.method_history(s)
            tenant = await self._repo.tenant_stock(s)
            state = dict(tenant.valuation_state or {})
            before = _body(history, today)
            decision = decide_change(
                history,
                today,
                method,
                changed_this_year=state.get("changed_year") == today.year,
                moves_this_year=await self._repo.has_moves_since(s, day_start(year_start(today))),
            )
            if decision == "conflict":
                raise AppError(
                    ErrorCode.VALUATION_METHOD_CHANGE_NOT_ALLOWED,
                    params={"requested": method, "current_method": before["current_method"]},
                )
            if decision == "pending":
                await self._repo.upsert_method(
                    s, actor.tenant_id, date(today.year + 1, 1, 1), method, actor.user_id
                )
            elif decision == "immediate":
                source = applied_method(state, history)
                await self._repo.upsert_method(s, actor.tenant_id, year_start(today), method, actor.user_id)
                await self.convert(s, actor.tenant_id, source, method)
                await self._repo.save_valuation_state(
                    s, actor.tenant_id, {**state, "applied_method": method, "changed_year": today.year}
                )
            body = _body(await self._repo.method_history(s), today)
            if decision != "noop":
                await record_audit(
                    s, tenant_id=actor.tenant_id, user_id=actor.user_id, action="valuation_method.changed",
                    entity="valuation_method_history", before=before, after={**body, "mode": decision}, ip=ip,
                )  # fmt: skip
            stage_response(body, 200)
        return body


def _body(history: list[MethodRow], today: date) -> dict[str, Any]:
    current = current_row(history, today)
    pending = pending_row(history, today)
    return {
        "current_method": method_on(history, today),
        "effective_from": current.valid_from.isoformat() if current else None,
        "pending_change": {"method": pending.method, "effective_from": pending.valid_from.isoformat()}
        if pending
        else None,
    }
