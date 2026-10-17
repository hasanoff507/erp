"""Transfers between own branches — ``TransferPostingService`` (19 §13, 13 §2.9–§2.10, qaror #63).

States ``draft → posted → sent → received | discrepancy``; ``cancelled`` from ``draft``/``posted``
(no registers) or ``sent`` (storno of the send).

* ``post`` — number ``P-…``; ``transport_mode='vehicle'`` needs ``vehicle_plate`` and creates the
  outgoing e-TTN ``ettn_documents(direction='out', transport_type='warehouse_to_warehouse',
  status='pending_signature')``. Bosqich 2 stand-in for E-IMZO (27 B2): with the ``fake`` operator
  the post also queues ``outbox_jobs(kind='ettn_send')`` and the worker registers it; with the real
  operator the e-TTN waits for the Bosqich 5 sign flow (19 §20). ``negative_stock_policy='block'``
  refuses a post the sender cannot cover (stock does not move yet).
* ``send`` — vehicle mode needs the e-TTN ``registered`` (``409 ETTN_REQUIRED``); every line is
  issued from the sender with the cost line ``Dt 2970 / Kt inv_acct(from)`` (13 §2.9, branch = sender,
  ``entry_date = doc_date``); ``lot_allocations``/``unit_cost`` are stored.
* ``receive`` — the receiving branch (scope) fills the live allocations in order
  (:func:`inventory.domain.transfers.receive_pieces`); one destination lot per received piece at the
  sender's cost, the original lot's ``expiry_date`` and ``received_at`` (13 §2.10 "partiya saqlanadi",
  3.2a). Ledger (branch = receiver, ``entry_date = max(doc_date, receive day)``): ``Dt inv_acct(to) /
  Kt 2970`` = received cost, ``Dt 5910 / Kt 2970`` = send cost − received cost.
  A piece still *pending* at the sender (negative stock not settled yet) has no real cost to carry:
  the receive is refused with ``409 TRANSFER_COST_PENDING`` (``params: {line_id, product_id, qty}``)
  until a sender receipt settles it (13 §3.1) — then the receive books the real cost and 2970 closes.
* ``cancel`` — ``sent`` → ``reverse_issue`` + ledger storno; an e-TTN already ``registered`` stays and
  the answer carries ``warnings: ["ETTN_CANCEL_IN_OPERATOR"]``, any other e-TTN becomes ``cancelled``.
  Locks are taken transfer → ``outbox_jobs(ettn_send)`` → e-TTN, the order the outbox worker uses.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, Protocol
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.audit import record_audit
from app.core.auth.principal import Principal
from app.core.db.base import uuid7
from app.core.db.session import tenant_transaction
from app.core.doc_numbers import next_doc_number
from app.core.error_codes import ErrorCode
from app.core.errors import AppError, ErrorDetail
from app.core.idempotency import stage_response
from app.core.money import price, qty
from app.core.permissions import BranchScope
from app.modules.accounting.application.posting import LedgerPoster
from app.modules.accounting.domain.calendar import business_date
from app.modules.accounting.domain.entries import LedgerLine
from app.modules.inventory.application.doc_support import (
    check_doc_date,
    decode_cursor,
    encode_cursor,
    in_scope,
    invalid,
    invalid_state,
    p4,
    q3,
    require_scope,
    scoped_branches,
    ts,
)
from app.modules.inventory.application.ports import JobEnqueuer, StockRepository, Warehouse
from app.modules.inventory.application.stock import CostPosting, StockService, StockTxn
from app.modules.inventory.domain.costing import ZERO_QTY, Allocation
from app.modules.inventory.domain.transfers import (
    SHORTAGE_ACCOUNT,
    TRANSIT_ACCOUNT,
    IssuedPiece,
    TransportMode,
    is_overdue,
    receive_pieces,
    weighted_unit_cost,
)

log = structlog.get_logger(__name__)

DOC_TYPE = "transfers"
MAX_LINES = 1000
ETTN_SEND_KIND = "ettn_send"
CANCEL_IN_OPERATOR = "ETTN_CANCEL_IN_OPERATOR"
ETTN_KEEP_ON_CANCEL = frozenset({"registered", "accepted"})


# --- model -------------------------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class TransferLineInput:
    product_id: UUID
    qty_sent: Decimal


@dataclass(frozen=True, slots=True)
class ReceiveLineInput:
    transfer_line_id: UUID
    qty_received: Decimal


@dataclass(frozen=True, slots=True)
class TransferLine:
    id: UUID
    line_no: int
    product_id: UUID
    product_name: str
    qty_sent: Decimal
    qty_received: Decimal | None
    unit_cost: Decimal | None
    lot_allocations: tuple[dict[str, Any], ...]


@dataclass(frozen=True, slots=True)
class EttnRef:
    id: UUID
    status: str
    operator_doc_id: str | None


@dataclass(frozen=True, slots=True)
class Transfer:
    id: UUID
    branch_id: UUID
    number: str | None
    doc_date: date
    status: str
    from_branch_id: UUID
    to_branch_id: UUID
    from_warehouse_id: UUID
    to_warehouse_id: UUID
    transport_mode: str
    vehicle_plate: str | None
    driver_name: str | None
    ettn_ref: str | None
    sent_at: datetime | None
    sent_by: UUID | None
    received_at: datetime | None
    received_by: UUID | None
    created_by: UUID
    created_at: datetime
    posted_at: datetime | None
    cancelled_at: datetime | None
    cancel_reason: str | None
    comment: str | None
    ettn: EttnRef | None
    lines: tuple[TransferLine, ...] = field(default=())


@dataclass(frozen=True, slots=True)
class TransferFilter:
    status: str | None = None
    ettn_status: str | None = None
    date_from: date | None = None
    date_to: date | None = None


class TransferRepository(Protocol):
    async def insert(
        self, s: AsyncSession, head: Mapping[str, Any], lines: Sequence[Mapping[str, Any]]
    ) -> None: ...
    async def get(self, s: AsyncSession, doc_id: UUID, *, lock: bool = False) -> Transfer | None: ...
    async def page(
        self,
        s: AsyncSession,
        flt: TransferFilter,
        *,
        branch_ids: Sequence[UUID] | None,
        after: tuple[datetime, UUID] | None,
        limit: int,
    ) -> list[Transfer]: ...
    async def mark_posted(self, s: AsyncSession, doc_id: UUID, number: str, posted_at: datetime) -> None: ...
    async def mark_sent(
        self, s: AsyncSession, doc_id: UUID, at: datetime, user_id: UUID, lines: Sequence[Mapping[str, Any]]
    ) -> None: ...
    async def mark_received(
        self,
        s: AsyncSession,
        doc_id: UUID,
        status: str,
        at: datetime,
        user_id: UUID,
        lines: Sequence[Mapping[str, Any]],
    ) -> None: ...
    async def mark_cancelled(self, s: AsyncSession, doc_id: UUID, user_id: UUID, reason: str) -> None: ...
    async def insert_ettn(self, s: AsyncSession, row: Mapping[str, Any]) -> None: ...
    async def lock_outbox(self, s: AsyncSession, idempotency_key: str) -> None: ...
    async def lock_ettn(self, s: AsyncSession, ettn_id: UUID) -> EttnRef | None: ...
    async def set_ettn_status(self, s: AsyncSession, ettn_id: UUID, status: str) -> None: ...
    async def insert_outbox(self, s: AsyncSession, row: Mapping[str, Any]) -> bool: ...
    async def close_outbox(self, s: AsyncSession, idempotency_key: str, note: str) -> None: ...
    async def ettn_payload_refs(
        self, s: AsyncSession, warehouse_ids: Sequence[UUID], product_ids: Sequence[UUID]
    ) -> tuple[dict[UUID, dict[str, Any]], dict[UUID, dict[str, Any]]]: ...
    async def overdue_hours(self, s: AsyncSession) -> int: ...
    async def free_qty(
        self, s: AsyncSession, warehouse_id: UUID, product_ids: Sequence[UUID]
    ) -> dict[UUID, Decimal]: ...


@dataclass(frozen=True, slots=True)
class OutboxConfig:
    """How a posted vehicle transfer's e-TTN leaves (27 B2): ``auto_send`` — the fake operator
    registers at once (no E-IMZO in Bosqich 2); ``job`` — the SAQ job name of the outbox worker."""

    auto_send: bool
    job: str


# --- JSON --------------------------------------------------------------------------------------------
def _allocations_out(raw: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [Allocation.from_json(a).as_json() for a in raw]


def transfer_json(
    doc: Transfer, now: datetime, overdue_hours: int, warnings: Sequence[str] = ()
) -> dict[str, Any]:
    return {
        "id": str(doc.id),
        "number": doc.number,
        "status": doc.status,
        "doc_date": doc.doc_date.isoformat(),
        "branch_id": str(doc.branch_id),
        "from_branch_id": str(doc.from_branch_id),
        "to_branch_id": str(doc.to_branch_id),
        "from_warehouse_id": str(doc.from_warehouse_id),
        "to_warehouse_id": str(doc.to_warehouse_id),
        "transport_mode": doc.transport_mode,
        "vehicle_plate": doc.vehicle_plate,
        "driver_name": doc.driver_name,
        "ettn_ref": doc.ettn_ref,
        "ettn": None
        if doc.ettn is None
        else {"id": str(doc.ettn.id), "status": doc.ettn.status, "operator_doc_id": doc.ettn.operator_doc_id},
        "is_overdue": is_overdue(doc.status, doc.sent_at, now, overdue_hours),
        "comment": doc.comment,
        "created_by": str(doc.created_by),
        "created_at": ts(doc.created_at),
        "posted_at": ts(doc.posted_at),
        "sent_at": ts(doc.sent_at),
        "sent_by": str(doc.sent_by) if doc.sent_by else None,
        "received_at": ts(doc.received_at),
        "received_by": str(doc.received_by) if doc.received_by else None,
        "cancelled_at": ts(doc.cancelled_at),
        "cancel_reason": doc.cancel_reason,
        "lines": [
            {
                "id": str(ln.id),
                "line_no": ln.line_no,
                "product_id": str(ln.product_id),
                "product_name": ln.product_name,
                "qty_sent": q3(ln.qty_sent),
                "qty_received": q3(ln.qty_received),
                "unit_cost": p4(ln.unit_cost),
                "lot_allocations": _allocations_out(ln.lot_allocations),
            }
            for ln in doc.lines
        ],
        "warnings": list(warnings),
    }


# --- service -----------------------------------------------------------------------------------------
class TransferService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        docs: TransferRepository,
        repo: StockRepository,
        stock: StockService,
        poster: LedgerPoster,
        queue: JobEnqueuer | None,
        outbox: OutboxConfig,
    ) -> None:
        self._sf = session_factory
        self._docs = docs
        self._repo = repo
        self._stock = stock
        self._poster = poster
        self._queue = queue
        self._outbox = outbox

    # --- create -----------------------------------------------------------------------------------
    async def create(
        self,
        actor: Principal,
        scope: BranchScope,
        *,
        from_warehouse_id: UUID,
        to_warehouse_id: UUID,
        doc_date: date,
        transport_mode: TransportMode,
        vehicle_plate: str | None,
        driver_name: str | None,
        comment: str | None,
        lines: Sequence[TransferLineInput],
        ip: str | None,
    ) -> dict[str, Any]:
        _check_lines(lines)
        check_doc_date(doc_date)
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            src = await self._warehouse(s, from_warehouse_id, "from_warehouse_id")
            if not in_scope(scope, src.branch_id) or (
                scope.current is not None and scope.current != src.branch_id
            ):
                raise AppError(ErrorCode.BRANCH_SCOPE_DENIED)
            dst = await self._warehouse(s, to_warehouse_id, "to_warehouse_id")
            if dst.branch_id == src.branch_id:
                raise invalid("to_warehouse_id", "validation.transfer_same_branch")
            await self._check_products(s, [ln.product_id for ln in lines])
            doc_id = uuid7()
            await self._docs.insert(
                s,
                {
                    "id": doc_id,
                    "tenant_id": actor.tenant_id,
                    "branch_id": src.branch_id,
                    "doc_date": doc_date,
                    "from_branch_id": src.branch_id,
                    "to_branch_id": dst.branch_id,
                    "from_warehouse_id": src.id,
                    "to_warehouse_id": dst.id,
                    "transport_mode": transport_mode,
                    "vehicle_plate": (vehicle_plate or "").strip() or None,
                    "driver_name": (driver_name or "").strip() or None,
                    "created_by": actor.user_id,
                    "comment": comment,
                },
                [
                    {
                        "id": uuid7(),
                        "tenant_id": actor.tenant_id,
                        "transfer_id": doc_id,
                        "line_no": n,
                        "product_id": ln.product_id,
                        "qty_sent": qty(ln.qty_sent),
                    }
                    for n, ln in enumerate(lines, start=1)
                ],
            )
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="transfer.created",
                entity=DOC_TYPE,
                entity_id=doc_id,
                ip=ip,
                after={"lines": len(lines), "from_warehouse_id": str(src.id), "to_warehouse_id": str(dst.id)},
            )
            body = await self._body(s, doc_id)
            stage_response(body, 201)
        return body

    # --- read -------------------------------------------------------------------------------------
    async def get(self, actor: Principal, scope: BranchScope, doc_id: UUID) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            doc = await self._load(s, doc_id)
            if not (in_scope(scope, doc.from_branch_id) or in_scope(scope, doc.to_branch_id)):
                raise AppError(ErrorCode.BRANCH_SCOPE_DENIED)
            hours = await self._docs.overdue_hours(s)
        return transfer_json(doc, datetime.now(UTC), hours)

    async def page(
        self, actor: Principal, scope: BranchScope, flt: TransferFilter, cursor: str | None, limit: int
    ) -> dict[str, Any]:
        after = decode_cursor(cursor) if cursor else None
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            rows = await self._docs.page(
                s, flt, branch_ids=scoped_branches(scope), after=after, limit=limit + 1
            )
            hours = await self._docs.overdue_hours(s)
        now = datetime.now(UTC)
        page = rows[:limit]
        return {
            "items": [transfer_json(d, now, hours) for d in page],
            "next_cursor": encode_cursor(page[-1].created_at, page[-1].id) if len(rows) > limit else None,
        }

    # --- post (draft → posted) ----------------------------------------------------------------------
    async def post(
        self, actor: Principal, scope: BranchScope, doc_id: UUID, ip: str | None
    ) -> dict[str, Any]:
        job_id: UUID | None = None
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            doc = await self._load(s, doc_id, lock=True)
            require_scope(scope, doc.from_branch_id)
            if doc.status != "draft":
                raise AppError(
                    ErrorCode.DOC_NOT_DRAFT, params={"expected_status": "draft", "actual_status": doc.status}
                )
            check_doc_date(doc.doc_date)
            if doc.transport_mode == "vehicle" and not doc.vehicle_plate:
                raise AppError(
                    ErrorCode.VALIDATION_ERROR,
                    params={"field": "vehicle_plate"},
                    details=[ErrorDetail(field="vehicle_plate", message_key="validation.required")],
                )
            await self._poster.assert_period_open(s, doc.doc_date)
            await self._check_block_policy(s, doc)
            number = await next_doc_number(
                s, tenant_id=actor.tenant_id, branch_id=doc.branch_id, table=DOC_TYPE, year=doc.doc_date.year
            )
            await self._docs.mark_posted(s, doc.id, number, datetime.now(UTC))
            ettn_id: UUID | None = None
            if doc.transport_mode == "vehicle":
                ettn_id = uuid7()
                await self._docs.insert_ettn(
                    s,
                    {
                        "id": ettn_id,
                        "tenant_id": actor.tenant_id,
                        "transfer_id": doc.id,
                        "transport_type": "warehouse_to_warehouse",
                        "direction": "out",
                        "status": "pending_signature",
                        "doc_date": doc.doc_date,
                        "payload": json.dumps(await self._ettn_payload(s, doc, number), ensure_ascii=False),
                    },
                )
                if self._outbox.auto_send:
                    job_id = uuid7()
                    await self._docs.insert_outbox(
                        s,
                        {
                            "id": job_id,
                            "tenant_id": actor.tenant_id,
                            "kind": ETTN_SEND_KIND,
                            "payload": json.dumps({"ettn_id": str(ettn_id), "transfer_id": str(doc.id)}),
                            "idempotency_key": f"{ETTN_SEND_KIND}:{ettn_id}",
                            "created_by": actor.user_id,
                        },
                    )
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="transfer.posted",
                entity=DOC_TYPE,
                entity_id=doc.id,
                ip=ip,
                after={"number": number, "ettn_id": str(ettn_id) if ettn_id else None},
            )
            body = await self._body(s, doc.id)
            stage_response(body, 200)
        if job_id is not None and self._queue is not None:
            try:
                await self._queue.enqueue(
                    self._outbox.job, actor.tenant_id, job_id=str(job_id), key=f"ettn:{job_id}"
                )
            except Exception:  # the cron sweeper picks queued outbox jobs up
                log.warning("ettn_enqueue_failed", job_id=str(job_id), exc_info=True)
        return body

    async def _check_block_policy(self, s: AsyncSession, doc: Transfer) -> None:
        """19 §13 post: ``negative_stock_policy='block'`` and the sender cannot cover a product."""
        if (await self._repo.tenant_stock(s)).negative_stock_policy != "block":
            return
        need: dict[UUID, Decimal] = {}
        for ln in doc.lines:
            need[ln.product_id] = need.get(ln.product_id, ZERO_QTY) + ln.qty_sent
        free = await self._docs.free_qty(s, doc.from_warehouse_id, list(need))
        for product_id, requested in need.items():
            available = free.get(product_id, ZERO_QTY)
            if available < requested:
                raise AppError(
                    ErrorCode.NEGATIVE_STOCK_NOT_ALLOWED,
                    params={
                        "warehouse_id": str(doc.from_warehouse_id),
                        "product_id": str(product_id),
                        "requested": format(qty(requested), "f"),
                        "available": format(qty(max(available, ZERO_QTY)), "f"),
                    },
                )

    async def _ettn_payload(self, s: AsyncSession, doc: Transfer, number: str) -> dict[str, Any]:
        warehouses, products = await self._docs.ettn_payload_refs(
            s, [doc.from_warehouse_id, doc.to_warehouse_id], [ln.product_id for ln in doc.lines]
        )
        return {
            "number": number,
            "doc_date": doc.doc_date.isoformat(),
            "transport_type": "warehouse_to_warehouse",
            "from": warehouses[doc.from_warehouse_id],
            "to": warehouses[doc.to_warehouse_id],
            "vehicle_plate": doc.vehicle_plate,
            "driver_name": doc.driver_name,
            "lines": [
                {
                    "line_no": ln.line_no,
                    "product_id": str(ln.product_id),
                    **products.get(ln.product_id, {}),
                    "qty": q3(ln.qty_sent),
                }
                for ln in doc.lines
            ],
        }

    # --- send (posted → sent) ------------------------------------------------------------------------
    async def send(
        self, actor: Principal, scope: BranchScope, doc_id: UUID, ip: str | None
    ) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            doc = await self._load(s, doc_id, lock=True)
            require_scope(scope, doc.from_branch_id)
            txn = await self.send_in(s, actor.tenant_id, actor.user_id, doc)
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="transfer.sent",
                entity=DOC_TYPE,
                entity_id=doc.id,
                ip=ip,
                after={"lines": len(doc.lines)},
            )
            body = await self._body(s, doc.id)
            stage_response(body, 200)
        await self._stock.after_commit(txn)
        return body

    async def send_in(self, s: AsyncSession, tenant_id: UUID, user_id: UUID, doc: Transfer) -> StockTxn:
        """``posted → sent`` inside the caller's transaction (REST ``send``; Bosqich 3 ``transfer.sent``)."""
        if doc.status != "posted":
            raise invalid_state("posted", doc.status)
        if doc.transport_mode == "vehicle":
            status = doc.ettn.status if doc.ettn is not None else "missing"
            if status != "registered":
                raise AppError(ErrorCode.ETTN_REQUIRED, params={"ettn_status": status})
        await self._poster.assert_period_open(s, doc.doc_date)
        txn = await self._stock.lock(
            s, tenant_id, [(doc.from_warehouse_id, ln.product_id) for ln in doc.lines]
        )
        extra = {"from_branch_id": str(doc.from_branch_id), "to_branch_id": str(doc.to_branch_id)}
        updates: list[dict[str, Any]] = []
        for ln in doc.lines:
            res = await txn.issue(
                doc.from_warehouse_id,
                ln.product_id,
                ln.qty_sent,
                doc_type=DOC_TYPE,
                doc_id=doc.id,
                line_id=ln.id,
                cost=CostPosting(TRANSIT_ACCOUNT, doc.doc_date, doc.from_branch_id, extra),
            )
            updates.append(
                {
                    "id": ln.id,
                    "unit_cost": weighted_unit_cost(res.cost, ln.qty_sent),
                    "lot_allocations": json.dumps(res.allocations_json()),
                }
            )
        await self._docs.mark_sent(s, doc.id, txn.at, user_id, updates)
        return txn

    # --- receive (sent → received | discrepancy) -----------------------------------------------------
    async def receive(
        self,
        actor: Principal,
        scope: BranchScope,
        doc_id: UUID,
        lines: Sequence[ReceiveLineInput],
        ip: str | None,
    ) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            doc = await self._load(s, doc_id, lock=True)
            require_scope(scope, doc.to_branch_id)
            txn, status = await self.receive_in(s, actor.tenant_id, actor.user_id, doc, lines)
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="transfer.received",
                entity=DOC_TYPE,
                entity_id=doc.id,
                ip=ip,
                after={
                    "status": status,
                    "lines": {str(x.transfer_line_id): q3(x.qty_received) for x in lines},
                },
            )
            body = await self._body(s, doc.id)
            stage_response(body, 200)
        await self._stock.after_commit(txn)
        return body

    async def receive_in(
        self,
        s: AsyncSession,
        tenant_id: UUID,
        user_id: UUID,
        doc: Transfer,
        lines: Sequence[ReceiveLineInput],
    ) -> tuple[StockTxn, str]:
        """``sent → received|discrepancy`` inside the caller's transaction (REST; ``transfer.received``)."""
        if doc.status != "sent":
            raise invalid_state("sent", doc.status)
        received = _received_by_line(doc, lines)
        keys = [(doc.from_warehouse_id, ln.product_id) for ln in doc.lines]
        keys += [(doc.to_warehouse_id, ln.product_id) for ln in doc.lines]
        txn = await self._stock.lock(s, tenant_id, keys)
        assert doc.sent_at is not None
        entry_date = max(doc.doc_date, business_date(txn.at))
        inv_to = await txn.inv_acct(doc.to_warehouse_id)
        moves = await self._repo.doc_moves(s, DOC_TYPE, doc.id, live_only=True)
        ledger: list[LedgerLine] = []
        updates: list[dict[str, Any]] = []
        for ln in doc.lines:
            issued = [
                IssuedPiece(m.lot_id, -m.qty, -m.cost_amount, m.lot_id is None)
                for m in moves
                if m.line_id == ln.id and m.qty < 0 and m.warehouse_id == doc.from_warehouse_id
            ]
            got = received[ln.id]
            plan = receive_pieces(issued, got)
            for piece in plan.pieces:
                if piece.piece.pending:
                    raise AppError(
                        ErrorCode.TRANSFER_COST_PENDING,
                        params={
                            "line_id": str(ln.id),
                            "product_id": str(ln.product_id),
                            "qty": q3(piece.qty),
                        },
                    )
            lot_ids: list[str] = []
            for piece in plan.pieces:
                lot = await self._repo.lot(s, piece.piece.lot_id) if piece.piece.lot_id else None
                res = await txn.receive(
                    doc.to_warehouse_id,
                    ln.product_id,
                    piece.qty,
                    piece.amount,
                    source_doc_type=DOC_TYPE,
                    source_doc_id=doc.id,
                    source_line_id=ln.id,
                    expiry_date=lot.expiry_date if lot else None,
                    received_at=lot.received_at if lot else doc.sent_at,
                )
                lot_ids.append(str(res.lot_id))
            analytics = {
                "product_id": str(ln.product_id),
                "line_id": str(ln.id),
                "from_branch_id": str(doc.from_branch_id),
                "to_branch_id": str(doc.to_branch_id),
            }
            ledger.append(
                LedgerLine(
                    entry_date,
                    doc.to_branch_id,
                    inv_to,
                    TRANSIT_ACCOUNT,
                    plan.received_cost,
                    {**analytics, "warehouse_id": str(doc.to_warehouse_id), "lot_ids": sorted(lot_ids)},
                )
            )
            if plan.shortage_cost < 0:
                raise RuntimeError(f"transfer {doc.id} line {ln.id}: received cost above the send cost")
            ledger.append(
                LedgerLine(
                    entry_date,
                    doc.to_branch_id,
                    SHORTAGE_ACCOUNT,
                    TRANSIT_ACCOUNT,
                    plan.shortage_cost,
                    {**analytics, "shortage_qty": q3(ln.qty_sent - got)},
                )
            )
            live = [Allocation(p.lot_id, p.qty, price(p.cost / p.qty), p.pending) for p in issued]
            updates.append(
                {
                    "id": ln.id,
                    "qty_received": got,
                    "unit_cost": weighted_unit_cost(plan.send_cost, sum((p.qty for p in issued), ZERO_QTY)),
                    "lot_allocations": json.dumps([a.as_json() for a in live]),
                }
            )
        await self._poster.post(s, tenant_id, DOC_TYPE, doc.id, ledger)
        status = "received" if all(received[ln.id] == ln.qty_sent for ln in doc.lines) else "discrepancy"
        await self._docs.mark_received(s, doc.id, status, txn.at, user_id, updates)
        return txn, status

    # --- cancel -----------------------------------------------------------------------------------
    async def cancel(
        self, actor: Principal, scope: BranchScope, doc_id: UUID, reason: str, ip: str | None
    ) -> dict[str, Any]:
        txn: StockTxn | None = None
        warnings: list[str] = []
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            doc = await self._load(s, doc_id, lock=True)
            require_scope(scope, doc.from_branch_id)
            if doc.status == "cancelled":
                raise AppError(ErrorCode.DOC_ALREADY_CANCELLED)
            if doc.status not in ("draft", "posted", "sent"):
                raise invalid_state("draft|posted|sent", doc.status)
            if doc.status == "sent":
                txn = await self._stock.lock(
                    s, actor.tenant_id, [(doc.from_warehouse_id, ln.product_id) for ln in doc.lines]
                )
                await txn.reverse_issue(DOC_TYPE, doc.id)
                await self._poster.reverse_document(s, actor.tenant_id, DOC_TYPE, doc.id)
            if doc.ettn is not None:  # lock order transfer → outbox → e-TTN, as the outbox worker (SEC-03)
                await self._docs.lock_outbox(s, f"{ETTN_SEND_KIND}:{doc.ettn.id}")
                ettn = await self._docs.lock_ettn(s, doc.ettn.id)
                if ettn is not None and ettn.status in ETTN_KEEP_ON_CANCEL:
                    warnings.append(CANCEL_IN_OPERATOR)
                elif ettn is not None and ettn.status != "cancelled":
                    await self._docs.set_ettn_status(s, ettn.id, "cancelled")
                    await self._docs.close_outbox(
                        s, f"{ETTN_SEND_KIND}:{ettn.id}", "e-TTN cancelled with the transfer"
                    )
            await self._docs.mark_cancelled(s, doc.id, actor.user_id, reason)
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="transfer.cancelled",
                entity=DOC_TYPE,
                entity_id=doc.id,
                ip=ip,
                before={"status": doc.status},
                after={"reason": reason, "warnings": warnings},
            )
            body = await self._body(s, doc.id, warnings)
            stage_response(body, 200)
        if txn is not None:
            await self._stock.after_commit(txn)
        return body

    # --- helpers ----------------------------------------------------------------------------------
    async def _body(self, s: AsyncSession, doc_id: UUID, warnings: Sequence[str] = ()) -> dict[str, Any]:
        doc = await self._load(s, doc_id)
        return transfer_json(doc, datetime.now(UTC), await self._docs.overdue_hours(s), warnings)

    async def _load(self, s: AsyncSession, doc_id: UUID, *, lock: bool = False) -> Transfer:
        doc = await self._docs.get(s, doc_id, lock=lock)
        if doc is None:
            raise AppError(ErrorCode.NOT_FOUND, params={"resource": "transfer"})
        return doc

    async def load(self, s: AsyncSession, doc_id: UUID, *, lock: bool = False) -> Transfer:
        return await self._load(s, doc_id, lock=lock)

    async def _warehouse(self, s: AsyncSession, warehouse_id: UUID, field_name: str) -> Warehouse:
        wh = await self._repo.warehouse(s, warehouse_id)
        if wh is None:
            raise invalid(field_name, "validation.warehouse_not_found")
        if wh.archived:
            raise AppError(ErrorCode.RESOURCE_ARCHIVED, params={"resource": "warehouse"})
        return wh

    async def _check_products(self, s: AsyncSession, product_ids: Sequence[UUID]) -> None:
        flags = await self._repo.product_ids(s, product_ids)
        for index, pid in enumerate(product_ids):
            if pid not in flags:
                raise invalid(f"lines[{index}].product_id", "validation.product_not_found")
            if flags[pid]:
                raise AppError(
                    ErrorCode.RESOURCE_ARCHIVED,
                    params={"resource": "product"},
                    details=[
                        ErrorDetail(field=f"lines[{index}].product_id", message_key="validation.archived")
                    ],
                )


