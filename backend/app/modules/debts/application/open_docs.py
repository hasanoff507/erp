"""16 §1 ``customers[].open_debt_docs[]`` — the offline cache the POS allocates a debt payment against.

Exact row shape: ``.claude-scratch/b4/contracts/customers-pull.md``; the same open documents the server
re-allocates on ``debt_payment.created`` (one SQL — ``DebtDocsRepository.target_docs``), in the allocation
order of
``app.shared.debt_allocation.allocation_order``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.money import money_str, percent_str, price_str, qty_str
from app.modules.debts.application.doc_ports import DebtDocsRepository, SaleLineRow, TargetDoc
from app.shared.debt_allocation import OpenDoc, allocation_order, reconcile_to_balance


def reconcile_targets(targets: Sequence[TargetDoc], balance: Decimal) -> list[TargetDoc]:
    """ACC-02 (13 §2.14): the open sales/openings trimmed oldest first to the customer's receivable balance —
    a credit on the account without a document closes the oldest debt; write-offs are never trimmed."""
    docs = reconcile_to_balance(
        [
            OpenDoc(
                t.doc_type,
                str(t.doc_id),
                t.doc_date.isoformat(),
                t.due_date.isoformat() if t.due_date else None,
                t.open_amount,
            )
            for t in targets
        ],
        balance,
    )
    return [
        t if d.open_amount == t.open_amount else replace(t, open_amount=d.open_amount)
        for t, d in zip(targets, docs, strict=True)
    ]


async def reconciled_targets(
    repo: DebtDocsRepository,
    s: AsyncSession,
    counterparty_ids: Sequence[UUID],
    *,
    balances: Mapping[UUID, Decimal] | None = None,
    only_open: bool = True,
) -> dict[UUID, list[TargetDoc]]:
    """``target_docs`` reconciled to ``debt_balances`` — THE receivable open documents of every consumer
    (pull, payment limit/allocation, write-off limit, aging, daily check, ledger). ``only_open`` also drops
    the documents the reconcile closed."""
    targets = await repo.target_docs(s, counterparty_ids, only_open=only_open)
    if balances is None:
        balances = await repo.receivable_balances(s, list(targets))
    out: dict[UUID, list[TargetDoc]] = {}
    for cid, docs in targets.items():
        fixed = reconcile_targets(docs, balances.get(cid, Decimal("0.00")))
        out[cid] = [t for t in fixed if t.open_amount > 0] if only_open else fixed
    return out


def _line_json(ln: SaleLineRow) -> dict[str, Any]:
    return {
        "sale_line_id": str(ln.sale_line_id),
        "line_no": ln.line_no,
        "product_id": str(ln.product_id),
        "name": ln.name,
        "name_ru": ln.name_ru,
        "mxik_code": ln.mxik_code,
        "package_code": ln.package_code,
        "unit_code": ln.unit_code,
        "barcode": ln.barcode,
        "qty": qty_str(ln.qty),
        "price": price_str(ln.price),
        "line_total": money_str(ln.line_total),
        "vat_rate": percent_str(ln.vat_rate),
        "vat_exemption_code": ln.vat_exemption_code,
        "settled_amount": money_str(ln.settled_amount),
        "marking_code": ln.marking_code,
        "returned_qty": qty_str(ln.returned_qty),
        "returned_amount": money_str(ln.returned_amount),
    }


def open_doc_json(t: TargetDoc, lines: Sequence[SaleLineRow]) -> dict[str, Any]:
    return {
        "doc_type": t.doc_type,
        "doc_id": str(t.doc_id),
        "number": t.number,
        "doc_date": t.doc_date.isoformat(),
        "due_date": t.due_date.isoformat() if t.due_date else None,
        "open_amount": money_str(t.open_amount),
        "lines": [_line_json(ln) for ln in lines] if t.doc_type == "sales" else [],
    }


class OpenDebtDocsReader:
    def __init__(self, repo: DebtDocsRepository) -> None:
        self._repo = repo

    async def for_customers(
        self, s: AsyncSession, counterparty_ids: Sequence[UUID]
    ) -> dict[UUID, list[dict[str, Any]]]:
        targets = await reconciled_targets(self._repo, s, counterparty_ids)
        sale_ids = [t.doc_id for docs in targets.values() for t in docs if t.doc_type == "sales"]
        lines = await self._repo.sale_lines(s, sale_ids)
        out: dict[UUID, list[dict[str, Any]]] = {}
        for cid, docs in targets.items():
            by_key = {str(t.doc_id): t for t in docs}
            order = allocation_order(
                [
                    OpenDoc(
                        t.doc_type,
                        str(t.doc_id),
                        t.doc_date.isoformat(),
                        t.due_date.isoformat() if t.due_date else None,
                        t.open_amount,
                    )
                    for t in docs
                ]
            )
            out[cid] = [
                open_doc_json(by_key[d.doc_id], lines.get(by_key[d.doc_id].doc_id, [])) for d in order
            ]
        return out
