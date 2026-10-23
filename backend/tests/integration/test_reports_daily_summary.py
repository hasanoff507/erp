"""The daily-summary building block (``reports.wiring.daily_summary()``, contract daily-summary.md) behind the
Telegram evening report (21 §11, US-M18-02, QT-M18-02) and ``GET /reports/dashboard`` (20 #17)."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

import pytest

from app.core.db.base import uuid7
from app.core.db.session import tenant_transaction
from app.modules.reports.wiring import DailySummary, daily_summary
from tests.support.reports import (
    doc_day,
    ok,
    post_debt_payment,
    post_expense,
    second_pos,
    sell_lines,
    sell_one,
)
from tests.support.sales import (
    D,
    Env,
    Pos,
    add_customer,
    execute,
    make_pos,
    new_item,
    sale_line,
    sales_env_fixture,
)

pytestmark = [pytest.mark.db, pytest.mark.redis]
__all__ = ["sales_env_fixture"]


async def _summary(env: Env, pos: Pos, day: date, branches: tuple[UUID, ...] | None = None) -> DailySummary:
    async with env.db.session_factory() as s, tenant_transaction(s, pos.tenant_id):
        return await daily_summary().for_day(s, pos.tenant_id, day, branches)


async def _opening(env: Env, pos: Pos, customer: UUID, amount: str, due: date) -> None:
    """A posted receivable opening (13 §2.13): document + ``debt_moves`` + ``debt_balances``."""
    opening = uuid7()
    await execute(
        env.db, pos.tenant_id,
        "INSERT INTO app.debt_openings (id, tenant_id, branch_id, number, doc_date, status, counterparty_id, amount, "
        "direction, due_date, created_by, posted_at) VALUES (:id, :t, :b, :n, :d, 'posted', :c, CAST(:a AS numeric), "
        "'receivable', :due, :u, now())",
        id=opening, t=pos.tenant_id, b=pos.branch_id, n=f"QB-{opening.hex[-6:]}", d=due - timedelta(days=20),
        c=customer, a=amount, due=due, u=pos.shop.user_ids["owner"],
    )  # fmt: skip
    await execute(
        env.db, pos.tenant_id,
        "INSERT INTO app.debt_moves (tenant_id, counterparty_id, direction, amount, due_date, doc_type, doc_id) "
        "VALUES (:t, :c, 'receivable', CAST(:a AS numeric), :due, 'debt_openings', :id)",
        t=pos.tenant_id, c=customer, a=amount, due=due, id=opening,
    )  # fmt: skip
    await execute(
        env.db, pos.tenant_id,
        "INSERT INTO app.debt_balances (tenant_id, counterparty_id, direction, balance) "
        "VALUES (:t, :c, 'receivable', CAST(:a AS numeric)) ON CONFLICT (tenant_id, counterparty_id, direction) "
        "DO UPDATE SET balance = app.debt_balances.balance + EXCLUDED.balance",
        t=pos.tenant_id, c=customer, a=amount,
    )  # fmt: skip


async def test_qt_m18_02_daily_summary_figures(env: Env) -> None:
    pos = await make_pos(env)
    day = doc_day()
    tomorrow = day + timedelta(days=1)
    product = await new_item(env, pos, stock="10.000", cost="8000.00")
    customer = await add_customer(env, pos)
    await execute(env.db, pos.tenant_id, "UPDATE app.counterparties SET name = 'Aziz aka', phone = '+998901112233' "
                  "WHERE id = :c", c=customer)  # fmt: skip
    await sell_one(env, pos, product)  # cash
    credit = await sell_lines(
        env, pos, [sale_line(product)], [{"method": "debt", "amount": "12000.00", "due_date": tomorrow.isoformat()}],
        counterparty_id=str(customer),
    )  # fmt: skip
    await post_debt_payment(env, pos, customer, credit, "5000.00")
    await post_expense(env, pos, "1000.00")
    late = await add_customer(env, pos)
    await _opening(env, pos, late, "30000.00", day - timedelta(days=3))

    summary = await _summary(env, pos, day)
    assert summary.day == day and summary.tenant_id == pos.tenant_id and len(summary.branches) == 1
    branch = summary.branches[0]
    assert branch.branch_id == pos.branch_id
    assert (branch.sales_total, branch.receipts_count, branch.avg_receipt) == (
        D("24000.00"),
        2,
        D("12000.00"),
    )
    # 2 × 10714.29 − COGS 16000 − rent 1000
    assert (branch.revenue, branch.cogs, branch.expenses) == (D("21428.58"), D("16000.00"), D("1000.00"))
    assert branch.net_profit == D("4428.58")
    assert (branch.new_debts, branch.debt_payments) == (D("12000.00"), D("5000.00"))
    assert branch.overdue_debt_total == D("30000.00")  # the opening was due 3 days ago
    assert branch.cash_on_hand == D("11000.00")  # 12000 cash sale − 1000 cash expense
    assert summary.total.net_profit == branch.net_profit and summary.total.branch_id == pos.tenant_id
    registers = {r.cash_register_id: r for r in summary.cash_registers}  # + the seeded "Kassa 1" (no shift)
    assert (registers[pos.register_id].name, registers[pos.register_id].cash_on_hand) == ("K1", D("11000.00"))
    assert sum((r.cash_on_hand for r in summary.cash_registers), D("0")) == D("11000.00")
    [due] = summary.debtors_due_tomorrow
    assert (due.counterparty_id, due.name, due.phone) == (customer, "Aziz aka", "+998901112233")
    assert (due.amount_due, due.due_date) == (D("7000.00"), tomorrow)  # 12000 − 5000 paid
    assert summary.unsynced_devices is False and summary.unsynced_device_count == 0


async def test_daily_summary_branches_total_and_dashboard_agree(env: Env) -> None:
    pos = await make_pos(env)
    pos_b = await second_pos(env, pos)
    product = await new_item(env, pos, stock="10.000", cost="8000.00")
    from tests.support.reports import stock_in

    await stock_in(env, pos_b, product, "3.000")
    await sell_one(env, pos, product, qty="2.000")
    await sell_one(env, pos_b, product)
    summary = await _summary(env, pos, doc_day())
    names = [b.branch_name for b in summary.branches]
    assert "Chilonzor" in names and names == sorted(names)
    total = summary.total
    assert total.sales_total == sum((b.sales_total for b in summary.branches), Decimal("0"))
    assert (total.receipts_count, total.avg_receipt) == (2, D("18000.00"))
    dash = await ok(env, pos.shop, "/reports/dashboard")
    assert (
        dash["total_sales"] == f"{total.sales_total:.2f}" and dash["net_profit"] == f"{total.net_profit:.2f}"
    )
    only_b = await _summary(env, pos, doc_day(), (pos_b.branch_id,))
    assert [b.branch_id for b in only_b.branches] == [pos_b.branch_id]
    assert only_b.total.sales_total == D("12000.00")
    assert [r.cash_register_id for r in only_b.cash_registers] == [pos_b.register_id]
    assert only_b.total.cash_on_hand == D("12000.00")
    yesterday = await _summary(env, pos, doc_day() - timedelta(days=1))
    assert yesterday.total.sales_total == D("0.00") and yesterday.total.receipts_count == 0


async def test_dashboard_receivables_and_overdue(env: Env) -> None:
    pos = await make_pos(env)
    on_time = await add_customer(env, pos)
    late = await add_customer(env, pos)
    await _opening(env, pos, on_time, "20000.00", doc_day() + timedelta(days=5))
    await _opening(env, pos, late, "30000.00", doc_day() - timedelta(days=1))
    # ACC-12 / F6: a renewed promise (counterparties.debt_due_date) does NOT hide the overdue amount
    renewed = await add_customer(env, pos)
    await _opening(env, pos, renewed, "7000.00", doc_day() - timedelta(days=10))
    await execute(env.db, pos.tenant_id, "UPDATE app.counterparties SET debt_due_date = :d WHERE id = :c",
                  d=doc_day() + timedelta(days=2), c=renewed)  # fmt: skip
    dash = await ok(env, pos.shop, "/reports/dashboard")
    assert dash["receivables"] == {
        "total": "57000.00", "debtors_count": 3, "overdue_count": 2, "overdue_amount": "37000.00"
    }  # fmt: skip
    alert = next(a for a in dash["alerts"] if a["type"] == "overdue_debts")
    assert (alert["count"], alert["amount"], alert["route"]) == (2, "37000.00", "/app/debts")


async def test_acc12_promise_does_not_hide_overdue_on_dashboard(env: Env) -> None:
    """ACC-12 / F6: overdue ⇔ ``COALESCE(due_date, doc_date) < as_of`` everywhere (20 #21). The customer's
    promise (``counterparties.debt_due_date``) renegotiates collection, not age — it neither hides the
    overdue amount (dashboard, alert, Telegram summary) nor moves the document to "due tomorrow"."""
    pos = await make_pos(env)
    promised = await add_customer(env, pos)
    await _opening(env, pos, promised, "7000.00", doc_day() - timedelta(days=10))
    await execute(env.db, pos.tenant_id, "UPDATE app.counterparties SET debt_due_date = :d WHERE id = :c",
                  d=doc_day() + timedelta(days=1), c=promised)  # fmt: skip
    dash = await ok(env, pos.shop, "/reports/dashboard")
    assert (dash["receivables"]["overdue_count"], dash["receivables"]["overdue_amount"]) == (1, "7000.00")
    alert = next(a for a in dash["alerts"] if a["type"] == "overdue_debts")
    assert (alert["count"], alert["amount"]) == (1, "7000.00")
    summary = await _summary(env, pos, doc_day())
    [branch] = [b for b in summary.branches if b.branch_id == pos.branch_id]
    assert branch.overdue_debt_total == D("7000.00")
    assert summary.debtors_due_tomorrow == ()
