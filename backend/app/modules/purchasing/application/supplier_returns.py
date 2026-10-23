"""Supplier returns (19 §12; 13 §2.20, §5.2; US-M07-05; QT-M07-06).

``POST`` (``purchases.return``) creates a draft against a **posted** goods receipt: every line names a
receipt line and the lot created from it; ``cost`` and ``vat_amount`` are derived from the receipt line
(:mod:`app.modules.purchasing.domain.supplier_returns`). ``post`` (``purchases.post``) issues each line
from its lot (``422 INSUFFICIENT_STOCK {lot_id, available}``), writes the 13 §2.20 ledger lines and
``debt_moves`` payable ``−Σ invoice``; numbers it ``MV-…``. A return more than 12 months after the
receipt is refused (``409 DOC_INVALID_STATE {reason: "reverse_sale_required"}``) — the reverse sale
is a separate flow. The VAT row (``Dt 6010 / Kt 4410``) and the negative ``vat_moves`` are written
when the supplier's additional e-invoice is accepted (``integrations.einvoice`` ``VatCredit``;
``vat_adjustment_status='adjusted'``); such a return can no longer be cancelled (``409 DOC_INVALID_STATE``,
``reason='vat_adjusted'`` — the EHF is registered at the operator). Marked lines carry their codes
(``lines[].marking_codes``); ``post`` hands them to the marking hook (CRPT ``marking_supplier_return``,
contract marking.md §2), ``cancel`` of a posted return gives them back (§4).
``cancel``: draft → cancelled; posted → stock back to the same lots, storno of ledger and debt rows.

Lock order (23 §2.1): return row → ``stock_balances`` → ``debt_balances``; the receipt status is
re-read after the stock lock, so a concurrent receipt cancel is seen.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, Final
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.audit import record_audit
from app.core.auth.principal import Principal
from app.core.db.base import uuid7
from app.core.db.session import tenant_transaction
from app.core.doc_numbers import next_doc_number
from app.core.error_codes import ErrorCode
from app.core.errors import AppError, ErrorDetail
from app.core.idempotency import stage_response
from app.core.money import money, money_str, price_str, qty, qty_str
from app.core.permissions import BranchScope
from app.modules.accounting.application.posting import LedgerPoster
from app.modules.accounting.domain.entries import LedgerLine
from app.modules.debts.application.register import DebtRegister
from app.modules.debts.domain.register import DebtMoveInput
from app.modules.integrations.marking.application.hooks import MarkedLine
from app.modules.inventory.application.stock import StockService, StockTxn
from app.modules.inventory.domain.analytics import cost_analytics
from app.modules.purchasing.application.goods_receipts import check_doc_date, decode_cursor, encode_cursor
from app.modules.purchasing.application.ports import (
    DocFilter,
    GoodsReceiptRepository,
    MarkingHooksPort,
    ReturnedSoFar,
    SupplierReturnRepository,
)
from app.modules.purchasing.application.purchase_orders import check_read_scope
from app.modules.purchasing.domain.receipts import ZERO_QTY, GoodsReceipt, ReceiptLine
from app.modules.purchasing.domain.supplier_returns import (
    MAX_LINES,
    ZERO,
    SupplierReturn,
    invoice_amount,
    return_entries,
    reverse_sale_required,
    vat_share,
)

DOC_TYPE: Final = "supplier_returns"
PAYABLE: Final = "payable"


@dataclass(frozen=True, slots=True)
class ReturnLineInput:
    receipt_line_id: UUID
    lot_id: UUID
    qty: Decimal
    marking_codes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ReturnInput:
    receipt_id: UUID
    doc_date: date
    reason: str
    lines: Sequence[ReturnLineInput]
    comment: str | None = None


def _invalid(field: str, key: str) -> AppError:
    return AppError(ErrorCode.VALIDATION_ERROR, details=[ErrorDetail(field=field, message_key=key)])


def not_found() -> AppError:
    return AppError(ErrorCode.NOT_FOUND, params={"resource": "supplier_return"})


def _ts(value: datetime | None) -> str | None:
    return None if value is None else value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _vat_adjustment(sr: SupplierReturn) -> str | None:
    """US-M07-05: a posted VAT-regime return with VAT waits for the supplier's additional e-invoice."""
    if sr.status != "posted":
        return None
    if sr.vat_adjusted:
        return "adjusted"
    if sr.receipt_regime == "vat" and sr.vat_total > 0:
        return "awaiting_einvoice"
    return "not_required"


