"""Debt book reads: the paper-book ledger of one counterparty (18 §12.1, US-M08-06, QT-M08-09/14) and the
debts
aging report (20 #21 = 18 §12.8, US-M08-10/11).

* **Ledger** — one row per document over ``debt_moves`` of the counterparty in the requested direction
  (``receivable`` — the customer book; ``payable`` — «Men qarzdorman», goods receipts / supplier payments /
  returns / openings): amount (net, storno included — cancelled documents drop out), running balance, number,
  date, who wrote it, comment, the goods of a sale, the documents a payment closed. Receivable debt rows carry
  ``status`` (open / partially_paid / paid / written_off, from the allocations — 11 §8) and ``promise_date``
  (the latest promise of a payment allocated to it, else the sale's own due date). Payable rows get the status
  first-in-first-out from the balance (the open part of a supplier balance is its newest charges).
* **Branch scope** (SEC-01, 15 §2.4): a branch-restricted user sees only the rows of documents of his
  branches; every figure (balances, running balance, aging balance) is computed over those rows only.
* **Open amounts** of receivable documents are reconciled to the balance (ACC-02, 13 §2.14 — the oldest open
  documents absorb a credit on the account that has no document).
* **Aging** — rows of counterparties with a positive balance: ``overdue_since = min(COALESCE(due_date,
  doc_date))`` of their open documents, ``days_overdue = max(0, as_of − overdue_since)``, bucket
  0-30/31-60/60+;
  ``limit_exceeded_offline`` (an open sale written over the limit offline), ``doubtful_flag``. Nothing is ever
  flagged automatically (US-M08-10).
"""

from __future__ import annotations

import base64
import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, Final
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.auth.principal import Principal
from app.core.db.session import tenant_transaction
from app.core.error_codes import ErrorCode
from app.core.errors import AppError, ErrorDetail
from app.core.money import money, money_str, qty_str
from app.core.permissions import BranchScope
from app.modules.accounting.domain.calendar import business_today
from app.modules.debts.application.doc_ports import DebtDocsRepository, Row
from app.modules.debts.application.open_docs import reconciled_targets
from app.modules.debts.application.ports import CounterpartyRepository
from app.modules.debts.application.register import DebtRegister
from app.modules.debts.domain.documents import aging_bucket, doc_status

ZERO: Final = Decimal("0.00")
CREDIT_DOCS: Final = frozenset(
    {"debt_payments", "returns", "debt_writeoffs", "supplier_payments", "supplier_returns"}
)


def _invalid(field_name: str, key: str) -> AppError:
    return AppError(ErrorCode.VALIDATION_ERROR, details=[ErrorDetail(field=field_name, message_key=key)])


def _d(value: date | None) -> str | None:
    return None if value is None else value.isoformat()


def _encode(offset: int) -> str:
    return base64.urlsafe_b64encode(json.dumps({"o": offset}).encode()).decode().rstrip("=")


def _decode(cursor: str) -> int:
    try:
        value = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))["o"]
        if not isinstance(value, int) or value < 0:
            raise ValueError(cursor)
        return value
    except (ValueError, TypeError, KeyError) as exc:
        raise _invalid("cursor", "validation.cursor_invalid") from exc


@dataclass
class _Entry:
    doc_type: str
    doc_id: UUID
    first_id: UUID
    amount: Decimal
    doc_date: date | None
    data: dict[str, Any] = field(default_factory=dict)


def fifo_open(balance: Decimal, charges: Sequence[Row]) -> dict[tuple[str, UUID], Decimal]:
    """Open part of each positive charge when ``balance`` is covered by the newest charges first."""
    rest = money(balance)
    out: dict[tuple[str, UUID], Decimal] = {}
    for c in sorted(charges, key=lambda c: (c["doc_date"] or date.min, str(c["doc_id"])), reverse=True):
        take = min(max(rest, ZERO), money(c["amount"]))
        out[(c["doc_type"], c["doc_id"])] = take
        rest = money(rest - take)
    return out


