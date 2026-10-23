"""Stock read API (19 §7: ``stock-balances``, ``stock-lots``, ``stock-moves``), daily stock
notifications (27 B2 "Bildirishnoma voqealari", QT-M04-02/07) and the product cost reader of the
catalog list (19 §1 ``current_cost``).

Warehouse resolution (19 §7, qaror #54): ``warehouse_id`` if given — it must belong to one of the
user's branches (``403 BRANCH_SCOPE_DENIED``, QT-PERM-08); else the warehouse of the ``X-Branch-Id``
branch; without the header the default branch (unrestricted users) or the user's only branch; a
user restricted to several branches must send the header. Owners (no branch restriction) are never
refused (QT-PERM-09).
"""

from __future__ import annotations

import base64
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.auth.principal import Principal
from app.core.db.session import tenant_transaction
from app.core.error_codes import ErrorCode
from app.core.errors import AppError, ErrorDetail
from app.core.money import money, price, qty
from app.core.permissions import BranchScope
from app.modules.accounting.domain.calendar import business_today, day_end, day_start
from app.modules.inventory.application.ports import EventRecorderPort, StockRepository, Warehouse
from app.modules.inventory.application.valuation import applied_method
from app.modules.inventory.domain.costing import Method


@dataclass(frozen=True, slots=True)
class BalanceFilter:
    product_id: UUID | None = None
    search: str | None = None
    low_stock: bool = False


@dataclass(frozen=True, slots=True)
class LotFilter:
    product_id: UUID | None = None
    expiring_within_days: int | None = None
    include_empty: bool = False


@dataclass(frozen=True, slots=True)
class MoveFilter:
    product_id: UUID | None = None
    doc_type: str | None = None
    date_from: date | None = None
    date_to: date | None = None


class StockQueryRepository(Protocol):
    async def balances(
        self,
        s: AsyncSession,
        warehouse_id: UUID,
        flt: BalanceFilter,
        after: tuple[str, UUID] | None,
        limit: int,
    ) -> list[dict[str, Any]]: ...
    async def lots(
        self,
        s: AsyncSession,
        warehouse_id: UUID,
        flt: LotFilter,
        expiry_until: date | None,
        after: tuple[str, UUID] | None,
        limit: int,
    ) -> list[dict[str, Any]]: ...
    async def moves(
        self,
        s: AsyncSession,
        warehouse_id: UUID,
        flt: MoveFilter,
        since: datetime | None,
        until: datetime | None,
        after: tuple[str, UUID] | None,
        limit: int,
    ) -> list[dict[str, Any]]: ...
    async def expiring_lots(self, s: AsyncSession, today: date, until: date) -> list[dict[str, Any]]: ...
    async def low_stock(self, s: AsyncSession) -> list[dict[str, Any]]: ...
    async def current_costs(
        self, s: AsyncSession, warehouse_id: UUID, product_ids: Sequence[UUID]
    ) -> dict[UUID, tuple[Decimal | None, Decimal | None, Decimal | None]]: ...


def _invalid(field: str, key: str) -> AppError:
    return AppError(ErrorCode.VALIDATION_ERROR, details=[ErrorDetail(field=field, message_key=key)])


def _ts(value: datetime | None) -> str | None:
    return None if value is None else value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _encode(sort: str, row_id: UUID) -> str:
    return base64.urlsafe_b64encode(json.dumps([sort, str(row_id)]).encode()).decode().rstrip("=")


def _decode(cursor: str) -> tuple[str, UUID]:
    try:
        sort, rid = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
        return str(sort), UUID(rid)
    except (ValueError, TypeError) as exc:
        raise _invalid("cursor", "validation.cursor_invalid") from exc


def _q(value: Decimal | None) -> str | None:
    return None if value is None else format(qty(value), "f")


def balance_json(r: Mapping[str, Any]) -> dict[str, Any]:
    q: Decimal = r["qty"]
    min_stock: Decimal | None = r["min_stock"]
    return {
        "product_id": str(r["product_id"]),
        "product_name": r["product_name"],
        "warehouse_id": str(r["warehouse_id"]),
        "qty": format(qty(q), "f"),
        "value": format(money(r["value"]), "f"),
        "avg_cost": format(price(r["value"] / q), "f") if q > 0 else None,
        "min_stock": _q(min_stock),
        "is_low": min_stock is not None and q <= min_stock,
        "is_negative": q < 0,
        "updated_at": _ts(r["updated_at"]),
    }