def return_header_json(sr: SupplierReturn) -> dict[str, Any]:
    return {
        "id": str(sr.id),
        "number": sr.number,
        "status": sr.status,
        "doc_date": sr.doc_date.isoformat(),
        "branch_id": str(sr.branch_id),
        "warehouse_id": str(sr.warehouse_id),
        "supplier_id": str(sr.supplier_id),
        "supplier": {"id": str(sr.supplier_id), "name": sr.supplier_name, "stir": sr.supplier_stir},
        "receipt_id": str(sr.receipt_id),
        "receipt_number": sr.receipt_number,
        "reason": sr.reason,
        "comment": sr.comment,
        "line_count": sr.line_count,
        "net_total": money_str(sr.net_total),
        "vat_total": money_str(sr.vat_total),
        "invoice_total": money_str(sr.invoice_total),
        "vat_adjustment_status": _vat_adjustment(sr),
        "created_by": str(sr.created_by),
        "created_by_name": sr.created_by_name,
        "created_at": _ts(sr.created_at),
        "updated_at": _ts(sr.updated_at),
        "posted_at": _ts(sr.posted_at),
        "cancelled_at": _ts(sr.cancelled_at),
        "cancel_reason": sr.cancel_reason,
    }


def return_json(sr: SupplierReturn) -> dict[str, Any]:
    lines = [
        {
            "id": str(ln.id),
            "line_no": ln.line_no,
            "receipt_line_id": str(ln.receipt_line_id),
            "lot_id": str(ln.lot_id),
            "product_id": str(ln.product_id),
            "product_name": ln.product_name,
            "unit_code": ln.unit_code,
            "qty": qty_str(ln.qty),
            "cost": price_str(ln.cost),
            "vat_amount": money_str(ln.vat_amount),
            "net_amount": money_str(ln.net),
            "marking_codes": list(ln.marking_codes),
            "invoice_amount": money_str(
                invoice_amount(ln.qty, ln.cost, ln.vat_amount, regime=sr.receipt_regime)
            ),
        }
        for ln in sr.lines
    ]
    return return_header_json(sr) | {"lines": lines}


class _Shares:
    """Running VAT shares per receipt line (earlier posted returns + the lines of this document)."""

    def __init__(self, so_far: dict[UUID, ReturnedSoFar]) -> None:
        self._qty = {k: v.qty for k, v in so_far.items()}
        self._vat = {k: v.vat for k, v in so_far.items()}

    def take(self, rl: ReceiptLine, quantity: Decimal) -> Decimal:
        earlier_qty, earlier_vat = self._qty.get(rl.id, ZERO_QTY), self._vat.get(rl.id, ZERO)
        share = vat_share(rl.vat_amount, rl.qty, quantity, earlier_qty, earlier_vat)
        self._qty[rl.id], self._vat[rl.id] = earlier_qty + quantity, earlier_vat + share
        return share