class DebtLedgerQueries:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        repo: DebtDocsRepository,
        counterparties: CounterpartyRepository,
        register: DebtRegister,
    ) -> None:
        self._sf = session_factory
        self._repo = repo
        self._cps = counterparties
        self._register = register

    # --- 18 §12.1 ---------------------------------------------------------------------------------
    async def ledger(
        self,
        actor: Principal,
        scope: BranchScope,
        counterparty_id: UUID,
        direction: str,
        cursor: str | None,
        limit: int,
    ) -> dict[str, Any]:
        offset = _decode(cursor) if cursor else 0
        allowed = None if scope.unrestricted else frozenset(scope.allowed)
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            cp = await self._cps.get(s, counterparty_id)
            if cp is None:
                raise AppError(ErrorCode.NOT_FOUND, params={"resource": "counterparty"})
            raw = await self._register.balances(s, counterparty_id)
            balances: dict[str, Decimal] = {"receivable": raw["receivable"], "payable": raw["payable"]}
            total_receivable = balances["receivable"]
            if allowed is not None:
                for d in ("receivable", "payable"):
                    balances[d] = await self._scoped_balance(s, counterparty_id, d, allowed)
            balance = balances["receivable" if direction == "receivable" else "payable"]
            entries = await self._entries(
                s, counterparty_id, direction, balance, allowed=allowed, total_receivable=total_receivable
            )
            flags = await self._repo.active_flags(s, [counterparty_id])
            due = await self._repo.counterparty_due_date(s, counterparty_id)
        flag = flags.get(counterparty_id)
        page = entries[offset : offset + limit]
        return {
            "counterparty": {
                "id": str(cp.id),
                "name": cp.name,
                "phone": cp.phone,
                "kind": cp.kind,
                "is_customer": cp.is_customer,
                "is_supplier": cp.is_supplier,
                "credit_limit": money_str(cp.credit_limit) if cp.credit_limit is not None else None,
                "receivable_balance": money_str(balances["receivable"]),
                "payable_balance": money_str(balances["payable"]),
                "debt_due_date": _d(due),
                "doubtful_flag": None if flag is None else {"id": str(flag["id"]), "reason": flag["reason"]},
            },
            "direction": direction,
            "balance": money_str(balance),
            "entries": page,
            "next_cursor": _encode(offset + limit) if offset + limit < len(entries) else None,
        }

    async def _scoped_balance(
        self, s: AsyncSession, counterparty_id: UUID, direction: str, allowed: frozenset[UUID]
    ) -> Decimal:
        """Σ ``debt_moves`` of the counterparty over documents of the allowed branches (SEC-01)."""
        moves = await self._repo.ledger_moves(s, counterparty_id, direction)
        infos = await self._repo.doc_infos(s, [(m.doc_type, m.doc_id) for m in moves])
        total = ZERO
        for m in moves:
            info = infos.get((m.doc_type, m.doc_id))
            if info is not None and info.branch_id in allowed:
                total += m.amount
        return money(total)

    async def _entries(
        self,
        s: AsyncSession,
        counterparty_id: UUID,
        direction: str,
        balance: Decimal,
        *,
        allowed: frozenset[UUID] | None = None,
        total_receivable: Decimal | None = None,
    ) -> list[dict[str, Any]]:
        moves = [
            m
            for m in await self._repo.ledger_moves(s, counterparty_id, direction)
            if not (m.reversed and m.amount == 0)
        ]
        refs = [(m.doc_type, m.doc_id) for m in moves]
        infos = await self._repo.doc_infos(s, refs)
        rows: list[_Entry] = []
        for m in moves:
            info = infos.get((m.doc_type, m.doc_id))
            rows.append(
                _Entry(
                    m.doc_type,
                    m.doc_id,
                    m.first_id,
                    m.amount,
                    info.doc_date if info else None,
                    {
                        "number": info.number if info else None,
                        "comment": info.comment if info else None,
                        "created_by": str(info.created_by) if info and info.created_by else None,
                        "created_by_name": info.created_by_name if info else None,
                        "doc_status": info.status if info else None,
                        "due_date": m.due_date,
                        "branch_id": info.branch_id if info else None,
                    },
                )
            )
        if allowed is not None:
            rows = [e for e in rows if e.data.get("branch_id") in allowed]
        statuses: dict[tuple[str, UUID], dict[str, Any]] = {}
        if direction == "receivable":
            whole = balance if total_receivable is None else total_receivable
            targets = (
                await reconciled_targets(
                    self._repo, s, [counterparty_id], balances={counterparty_id: whole}, only_open=False
                )
            )[counterparty_id]
            promises = await self._repo.promise_dates(s, counterparty_id)
            for t in targets:
                if t.doc_type == "debt_writeoffs":
                    continue
                statuses[(t.doc_type, t.doc_id)] = {
                    "status": doc_status(t.original, t.open_amount, t.written_off),
                    "open_amount": money_str(max(t.open_amount, ZERO)),
                    "promise_date": _d(promises.get((t.doc_type, t.doc_id)) or t.due_date),
                    "due_date": t.due_date,
                }
            await self._add_payment_rows(s, counterparty_id, rows, allowed)
        else:
            charges: list[dict[str, Any]] = [
                {"doc_type": e.doc_type, "doc_id": e.doc_id, "amount": e.amount, "doc_date": e.doc_date}
                for e in rows
                if e.amount > 0 and e.doc_type not in CREDIT_DOCS
            ]
            for (doc_type, doc_id), open_amount in fifo_open(balance, charges).items():
                original = next(
                    Decimal(str(c["amount"]))
                    for c in charges
                    if (c["doc_type"], c["doc_id"]) == (doc_type, doc_id)
                )
                statuses[(doc_type, doc_id)] = {
                    "status": doc_status(original, open_amount),
                    "open_amount": money_str(open_amount),
                    "promise_date": None,
                    "due_date": None,
                }
        sale_ids = [e.doc_id for e in rows if e.doc_type == "sales"]
        lines = await self._repo.sale_lines(s, sale_ids)
        pay_ids = [e.doc_id for e in rows if e.doc_type == "debt_payments"]
        allocs = await self._repo.allocations_of(s, "debt_payment_allocations", pay_ids)
        wo_ids = [e.doc_id for e in rows if e.doc_type == "debt_writeoffs"]
        wo_allocs = await self._repo.allocations_of(s, "debt_writeoff_allocations", wo_ids)
        rows.sort(key=lambda e: (e.doc_date or date.min, e.first_id.bytes))
        running = ZERO
        out: list[dict[str, Any]] = []
        for e in rows:
            running = money(running + e.amount)
            st = statuses.get((e.doc_type, e.doc_id), {})
            due = st.get("due_date") or e.data.get("due_date")
            item: dict[str, Any] = {
                "id": str(e.first_id),
                "doc_type": e.doc_type,
                "doc_id": str(e.doc_id),
                "number": e.data.get("number"),
                "doc_date": _d(e.doc_date),
                "amount": money_str(e.amount),
                "direction": direction,
                "kind": "debt"
                if e.amount > 0
                else "payment"
                if e.doc_type in ("debt_payments", "supplier_payments")
                else "credit",
                "running_balance": money_str(running),
                "due_date": _d(due),
                "promise_date": st.get("promise_date"),
                "comment": e.data.get("comment"),
                "status": st.get("status"),
                "open_amount": st.get("open_amount"),
                "created_by": e.data.get("created_by"),
                "created_by_name": e.data.get("created_by_name"),
                "paid_amount": e.data.get("paid_amount"),
                "products": [
                    {
                        "product_id": str(ln.product_id),
                        "name": ln.name,
                        "name_ru": ln.name_ru,
                        "qty": qty_str(ln.qty),
                        "line_total": money_str(ln.line_total),
                    }
                    for ln in lines.get(e.doc_id, [])
                ]
                if e.doc_type == "sales"
                else [],
                "allocations": [
                    {
                        "target_doc_type": a["target_doc_type"],
                        "target_doc_id": str(a["target_doc_id"]),
                        "target_number": a.get("target_number"),
                        "amount": money_str(a["amount"]),
                    }
                    for a in (allocs.get(e.doc_id) or wo_allocs.get(e.doc_id) or [])
                ],
            }
            out.append(item)
        out.reverse()  # newest first; running_balance is the balance after the row
        return out

    async def _add_payment_rows(
        self,
        s: AsyncSession,
        counterparty_id: UUID,
        rows: list[_Entry],
        allowed: frozenset[UUID] | None = None,
    ) -> None:
        """Every posted payment is a book row — also one that moved no debt (written-off debt,
        overpayment)."""
        page = await self._repo.docs_page(
            s,
            "debt_payments",
            filters={"counterparty_id": counterparty_id, "status": "posted"},
            branch_ids=None if allowed is None else sorted(allowed, key=lambda u: u.bytes),
            after=None,
            limit=10_000,
        )
        by_id = {e.doc_id: e for e in rows if e.doc_type == "debt_payments"}
        for p in page:
            entry = by_id.get(p["id"])
            if entry is None:
                entry = _Entry(
                    "debt_payments",
                    p["id"],
                    p["id"],
                    ZERO,
                    p["doc_date"],
                    {
                        "number": p["number"],
                        "comment": p["comment"],
                        "created_by": str(p["created_by"]),
                        "created_by_name": None,
                        "doc_status": p["status"],
                        "due_date": None,
                    },
                )
                rows.append(entry)
            entry.data["paid_amount"] = money_str(p["amount"])
        missing = [e for e in rows if e.data.get("created_by") and not e.data.get("created_by_name")]
        if missing:
            names = await self._repo.user_names(s, [UUID(e.data["created_by"]) for e in missing])
            for e in missing:
                e.data["created_by_name"] = names.get(UUID(e.data["created_by"]))

    # --- 20 #21 -----------------------------------------------------------------------------------
    async def aging(
        self,
        actor: Principal,
        scope: BranchScope,
        *,
        direction: str,
        as_of: date | None,
        branch_id: UUID | None,
        bucket: str | None,
        limit_exceeded_offline: bool | None,
    ) -> dict[str, Any]:
        day = as_of or business_today()
        if day > business_today():
            raise _invalid("as_of", "validation.date_in_future")
        if branch_id is not None and not scope.unrestricted and branch_id not in scope.allowed:
            raise AppError(ErrorCode.BRANCH_SCOPE_DENIED)
        branch_ids: frozenset[UUID] | None
        if branch_id is not None:
            branch_ids = frozenset({branch_id})
        else:
            branch_ids = None if scope.unrestricted else frozenset(scope.allowed)
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            rows = await aging_rows(self._repo, s, direction, day, branch_ids)
        summary = aging_summary(rows)
        if bucket is not None:
            rows = [r for r in rows if r["bucket"] == bucket]
        if limit_exceeded_offline is not None:
            rows = [r for r in rows if r["limit_exceeded_offline"] is limit_exceeded_offline]
        return {"as_of": day.isoformat(), "direction": direction, "summary": summary, "rows": rows}


