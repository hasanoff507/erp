"""Goods receipts (19 §8; 13 §2.6–§2.8, §4.3, §5.2; US-M04-01, US-M07-02/03; QT-M04-01, QT-M07-02…09).

``POST`` creates a ``draft`` (``purchases.receive``); ``PATCH`` replaces the whole draft; ``post``
(``purchases.post``, qaror #49) creates one lot per line through the stock toolkit, writes the ledger /
VAT / payable (:func:`app.modules.purchasing.domain.receipts.receipt_posting`), numbers it ``M-…`` and
refreshes the linked purchase order — all in ONE transaction. ``cancel``: a draft just becomes
``cancelled``; a posted receipt is reversed (13 §5.2): ``409 LOT_ALREADY_CONSUMED`` when any of its lots
was touched (sold, returned to the supplier, blocked), else storno of the stock moves, ledger, VAT and
debt rows, and the PO status is recomputed. A receipt that a posted supplier payment is allocated to
is refused (``409 DOC_INVALID_STATE``, ``params.reason='supplier_payment_allocated'``) — cancel the
payments first.

Lock order (23 §2.1): receipt row → purchase order row → ``stock_balances`` (one ``lock`` call with
every key) → ``debt_balances``.

Marking codes (12 ``marking_codes``; 19 §8): a draft registers its codes as
``status='pending_verification'``, ``last_doc_id`` = the receipt; ``post`` moves them to ``in_stock``;
``cancel`` / ``PATCH`` drop them. The CRPT acceptance (``outbox_jobs(kind='marking_accept')``) is
Bosqich 5.
"""

from __future__ import annotations

import base64
import json
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
from app.core.money import money_str, percent, percent_str, price, price_str, qty, qty_str
from app.core.permissions import BranchScope
from app.modules.accounting.application.posting import LedgerPoster
from app.modules.accounting.domain.calendar import business_today
from app.modules.debts.application.counterparties import CounterpartyDirectory
from app.modules.debts.application.register import DebtRegister
from app.modules.debts.domain.register import DebtMoveInput
from app.modules.inventory.application.stock import ReceiveResult, StockService, StockTxn
from app.modules.purchasing.application.po_receipts import PurchaseOrderReceipts
from app.modules.purchasing.application.ports import (
    DocFilter,
    GoodsReceiptRepository,
    ProductRef,
    PurchaseOrderRepository,
)
from app.modules.purchasing.application.purchase_orders import check_read_scope
from app.modules.purchasing.domain.purchase_orders import PurchaseOrder, ordered_by_product
from app.modules.purchasing.domain.receipts import (
    ALLOWED_VAT_RATES,
    MAX_LINES,
    ZERO,
    GoodsReceipt,
    ReceiptLine,
    discrepant_products,
    line_net,
    line_vat,
    lot_amount,
    receipt_posting,
    remaining_by_product,
)

DOC_TYPE: Final = "goods_receipts"
PAYABLE: Final = "payable"


@dataclass(frozen=True, slots=True)
class ReceiptLineInput:
    product_id: UUID
    qty: Decimal
    cost: Decimal | None = None
    vat_rate: Decimal | None = None
    vat_exemption_code: str | None = None
    expiry_date: date | None = None
    marking_codes: tuple[str, ...] | None = None
    discrepancy_reason: str | None = None


@dataclass(frozen=True, slots=True)
class ReceiptInput:
    warehouse_id: UUID
    doc_date: date
    lines: Sequence[ReceiptLineInput]
    supplier_id: UUID | None = None
    po_id: UUID | None = None
    paid_immediately: bool = False
    kind: str = "purchase"
    ettn_ref: str | None = None
    poa_id: UUID | None = None
    poa_number: str | None = None
    comment: str | None = None


def _invalid(field: str, key: str) -> AppError:
    return AppError(ErrorCode.VALIDATION_ERROR, details=[ErrorDetail(field=field, message_key=key)])


def not_found() -> AppError:
    return AppError(ErrorCode.NOT_FOUND, params={"resource": "goods_receipt"})