def lot_json(r: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": str(r["id"]),
        "product_id": str(r["product_id"]),
        "product_name": r["product_name"],
        "warehouse_id": str(r["warehouse_id"]),
        "received_at": _ts(r["received_at"]),
        "qty_in": format(qty(r["qty_in"]), "f"),
        "qty_left": format(qty(r["qty_left"]), "f"),
        "blocked_qty": format(qty(r["blocked_qty"]), "f"),
        "unit_cost": format(price(r["unit_cost"]), "f"),
        "expiry_date": r["expiry_date"].isoformat() if r["expiry_date"] else None,
        "receipt_line_id": str(r["receipt_line_id"]) if r["receipt_line_id"] else None,
        "source_doc_type": r["source_doc_type"],
        "source_doc_id": str(r["source_doc_id"]),
    }


def move_json(r: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": str(r["id"]),
        "warehouse_id": str(r["warehouse_id"]),
        "product_id": str(r["product_id"]),
        "lot_id": str(r["lot_id"]) if r["lot_id"] else None,
        "qty": format(qty(r["qty"]), "f"),
        "cost_amount": format(money(r["cost_amount"]), "f"),
        "doc_type": r["doc_type"],
        "doc_id": str(r["doc_id"]),
        "line_id": str(r["line_id"]) if r["line_id"] else None,
        "reversal_of_id": str(r["reversal_of_id"]) if r["reversal_of_id"] else None,
        "moved_at": _ts(r["moved_at"]),
    }


async def scope_branch(repo: StockRepository, s: AsyncSession, scope: BranchScope) -> UUID | None:
    """``X-Branch-Id``; else the default branch (unrestricted) or the user's only branch."""
    if scope.current is not None:
        return scope.current
    if scope.unrestricted:
        return await repo.default_branch_id(s)
    if len(scope.allowed) == 1:
        return scope.allowed[0]
    return None


class StockQueryService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        repo: StockRepository,
        reads: StockQueryRepository,
    ) -> None:
        self._sf = session_factory
        self._repo = repo
        self._reads = reads

    async def _warehouse(
        self, s: AsyncSession, scope: BranchScope, warehouse_id: UUID | None
    ) -> Warehouse | None:
        if warehouse_id is not None:
            wh = await self._repo.warehouse(s, warehouse_id)
            if wh is None:
                raise AppError(ErrorCode.NOT_FOUND, params={"resource": "warehouse"})
            if not scope.unrestricted and wh.branch_id not in scope.allowed:
                raise AppError(ErrorCode.BRANCH_SCOPE_DENIED)
            return wh
        branch = await scope_branch(self._repo, s, scope)
        if branch is None:
            raise _invalid("X-Branch-Id", "validation.required")
        return await self._repo.branch_warehouse(s, branch)

    async def balances(
        self, actor: Principal, scope: BranchScope, warehouse_id: UUID | None, flt: BalanceFilter,
        cursor: str | None, limit: int,
    ) -> dict[str, Any]:  # fmt: skip
        after = _decode(cursor) if cursor else None
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            wh = await self._warehouse(s, scope, warehouse_id)
            rows = [] if wh is None else await self._reads.balances(s, wh.id, flt, after, limit + 1)
        page = rows[:limit]
        nxt = _encode(page[-1]["sort"], page[-1]["product_id"]) if len(rows) > limit else None
        return {"items": [balance_json(r) for r in page], "next_cursor": nxt}

    async def lots(
        self, actor: Principal, scope: BranchScope, warehouse_id: UUID | None, flt: LotFilter,
        cursor: str | None, limit: int,
    ) -> dict[str, Any]:  # fmt: skip
        after = _decode(cursor) if cursor else None
        until = (
            business_today() + timedelta(days=flt.expiring_within_days)
            if flt.expiring_within_days is not None
            else None
        )
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            wh = await self._warehouse(s, scope, warehouse_id)
            rows = [] if wh is None else await self._reads.lots(s, wh.id, flt, until, after, limit + 1)
        page = rows[:limit]
        nxt = _encode(page[-1]["sort"], page[-1]["id"]) if len(rows) > limit else None
        return {"items": [lot_json(r) for r in page], "next_cursor": nxt}

    async def moves(
        self, actor: Principal, scope: BranchScope, warehouse_id: UUID | None, flt: MoveFilter,
        cursor: str | None, limit: int,
    ) -> dict[str, Any]:  # fmt: skip
        if flt.date_from and flt.date_to and flt.date_from > flt.date_to:
            raise _invalid("from", "validation.date_range")
        after = _decode(cursor) if cursor else None
        since = day_start(flt.date_from) if flt.date_from else None
        until = day_end(flt.date_to) if flt.date_to else None
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            wh = await self._warehouse(s, scope, warehouse_id)
            rows = (
                [] if wh is None else await self._reads.moves(s, wh.id, flt, since, until, after, limit + 1)
            )
        page = rows[:limit]
        nxt = _encode(page[-1]["sort"], page[-1]["id"]) if len(rows) > limit else None
        return {"items": [move_json(r) for r in page], "next_cursor": nxt}