async def aging_rows(
    repo: DebtDocsRepository,
    s: AsyncSession,
    direction: str,
    as_of: date,
    branch_ids: frozenset[UUID] | None,
) -> list[dict[str, Any]]:
    """``branch_ids`` (a ``branch_id`` filter or a restricted scope): only open documents of those branches,
    ``balance`` = their Σ."""
    debtors = await repo.debtors(s, direction)
    ids = [d["counterparty_id"] for d in debtors]
    flags = await repo.active_flags(s, ids)
    out: list[dict[str, Any]] = []
    if direction == "receivable":
        docs = await reconciled_targets(
            repo, s, ids, balances={d["counterparty_id"]: money(d["balance"]) for d in debtors}
        )
        last = await repo.last_payments(s, ids)
    else:
        charges = await repo.payable_charges(s, ids)
        last = {}
    for d in debtors:
        cid = d["counterparty_id"]
        if direction == "receivable":
            open_docs = [
                (t.doc_date, t.due_date, t.open_amount, t.limit_exceeded, t.branch_id)
                for t in docs.get(cid, [])
                if t.doc_type != "debt_writeoffs" and t.doc_date <= as_of
            ]
        else:
            fifo = fifo_open(Decimal(d["balance"]), charges.get(cid, []))
            open_docs = [
                (c["doc_date"], c["due_date"], fifo[(c["doc_type"], c["doc_id"])], False, c["branch_id"])
                for c in charges.get(cid, [])
                if fifo.get((c["doc_type"], c["doc_id"]), ZERO) > 0 and c["doc_date"] <= as_of
            ]
        if branch_ids is not None:
            open_docs = [o for o in open_docs if o[4] in branch_ids]
            balance = money(sum((o[2] for o in open_docs), ZERO))
        else:
            balance = money(d["balance"])
        if balance <= 0 or not open_docs:
            continue
        oldest = min(open_docs, key=lambda o: (o[1] or o[0], o[0]))
        overdue_since = oldest[1] or oldest[0]
        days = max(0, (as_of - overdue_since).days)
        flag = flags.get(cid)
        pay = last.get(cid)
        out.append(
            {
                "counterparty_id": str(cid),
                "name": d["name"],
                "phone": d["phone"],
                "balance": money_str(balance),
                "credit_limit": money_str(d["credit_limit"]) if d["credit_limit"] is not None else None,
                "due_date": _d(oldest[1]),
                "overdue_since": overdue_since.isoformat(),
                "days_overdue": days,
                "bucket": aging_bucket(days),
                "promise_date": _d(d["debt_due_date"]),
                "open_docs": len(open_docs),
                "limit_exceeded_offline": any(o[3] for o in open_docs),
                "doubtful_flag": flag is not None,
                "doubtful_flag_id": str(flag["id"]) if flag else None,
                "last_payment_amount": money_str(pay["amount"]) if pay else None,
                "last_payment_date": _d(pay["doc_date"]) if pay else None,
            }
        )
    out.sort(key=lambda r: (-r["days_overdue"], -Decimal(r["balance"]), r["counterparty_id"]))
    return out


def aging_summary(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    buckets: dict[str, list[Decimal]] = {"0-30": [], "31-60": [], "60+": []}
    for r in rows:
        buckets[r["bucket"]].append(Decimal(r["balance"]))
    total = money(sum((Decimal(r["balance"]) for r in rows), ZERO))
    return {
        "total": money_str(total),
        "count": len(rows),
        "buckets": [
            {"bucket": b, "count": len(v), "amount": money_str(sum(v, ZERO))} for b, v in buckets.items()
        ],
    }


def utc_now() -> datetime:
    return datetime.now(UTC)
