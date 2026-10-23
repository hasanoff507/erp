"""Recost jobs (13 §3.3–§3.4, 23 §2.4, 19 §18).

What a job does — for its ``(warehouse, product)``, under the stock lock (23 §2.1):

1. settles any still-pending issue pieces from free stock (normally already done synchronously by
   the receipt that queued the job — see ``StockTxn.settle_pending``);
2. replays, ``ORDER BY moved_at, created_at, id``, every issued document line of that key with
   pending history (``lot_id IS NULL`` moves) and ``moved_at ≥ from_date``: when the line's stock
   cost (``−Σ stock_moves.cost_amount``) differs from its cost ledger lines (contract:
   ``inventory.domain.analytics``), the live cost lines are reversed and a new line with the same
   accounts/analytics + ``recost_job_id`` is written for the settled cost. ``doc_type/doc_id`` stay
   the original issue document; ``entry_date`` = the original date when its period is open, else the
   first open date with ``analytics.correction_of_period = "YYYY-MM"`` (13 §3.4).

Statuses ``queued → running → done | failed``. The trigger in Bosqich 2 is a receipt-type posting
into a (warehouse, product) with pending issues; :meth:`StockService.queue_recost` is public for the
Bosqich 3 late-sync triggers. ``rejected_period_closed`` is never set automatically: a closed period
is handled by a correction in the open period (13 §3.4); the status exists for the retry rule.
"""

from __future__ import annotations

import base64
import json
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.audit import record_audit
from app.core.auth.principal import Principal
from app.core.db.session import tenant_transaction
from app.core.error_codes import ErrorCode
from app.core.errors import AppError, ErrorDetail
from app.core.idempotency import stage_response
from app.core.money import money
from app.core.permissions import BranchScope
from app.modules.accounting.application.ports import StoredEntry
from app.modules.accounting.application.posting import LedgerPoster
from app.modules.accounting.domain.calendar import day_start, period_label
from app.modules.accounting.domain.entries import LedgerLine
from app.modules.inventory.application.ports import Key, RecostJob, RecostRepository, StockRepository
from app.modules.inventory.application.stock import StockService, StockTxn
from app.modules.inventory.domain.analytics import cost_line_key
from app.modules.inventory.domain.costing import ZERO_MONEY

log = structlog.get_logger(__name__)


def _invalid(field: str, key: str) -> AppError:
    return AppError(ErrorCode.VALIDATION_ERROR, details=[ErrorDetail(field=field, message_key=key)])


def _ts(value: datetime | None) -> str | None:
    return None if value is None else value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def job_json(job: RecostJob) -> dict[str, Any]:
    return {
        "id": str(job.id),
        "warehouse_id": str(job.warehouse_id),
        "product_id": str(job.product_id),
        "from_date": job.from_date.isoformat(),
        "status": job.status,
        "reason_doc_type": job.reason_doc_type,
        "reason_doc_id": str(job.reason_doc_id),
        "attempts": job.attempts,
        "last_error": job.last_error,
        "created_at": _ts(job.created_at),
        "finished_at": _ts(job.finished_at),
    }


def _cursor(job: RecostJob) -> str:
    raw = json.dumps([job.created_at.isoformat(), str(job.id)]).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


_CURSOR_MIN = datetime(2000, 1, 1, tzinfo=UTC)
_CURSOR_MAX = datetime(2100, 1, 1, tzinfo=UTC)


def _decode(cursor: str) -> tuple[datetime, UUID]:
    """A page cursor: a tz-aware instant within 2000-01-01..2100-01-01 UTC and a job id, else 422."""
    try:
        at, jid = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
        when = datetime.fromisoformat(at)
        if when.tzinfo is None or not _CURSOR_MIN <= when <= _CURSOR_MAX:
            raise ValueError("cursor instant out of range")
        return when, UUID(jid)
    except (ValueError, TypeError, OverflowError) as exc:
        raise _invalid("cursor", "validation.cursor_invalid") from exc


def _net(entries: list[StoredEntry]) -> Decimal:
    """Net cost booked by a line's cost entries: originals minus their stornos."""
    return money(sum((-e.amount if e.reversal_of_id else e.amount for e in entries), ZERO_MONEY))


def _live(entries: list[StoredEntry]) -> list[StoredEntry]:
    reversed_ids = {e.reversal_of_id for e in entries if e.reversal_of_id}
    return [e for e in entries if e.reversal_of_id is None and e.id not in reversed_ids]


