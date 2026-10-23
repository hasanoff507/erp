"""M12 report endpoints (20 #12, #17–#20; US-M03-03, US-M04-03, US-M12-01/02, US-M14-01, US-M15-03).

Read-only: every call is one tenant transaction marked ``READ ONLY``. Branch scope (15 §2.4, SEC-11):
``branch_id`` given → that branch (must be in the caller's scope, else ``403 BRANCH_SCOPE_DENIED``); absent →
the caller's branches — every branch for an unrestricted user (consolidation «Barchasi», 13 §5.4), only the
assigned ones for a restricted user. Money/qty are decimal strings. Day boundaries are Asia/Tashkent.

``data_complete`` / ``unsynced_devices`` (QT-M12-04): POS devices of the scope with unsent outbox events
(``devices.outbox_pending_count > 0``) — their sales are not in the figures yet, the UI shows the "faqat
sinxronlangan ma'lumot" warning.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.auth.principal import Principal
from app.core.db.session import tenant_transaction
from app.core.error_codes import ErrorCode
from app.core.errors import AppError, ErrorDetail
from app.core.money import money_str, price_str, qty_str
from app.core.permissions import BranchScope
from app.modules.reports.application.ports import Branches, ReportsRepository, SalesAgg, SalesGroup, StockRow
from app.modules.reports.application.summary import SummaryService
from app.modules.reports.domain.alerts import build_alerts
from app.modules.reports.domain.daily_summary import ZERO, average, m2
from app.modules.reports.domain.periods import (
    DashboardPeriod,
    RangeError,
    business_today,
    checked_range,
    dashboard_range,
    month_range,
)

Grants = Mapping[str, Decimal | None]  # granted permission code → most generous limit (None = unlimited)
DiscountGroup = Literal["day", "branch", "cashier", "product"]
FISCAL_UNACKED_HOURS = 24
TOP_ON_DASHBOARD = 5


def _invalid(exc: RangeError) -> AppError:
    return AppError(
        ErrorCode.VALIDATION_ERROR, details=[ErrorDetail(field=exc.field, message_key=exc.message_key)]
    )


def _m(value: Decimal) -> str:
    return money_str(value)


def _pct(part: Decimal, whole: Decimal) -> str | None:
    return None if whole == 0 else money_str(part * 100 / whole)


@dataclass(frozen=True, slots=True)
class Scope:
    branch_ids: Branches
    unrestricted: bool
    branch_id: UUID | None


def resolve_scope(scope: BranchScope, branch_id: UUID | None) -> Scope:
    if branch_id is not None:
        if not scope.unrestricted and branch_id not in scope.allowed:
            raise AppError(ErrorCode.BRANCH_SCOPE_DENIED)
        return Scope((branch_id,), scope.unrestricted, branch_id)
    return Scope(None if scope.unrestricted else tuple(scope.allowed), scope.unrestricted, None)


def _sales_row(agg: SalesAgg | None, key: str, label: str | None) -> dict[str, Any]:
    gross = agg.gross_sales if agg else ZERO
    returned = agg.returns_total if agg else ZERO
    count = agg.receipts_count if agg else 0
    return {
        "group_key": key,
        "group_label": label,
        "total_sales": _m(gross - returned),
        "gross_sales": _m(gross),
        "returns_total": _m(returned),
        "receipt_count": count,
        "avg_receipt": _m(average(gross, count)),
    }


class ReportsService:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession], repo: ReportsRepository) -> None:
        self._sf = session_factory
        self._repo = repo
        self.summary = SummaryService(repo)

    async def _read(self, s: AsyncSession) -> None:
        await s.execute(text("SET TRANSACTION READ ONLY"))

    async def _sync_flags(self, s: AsyncSession, branch_ids: Branches) -> dict[str, Any]:
        unsynced = await self._repo.unsynced_devices(s, branch_ids)
        return {"unsynced_devices": unsynced.count, "data_complete": unsynced.count == 0}

    # --- 20 #17 ---------------------------------------------------------------------------------------------
    async def dashboard(
        self,
        actor: Principal,
        scope: BranchScope,
        *,
        period: DashboardPeriod,
        branch_id: UUID | None,
        grants: Grants,
        today: date | None = None,
    ) -> dict[str, Any]:
        sc = resolve_scope(scope, branch_id)
        day = today or business_today()
        rng = dashboard_range(period, day)
        granted = frozenset(grants)
        finance = "reports.finance.view" in granted
        debts_visible = finance or "debts.payment.accept" in granted
        stock_visible = "stock.view" in granted
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            await self._read(s)
            summary = await self.summary.for_range(s, actor.tenant_id, rng, sc.branch_ids)
            previous = await self._repo.sales(s, rng.previous(), sc.branch_ids, "branch")
            top = await self._repo.product_sales(s, rng, sc.branch_ids, "top", TOP_ON_DASHBOARD)
            open_docs, _ = await self.summary.open_debts(s, sc.branch_ids, day)
            stock_value, positions = await self._repo.stock_value(s, sc.branch_ids)
            settings = await self._repo.tenant_settings(s)
            warn_days = settings.get("expiry_warning_days", 7)
            expiring = await self._repo.expiring_lots(
                s, sc.branch_ids, day + timedelta(days=int(warn_days) if isinstance(warn_days, int) else 7)
            )
            variance_count, variance_amount = await self._repo.cash_variance(s, rng, sc.branch_ids)
            approvals = await self._repo.pending_approvals(s, sc.branch_ids)
            fiscal = await self._repo.fiscal_unacked(
                s, sc.branch_ids, datetime.now(UTC) - timedelta(hours=FISCAL_UNACKED_HOURS)
            )
            tenant_counts = await self._repo.tenant_counts(s) if sc.unrestricted else {}
        overdue_count, overdue_amount = self.summary.overdue(open_docs, day)
        debtors = {d.counterparty_id for d in open_docs}
        receivable = sum((d.open_amount for d in open_docs), ZERO)
        visible_approvals = sum(
            1
            for a in approvals
            if a.permission_code in grants
            and (
                a.kind == "card_manual_entry"
                or a.requested_value is None
                or (limit := grants[a.permission_code]) is None
                or a.requested_value <= limit
            )
        )
        total = summary.total
        counts: dict[str, tuple[int, Decimal | None]] = {
            "fiscal_unacked": (fiscal, None),
            "unsynced_devices": (summary.unsynced_device_count, None),
            "cash_variance": (variance_count, m2(variance_amount)),
            "overdue_debts": (overdue_count, overdue_amount),
            "low_stock": (total.low_stock_count, None),
            "expiring_lots": (expiring, None),
            "pending_approvals": (visible_approvals, None),
            **{k: (v, None) for k, v in tenant_counts.items()},
        }
        alerts = build_alerts(counts, granted, sc.unrestricted)
        previous_total = sum((a.gross_sales - a.returns_total for a in previous), ZERO)
        return {
            "period": period,
            "date_from": rng.date_from.isoformat(),
            "date_to": rng.date_to.isoformat(),
            "branch_id": None if sc.branch_id is None else str(sc.branch_id),
            "total_sales": _m(total.sales_total),
            "gross_sales": _m(total.gross_sales),
            "returns_total": _m(total.returns_total),
            "receipt_count": total.receipts_count,
            "avg_receipt": _m(total.avg_receipt),
            "previous_total_sales": _m(previous_total),
            "net_profit": _m(total.net_profit) if finance else None,
            "cash_on_hand": _m(total.cash_on_hand),
            "by_branch": [
                {
                    "branch_id": str(b.branch_id),
                    "name": b.branch_name,
                    "sales": _m(b.sales_total),
                    "receipt_count": b.receipts_count,
                    "avg_receipt": _m(b.avg_receipt),
                    "profit": _m(b.net_profit) if finance else None,
                    "cash_on_hand": _m(b.cash_on_hand),
                    "low_stock_count": b.low_stock_count if stock_visible else None,
                }
                for b in summary.branches
            ],
            "top_products": [
                {
                    "product_id": str(p.product_id),
                    "name": p.name,
                    "unit_code": p.unit_code,
                    "qty": qty_str(p.qty_sold),
                }
                for p in top
                if p.qty_sold > 0
            ],
            "receivables": {
                "total": _m(receivable),
                "debtors_count": len(debtors),
                "overdue_count": overdue_count,
                "overdue_amount": _m(overdue_amount),
            }
            if debts_visible
            else None,
            "stock": {
                "value": _m(stock_value),
                "positions": positions,
                "low_stock_count": total.low_stock_count,
                "expiring_lots": expiring,
            }
            if stock_visible
            else None,
            "alerts": [
                {
                    "type": a.type,
                    "message_key": a.message_key,
                    "severity": a.severity,
                    "count": a.count,
                    "amount": None if a.amount is None else _m(a.amount),
                    "route": a.route,
                }
                for a in alerts
            ],
            "unsynced_devices": summary.unsynced_device_count,
            "data_complete": not summary.unsynced_devices,
        }

    # --- 20 #18 ---------------------------------------------------------------------------------------------
    async def sales(
        self,
        actor: Principal,
        scope: BranchScope,
        *,
        date_from: date | None,
        date_to: date | None,
        branch_id: UUID | None,
        group_by: SalesGroup,
    ) -> dict[str, Any]:
        sc = resolve_scope(scope, branch_id)
        try:
            rng = checked_range(date_from, date_to, business_today())
        except RangeError as exc:
            raise _invalid(exc) from None
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            await self._read(s)
            aggs = await self._repo.sales(s, rng, sc.branch_ids, group_by)
            branches = await self._repo.branches(s, sc.branch_ids) if group_by == "branch" else []
            flags = await self._sync_flags(s, sc.branch_ids)
        by_key = {a.group_key: a for a in aggs}
        rows: list[dict[str, Any]]
        if group_by == "day":
            rows = [_sales_row(by_key.get(d.isoformat()), d.isoformat(), None) for d in rng.each_day()]
        elif group_by == "branch":
            names = {str(b.id): b.name for b in branches}
            keys = [str(b.id) for b in branches] + [k for k in by_key if k not in names]
            rows = []
            for k in keys:
                agg = by_key.get(k)
                rows.append(_sales_row(agg, k, names.get(k) or (agg.group_label if agg else None)))
        else:
            rows = [_sales_row(a, a.group_key, a.group_label) for a in aggs]
        total = SalesAgg(
            "total",
            None,
            sum((a.gross_sales for a in aggs), ZERO),
            sum(a.receipts_count for a in aggs),
            sum((a.returns_total for a in aggs), ZERO),
        )
        return {
            "date_from": rng.date_from.isoformat(),
            "date_to": rng.date_to.isoformat(),
            "branch_id": None if sc.branch_id is None else str(sc.branch_id),
            "group_by": group_by,
            "rows": rows,
            "total": _sales_row(total, "total", None),
            **flags,
        }

    # --- 20 #19 ---------------------------------------------------------------------------------------------
    async def top_products(
        self,
        actor: Principal,
        scope: BranchScope,
        *,
        date_from: date | None,
        date_to: date | None,
        branch_id: UUID | None,
        order: Literal["top", "bottom"],
        limit: int,
    ) -> dict[str, Any]:
        sc = resolve_scope(scope, branch_id)
        try:
            rng = checked_range(date_from, date_to, business_today())
        except RangeError as exc:
            raise _invalid(exc) from None
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            await self._read(s)
            items = await self._repo.product_sales(s, rng, sc.branch_ids, order, limit)
            flags = await self._sync_flags(s, sc.branch_ids)
        return {
            "date_from": rng.date_from.isoformat(),
            "date_to": rng.date_to.isoformat(),
            "branch_id": None if sc.branch_id is None else str(sc.branch_id),
            "order": order,
            "items": [
                {
                    "product_id": str(p.product_id),
                    "name": p.name,
                    "unit_code": p.unit_code,
                    "qty_sold": qty_str(p.qty_sold),
                    "revenue": _m(p.revenue),
                }
                for p in items
            ],
            **flags,
        }

    # --- 20 #20 ---------------------------------------------------------------------------------------------
    async def stock(
        self,
        actor: Principal,
        scope: BranchScope,
        *,
        branch_id: UUID | None,
        warehouse_id: UUID | None,
        below_min_only: bool,
        search: str | None,
        category_id: UUID | None,
    ) -> dict[str, Any]:
        sc = resolve_scope(scope, branch_id)
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            await self._read(s)
            if warehouse_id is not None:
                wh_branch = await self._repo.warehouse_branch(s, warehouse_id)
                if wh_branch is not None and sc.branch_ids is not None and wh_branch not in sc.branch_ids:
                    raise AppError(ErrorCode.BRANCH_SCOPE_DENIED)
            rows = await self._repo.stock(
                s, sc.branch_ids, warehouse_id=warehouse_id, search=search, category_id=category_id
            )
            branches = await self._repo.branches(s, sc.branch_ids)
        names = {b.id: b.name for b in branches}
        grouped: dict[UUID, list[StockRow]] = defaultdict(list)
        for r in rows:
            grouped[r.product_id].append(r)
        items: list[dict[str, Any]] = []
        branch_totals: dict[UUID, list[Decimal]] = defaultdict(
            lambda: [ZERO, ZERO, ZERO]
        )  # value, items, low
        for product_rows in grouped.values():
            first = product_rows[0]
            qty_total = sum((r.qty for r in product_rows), Decimal("0"))
            value_total = sum((r.value for r in product_rows), ZERO)
            below = any(r.below_min for r in product_rows)
            for r in product_rows:
                acc = branch_totals[r.branch_id]
                acc[0] += r.value
                acc[1] += 1
                acc[2] += 1 if r.below_min else 0
            if below_min_only and not below:
                continue
            items.append(
                {
                    "product_id": str(first.product_id),
                    "name": first.name,
                    "name_ru": first.name_ru,
                    "unit_code": first.unit_code,
                    "category_id": None if first.category_id is None else str(first.category_id),
                    "category_name": first.category_name,
                    "barcode": first.barcode,
                    "is_marked": first.is_marked,
                    "is_weighed": first.is_weighed,
                    "min_stock": None if first.min_stock is None else qty_str(first.min_stock),
                    "qty": qty_str(qty_total),
                    "value": _m(value_total),
                    "avg_cost": None if qty_total <= 0 else price_str(value_total / qty_total),
                    "below_min": below,
                    "by_branch": [
                        {
                            "branch_id": str(r.branch_id),
                            "branch_name": names.get(r.branch_id),
                            "qty": qty_str(r.qty),
                            "value": _m(r.value),
                            "below_min": r.below_min,
                        }
                        for r in sorted(
                            product_rows, key=lambda r: (names.get(r.branch_id, ""), str(r.branch_id))
                        )
                    ],
                }
            )
        return {
            "branch_id": None if sc.branch_id is None else str(sc.branch_id),
            "consolidated": sc.branch_id is None and len(branches) > 1,
            "items": items,
            "branches": [
                {
                    "branch_id": str(b.id),
                    "name": b.name,
                    "value": _m(branch_totals[b.id][0]) if b.id in branch_totals else _m(ZERO),
                    "positions": int(branch_totals[b.id][1]) if b.id in branch_totals else 0,
                    "below_min_count": int(branch_totals[b.id][2]) if b.id in branch_totals else 0,
                }
                for b in branches
            ],
            "total": {
                "value": _m(sum((v[0] for v in branch_totals.values()), ZERO)),
                "positions": len(grouped),
                "below_min_count": sum(1 for rs in grouped.values() if any(r.below_min for r in rs)),
            },
        }

    # --- 20 #12 ---------------------------------------------------------------------------------------------
    async def profit_and_loss(
        self,
        actor: Principal,
        scope: BranchScope,
        *,
        period: str | None,
        date_from: date | None,
        date_to: date | None,
        branch_id: UUID | None,
    ) -> dict[str, Any]:
        sc = resolve_scope(scope, branch_id)
        try:
            if period is not None:
                rng = month_range(period)
            elif date_from is None and date_to is None:
                rng = month_range(business_today().strftime("%Y-%m"))
            else:
                rng = checked_range(date_from, date_to, business_today())
        except RangeError as exc:
            raise _invalid(exc) from None
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            await self._read(s)
            totals = await self._repo.ledger_totals(s, rng, sc.branch_ids)
            expenses = await self._repo.expense_lines(s, rng, sc.branch_ids)
            settings = await self._repo.tenant_settings(s)
            net_mode = settings.get("discount_posting") == "net"
            line_discounts = await self._repo.discounts(s, rng, sc.branch_ids, "branch") if net_mode else []
            branches = await self._repo.branches(s, sc.branch_ids)
            flags = await self._sync_flags(s, sc.branch_ids)

        def block(
            ledger: Sequence[Any], lines: Sequence[Any], info_discount: Decimal | None
        ) -> dict[str, Any]:
            revenue = sum((t.revenue_9020 for t in ledger), ZERO)
            returns = sum((t.returns_9040 for t in ledger), ZERO)
            disc_posted = sum((t.discounts_9050 for t in ledger), ZERO)
            cogs = sum((t.cogs_9120 for t in ledger), ZERO)
            other = sum((t.other_income_9390 for t in ledger), ZERO)
            net_revenue = revenue - returns - disc_posted
            gross_profit = net_revenue - cogs
            cats: dict[tuple[str, str | None, str | None, str], Decimal] = defaultdict(lambda: ZERO)
            for line in lines:
                key = (
                    line.account,
                    None if line.category_id is None else str(line.category_id),
                    line.category_name,
                    "expenses" if line.category_id is not None else line.source,
                )
                cats[key] += line.amount
            expense_total = sum(cats.values(), ZERO)
            return {
                "revenue": _m(revenue),
                "returns": _m(returns),
                "discounts": _m(disc_posted if info_discount is None else info_discount),
                "net_revenue": _m(net_revenue),
                "cogs": _m(cogs),
                "gross_profit": _m(gross_profit),
                "gross_margin_pct": _pct(gross_profit, net_revenue),
                "other_income": _m(other),
                "expenses_by_category": [
                    {
                        "category_id": cid,
                        "category": cname,
                        "account": account,
                        "source": source,
                        "amount": _m(amount),
                    }
                    for (account, cid, cname, source), amount in sorted(
                        cats.items(), key=lambda kv: (-kv[1], kv[0][0], kv[0][2] or "", kv[0][3])
                    )
                    if amount != 0
                ],
                "expenses_total": _m(expense_total),
                "net_profit": _m(gross_profit - expense_total + other),
            }

        def info(branch: UUID | None) -> Decimal | None:
            if not net_mode:
                return None
            wanted = None if branch is None else str(branch)
            return sum(
                (d.discount_net for d in line_discounts if wanted is None or d.group_key == wanted), ZERO
            )

        body: dict[str, Any] = {
            "period": f"{rng.date_from.year:04d}-{rng.date_from.month:02d}" if period is not None else None,
            "date_from": rng.date_from.isoformat(),
            "date_to": rng.date_to.isoformat(),
            "branch_id": None if sc.branch_id is None else str(sc.branch_id),
            "discount_posting": "net" if net_mode else "gross_9050",
            **block(totals, expenses, info(None)),
            "by_branch": [
                {
                    "branch_id": str(b.id),
                    "name": b.name,
                    **block(
                        [t for t in totals if t.branch_id == b.id],
                        [e for e in expenses if e.branch_id == b.id],
                        info(b.id),
                    ),
                }
                for b in branches
            ]
            if sc.branch_id is None and len(branches) > 1
            else [],
            **flags,
        }
        return body

    # --- US-M03-03
    # -------------------------------------------------------------------------------------------
    async def discounts(
        self,
        actor: Principal,
        scope: BranchScope,
        *,
        date_from: date | None,
        date_to: date | None,
        branch_id: UUID | None,
        group_by: DiscountGroup,
    ) -> dict[str, Any]:
        sc = resolve_scope(scope, branch_id)
        try:
            rng = checked_range(date_from, date_to, business_today())
        except RangeError as exc:
            raise _invalid(exc) from None
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            await self._read(s)
            aggs = await self._repo.discounts(s, rng, sc.branch_ids, group_by)
            flags = await self._sync_flags(s, sc.branch_ids)

        def row(key: str, label: str | None, items: Sequence[Any]) -> dict[str, Any]:
            sales = sum((a.sales_total for a in items), ZERO)
            disc = sum((a.discount_total for a in items), ZERO)
            disc_net = sum((a.discount_net for a in items), ZERO)
            revenue = sum((a.revenue_net for a in items), ZERO)
            cost = sum((a.cost for a in items), ZERO)
            margin = revenue - cost
            full = margin + disc_net
            return {
                "group_key": key,
                "group_label": label,
                "sales_total": _m(sales),
                "discount_total": _m(disc),
                "discount_net": _m(disc_net),
                "revenue_net": _m(revenue),
                "cost": _m(cost),
                "margin": _m(margin),
                "margin_without_discounts": _m(full),
                "margin_pct": _pct(margin, revenue),
                "margin_pct_without_discounts": _pct(full, revenue + disc_net),
            }

        return {
            "date_from": rng.date_from.isoformat(),
            "date_to": rng.date_to.isoformat(),
            "branch_id": None if sc.branch_id is None else str(sc.branch_id),
            "group_by": group_by,
            "rows": [row(a.group_key, a.group_label, [a]) for a in aggs],
            "total": row("total", None, aggs),
            **flags,
        }