class StockNotifier:
    """Daily cron body per tenant: ``expiry_soon`` and ``low_stock`` telegram events (record only)."""

    def __init__(self, repo: StockRepository, reads: StockQueryRepository, events: EventRecorderPort) -> None:
        self._repo = repo
        self._reads = reads
        self._events = events

    async def run(self, s: AsyncSession, tenant_id: UUID, today: date | None = None) -> dict[str, int]:
        day = today or business_today()
        tenant = await self._repo.tenant_stock(s)
        expiring = 0
        for lot in await self._reads.expiring_lots(s, day, day + timedelta(days=tenant.expiry_warning_days)):
            payload = {
                "product_id": str(lot["product_id"]), "product_name": lot["product_name"],
                "lot_id": str(lot["id"]), "warehouse_id": str(lot["warehouse_id"]),
                "branch_id": str(lot["branch_id"]), "qty_left": format(qty(lot["qty_left"]), "f"),
                "expiry_date": lot["expiry_date"].isoformat(), "days_left": (lot["expiry_date"] - day).days,
            }  # fmt: skip
            if await self._events.record_event(
                s, tenant_id, "expiry_soon", payload, f"expiry_soon:{lot['id']}:{day.isoformat()}"
            ):
                expiring += 1
        low = 0
        if tenant.low_stock_check_enabled:
            for row in await self._reads.low_stock(s):
                payload = {
                    "product_id": str(row["product_id"]), "product_name": row["product_name"],
                    "warehouse_id": str(row["warehouse_id"]), "branch_id": str(row["branch_id"]),
                    "qty": format(qty(row["qty"]), "f"), "min_stock": format(qty(row["min_stock"]), "f"),
                }  # fmt: skip
                key = f"low_stock:{row['warehouse_id']}:{row['product_id']}:{day.isoformat()}"
                if await self._events.record_event(s, tenant_id, "low_stock", payload, key):
                    low += 1
        return {"expiry_soon": expiring, "low_stock": low}


class ProductCostReader:
    """``current_cost`` per product for the catalog list (19 §1, BO-05) — one batched query.

    Unit cost in the request branch's warehouse: AVECO → ``avg_costs.avg_cost``; FIFO →
    ``Σ qty_left × unit_cost / Σ qty_left`` of the open lots; fallback ``last_purchase_cost``
    (13 §2.11). ``None`` when nothing is known.
    """

    def __init__(self, repo: StockRepository, reads: StockQueryRepository) -> None:
        self._repo = repo
        self._reads = reads

    async def __call__(
        self, s: AsyncSession, product_ids: Sequence[UUID], scope: BranchScope
    ) -> dict[UUID, Decimal]:
        if not product_ids:
            return {}
        branch = await scope_branch(self._repo, s, scope)
        wh = await self._repo.branch_warehouse(s, branch) if branch is not None else None
        if wh is None:
            return {}
        method: Method = applied_method(
            (await self._repo.tenant_stock(s)).valuation_state, await self._repo.method_history(s)
        )
        out: dict[UUID, Decimal] = {}
        for pid, (avg, fifo, last) in (await self._reads.current_costs(s, wh.id, product_ids)).items():
            candidates = (avg, fifo, last) if method == "aveco" else (fifo, last)
            for value in candidates:
                if value is not None and value > 0:
                    out[pid] = price(value)
                    break
        return out