class SupplierReturnService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        repo: SupplierReturnRepository,
        receipts: GoodsReceiptRepository,
        stock: StockService,
        poster: LedgerPoster,
        debts: DebtRegister,
        marking: MarkingHooksPort | None = None,
    ) -> None:
        self._sf = session_factory
        self._repo = repo
        self._receipts = receipts
        self._stock = stock
        self._poster = poster
        self._debts = debts
        self._marking = marking

    # --- reads ------------------------------------------------------------------------------------
    async def list_page(
        self, actor: Principal, flt: DocFilter, cursor: str | None, limit: int
    ) -> dict[str, Any]:
        after = decode_cursor(cursor) if cursor else None
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            rows = await self._repo.list_page(s, flt, after, limit + 1)
        page = rows[:limit]
        next_cursor = encode_cursor(page[-1].created_at, page[-1].id) if len(rows) > limit else None
        return {"items": [return_header_json(sr) for sr in page], "next_cursor": next_cursor}

    async def get(self, actor: Principal, scope: BranchScope, return_id: UUID) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            sr = await self._repo.get(s, return_id)
            if sr is None:
                raise not_found()
            check_read_scope(scope, sr.branch_id)
        return return_json(sr)

    # --- create -----------------------------------------------------------------------------------
    async def create(
        self, actor: Principal, scope: BranchScope, data: ReturnInput, ip: str | None
    ) -> dict[str, Any]:
        _check_input(data)
        check_doc_date(data.doc_date)
        return_id = uuid7()
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            gr = await self._receipts.get(s, data.receipt_id)
            if gr is None:
                raise AppError(ErrorCode.NOT_FOUND, params={"resource": "goods_receipt"})
            check_read_scope(scope, gr.branch_id)
            if scope.current is not None and gr.branch_id != scope.current:
                raise _invalid("receipt_id", "validation.receipt_not_in_branch")
            _check_receipt(gr)
            by_id = {ln.id: ln for ln in gr.lines}
            shares = _Shares(
                await self._repo.returned_so_far(s, [ln.receipt_line_id for ln in data.lines], None)
            )
            wanted: dict[UUID, Decimal] = {}
            rows: list[dict[str, Any]] = []
            for index, ln in enumerate(data.lines):
                rl = by_id.get(ln.receipt_line_id)
                if rl is None:
                    raise _invalid(f"lines[{index}].receipt_line_id", "validation.receipt_line_not_found")
                lot = await self._stock.repo.lot(s, ln.lot_id)
                if lot is None or lot.receipt_line_id != rl.id:
                    raise _invalid(f"lines[{index}].lot_id", "validation.lot_not_of_receipt_line")
                quantity = qty(ln.qty)
                wanted[lot.id] = wanted.get(lot.id, ZERO_QTY) + quantity
                available = lot.qty_left - lot.blocked_qty
                if wanted[lot.id] > available:
                    raise AppError(
                        ErrorCode.INSUFFICIENT_STOCK,
                        params={
                            "lot_id": str(lot.id),
                            "available": format(qty(max(available, ZERO_QTY)), "f"),
                        },
                    )
                rows.append(
                    {"id": uuid7(), "tenant_id": actor.tenant_id, "supplier_return_id": return_id,
                     "line_no": index + 1, "receipt_line_id": rl.id, "lot_id": lot.id, "qty": quantity,
                     "cost": rl.cost, "vat_amount": shares.take(rl, quantity),
                     "marking_codes": _line_codes(index, ln, rl.is_marked)}
                )  # fmt: skip
            head = {
                "id": return_id, "tenant_id": actor.tenant_id, "branch_id": gr.branch_id,
                "doc_date": data.doc_date, "supplier_id": gr.supplier_id, "receipt_id": gr.id,
                "reason": data.reason, "created_by": actor.user_id, "comment": data.comment,
            }  # fmt: skip
            await self._repo.insert(s, head, rows)
            await record_audit(
                s, tenant_id=actor.tenant_id, user_id=actor.user_id, action="supplier_return.created",
                entity=DOC_TYPE, entity_id=return_id, ip=ip,
                after={"receipt_id": str(gr.id), "reason": data.reason, "doc_date": data.doc_date.isoformat(),
                       "lines": [{"lot_id": str(r["lot_id"]), "qty": qty_str(r["qty"])} for r in rows]},
            )  # fmt: skip
            body = return_json(await self._load(s, return_id))
            stage_response(body, 201)
        return body

    # --- post -------------------------------------------------------------------------------------
    async def post(
        self, actor: Principal, scope: BranchScope, return_id: UUID, ip: str | None
    ) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            sr = await self._locked(s, scope, return_id)
            if sr.status != "draft":
                raise AppError(
                    ErrorCode.DOC_NOT_DRAFT, params={"expected_status": "draft", "actual_status": sr.status}
                )
            check_doc_date(sr.doc_date)
            await self._poster.assert_period_open(s, sr.doc_date)
            txn = await self._stock.lock(
                s, actor.tenant_id, [(sr.warehouse_id, ln.product_id) for ln in sr.lines]
            )
            gr = await self._receipts.get(s, sr.receipt_id)  # after the stock lock: sees a cancel
            assert gr is not None
            _check_receipt(gr)
            if reverse_sale_required(gr.doc_date, sr.doc_date):
                raise AppError(
                    ErrorCode.DOC_INVALID_STATE,
                    params={"reason": "reverse_sale_required", "receipt_doc_date": gr.doc_date.isoformat()},
                )
            await self._debts.lock(s, actor.tenant_id, [(sr.supplier_id, PAYABLE)])
            invoice_total = await self._post_lines(s, actor.tenant_id, txn, sr, gr)
            marked = [
                MarkedLine(index=i, product_id=ln.product_id, qty=ln.qty, codes=ln.marking_codes)
                for i, ln in enumerate(sr.lines)
                if ln.is_marked
            ]
            if marked and self._marking is not None:  # contract marking.md §2 (CRPT, 3 business days)
                await self._marking.on_supplier_return_posted(
                    s, actor.tenant_id, sr.id, lines=marked, actor_user_id=actor.user_id
                )
            if invoice_total > 0:
                await self._debts.post(
                    s,
                    actor.tenant_id,
                    [DebtMoveInput(sr.supplier_id, PAYABLE, -invoice_total, DOC_TYPE, sr.id)],
                )
            number = await next_doc_number(
                s, tenant_id=actor.tenant_id, branch_id=sr.branch_id, table=DOC_TYPE, year=sr.doc_date.year
            )
            await self._repo.update(s, sr.id, {"status": "posted", "number": number, "posted_at": txn.at})
            await record_audit(
                s, tenant_id=actor.tenant_id, user_id=actor.user_id, action="supplier_return.posted",
                entity=DOC_TYPE, entity_id=sr.id, ip=ip, before={"status": sr.status},
                after={"status": "posted", "number": number, "invoice_total": money_str(invoice_total)},
            )  # fmt: skip
            body = return_json(await self._load(s, sr.id))
            stage_response(body)
        await self._stock.after_commit(txn)
        return body

    async def _post_lines(
        self, s: AsyncSession, tenant_id: UUID, txn: StockTxn, sr: SupplierReturn, gr: GoodsReceipt
    ) -> Decimal:
        by_id = {ln.id: ln for ln in gr.lines}
        shares = _Shares(await self._repo.returned_so_far(s, [ln.receipt_line_id for ln in sr.lines], sr.id))
        inv_acct = await txn.inv_acct(sr.warehouse_id)
        ledger: list[LedgerLine] = []
        invoice_total = ZERO
        for ln in sr.lines:
            rl = by_id[ln.receipt_line_id]
            vat = shares.take(rl, ln.qty)
            if vat != ln.vat_amount:  # earlier returns of the line were posted since the draft
                await self._repo.set_line_vat(s, ln.id, vat)
            res = await txn.issue(
                sr.warehouse_id,
                ln.product_id,
                ln.qty,
                doc_type=DOC_TYPE,
                doc_id=sr.id,
                line_id=ln.id,
                lot_id=ln.lot_id,
            )  # 422 INSUFFICIENT_STOCK {lot_id, available}; never pending
            invoice = invoice_amount(ln.qty, ln.cost, vat, regime=sr.receipt_regime)
            analytics = cost_analytics(
                product_id=ln.product_id, warehouse_id=sr.warehouse_id, line_id=ln.id,
                lot_ids=[a.lot_id for a in res.allocations], extra={"counterparty_id": str(sr.supplier_id)},
            )  # fmt: skip
            ledger += return_entries(
                invoice=invoice, book=res.cost, inv_acct=inv_acct, entry_date=sr.doc_date,
                branch_id=sr.branch_id, cost_analytics=analytics, supplier_id=sr.supplier_id,
            )  # fmt: skip
            invoice_total += invoice
        await self._poster.post(s, tenant_id, DOC_TYPE, sr.id, ledger)
        return money(invoice_total)

    # --- cancel -----------------------------------------------------------------------------------
    async def cancel(
        self, actor: Principal, scope: BranchScope, return_id: UUID, reason: str, ip: str | None
    ) -> dict[str, Any]:
        txn: StockTxn | None = None
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            sr = await self._locked(s, scope, return_id)
            if sr.status == "cancelled":
                raise AppError(
                    ErrorCode.DOC_INVALID_STATE,
                    params={"expected_status": "draft|posted", "actual_status": sr.status},
                )
            if sr.status == "posted" and sr.vat_adjusted:
                raise AppError(ErrorCode.DOC_INVALID_STATE, params={"reason": "vat_adjusted"})
            if sr.status == "posted":
                txn = await self._stock.lock(
                    s, actor.tenant_id, [(sr.warehouse_id, ln.product_id) for ln in sr.lines]
                )
                await txn.reverse_issue(DOC_TYPE, sr.id)
                if self._marking is not None and any(ln.marking_codes for ln in sr.lines):
                    await self._marking.on_codes_document_cancelled(
                        s, actor.tenant_id, sr.id, actor_user_id=actor.user_id
                    )
                await self._poster.reverse_document(s, actor.tenant_id, DOC_TYPE, sr.id)
                await self._debts.reverse(s, actor.tenant_id, DOC_TYPE, sr.id)
            await self._repo.update(
                s, sr.id,
                {"status": "cancelled", "cancelled_at": datetime.now(UTC), "cancelled_by": actor.user_id,
                 "cancel_reason": reason},
            )  # fmt: skip
            await record_audit(
                s, tenant_id=actor.tenant_id, user_id=actor.user_id, action="supplier_return.cancelled",
                entity=DOC_TYPE, entity_id=sr.id, ip=ip, before={"status": sr.status},
                after={"status": "cancelled", "reason": reason},
            )  # fmt: skip
            body = return_json(await self._load(s, sr.id))
            stage_response(body)
        if txn is not None:
            await self._stock.after_commit(txn)
        return body

    # --- helpers ----------------------------------------------------------------------------------
    async def _load(self, s: AsyncSession, return_id: UUID) -> SupplierReturn:
        sr = await self._repo.get(s, return_id)
        assert sr is not None
        return sr

    async def _locked(self, s: AsyncSession, scope: BranchScope, return_id: UUID) -> SupplierReturn:
        sr = await self._repo.get(s, return_id, lock=True)
        if sr is None:
            raise not_found()
        check_read_scope(scope, sr.branch_id)
        return sr