class RecostService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        jobs: RecostRepository,
        repo: StockRepository,
        stock: StockService,
        poster: LedgerPoster,
    ) -> None:
        self._sf = session_factory
        self._jobs = jobs
        self._repo = repo
        self._stock = stock
        self._poster = poster

    # --- worker -----------------------------------------------------------------------------------
    async def run(self, tenant_id: UUID, job_id: UUID) -> dict[str, Any]:
        """Claim and process one job in ONE transaction (23 §2.4).

        Lock order = the posters' (``upsert_queued`` under the stock lock): the stock lock of the
        job's key first, then the job row (``FOR UPDATE SKIP LOCKED`` — a job another worker holds,
        or no longer ``queued``, is skipped). ``running`` is only visible inside that transaction: a
        dead worker rolls back, the job stays ``queued`` and the sweeper re-runs it. A failure is
        recorded in a new transaction (``failed``, ``attempts + 1``).
        """
        async with self._sf() as s, tenant_transaction(s, tenant_id):
            peek = await self._jobs.get(s, job_id)  # no lock: only the key is needed
        if peek is None or peek.status != "queued":
            return {"skipped": True}
        key: Key = (peek.warehouse_id, peek.product_id)
        try:
            async with self._sf() as s, tenant_transaction(s, tenant_id):
                txn = await self._stock.lock(s, tenant_id, [key])
                job = await self._jobs.claim(s, job_id)  # queued → running, attempts + 1 (SKIP LOCKED)
                if job is None:
                    return {"skipped": True}
                corrected = await self.process(s, tenant_id, job, txn=txn)
                await self._jobs.finish(s, job.id, "done", None)
        except Exception as exc:
            log.exception("recost_failed", job_id=str(job_id))
            async with self._sf() as s, tenant_transaction(s, tenant_id):
                await self._jobs.fail(s, job_id, f"{type(exc).__name__}: {exc}"[:1000])
            return {"status": "failed"}
        return {"status": "done", "corrected_lines": corrected}

    async def process(
        self, s: AsyncSession, tenant_id: UUID, job: RecostJob, *, txn: StockTxn | None = None
    ) -> int:
        """Reconcile the cost ledger of ``job``'s key with its stock moves (caller's transaction;
        ``txn`` — the caller's stock lock of the key, else it is taken here)."""
        key: Key = (job.warehouse_id, job.product_id)
        if txn is None:
            txn = await self._stock.lock(s, tenant_id, [key])
        await txn.settle_pending(key, job.reason_doc_type, job.reason_doc_id)
        lines = await self._repo.pending_history_lines(s, key, day_start(job.from_date))
        corrected = 0
        for doc_type, doc_id, line_id in lines:
            if line_id is None:
                continue
            if await self._reconcile_line(s, tenant_id, txn, job, key, doc_type, doc_id, line_id):
                corrected += 1
        return corrected

    async def _reconcile_line(
        self,
        s: AsyncSession,
        tenant_id: UUID,
        txn: StockTxn,
        job: RecostJob,
        key: Key,
        doc_type: str,
        doc_id: UUID,
        line_id: UUID,
    ) -> bool:
        stock_cost = await self._repo.line_cost(s, key, doc_type, doc_id, line_id)
        match = cost_line_key(product_id=key[1], warehouse_id=key[0], line_id=line_id)
        entries = await self._poster.doc_entries(s, doc_type, doc_id, analytics=match)
        if _net(entries) == stock_cost:
            return False
        live = _live(entries)
        template = await self._template(s, live, doc_type, doc_id, line_id, key)
        if template is None:
            log.warning("recost_no_cost_line", doc_type=doc_type, doc_id=str(doc_id), line_id=str(line_id))
            return False
        original_date = live[0].entry_date if live else template.entry_date
        closed = await self._poster.is_closed(s, original_date)
        on = await self._poster.first_open_date(s) if closed else original_date
        extra: dict[str, Any] = {"recost_job_id": str(job.id)}
        if closed:
            extra["correction_of_period"] = period_label(original_date)
        if live:
            await self._poster.reverse_entries(s, tenant_id, live, on=on, extra_analytics=extra)
        if stock_cost > 0:
            allocations = await txn.live_allocations(doc_type, doc_id, line_id)
            analytics = {
                k: v
                for k, v in template.analytics.items()
                if k not in ("recost_job_id", "correction_of_period")
            }
            analytics["lot_ids"] = sorted({str(a.lot_id) for a in allocations if a.lot_id})
            await self._poster.post(
                s,
                tenant_id,
                doc_type,
                doc_id,
                [LedgerLine(on, template.branch_id, template.account_dt, template.account_kt, stock_cost,
                            {**analytics, **extra})],
            )  # fmt: skip
        return True

    async def _template(
        self, s: AsyncSession, live: list[StoredEntry], doc_type: str, doc_id: UUID, line_id: UUID, key: Key
    ) -> LedgerLine | None:
        """Accounts/analytics of the line's cost entry — the live one, else the ``cost_unknown`` record."""
        if live:
            e = live[0]
            assert e.branch_id is not None
            return LedgerLine(e.entry_date, e.branch_id, e.account_dt, e.account_kt, e.amount, e.analytics)
        raw = await self._repo.cost_unknown_template(s, doc_type, doc_id, line_id, key[1])
        if raw is None:
            return None
        analytics = cost_line_key(product_id=key[1], warehouse_id=key[0], line_id=line_id)
        analytics.update(raw.get("analytics") or {})
        return LedgerLine(
            date.fromisoformat(raw["entry_date"]),
            UUID(raw["branch_id"]),
            raw["account_dt"],
            raw["account_kt"],
            ZERO_MONEY,
            analytics,
        )

    async def sweep(self, tenant_id: UUID, *, limit: int = 100) -> int:
        """Re-enqueue queued jobs (lost enqueues, crashed workers) — the cron backstop."""
        async with self._sf() as s, tenant_transaction(s, tenant_id):
            ids = await self._jobs.queued_ids(s, limit)
        await self._stock.enqueue_recost(tenant_id, ids)
        return len(ids)

    # --- API --------------------------------------------------------------------------------------
    async def page(
        self,
        actor: Principal,
        scope: BranchScope,
        *,
        status: str | None,
        warehouse_id: UUID | None,
        product_id: UUID | None,
        cursor: str | None,
        limit: int,
    ) -> dict[str, Any]:
        after = _decode(cursor) if cursor else None
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            warehouses = await self._scoped_warehouses(s, scope, warehouse_id)
            rows = await self._jobs.page(
                s,
                status=status,
                warehouse_ids=warehouses,
                product_id=product_id,
                after=after,
                limit=limit + 1,
            )
        page = rows[:limit]
        return {
            "items": [job_json(j) for j in page],
            "next_cursor": _cursor(page[-1]) if len(rows) > limit else None,
        }

    async def get(self, actor: Principal, scope: BranchScope, job_id: UUID) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            job = await self._job(s, scope, job_id)
            ledger, moves = await self._jobs.corrections(s, job.id)
        return {**job_json(job), "ledger_entries": ledger, "stock_moves": moves}

    async def retry(
        self, actor: Principal, scope: BranchScope, job_id: UUID, ip: str | None
    ) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            # lock order = the posters' / the worker's: stock lock of the key, then the job rows
            peek = await self._job(s, scope, job_id)
            await self._stock.lock(s, actor.tenant_id, [(peek.warehouse_id, peek.product_id)])
            job = await self._job(s, scope, job_id, lock=True)
            if job.status == "rejected_period_closed":
                raise AppError(ErrorCode.RECOST_REJECTED_PERIOD_CLOSED, params={"job_id": str(job.id)})
            if job.status != "failed":
                raise AppError(
                    ErrorCode.DOC_INVALID_STATE,
                    params={"expected_status": "failed", "actual_status": job.status},
                )
            from_date = job.from_date
            other = await self._jobs.queued_for(s, (job.warehouse_id, job.product_id))
            if other is not None:  # one queued job per key: this one absorbs the other
                from_date = min(from_date, other.from_date)
                await self._jobs.finish(s, other.id, "done", f"merged into recost job {job.id}")
            await self._jobs.requeue(s, job.id, from_date)
            await record_audit(
                s, tenant_id=actor.tenant_id, user_id=actor.user_id, action="recost_job.retried",
                entity="recost_jobs", entity_id=job.id,
                before={"status": job.status, "last_error": job.last_error},
                after={"status": "queued", "from_date": from_date.isoformat()}, ip=ip,
            )  # fmt: skip
            fresh = await self._jobs.get(s, job.id)
            assert fresh is not None
            body = job_json(fresh)
            stage_response(body, 200)
        await self._stock.enqueue_recost(actor.tenant_id, [job.id])
        return body

    async def _job(
        self, s: AsyncSession, scope: BranchScope, job_id: UUID, *, lock: bool = False
    ) -> RecostJob:
        job = await self._jobs.get(s, job_id, lock=lock)
        if job is None:
            raise AppError(ErrorCode.NOT_FOUND, params={"resource": "recost_job"})
        if not scope.unrestricted:
            wh = await self._repo.warehouse(s, job.warehouse_id)
            if wh is None or wh.branch_id not in scope.allowed:
                raise AppError(ErrorCode.NOT_FOUND, params={"resource": "recost_job"})
        return job

    async def _scoped_warehouses(
        self, s: AsyncSession, scope: BranchScope, warehouse_id: UUID | None
    ) -> list[UUID] | None:
        if warehouse_id is not None:
            wh = await self._repo.warehouse(s, warehouse_id)
            if wh is None:
                raise AppError(ErrorCode.NOT_FOUND, params={"resource": "warehouse"})
            if not scope.unrestricted and wh.branch_id not in scope.allowed:
                raise AppError(ErrorCode.BRANCH_SCOPE_DENIED)
            return [warehouse_id]
        if scope.unrestricted:
            return None
        return await self._repo.warehouse_ids(s, scope.allowed)