def _check_lines(lines: Sequence[TransferLineInput]) -> None:
    if not lines:
        raise invalid("lines", "validation.required")
    if len(lines) > MAX_LINES:
        raise invalid("lines", "validation.max_items")
    for index, ln in enumerate(lines):
        if qty(ln.qty_sent) <= 0:
            raise invalid(f"lines[{index}].qty_sent", "validation.positive")


def _received_by_line(doc: Transfer, lines: Sequence[ReceiveLineInput]) -> dict[UUID, Decimal]:
    """Every line of the transfer exactly once; ``0 ≤ qty_received ≤ qty_sent`` (19 §13)."""
    by_id = {ln.id: ln for ln in doc.lines}
    out: dict[UUID, Decimal] = {}
    for index, x in enumerate(lines):
        line = by_id.get(x.transfer_line_id)
        if line is None:
            raise invalid(f"lines[{index}].transfer_line_id", "validation.transfer_line_not_found")
        if x.transfer_line_id in out:
            raise invalid(f"lines[{index}].transfer_line_id", "validation.duplicate_line")
        got = qty(x.qty_received)
        if got < 0:
            raise invalid(f"lines[{index}].qty_received", "validation.non_negative")
        if got > line.qty_sent:
            raise invalid(f"lines[{index}].qty_received", "validation.qty_received_above_sent")
        out[x.transfer_line_id] = got
    missing = [ln for ln in doc.lines if ln.id not in out]
    if missing:
        raise invalid("lines", "validation.transfer_lines_missing")
    return out


__all__ = [
    "DOC_TYPE",
    "EttnRef",
    "OutboxConfig",
    "ReceiveLineInput",
    "Transfer",
    "TransferFilter",
    "TransferLine",
    "TransferLineInput",
    "TransferRepository",
    "TransferService",
    "transfer_json",
]