def _line_codes(index: int, ln: ReturnLineInput, is_marked: bool) -> list[str]:
    """Marked lines need exactly ``qty`` distinct codes (CRPT notice, VM 833 85); unmarked — none. Whether the
    codes are in stock is checked by the marking hook on ``post``."""
    codes = list(ln.marking_codes)
    field = f"lines[{index}].marking_codes"
    if not is_marked:
        if codes:
            raise _invalid(field, "validation.marking_not_required")
        return []
    quantity = qty(ln.qty)
    if quantity != quantity.to_integral_value() or Decimal(len(codes)) != quantity:
        raise _invalid(field, "validation.marking_count_mismatch")
    if len(set(codes)) != len(codes):
        raise _invalid(field, "validation.duplicate")
    return codes


def _check_input(data: ReturnInput) -> None:
    if not data.lines:
        raise _invalid("lines", "validation.required")
    if len(data.lines) > MAX_LINES:
        raise _invalid("lines", "validation.max_items")
    for index, ln in enumerate(data.lines):
        if qty(ln.qty) <= 0:
            raise _invalid(f"lines[{index}].qty", "validation.positive")


def _check_receipt(gr: GoodsReceipt) -> None:
    if gr.status != "posted":
        raise AppError(
            ErrorCode.DOC_INVALID_STATE,
            params={"reason": "receipt_not_posted", "expected_status": "posted", "actual_status": gr.status},
        )
    if gr.kind == "gratuitous":  # nothing is owed to the "supplier" of a gift (13 §2.6a)
        raise AppError(ErrorCode.DOC_INVALID_STATE, params={"reason": "gratuitous_receipt"})
