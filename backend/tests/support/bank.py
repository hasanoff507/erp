"""Helpers for the BO-24 bank settlement tests (Bosqich 4, b4-bank slice).

Real app + PostgreSQL/Redis (the cash test setup). The 5710 inflows the slice only *reads* (card sales,
card refunds, collections) are written through the real accounting ``LedgerPoster`` exactly the way the
sales / returns / cash-movement postings write them (``analytics.payment_method``, ``rrn`` for an
integrated card payment) — :func:`transit_in` / :func:`transit_out`.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import text

from app.core.db.base import uuid7
from app.core.db.session import tenant_transaction
from app.modules.accounting.wiring import LedgerLine, business_today, ledger_poster
from tests.support.cash import Till, make_till, one, sql
from tests.support.catalog import Env

API = "/api/v1/bank-settlements"
ACCOUNT = "20208000900100000001"
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "bank"
D17 = business_today()  # "today": the bank credit day
D16 = D17 - timedelta(days=1)  # "yesterday": the sales day
D15 = D17 - timedelta(days=2)


def dmy(day: date) -> str:
    return day.strftime("%d.%m.%Y")


async def bank_till(env: Env, name: str = "Bank do'kon", *, account: str | None = ACCOUNT) -> Till:
    till = await make_till(env, name)
    if account is not None:
        await sql(
            env.db, till.shop.tenant_id,
            "UPDATE app.tenants SET settings = settings || jsonb_build_object('bank_account', CAST(:a AS text)) "
            "WHERE id = :t",
            a=account, t=till.shop.tenant_id,
        )  # fmt: skip
    return till


async def transit_in(
    env: Env,
    till: Till,
    method: str,
    amount: str,
    day: date,
    *,
    rrn: str | None = None,
    branch_id: UUID | None = None,
    doc_type: str = "sales",
) -> UUID:
    """A sale paid by ``method`` (``Dt 5710 / Kt 9020``) — or a collection (``Dt 5710 / Kt 5010``)."""
    analytics: dict[str, Any] = {"payment_method": method}
    if rrn is not None:
        analytics["rrn"] = rrn
    kt = "5010" if method == "collection" else "9020"
    if method == "collection":
        doc_type = "cash_movements"
    return await _post(env, till, doc_type, [(day, "5710", kt, amount, analytics)], branch_id)


async def transit_out(env: Env, till: Till, method: str, amount: str, day: date) -> UUID:
    """A refund to the card (``Dt 9040 / Kt 5710``)."""
    return await _post(
        env, till, "returns", [(day, "9040", "5710", amount, {"payment_method": method})], None
    )


async def _post(
    env: Env,
    till: Till,
    doc_type: str,
    rows: list[tuple[date, str, str, str, dict[str, Any]]],
    branch_id: UUID | None,
) -> UUID:
    doc_id = uuid7()
    tenant = till.shop.tenant_id
    async with env.db.session_factory() as s, tenant_transaction(s, tenant):
        await ledger_poster().post(
            s,
            tenant,
            doc_type,
            doc_id,
            [
                LedgerLine(d, branch_id or till.shop.branch_id, dt, kt, Decimal(a), an)
                for d, dt, kt, a, an in rows
            ],
        )
    return doc_id


async def card_purchase(
    env: Env, till: Till, rrn: str, amount: str, day: date, *, tid: str = "T1", doc_id: UUID | None = None
) -> UUID:
    """An approved integrated purchase on terminal ``tid`` (bound to a sale) + its 5710 ledger line."""
    tenant = till.shop.tenant_id
    sale_id = doc_id or await transit_in(env, till, "card", amount, day, rrn=rrn)
    async with env.db.session_factory() as s, tenant_transaction(s, tenant):
        terminal = (
            await s.execute(text("SELECT id FROM app.card_terminals WHERE tid = :tid"), {"tid": tid})
        ).scalar()
        if terminal is None:
            terminal = uuid7()
            await s.execute(
                text(
                    "INSERT INTO app.card_terminals (id, tenant_id, branch_id, cash_register_id, name, vendor, "
                    "adapter, driver, tid, created_by) VALUES (:id, :t, :b, :c, :tid, 'fake', 'fake', 'fake', :tid, :u)"
                ),
                {"id": terminal, "t": tenant, "b": till.shop.branch_id, "c": till.register_id, "tid": tid,
                 "u": till.shop.user_ids["owner"]},
            )  # fmt: skip
        tx_id = uuid7()
        at = datetime.combine(day, time(9, 0), tzinfo=UTC)
        await s.execute(
            text(
                "INSERT INTO app.card_terminal_transactions (id, tenant_id, branch_id, card_terminal_id, "
                "cash_register_id, kind, amount, approved_amount, status, rrn, card_mask, card_type, "
                "card_type_source, resolved_by, requested_at, tx_at, resolved_at, doc_type, doc_id, created_by) "
                "VALUES (:id, :t, :b, :ct, :c, 'purchase', :a, :a, 'approved', :rrn, '8600****1234', 'personal', "
                "'terminal', 'auto', :at, :at, :at, 'sales', :doc, :u)"
            ),
            {"id": tx_id, "t": tenant, "b": till.shop.branch_id, "ct": terminal, "c": till.register_id,
             "a": Decimal(amount), "rrn": rrn, "at": at, "doc": sale_id, "u": till.shop.user_ids["cashier"]},
        )  # fmt: skip
    return tx_id


async def balance(env: Env, till: Till, method: str) -> str:
    value = await one(
        env.db, till.shop.tenant_id,
        "SELECT COALESCE(SUM(CASE WHEN account_dt = '5710' THEN amount ELSE -amount END), 0) FROM app.ledger_entries "
        "WHERE (account_dt = '5710' OR account_kt = '5710') AND analytics->>'payment_method' = :m",
        m=method,
    )  # fmt: skip
    return format(Decimal(value).quantize(Decimal("0.01")), "f")


def body(till: Till, **over: Any) -> dict[str, Any]:
    out: dict[str, Any] = {
        "branch_id": str(till.shop.branch_id), "doc_date": D17.isoformat(), "method": "card",
        "settled_from": D16.isoformat(), "settled_to": D16.isoformat(), "gross_amount": "950000.00",
        "commission_amount": "9500.00",
    }  # fmt: skip
    out.update(over)
    return {k: v for k, v in out.items() if v is not None}


def statement(*docs: dict[str, str], account: str = ACCOUNT, encoding: str = "utf-8") -> bytes:
    """A small 1CClientBankExchange file; each doc: number, amount, purpose (+ payer, payer_inn, to)."""
    lines = [
        "1CClientBankExchange", "ВерсияФормата=1.03", f"Кодировка={'Windows' if encoding == 'cp1251' else 'UTF-8'}",
        f"ДатаНачала={dmy(D17)}", f"ДатаКонца={dmy(D17)}", "СекцияРасчСчет", f"РасчСчет={account}",
        f"ДатаНачала={dmy(D17)}", f"ДатаКонца={dmy(D17)}", "КонецРасчСчет",
    ]  # fmt: skip
    for d in docs:
        lines += [
            "СекцияДокумент=Платежное поручение", f"Номер={d['number']}", f"Дата={d.get('date', dmy(D17))}",
            f"Сумма={d['amount']}", f"ПлательщикСчет={d.get('payer_account', '29801000100200000099')}",
            f"Плательщик={d.get('payer', 'ATB NAMUNA BANK')}", f"ПлательщикИНН={d.get('payer_inn', '200000001')}",
            f"ПолучательСчет={d.get('to', account)}", "Получатель=MChJ NAMUNA", f"ДатаПоступило={d.get('date', dmy(D17))}",
            f"НазначениеПлатежа={d['purpose']}", "КонецДокумента",
        ]  # fmt: skip
    lines.append("КонецФайла")
    return ("\r\n".join(lines) + "\r\n").encode(encoding)


def upload(content: bytes, name: str = "vypiska.txt", branch_id: UUID | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {"files": {"file": (name, content, "text/plain")}}
    if branch_id is not None:
        out["data"] = {"branch_id": str(branch_id)}
    return out
