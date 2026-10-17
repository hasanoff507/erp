"""Offline inventory events of ``/sync/push`` (19 §13–§14, 16 §2/§7; QT-M06-04, QT-M05-05).

Handlers run inside the per-event ``tenant_transaction`` opened by the sync module (contract —
:mod:`app.modules.sync.application.handlers`) and post through the B2 inventory services:

* ``transfer.sent`` — a new document (``id`` … ``lines``, own branch → another own branch) is created
  with the device's ``client_event_id``/``temp_number`` and posted (number ``P-…``); ``on_foot_or_public``
  is sent at once (``stock_moves`` of the sender, ``Dt 2970 / Kt inv``); ``vehicle`` stays ``posted`` with
  the e-TTN pending and ``warnings: ["ETTN_REQUIRED"]`` (qaror #63 — no e-TTN offline). ``{transfer_id}``
  sends an existing ``posted`` transfer (vehicle: only with a ``registered`` e-TTN — ``409 ETTN_REQUIRED``).
* ``transfer.received`` — receives a ``sent`` transfer at the device's branch; a transfer the server does
  not know yet → ``DEPENDENCY_NOT_SYNCED`` (``params.entity='transfers'``, retryable).
* ``stock_count.line_recorded`` — absolute count of one product on the count's single device
  (``stock_counts.device_id``, claimed by the first event; another device → ``409 DOC_INVALID_STATE``,
  ``reason='count_device_mismatch'``); the latest ``recorded_at`` wins; ``counted_at`` = ``recorded_at``
  shifted by the 16 §8 clamp; an unknown barcode is accepted with ``warnings: ["BARCODE_NOT_IN_CATALOG"]``.
  ``submit-for-review``/``post`` stay online (QT-M05-05).
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any, Protocol
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit
from app.core.db.base import uuid7
from app.core.doc_numbers import next_doc_number
from app.core.error_codes import ErrorCode
from app.core.errors import AppError, ErrorDetail
from app.core.money import qty
from app.modules.accounting.application.posting import LedgerPoster
from app.modules.accounting.domain.calendar import business_date
from app.modules.inventory.application.doc_support import invalid, invalid_state, p4, q3
from app.modules.inventory.application.ports import JobEnqueuer, StockRepository
from app.modules.inventory.application.stock import StockService, StockTxn
from app.modules.inventory.application.stock_counts import CountLineInput, CountRepository, StockCountService
from app.modules.inventory.application.transfers import (
    DOC_TYPE as TRANSFERS,
)
from app.modules.inventory.application.transfers import (
    ETTN_SEND_KIND,
    OutboxConfig,
    ReceiveLineInput,
    Transfer,
    TransferRepository,
    TransferService,
)
from app.modules.inventory.domain.stock_counts import EVENT_LINE_RECORDED, parse_line_recorded
from app.modules.inventory.domain.transfers import (
    EVENT_TRANSFER_RECEIVED,
    EVENT_TRANSFER_SENT,
    EventPayloadError,
    TransferSentEvent,
    parse_transfer_received,
    parse_transfer_sent,
)
from app.modules.sync.application.handlers import (
    EventContext,
    HandlerResult,
    SyncEventHandler,
    SyncExceptionRow,
)

log = structlog.get_logger(__name__)

COUNTS = "stock_counts"
ETTN_REQUIRED = "ETTN_REQUIRED"
BARCODE_NOT_IN_CATALOG = "BARCODE_NOT_IN_CATALOG"
MAX_LINES = 1000


class InventorySyncRepository(Protocol):
    """Offline-only columns of the inventory documents (``client_event_id``, ``device_id``, "
    "``temp_number``)."""

    async def tag_transfer(
        self,
        s: AsyncSession,
        transfer_id: UUID,
        client_event_id: UUID,
        device_id: UUID,
        temp_number: str | None,
    ) -> None: ...
    async def claim_count(self, s: AsyncSession, count_id: UUID, device_id: UUID) -> UUID | None: ...
    async def temp_number_taken(self, s: AsyncSession, device_id: UUID, temp_number: str) -> bool: ...


@dataclass(frozen=True, slots=True)
class InventorySyncDeps:
    transfers: TransferService
    transfer_docs: TransferRepository
    counts: StockCountService
    count_docs: CountRepository
    stock_repo: StockRepository
    stock: StockService
    poster: LedgerPoster
    sync_repo: InventorySyncRepository
    queue: JobEnqueuer | None
    outbox: OutboxConfig


def _payload_error(exc: EventPayloadError) -> AppError:
    return AppError(
        ErrorCode.VALIDATION_ERROR,
        details=[ErrorDetail(field=f"payload.{exc.field}", message_key=exc.message_key)],
    )


def _ensure_branch(ctx: EventContext, branch_id: UUID) -> None:
    """The device works for its own branch (16 §9; 19 §13 "o'z filiali")."""
    if branch_id != ctx.branch_id:
        raise AppError(ErrorCode.BRANCH_SCOPE_DENIED, params={"branch_id": str(branch_id)})


def _transfer_server(doc: Transfer) -> dict[str, Any]:
    return {"id": str(doc.id), "number": doc.number, "status": doc.status}


class InventorySyncHandlers:
    def __init__(self, deps: InventorySyncDeps) -> None:
        self._d = deps

    def handlers(self) -> dict[str, SyncEventHandler]:
        return {
            EVENT_TRANSFER_SENT: self.transfer_sent,
            EVENT_TRANSFER_RECEIVED: self.transfer_received,
            EVENT_LINE_RECORDED: self.line_recorded,
        }

    # --- transfer.sent ----------------------------------------------------------------------------
    async def transfer_sent(
        self, s: AsyncSession, ctx: EventContext, payload: Mapping[str, Any]
    ) -> HandlerResult:
        try:
            event = parse_transfer_sent(payload)
        except EventPayloadError as exc:
            raise _payload_error(exc) from exc
        warnings: list[str] = []
        job_id: UUID | None = None
        if event.transfer_id is None:
            doc_id = await self._create(s, ctx, event)
            doc = await self._d.transfers.load(s, doc_id, lock=True)
        else:
            found = await self._d.transfer_docs.get(s, event.transfer_id, lock=True)
            if found is None:
                raise AppError(ErrorCode.NOT_FOUND, params={"resource": "transfer"})
            doc = found
            _ensure_branch(ctx, doc.from_branch_id)
            if doc.status not in ("draft", "posted"):
                raise invalid_state("draft|posted", doc.status)
        late = await self._late(s, doc.doc_date)
        if doc.status == "draft":
            job_id = await self._post(s, ctx, doc, late=late is not None)
            doc = await self._d.transfers.load(s, doc.id, lock=True)
        txn: StockTxn | None = None
        if doc.transport_mode == "vehicle" and (doc.ettn is None or doc.ettn.status != "registered"):
            if event.transfer_id is not None:  # an explicit send of a posted transfer needs the e-TTN
                raise AppError(
                    ErrorCode.ETTN_REQUIRED,
                    params={"ettn_status": doc.ettn.status if doc.ettn else "missing"},
                )
            warnings.append(ETTN_REQUIRED)  # 19 §13: sent online once the e-TTN is registered
        else:
            txn = await self._d.transfers.send_in(
                s, ctx.tenant_id, ctx.actor_user_id, doc, entry_date=late, moved_at=ctx.created_at
            )
        doc = await self._d.transfers.load(s, doc.id)
        await record_audit(
            s,
            tenant_id=ctx.tenant_id,
            user_id=ctx.actor_user_id,
            action="transfer.sent",
            entity=TRANSFERS,
            entity_id=doc.id,
            device_id=ctx.device_id,
            after={
                "status": doc.status,
                "client_event_id": str(ctx.client_event_id),
                "offline": True,
                "warnings": warnings,
            },
        )
        exceptions: tuple[SyncExceptionRow, ...] = ()
        if late is not None:  # 16 §3.4, qaror #69: registers in the first open period, Buxgalter reviews
            exceptions = (
                SyncExceptionRow(
                    "late_in_closed_period",
                    {
                        "period": doc.doc_date.strftime("%Y-%m"),
                        "doc_date": doc.doc_date.isoformat(),
                        "entry_date": late.isoformat(),
                    },
                    TRANSFERS,
                    doc.id,
                ),
            )
        return HandlerResult(
            server=_transfer_server(doc),
            warnings=tuple(warnings),
            sync_exceptions=exceptions,
            after_commit=self._after(ctx.tenant_id, txn, job_id),
        )

    async def _late(self, s: AsyncSession, doc_date: date) -> date | None:
        """The first open day when ``doc_date`` lies in a closed period (POS events are never refused)."""
        if not await self._d.poster.is_closed(s, doc_date):
            return None
        return await self._d.poster.first_open_date(s, doc_date)

    async def _create(self, s: AsyncSession, ctx: EventContext, event: TransferSentEvent) -> UUID:
        assert event.id is not None
        assert event.doc_date is not None
        assert event.from_warehouse_id is not None
        assert event.to_warehouse_id is not None
        if len(event.lines) > MAX_LINES:
            raise invalid("payload.lines", "validation.max_items")
        # ACC-03 (13 §5.1, 16 §8): the business date is the event's own (effective) time, not the push time;
        # the payload ``doc_date`` is informational
        doc_date = business_date(ctx.created_at)
        src = await self._d.stock_repo.warehouse(s, event.from_warehouse_id)
        dst = await self._d.stock_repo.warehouse(s, event.to_warehouse_id)
        if src is None:
            raise invalid("payload.from_warehouse_id", "validation.warehouse_not_found")
        if dst is None:
            raise invalid("payload.to_warehouse_id", "validation.warehouse_not_found")
        _ensure_branch(ctx, src.branch_id)
        if dst.branch_id == src.branch_id:
            raise invalid("payload.to_warehouse_id", "validation.transfer_same_branch")
        products = [ln.product_id for ln in event.lines]
        flags = await self._d.stock_repo.product_ids(s, products)
        for index, pid in enumerate(products):
            if pid not in flags:
                raise invalid(f"payload.lines[{index}].product_id", "validation.product_not_found")
        line_ids = [ln.line_id for ln in event.lines]
        if len(set(line_ids)) != len(line_ids):
            raise invalid("payload.lines", "validation.duplicate_line")
        if event.temp_number and await self._d.sync_repo.temp_number_taken(
            s, ctx.device_id, event.temp_number
        ):
            raise invalid("payload.temp_number", "validation.duplicate")
        if event.transport_mode == "vehicle" and not event.vehicle_plate:
            raise invalid("payload.vehicle_plate", "validation.required")
        await self._d.transfer_docs.insert(
            s,
            {
                "id": event.id,
                "tenant_id": ctx.tenant_id,
                "branch_id": src.branch_id,
                "doc_date": doc_date,
                "from_branch_id": src.branch_id,
                "to_branch_id": dst.branch_id,
                "from_warehouse_id": src.id,
                "to_warehouse_id": dst.id,
                "transport_mode": event.transport_mode,
                "vehicle_plate": event.vehicle_plate,
                "driver_name": None,
                "created_by": ctx.actor_user_id,
                "comment": None,
            },
            [
                {
                    "id": ln.line_id,
                    "tenant_id": ctx.tenant_id,
                    "transfer_id": event.id,
                    "line_no": n,
                    "product_id": ln.product_id,
                    "qty_sent": qty(ln.qty_sent),
                }
                for n, ln in enumerate(event.lines, start=1)
            ],
        )
        await self._d.sync_repo.tag_transfer(
            s, event.id, ctx.client_event_id, ctx.device_id, event.temp_number
        )
        return event.id

    async def _post(self, s: AsyncSession, ctx: EventContext, doc: Transfer, *, late: bool) -> UUID | None:
        """``draft → posted`` in this transaction (19 §13 ``post``): number; vehicle → outgoing e-TTN."""
        if not late:
            await self._d.poster.assert_period_open(s, doc.doc_date)
        number = await next_doc_number(
            s, tenant_id=ctx.tenant_id, branch_id=doc.branch_id, table=TRANSFERS, year=doc.doc_date.year
        )
        await self._d.transfer_docs.mark_posted(s, doc.id, number, datetime.now(UTC))
        if doc.transport_mode != "vehicle":
            return None
        ettn_id = uuid7()
        warehouses, products = await self._d.transfer_docs.ettn_payload_refs(
            s, [doc.from_warehouse_id, doc.to_warehouse_id], [ln.product_id for ln in doc.lines]
        )
        body = {
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
        await self._d.transfer_docs.insert_ettn(
            s,
            {
                "id": ettn_id,
                "tenant_id": ctx.tenant_id,
                "transfer_id": doc.id,
                "transport_type": "warehouse_to_warehouse",
                "direction": "out",
                "status": "pending_signature",
                "doc_date": doc.doc_date,
                "payload": json.dumps(body, ensure_ascii=False),
            },
        )
        if not self._d.outbox.auto_send:
            return None
        job_id = uuid7()
        await self._d.transfer_docs.insert_outbox(
            s,
            {
                "id": job_id,
                "tenant_id": ctx.tenant_id,
                "kind": ETTN_SEND_KIND,
                "payload": json.dumps({"ettn_id": str(ettn_id), "transfer_id": str(doc.id)}),
                "idempotency_key": f"{ETTN_SEND_KIND}:{ettn_id}",
                "created_by": ctx.actor_user_id,
            },
        )
        return job_id

    def _after(
        self, tenant_id: UUID, txn: StockTxn | None, job_id: UUID | None
    ) -> tuple[Callable[[], Awaitable[None]], ...]:
        out: list[Callable[[], Awaitable[None]]] = []
        if txn is not None:

            async def recost() -> None:
                await self._d.stock.after_commit(txn)

            out.append(recost)
        if job_id is not None and self._d.queue is not None:
            queue = self._d.queue

            async def ettn() -> None:  # the e-TTN outbox sweeper picks it up if this fails
                await queue.enqueue(self._d.outbox.job, tenant_id, job_id=str(job_id), key=f"ettn:{job_id}")

            out.append(ettn)
        return tuple(out)

    # --- transfer.received ------------------------------------------------------------------------
    async def transfer_received(
        self, s: AsyncSession, ctx: EventContext, payload: Mapping[str, Any]
    ) -> HandlerResult:
        try:
            event = parse_transfer_received(payload)
        except EventPayloadError as exc:
            raise _payload_error(exc) from exc
        doc = await self._d.transfer_docs.get(s, event.transfer_id, lock=True)
        if doc is None:  # 19 §13: the sending device has not synced yet
            raise AppError(ErrorCode.DEPENDENCY_NOT_SYNCED, params={"entity": "transfers"})
        _ensure_branch(ctx, doc.to_branch_id)
        lines = [ReceiveLineInput(ln.transfer_line_id, ln.qty_received) for ln in event.lines]
        # ACC-03: dated by the event (16 §8); a closed month → first open day + correction (16 §3.4)
        day = max(doc.doc_date, business_date(ctx.created_at))
        late = await self._late(s, day)
        txn, status = await self._d.transfers.receive_in(
            s, ctx.tenant_id, ctx.actor_user_id, doc, lines,
            moved_at=ctx.created_at, entry_date=late or day,
            correction_of_period=day.strftime("%Y-%m") if late is not None else None,
        )  # fmt: skip
        doc = await self._d.transfers.load(s, doc.id)
        await record_audit(
            s,
            tenant_id=ctx.tenant_id,
            user_id=ctx.actor_user_id,
            action="transfer.received",
            entity=TRANSFERS,
            entity_id=doc.id,
            device_id=ctx.device_id,
            after={
                "status": status,
                "client_event_id": str(ctx.client_event_id),
                "offline": True,
                "lines": {str(x.transfer_line_id): q3(x.qty_received) for x in lines},
            },
        )
        server = {
            **_transfer_server(doc),
            "lines": [
                {
                    "id": str(ln.id),
                    "qty_received": q3(ln.qty_received),
                    "unit_cost": p4(ln.unit_cost),
                    "lot_allocations": list(ln.lot_allocations),
                }
                for ln in doc.lines
            ],
        }
        exceptions: tuple[SyncExceptionRow, ...] = ()
        if late is not None:
            exceptions = (
                SyncExceptionRow(
                    "late_in_closed_period",
                    {"period": day.strftime("%Y-%m"), "doc_date": doc.doc_date.isoformat(),
                     "entry_date": late.isoformat()},
                    TRANSFERS,
                    doc.id,
                ),
            )  # fmt: skip
        return HandlerResult(
            server=server, sync_exceptions=exceptions, after_commit=self._after(ctx.tenant_id, txn, None)
        )

    # --- stock_count.line_recorded ----------------------------------------------------------------
    async def line_recorded(
        self, s: AsyncSession, ctx: EventContext, payload: Mapping[str, Any]
    ) -> HandlerResult:
        try:
            event = parse_line_recorded(payload)
        except EventPayloadError as exc:
            raise _payload_error(exc) from exc
        doc = await self._d.count_docs.get(s, event.count_id, lock=True)
        if doc is None:
            raise AppError(ErrorCode.NOT_FOUND, params={"resource": "stock_count"})
        _ensure_branch(ctx, doc.branch_id)
        if doc.status != "counting":
            raise invalid_state("counting", doc.status)
        owner = await self._d.sync_repo.claim_count(s, doc.id, ctx.device_id)
        if owner is not None and owner != ctx.device_id:
            raise AppError(ErrorCode.DOC_INVALID_STATE, params={"reason": "count_device_mismatch"})
        product_id = event.product_id
        if event.barcode is not None:
            known = await self._d.stock_repo.products_by_barcode(s, [event.barcode])
            if event.barcode not in known:
                if product_id is None:  # 19 §14: accepted, not an error
                    server = {"count_id": str(doc.id), "product_id": None, "applied": False}
                    return HandlerResult(server=server, warnings=(BARCODE_NOT_IN_CATALOG,))
            elif product_id is None:
                product_id = known[event.barcode]
        assert product_id is not None
        # the device clock, corrected by the same shift the 16 §8 clamp applied to the event
        shift = ctx.created_at - ctx.client_created_at if ctx.client_created_at is not None else None
        counted_at = event.recorded_at + shift if shift is not None else event.recorded_at
        current = next((ln for ln in doc.lines if ln.product_id == product_id), None)
        applied = current is None or current.counted_at is None or current.counted_at <= counted_at
        if applied:  # 19 §14: the latest recorded_at wins (idempotent upsert)
            await self._d.counts.record_lines_in(
                s, ctx.tenant_id, doc, [CountLineInput(product_id, None, event.counted)], counted_at
            )
            await record_audit(
                s,
                tenant_id=ctx.tenant_id,
                user_id=ctx.actor_user_id,
                action="stock_count.line_recorded",
                entity=COUNTS,
                entity_id=doc.id,
                device_id=ctx.device_id,
                after={
                    "product_id": str(product_id),
                    "counted": q3(event.counted),
                    "counted_at": counted_at.isoformat(),
                    "client_event_id": str(ctx.client_event_id),
                },
            )
        server = {
            "count_id": str(doc.id),
            "product_id": str(product_id),
            "counted": q3(event.counted),
            "counted_at": counted_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
            "applied": applied,
        }
        return HandlerResult(server=server)


__all__ = ["InventorySyncDeps", "InventorySyncHandlers", "InventorySyncRepository"]
