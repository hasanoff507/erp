"""Debt register primitive (11 §7, 13 §5.2, 23 §2.1) — ``debt_moves``/``debt_balances`` under RLS, no HTTP."""

from __future__ import annotations

import asyncio
from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy import text

from app.core.db.base import uuid7
from app.core.db.session import Database, tenant_transaction
from app.modules.debts.wiring import DebtMoveInput, debt_register
from scripts.seed import seed_demo_tenant
from tests.support.auth import new_phone

pytestmark = [pytest.mark.db]


async def _tenant_with_counterparties(db: Database, count: int) -> tuple[UUID, list[UUID]]:
    tenant_id = uuid7()
    await seed_demo_tenant(db, tenant_id=tenant_id, name="Qarz reestri", phone=new_phone())
    ids = [uuid7() for _ in range(count)]
    async with db.session_factory() as s, tenant_transaction(s, tenant_id):
        for n, cp in enumerate(ids):
            await s.execute(
                text(
                    "INSERT INTO app.counterparties (id, tenant_id, kind, name, is_supplier) "
                    "VALUES (:id, :t, 'company', :n, true)"
                ),
                {"id": cp, "t": tenant_id, "n": f"Supplier {n}"},
            )
    return tenant_id, ids


async def _rows(db: Database, tenant_id: UUID, sql: str, **params: object) -> list[tuple[object, ...]]:
    async with db.session_factory() as s, tenant_transaction(s, tenant_id):
        return [tuple(r) for r in await s.execute(text(sql), params)]


async def test_post_moves_updates_balances_and_storno_reverts(app_db: Database, seeded: None) -> None:
    tenant_id, (a, b) = await _tenant_with_counterparties(app_db, 2)
    register = debt_register()
    receipt = uuid7()
    async with app_db.session_factory() as s, tenant_transaction(s, tenant_id):
        written = await register.post(
            s,
            tenant_id,
            [
                DebtMoveInput(b, "payable", Decimal("1120000.00"), "goods_receipts", receipt),
                DebtMoveInput(a, "payable", Decimal("500.50"), "goods_receipts", receipt),
                DebtMoveInput(a, "receivable", Decimal("0.00"), "goods_receipts", receipt),  # skipped
                DebtMoveInput(a, "payable", Decimal("-100.50"), "goods_receipts", receipt),
            ],
        )
        assert len(written) == 3 and all(m.reversal_of_id is None for m in written)
        assert await register.balances(s, a) == {"receivable": Decimal("0.00"), "payable": Decimal("400.00")}
        assert await register.balances(s, b) == {
            "receivable": Decimal("0.00"),
            "payable": Decimal("1120000.00"),
        }

    async with app_db.session_factory() as s, tenant_transaction(s, tenant_id):
        reversed_rows = await register.reverse(s, tenant_id, "goods_receipts", receipt)
        assert len(reversed_rows) == 3
        assert {m.reversal_of_id for m in reversed_rows} == {m.id for m in written}
        assert sorted(m.amount for m in reversed_rows) == [
            Decimal("-1120000.00"),
            Decimal("-500.50"),
            Decimal("100.50"),
        ]
        # a second cancel writes nothing (idempotent storno)
        assert await register.reverse(s, tenant_id, "goods_receipts", receipt) == []
        assert await register.balances(s, a) == {"receivable": Decimal("0.00"), "payable": Decimal("0.00")}
        assert await register.balances(s, b) == {"receivable": Decimal("0.00"), "payable": Decimal("0.00")}

    moves = await _rows(app_db, tenant_id, "SELECT count(*), sum(amount) FROM app.debt_moves")
    assert moves == [(6, Decimal("0.00"))]
    # a counterparty without moves reads as zero, no row is needed
    async with app_db.session_factory() as s, tenant_transaction(s, tenant_id):
        assert await register.balances(s, uuid7()) == {
            "receivable": Decimal("0.00"),
            "payable": Decimal("0.00"),
        }


async def test_register_rejects_bad_input(app_db: Database, seeded: None) -> None:
    tenant_id, (a,) = await _tenant_with_counterparties(app_db, 1)
    register = debt_register()
    async with app_db.session_factory() as s, tenant_transaction(s, tenant_id):
        with pytest.raises(ValueError, match="2 decimal"):
            await register.post(s, tenant_id, [DebtMoveInput(a, "payable", Decimal("1.005"), "x", uuid7())])
        with pytest.raises(ValueError, match="direction"):
            await register.post(s, tenant_id, [DebtMoveInput(a, "owed", Decimal("1.00"), "x", uuid7())])  # type: ignore[arg-type]
        assert await register.post(s, tenant_id, []) == []