def check_doc_date(doc_date: date) -> None:
    """13 §5.2 / 19 §1: a document is never dated after the current business day (Asia/Tashkent)."""
    if doc_date > business_today():
        raise _invalid("doc_date", "validation.doc_date_in_future")


def _ts(value: datetime | None) -> str | None:
    return None if value is None else value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _str(value: Any) -> str | None:
    return None if value is None else str(value)


def _marking_acceptance(gr: GoodsReceipt) -> dict[str, Any] | None:
    """19 §8 derived ``marking_acceptance``: CRPT acceptance is Bosqich 5 — a posted receipt with marked
    lines is ``pending`` with the strictest group deadline; ``due_at`` is unknown until the e-invoice /
    e-TTN dispatch date is linked (from-einvoice, Bosqich 5)."""
    marked = [ln for ln in gr.lines if ln.is_marked]
    if not marked or gr.status != "posted":
        return None
    kinds = {ln.marking_deadline for ln in marked}
    return {
        "status": "pending",
        "due_at": None,
        "deadline_kind": "72_hours" if "72_hours" in kinds else "3_business_days",
    }


def receipt_header_json(gr: GoodsReceipt) -> dict[str, Any]:
    return {
        "id": str(gr.id),
        "number": gr.number,
        "status": gr.status,
        "doc_date": gr.doc_date.isoformat(),
        "branch_id": str(gr.branch_id),
        "warehouse_id": str(gr.warehouse_id),
        "supplier_id": str(gr.supplier_id),
        "supplier": {"id": str(gr.supplier_id), "name": gr.supplier_name, "stir": gr.supplier_stir},
        "po_id": _str(gr.po_id),
        "kind": gr.kind,
        "source": gr.source,
        "paid_immediately": gr.paid_immediately,
        "einvoice_id": _str(gr.einvoice_id),
        "einvoice_risk_flag": gr.einvoice_risk_flag,
        "ettn_ref": gr.ettn_ref,
        "ettn_status": "received" if gr.ettn_ref else "none",
        "poa_id": _str(gr.poa_id),
        "poa_number": gr.poa_number,
        "comment": gr.comment,
        "line_count": gr.line_count,
        "net_total": money_str(gr.net_total),
        "vat_total": money_str(gr.vat_total),
        "total": money_str(gr.total),
        "created_by": str(gr.created_by),
        "created_by_name": gr.created_by_name,
        "created_at": _ts(gr.created_at),
        "updated_at": _ts(gr.updated_at),
        "posted_at": _ts(gr.posted_at),
        "cancelled_at": _ts(gr.cancelled_at),
        "cancel_reason": gr.cancel_reason,
    }


def receipt_json(gr: GoodsReceipt) -> dict[str, Any]:
    lines = [
        {
            "id": str(ln.id),
            "line_no": ln.line_no,
            "product_id": str(ln.product_id),
            "product_name": ln.product_name,
            "unit_code": ln.unit_code,
            "qty": qty_str(ln.qty),
            "cost": price_str(ln.cost),
            "vat_rate": percent_str(ln.vat_rate),
            "vat_exemption_code": ln.vat_exemption_code,
            "vat_amount": money_str(ln.vat_amount),
            "net_amount": money_str(ln.net),
            "total_amount": money_str(ln.total),
            "expiry_date": ln.expiry_date.isoformat() if ln.expiry_date else None,
            "discrepancy_reason": ln.discrepancy_reason,
            "is_marked": ln.is_marked,
            "marking_codes": list(ln.marking_codes),
            "lot_id": _str(ln.lot_id),
            "lot_qty_left": None if ln.lot_qty_left is None else qty_str(ln.lot_qty_left),
            "returned_qty": qty_str(ln.returned_qty),
        }
        for ln in gr.lines
    ]
    return receipt_header_json(gr) | {"marking_acceptance": _marking_acceptance(gr), "lines": lines}


def _encode_cursor(created_at: datetime, doc_id: UUID) -> str:
    raw = json.dumps([created_at.isoformat(), str(doc_id)]).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


CURSOR_MIN: Final = datetime(2000, 1, 1, tzinfo=UTC)
CURSOR_MAX: Final = datetime(2100, 1, 1, tzinfo=UTC)


def decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    """``[created_at, id]`` keyset cursor; the instant must be tz-aware and within 2000…2100 UTC (a
    crafted far-future offset would otherwise overflow inside the driver → 500)."""
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))
        at, did = json.loads(raw)
        when = datetime.fromisoformat(at)
        if when.tzinfo is None or not CURSOR_MIN <= when <= CURSOR_MAX:
            raise ValueError("cursor instant out of range")
        return when.astimezone(UTC), UUID(did)
    except (ValueError, TypeError, OverflowError) as exc:
        raise _invalid("cursor", "validation.cursor_invalid") from exc


def encode_cursor(created_at: datetime, doc_id: UUID) -> str:
    return _encode_cursor(created_at, doc_id)


class GoodsReceiptService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        repo: GoodsReceiptRepository,
        po_repo: PurchaseOrderRepository,
        po_receipts: PurchaseOrderReceipts,
        directory: CounterpartyDirectory,
        stock: StockService,
        poster: LedgerPoster,
        debts: DebtRegister,
    ) -> None:
        self._sf = session_factory
        self._repo = repo
        self._po_repo = po_repo
        self._po = po_receipts
        self._directory = directory
        self._stock = stock
        self._poster = poster
        self._debts = debts

    @property
    def repo(self) -> GoodsReceiptRepository:
        return self._repo

    # --- reads ------------------------------------------------------------------------------------
    async def list_page(
        self, actor: Principal, flt: DocFilter, cursor: str | None, limit: int
    ) -> dict[str, Any]:
        after = decode_cursor(cursor) if cursor else None
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            rows = await self._repo.list_page(s, flt, after, limit + 1)
        page = rows[:limit]
        next_cursor = _encode_cursor(page[-1].created_at, page[-1].id) if len(rows) > limit else None
        return {"items": [receipt_header_json(gr) for gr in page], "next_cursor": next_cursor}

    async def get(self, actor: Principal, scope: BranchScope, receipt_id: UUID) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            gr = await self._repo.get(s, receipt_id)
            if gr is None:
                raise not_found()
            check_read_scope(scope, gr.branch_id)
        return receipt_json(gr)

    # --- create / replace draft -------------------------------------------------------------------
    async def create(
        self, actor: Principal, scope: BranchScope, data: ReceiptInput, ip: str | None
    ) -> dict[str, Any]:
        _check_input(data)
        check_doc_date(data.doc_date)
        receipt_id = uuid7()
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            head, lines, codes = await self._prepare(s, scope, data, receipt_id, actor.tenant_id)
            await self._repo.insert(
                s, {**head, "id": receipt_id, "tenant_id": actor.tenant_id, "created_by": actor.user_id}
            )
            await self._repo.replace_lines(s, receipt_id, lines)
            await self._register_codes(s, actor.tenant_id, receipt_id, codes)
            await record_audit(
                s, tenant_id=actor.tenant_id, user_id=actor.user_id, action="goods_receipt.created",
                entity=DOC_TYPE, entity_id=receipt_id, ip=ip, after=_audit(head, lines),
            )  # fmt: skip
            body = receipt_json(await self._load(s, receipt_id))
            stage_response(body, 201)
        return body

    async def replace(
        self, actor: Principal, scope: BranchScope, receipt_id: UUID, data: ReceiptInput, ip: str | None
    ) -> dict[str, Any]:
        """19 §8 ``PATCH`` (draft only): the body replaces the whole draft."""
        _check_input(data)
        check_doc_date(data.doc_date)
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            gr = await self._locked(s, scope, receipt_id)
            _require_draft(gr)
            head, lines, codes = await self._prepare(s, scope, data, receipt_id, actor.tenant_id)
            await self._repo.update(s, receipt_id, head)
            await self._repo.replace_lines(s, receipt_id, lines)
            await self._register_codes(s, actor.tenant_id, receipt_id, codes)
            await record_audit(
                s, tenant_id=actor.tenant_id, user_id=actor.user_id, action="goods_receipt.updated",
                entity=DOC_TYPE, entity_id=receipt_id, ip=ip,
                before={"lines": gr.line_count, "total": money_str(gr.total)}, after=_audit(head, lines),
            )  # fmt: skip
            body = receipt_json(await self._load(s, receipt_id))
            stage_response(body)
        return body

    # --- post -------------------------------------------------------------------------------------
    async def post(
        self, actor: Principal, scope: BranchScope, receipt_id: UUID, ip: str | None
    ) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            gr = await self._locked(s, scope, receipt_id)
            _require_draft(gr)
            check_doc_date(gr.doc_date)
            if gr.po_id is not None:  # cancelled/closed meanwhile → 409 PURCHASE_ORDER_CLOSED
                await self._po.assert_open_for_receipt(s, gr.po_id, lock=True)
            await self._directory.require_supplier(s, gr.supplier_id)
            await self._poster.assert_period_open(s, gr.doc_date)
            txn, lots = await self._post_in(s, actor.tenant_id, gr)
            if gr.po_id is not None:
                await self._po.refresh_status(s, gr.po_id)
            await record_audit(
                s, tenant_id=actor.tenant_id, user_id=actor.user_id, action="goods_receipt.posted",
                entity=DOC_TYPE, entity_id=receipt_id, ip=ip, before={"status": gr.status},
                after={"status": "posted", "total": money_str(gr.total), "lots": len(lots)},
            )  # fmt: skip
            body = receipt_json(await self._load(s, receipt_id))
            body["lots_created"] = [
                {
                    "lot_id": str(res.lot_id),
                    "product_id": str(ln.product_id),
                    "qty_in": qty_str(ln.qty),
                    "unit_cost": price_str(res.unit_cost),
                }
                for ln, res in lots
            ]
            stage_response(body)
        await self._stock.after_commit(txn)
        return body

    async def _post_in(
        self, s: AsyncSession, tenant_id: UUID, gr: GoodsReceipt
    ) -> tuple[StockTxn, list[tuple[ReceiptLine, ReceiveResult]]]:
        regime = await self._repo.regime_on(s, gr.doc_date)
        txn = await self._stock.lock(s, tenant_id, [(gr.warehouse_id, ln.product_id) for ln in gr.lines])
        credit_purchase = gr.kind == "purchase" and not gr.paid_immediately
        advance = ZERO
        if credit_purchase:  # debt rows after the stock rows (23 §2.1); serialises advance offsets
            await self._debts.lock(s, tenant_id, [(gr.supplier_id, PAYABLE)])
            advance = await self._repo.advance_balance(s, gr.supplier_id)
        inv_acct = await txn.inv_acct(gr.warehouse_id)
        lots: list[tuple[ReceiptLine, ReceiveResult]] = []
        for ln in gr.lines:
            res = await txn.receive(
                gr.warehouse_id, ln.product_id, ln.qty, lot_amount(ln, regime=regime, kind=gr.kind),
                source_doc_type=DOC_TYPE, source_doc_id=gr.id, source_line_id=ln.id, receipt_line_id=ln.id,
                expiry_date=ln.expiry_date,
            )  # fmt: skip
            lots.append((ln, res))
        plan = receipt_posting(
            [(ln, res.lot_id) for ln, res in lots], regime=regime, kind=gr.kind,
            paid_immediately=gr.paid_immediately, risk_flag=gr.einvoice_risk_flag, advance=advance,
            entry_date=gr.doc_date, branch_id=gr.branch_id, inv_acct=inv_acct, supplier_id=gr.supplier_id,
            warehouse_id=gr.warehouse_id, einvoice_id=gr.einvoice_id,
        )  # fmt: skip
        await self._poster.post(s, tenant_id, DOC_TYPE, gr.id, plan.ledger, vat=plan.vat)
        if plan.payable > 0:
            await self._debts.post(
                s, tenant_id, [DebtMoveInput(gr.supplier_id, PAYABLE, plan.payable, DOC_TYPE, gr.id)]
            )
        number = await next_doc_number(
            s, tenant_id=tenant_id, branch_id=gr.branch_id, table=DOC_TYPE, year=gr.doc_date.year
        )
        await self._repo.update(s, gr.id, {"status": "posted", "number": number, "posted_at": txn.at})
        await self._repo.set_codes_status(s, gr.id, "in_stock")
        return txn, lots

    # --- cancel -----------------------------------------------------------------------------------
    async def cancel(
        self, actor: Principal, scope: BranchScope, receipt_id: UUID, reason: str, ip: str | None
    ) -> dict[str, Any]:
        txn: StockTxn | None = None
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            gr = await self._locked(s, scope, receipt_id)
            if gr.status == "cancelled":
                raise AppError(ErrorCode.DOC_ALREADY_CANCELLED)
            if gr.status == "posted":
                if gr.po_id is not None:  # PO row before the stock rows, as in post
                    await self._po_repo.get(s, gr.po_id, lock=True)
                txn = await self._stock.lock(
                    s, actor.tenant_id, [(gr.warehouse_id, ln.product_id) for ln in gr.lines]
                )
                # supplier payments allocate under this lock (13 §2.16): cancel those payments first
                await self._debts.lock(s, actor.tenant_id, [(gr.supplier_id, PAYABLE)])
                paying = await self._repo.paying_supplier_payments(s, gr.id)
                if paying:
                    raise AppError(
                        ErrorCode.DOC_INVALID_STATE,
                        params={
                            "reason": "supplier_payment_allocated",
                            "supplier_payment_ids": [str(p) for p in paying],
                        },
                    )
                await txn.reverse_receipt(DOC_TYPE, gr.id)  # 409 LOT_ALREADY_CONSUMED
                await self._poster.reverse_document(s, actor.tenant_id, DOC_TYPE, gr.id)
                await self._debts.reverse(s, actor.tenant_id, DOC_TYPE, gr.id)
            await self._repo.update(
                s, receipt_id,
                {"status": "cancelled", "cancelled_at": datetime.now(UTC), "cancelled_by": actor.user_id,
                 "cancel_reason": reason},
            )  # fmt: skip
            await self._repo.drop_codes(s, receipt_id)
            if gr.status == "posted" and gr.po_id is not None:
                await self._po.refresh_status(s, gr.po_id)
            await record_audit(
                s, tenant_id=actor.tenant_id, user_id=actor.user_id, action="goods_receipt.cancelled",
                entity=DOC_TYPE, entity_id=receipt_id, ip=ip, before={"status": gr.status},
                after={"status": "cancelled", "reason": reason},
            )  # fmt: skip
            body = receipt_json(await self._load(s, receipt_id))
            stage_response(body)
        if txn is not None:
            await self._stock.after_commit(txn)
        return body

    # --- helpers ----------------------------------------------------------------------------------
    async def _register_codes(
        self, s: AsyncSession, tenant_id: UUID, receipt_id: UUID, codes: Sequence[dict[str, Any]]
    ) -> None:
        """SEC-08: a code taken by a concurrent draft after the ``foreign_codes`` pre-check → 422."""
        taken = await self._repo.replace_codes(s, tenant_id, receipt_id, codes)
        if taken:
            raise AppError(
                ErrorCode.MARKING_CODE_INVALID,
                params={"reason": "already_registered", "codes": sorted(taken)[:20]},
            )

    async def _load(self, s: AsyncSession, receipt_id: UUID) -> GoodsReceipt:
        gr = await self._repo.get(s, receipt_id)
        assert gr is not None
        return gr

    async def _locked(self, s: AsyncSession, scope: BranchScope, receipt_id: UUID) -> GoodsReceipt:
        gr = await self._repo.get(s, receipt_id, lock=True)
        if gr is None:
            raise not_found()
        check_read_scope(scope, gr.branch_id)
        return gr

    async def _prepare(
        self, s: AsyncSession, scope: BranchScope, data: ReceiptInput, receipt_id: UUID, tenant_id: UUID
    ) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
        """Validate the draft against the PO, supplier, warehouse and products; header, line and
        marking-code rows."""
        po: PurchaseOrder | None = None
        if data.po_id is not None:
            po = await self._po.assert_open_for_receipt(s, data.po_id)  # 409 PURCHASE_ORDER_CLOSED
            check_read_scope(scope, po.branch_id)  # 403 BRANCH_SCOPE_DENIED (19 §8)
            if po.warehouse_id != data.warehouse_id:
                raise _invalid("warehouse_id", "validation.po_warehouse_mismatch")
            if data.supplier_id is not None and data.supplier_id != po.supplier_id:
                raise _invalid("supplier_id", "validation.supplier_mismatch")
        supplier_id = data.supplier_id or (po.supplier_id if po is not None else None)
        if supplier_id is None:
            raise _invalid("supplier_id", "validation.required")
        await self._directory.require_supplier(s, supplier_id)
        branch_id = await self._warehouse_branch(s, scope, data.warehouse_id)
        products = await self._products(s, data.lines)
        po_price: dict[UUID, Decimal] = {}
        remaining: dict[UUID, Decimal] = {}
        if po is not None:
            for pl in po.lines:
                if pl.price is not None:
                    po_price.setdefault(pl.product_id, pl.price)
            remaining = remaining_by_product(
                ordered_by_product(po.lines), await self._po.received_qty(s, po.id)
            )
            discrepant = discrepant_products([(ln.product_id, qty(ln.qty)) for ln in data.lines], remaining)
        else:
            discrepant = set()
        rows: list[dict[str, Any]] = []
        codes: list[dict[str, Any]] = []
        seen_codes: set[str] = set()
        for index, ln in enumerate(data.lines):
            product = products[ln.product_id]
            cost = ln.cost if ln.cost is not None else po_price.get(ln.product_id)
            if cost is None:
                raise _invalid(f"lines[{index}].cost", "validation.required")
            rate, exemption = _vat(index, ln, product)
            quantity, unit_cost = qty(ln.qty), price(cost)
            vat_amount = ZERO if data.kind == "gratuitous" else line_vat(line_net(quantity, unit_cost), rate)
            if ln.product_id in discrepant and ln.discrepancy_reason is None:
                raise _invalid(f"lines[{index}].discrepancy_reason", "validation.required")
            line_id = uuid7()
            rows.append(
                {"id": line_id, "tenant_id": tenant_id, "receipt_id": receipt_id, "line_no": index + 1,
                 "product_id": ln.product_id, "qty": quantity, "cost": unit_cost, "vat_rate": rate,
                 "vat_exemption_code": exemption, "vat_amount": vat_amount, "expiry_date": ln.expiry_date,
                 "discrepancy_reason": ln.discrepancy_reason}
            )  # fmt: skip
            for code in _codes(index, ln, product, quantity, seen_codes):
                codes.append({"id": uuid7(), "code": code, "product_id": ln.product_id})
        if codes:
            taken = await self._repo.foreign_codes(s, receipt_id, [c["code"] for c in codes])
            if taken:
                raise AppError(
                    ErrorCode.MARKING_CODE_INVALID,
                    params={"reason": "already_registered", "codes": sorted(taken)[:20]},
                )
        poa_number = data.poa_number
        if data.poa_id is not None:
            exists, number = await self._repo.poa_number(s, data.poa_id)
            if not exists:
                raise _invalid("poa_id", "validation.not_found")
            poa_number = poa_number or number
        head = {
            "branch_id": branch_id, "doc_date": data.doc_date, "supplier_id": supplier_id,
            "po_id": data.po_id,
            "warehouse_id": data.warehouse_id, "paid_immediately": data.paid_immediately, "kind": data.kind,
            "source": "purchase_order" if data.po_id is not None else "manual", "ettn_ref": data.ettn_ref,
            "poa_id": data.poa_id, "poa_number": poa_number, "comment": data.comment,
        }  # fmt: skip
        return head, rows, codes

    async def _warehouse_branch(self, s: AsyncSession, scope: BranchScope, warehouse_id: UUID) -> UUID:
        warehouse = await self._po_repo.warehouse(s, warehouse_id)
        if warehouse is None:
            raise _invalid("warehouse_id", "validation.warehouse_not_found")
        if not scope.unrestricted and warehouse.branch_id not in scope.allowed:
            raise AppError(ErrorCode.BRANCH_SCOPE_DENIED)
        if scope.current is not None and warehouse.branch_id != scope.current:
            raise _invalid("warehouse_id", "validation.warehouse_not_in_branch")
        if warehouse.archived:
            raise AppError(ErrorCode.RESOURCE_ARCHIVED, params={"resource": "warehouse"})
        return warehouse.branch_id

    async def _products(self, s: AsyncSession, lines: Sequence[ReceiptLineInput]) -> dict[UUID, ProductRef]:
        products = await self._repo.products(s, [ln.product_id for ln in lines])
        for index, ln in enumerate(lines):
            found = products.get(ln.product_id)
            if found is None:
                raise _invalid(f"lines[{index}].product_id", "validation.product_not_found")
            if found.archived:
                raise AppError(
                    ErrorCode.RESOURCE_ARCHIVED,
                    params={"resource": "product"},
                    details=[
                        ErrorDetail(field=f"lines[{index}].product_id", message_key="validation.archived")
                    ],
                )
        return products


