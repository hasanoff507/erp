"""BO-02 «Diqqat talab qiladi» / topbar bell — ``GET /reports/dashboard`` → ``alerts[]`` (07 BO-02, 06 §1.9):
each alert carries a severity, a ``message_key``, a count and the target route, filtered by the caller's
permissions and branch scope (US-M04-02 low stock is one of them)."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest

from app.modules.access.domain.permissions import SystemRole
from tests.support.inventory import add_user, receive
from tests.support.reports import doc_day, ok, second_pos, sell_one
from tests.support.sales import Env, execute, make_pos, new_item, sales_env_fixture

pytestmark = [pytest.mark.db, pytest.mark.redis]
__all__ = ["sales_env_fixture"]


def _alerts(body: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {a["type"]: a for a in body["alerts"]}


async def test_dashboard_alerts_with_routes_and_permissions(env: Env) -> None:
    pos = await make_pos(env)
    pos_b = await second_pos(env, pos)
    low = await new_item(env, pos, "Sut", stock="3.000", cost="7000.00", min_stock="5.000")
    expiring = await new_item(env, pos, "Qatiq", stock=None)
    await receive(
        env, pos.shop, pos.warehouse_id, expiring, "4.000", "20000.00", expiry=doc_day() + timedelta(days=2)
    )
    await sell_one(env, pos, low, price="9000.0000")
    # a closed shift with a shortage (US-M16-02)
    await execute(
        env.db, pos.tenant_id,
        "UPDATE app.shifts SET status = 'closed', expected_cash = 9000, counted_cash = 8000, "
        "variance_note = 'kamomad', closed_at = now(), closed_by = opened_by WHERE id = :s",
        s=pos.shift_id,
    )  # fmt: skip
    # a pending over-limit discount approval in branch A (15 §2.3)
    await execute(
        env.db, pos.tenant_id,
        "INSERT INTO app.approval_requests (tenant_id, branch_id, kind, permission_code, requested_value, "
        "requested_by, expires_at) VALUES (:t, :b, 'discount_over_limit', 'discount.approve', 20, :u, "
        "now() + interval '15 minutes')",
        t=pos.tenant_id, b=pos.branch_id, u=pos.shop.user_ids["cashier"],
    )  # fmt: skip
    await execute(
        env.db, pos.tenant_id,
        "INSERT INTO app.sync_exceptions (tenant_id, device_id, kind) VALUES (:t, :d, 'price_mismatch')",
        t=pos.tenant_id, d=pos.device_id,
    )  # fmt: skip
    # the sale's fiscal receipt is still not acknowledged by the OFD after 30 h (offline kassa, qaror #43)
    await execute(
        env.db, pos.tenant_id,
        "UPDATE app.fiscal_receipts SET ofd_acked_at = NULL, fiscal_at = NULL, "
        "created_at = now() - interval '30 hours' WHERE cash_register_id = :r",
        r=pos.register_id,
    )  # fmt: skip

    owner = _alerts(await ok(env, pos.shop, "/reports/dashboard"))
    assert owner["low_stock"] == {
        "type": "low_stock", "message_key": "reports.alerts.low_stock", "severity": "warning", "count": 1,
        "amount": None, "route": "/app/warehouse/stock?lowStockOnly=1",
    }  # fmt: skip
    assert owner["expiring_lots"]["count"] == 1
    assert (owner["cash_variance"]["count"], owner["cash_variance"]["amount"]) == (1, "1000.00")
    assert (
        owner["pending_approvals"]["count"] == 1 and owner["pending_approvals"]["route"] == "/app/approvals"
    )
    assert owner["sync_exceptions"]["count"] == 1
    assert owner["fiscal_unacked"]["severity"] == "critical" and owner["fiscal_unacked"]["count"] == 1
    ordered = (await ok(env, pos.shop, "/reports/dashboard"))["alerts"]
    assert ordered[0]["type"] == "fiscal_unacked"  # most urgent first

    # accountant: no discount.approve, no settings.tenant but accounting.post (sync exceptions)
    accountant = _alerts(await ok(env, pos.shop, "/reports/dashboard", role="accountant"))
    assert "pending_approvals" not in accountant and "sync_exceptions" in accountant

    # a manager restricted to branch B: nothing of branch A, no tenant-wide alerts (SEC-11)
    await add_user(env, pos.shop, "manager_b", SystemRole.MANAGER, (pos_b.branch_id,))
    scoped = _alerts(await ok(env, pos.shop, "/reports/dashboard", role="manager_b"))
    assert not {"low_stock", "cash_variance", "pending_approvals", "sync_exceptions", "fiscal_unacked"} & set(
        scoped
    )

    only_b = _alerts(await ok(env, pos.shop, "/reports/dashboard", branch_id=pos_b.branch_id))
    assert "low_stock" not in only_b and "sync_exceptions" in only_b  # tenant-wide alerts for the owner


async def test_low_stock_dashboard_alert_follows_min_stock(env: Env) -> None:
    pos = await make_pos(env)
    product = await new_item(env, pos, "Non", stock="6.000", cost="3000.00", min_stock="5.000")
    before = _alerts(await ok(env, pos.shop, "/reports/dashboard"))
    assert "low_stock" not in before
    await sell_one(env, pos, product, price="4000.0000")  # 6 → 5: reaches the minimum (US-M04-02)
    after = await ok(env, pos.shop, "/reports/dashboard")
    assert _alerts(after)["low_stock"]["count"] == 1 and after["stock"]["low_stock_count"] == 1
    assert after["by_branch"][0]["low_stock_count"] == 1