async def test_debt_moves_are_append_only(app_db: Database, seeded: None) -> None:
    tenant_id, (a,) = await _tenant_with_counterparties(app_db, 1)
    async with app_db.session_factory() as s, tenant_transaction(s, tenant_id):
        await debt_register().post(
            s, tenant_id, [DebtMoveInput(a, "payable", Decimal("10.00"), "x", uuid7())]
        )
    with pytest.raises(Exception, match=r"permission denied|append-only"):
        async with app_db.session_factory() as s, tenant_transaction(s, tenant_id):
            await s.execute(text("UPDATE app.debt_moves SET amount = 0"))


async def test_concurrent_writers_on_one_counterparty_serialise(app_db: Database, seeded: None) -> None:
    """23 §2.1: the ``debt_balances`` row lock serialises posters — no lost update, no deadlock."""
    tenant_id, (a, b) = await _tenant_with_counterparties(app_db, 2)
    register = debt_register()
    writers = 8

    async def writer(n: int) -> None:
        async with app_db.session_factory() as s, tenant_transaction(s, tenant_id):
            # opposite argument order in every other writer: the register sorts the locks itself
            keys = [(a, "payable"), (b, "payable")] if n % 2 else [(b, "payable"), (a, "payable")]
            await register.lock(s, tenant_id, keys)  # type: ignore[arg-type]
            await asyncio.sleep(0.02)  # hold the locks so the others queue up behind them
            await register.post(
                s,
                tenant_id,
                [
                    DebtMoveInput(b, "payable", Decimal("2.00"), "goods_receipts", uuid7()),
                    DebtMoveInput(a, "payable", Decimal("1.25"), "goods_receipts", uuid7()),
                ],
            )

    await asyncio.wait_for(asyncio.gather(*(writer(n) for n in range(writers))), timeout=60)
    async with app_db.session_factory() as s, tenant_transaction(s, tenant_id):
        assert (await register.balances(s, a))["payable"] == Decimal("1.25") * writers
        assert (await register.balances(s, b))["payable"] == Decimal("2.00") * writers
    rows = await _rows(
        app_db,
        tenant_id,
        "SELECT counterparty_id, direction, balance FROM app.debt_balances ORDER BY balance",
    )
    assert rows == [(a, "payable", Decimal("10.00")), (b, "payable", Decimal("16.00"))]
    assert await _rows(app_db, tenant_id, "SELECT count(*) FROM app.debt_moves") == [(writers * 2,)]


async def test_lock_blocks_a_second_writer_until_commit(app_db: Database, seeded: None) -> None:
    tenant_id, (a,) = await _tenant_with_counterparties(app_db, 1)
    register = debt_register()
    events: list[str] = []
    locked = asyncio.Event()

    async def first() -> None:
        async with app_db.session_factory() as s, tenant_transaction(s, tenant_id):
            await register.post(s, tenant_id, [DebtMoveInput(a, "payable", Decimal("5.00"), "x", uuid7())])
            locked.set()
            await asyncio.sleep(0.3)
            events.append("first-commit")

    async def second() -> None:
        await locked.wait()
        async with app_db.session_factory() as s, tenant_transaction(s, tenant_id):
            balances = await register.lock(s, tenant_id, [(a, "payable")])
            events.append(f"second-sees-{balances[(a, 'payable')]}")

    await asyncio.wait_for(asyncio.gather(first(), second()), timeout=30)
    assert events == ["first-commit", "second-sees-5.00"]


async def test_register_is_tenant_isolated(app_db: Database, seeded: None) -> None:
    tenant_a, (a,) = await _tenant_with_counterparties(app_db, 1)
    tenant_b, _ = await _tenant_with_counterparties(app_db, 1)
    register = debt_register()
    doc = uuid7()
    async with app_db.session_factory() as s, tenant_transaction(s, tenant_a):
        await register.post(s, tenant_a, [DebtMoveInput(a, "receivable", Decimal("7.00"), "sales", doc)])
    async with app_db.session_factory() as s, tenant_transaction(s, tenant_b):
        assert await register.balances(s, a) == {"receivable": Decimal("0.00"), "payable": Decimal("0.00")}
        assert await register.reverse(s, tenant_b, "sales", doc) == []
    assert await _rows(app_db, tenant_b, "SELECT count(*) FROM app.debt_moves") == [(0,)]
    async with app_db.session_factory() as s, tenant_transaction(s, tenant_a):
        assert (await register.balances(s, a))["receivable"] == Decimal("7.00")