def _require_draft(gr: GoodsReceipt) -> None:
    if gr.status != "draft":
        raise AppError(
            ErrorCode.DOC_NOT_DRAFT, params={"expected_status": "draft", "actual_status": gr.status}
        )


def _check_input(data: ReceiptInput) -> None:
    if not data.lines:
        raise _invalid("lines", "validation.required")
    if len(data.lines) > MAX_LINES:
        raise _invalid("lines", "validation.max_items")
    if data.kind == "gratuitous" and data.paid_immediately:  # 12 CHECK (kind <> 'gratuitous' OR NOT paid)
        raise _invalid("paid_immediately", "validation.gratuitous_not_paid")
    for index, ln in enumerate(data.lines):
        if qty(ln.qty) <= 0:
            raise _invalid(f"lines[{index}].qty", "validation.positive")
        if ln.cost is not None and ln.cost < 0:
            raise _invalid(f"lines[{index}].cost", "validation.min_value")


def _vat(index: int, ln: ReceiptLineInput, product: ProductRef) -> tuple[Decimal, str | None]:
    """The line VAT rate (given, else the product card's) and exemption code (0% lines only)."""
    rate = ln.vat_rate if ln.vat_rate is not None else product.vat_rate
    if rate is None:  # exempt product without a rate on the card
        rate = Decimal("0.00")
    rate = percent(rate)
    if rate not in ALLOWED_VAT_RATES:
        raise _invalid(f"lines[{index}].vat_rate", "validation.vat_rate_invalid")
    exemption = ln.vat_exemption_code
    if exemption is None and rate == 0 and ln.vat_rate is None:
        exemption = product.vat_exemption_code
    if exemption is not None and rate != 0:
        raise _invalid(f"lines[{index}].vat_exemption_code", "validation.exemption_needs_zero_rate")
    return rate, exemption


def _codes(
    index: int, ln: ReceiptLineInput, product: ProductRef, quantity: Decimal, seen: set[str]
) -> list[str]:
    """19 §8: ``is_marked`` lines need exactly ``qty`` codes (GS separators kept as sent)."""
    codes = list(ln.marking_codes or ())
    field = f"lines[{index}].marking_codes"
    if not product.is_marked:
        if codes:
            raise _invalid(field, "validation.marking_not_required")
        return []
    if quantity != quantity.to_integral_value() or Decimal(len(codes)) != quantity:
        raise _invalid(field, "validation.marking_count_mismatch")
    for code in codes:
        if not code.strip():
            raise _invalid(field, "validation.required")
        if code in seen:
            raise _invalid(field, "validation.duplicate")
        seen.add(code)
    return codes


def _audit(head: dict[str, Any], lines: Sequence[dict[str, Any]]) -> dict[str, Any]:
    return {
        "supplier_id": str(head["supplier_id"]),
        "warehouse_id": str(head["warehouse_id"]),
        "po_id": _str(head["po_id"]),
        "doc_date": head["doc_date"].isoformat(),
        "kind": head["kind"],
        "paid_immediately": head["paid_immediately"],
        "lines": [
            {"product_id": str(r["product_id"]), "qty": qty_str(r["qty"]), "cost": price_str(r["cost"]),
             "vat_rate": percent_str(r["vat_rate"]), "discrepancy_reason": r["discrepancy_reason"]}
            for r in lines
        ],
    }  # fmt: skip
