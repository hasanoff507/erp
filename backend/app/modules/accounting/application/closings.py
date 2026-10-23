"""Month closing — ``/period-closings`` (20 #14–#16, 13 §5.1, §5.5, §3.4; qaror #23, #69; US-M11-02).

``POST`` re-checks readiness inside the closing transaction while holding the tenant's period-close lock
exclusively (every posting holds it shared — :class:`LedgerPoster`), so no document can land in the month
between the check and the ``period_closings`` row. Audit ``period_closing.posted``.

Readiness of a month (``YYYY-MM``; ``end`` = its last day, ``bound`` = 00:00 Tashkent of ``end + 1``):

* blockers — ``recost_pending`` (``recost_jobs`` queued/running/failed with ``from_date ≤ end``),
  ``fiscal_pending`` (b5-fiscal ``fiscal_readiness``), ``devices_unsynced`` (active web/android devices whose
  last
  push reported pending outbox events older than ``bound``);
* warnings — ``tax_settlement_missing`` / ``tax_settlement_stale`` (vat module, B5-T16),
  ``opening_0000_nonzero``
  (13 §5.5 — never blocks), ``open_shifts`` (opened before ``bound``), ``drafts_in_period`` (posting documents
  still ``draft``/``counting``/``review`` dated in the month), ``devices_not_synced_after_period_end`` (active
  device without a push after ``bound``), ``ledger_stock_mismatch`` (ACC-09: GL 2910/2920 ≠ Σ
  ``stock_balances.value`` of the warehouses booked to that account).
"""

from __future__ import annotations

import asyncio
import base64
import json
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.audit import record_audit
from app.core.auth.principal import Principal
from app.core.db.session import tenant_transaction
from app.core.error_codes import ErrorCode
from app.core.errors import AppError, ErrorDetail
from app.core.idempotency import stage_response
from app.modules.accounting.application.ports import (
    ClosingRepository,
    ClosingRow,
    FiscalReadinessReader,
    TaxReadinessReader,
)
from app.modules.accounting.domain.calendar import business_today, day_start, period_label
from app.modules.accounting.domain.closing import (
    Readiness,
    StaleSettlement,
    StockMismatch,
    UnsyncedDevice,
    close_verdict,
    parse_period,
    period_end,
)

ENTITY = "period_closings"
LOCK_ATTEMPTS = 100  # × 0.1 s: wait for running postings of the tenant to finish
LOCK_PAUSE_S = 0.1


def _invalid(field: str, key: str, **params: Any) -> AppError:
    return AppError(
        ErrorCode.VALIDATION_ERROR,
        params=params or None,
        details=[ErrorDetail(field=field, message_key=key)],
    )


def _ts(value: datetime | None) -> str | None:
    return None if value is None else value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def period_of(raw: str, field: str = "period") -> date:
    period = parse_period(raw)
    if period is None:
        raise _invalid(field, "validation.period_format")
    return period


def closing_json(row: ClosingRow) -> dict[str, Any]:
    return {
        "period": period_label(row.period),
        "closed_at": _ts(row.closed_at),
        "closed_by": str(row.closed_by),
    }


def readiness_json(r: Readiness) -> dict[str, Any]:
    return {
        "period": r.label,
        "ready": r.ready,
        "blockers": r.blockers,
        "warnings": r.warnings,
        "pending_recost_jobs": r.pending_recost_jobs,
        "pending_fiscal_receipts": r.pending_fiscal_receipts,
        "unsynced_devices": [
            {
                "device_id": d.device_id,
                "cash_register_name": d.cash_register_name,
                "outbox_pending_count": d.outbox_pending_count,
                "outbox_oldest_pending_at": d.outbox_oldest_pending_at,
            }
            for d in r.unsynced_devices
        ],
        "opening_balance_unresolved": r.opening_0000_balance != 0,
        "opening_0000_balance": format(r.opening_0000_balance, ".2f"),
        "stale_tax_settlements": [
            {
                "id": x.id,
                "tax_kind": x.tax_kind,
                "branch_id": x.branch_id,
                "amount": format(x.amount, ".2f"),
                "current_amount": format(x.current_amount, ".2f"),
            }
            for x in r.stale_tax_settlements
        ],
        "ledger_stock_mismatches": [
            {
                "account": m.account,
                "ledger_balance": format(m.ledger_balance, ".2f"),
                "stock_value": format(m.stock_value, ".2f"),
                "difference": format(m.difference, ".2f"),
            }
            for m in r.ledger_stock_mismatches
        ],
    }


def _encode(period: date) -> str:
    return base64.urlsafe_b64encode(json.dumps(period.isoformat()).encode()).decode().rstrip("=")


def _decode(cursor: str) -> date:
    try:
        return date.fromisoformat(json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))))
    except (ValueError, TypeError) as exc:
        raise _invalid("cursor", "validation.cursor_invalid") from exc


class PeriodClosingService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        repo: ClosingRepository,
        fiscal: FiscalReadinessReader,
        tax: TaxReadinessReader,
    ) -> None:
        self._sf = session_factory
        self._repo = repo
        self._fiscal = fiscal
        self._tax = tax

    async def collect(self, s: AsyncSession, tenant_id: UUID, period: date) -> Readiness:
        """Every readiness figure of ``period`` (caller's transaction)."""
        end = period_end(period)
        bound = day_start(end + timedelta(days=1))
        r = Readiness(period)
        r.pending_recost_jobs = await self._repo.pending_recost(s, end)
        r.pending_fiscal_receipts = await self._fiscal(s, tenant_id, period)
        r.unsynced_devices = [
            UnsyncedDevice(
                str(d.device_id),
                d.cash_register_name,
                d.outbox_pending_count,
                _ts(d.outbox_oldest_pending_at),
            )
            for d in await self._repo.unsynced_devices(s, bound)
        ]
        tax = await self._tax(s, tenant_id, period)
        r.tax_settlement_missing = tax.missing
        r.stale_tax_settlements = [
            StaleSettlement(str(i), kind, None if b is None else str(b), amount, current)
            for i, kind, b, amount, current in tax.stale
        ]
        r.opening_0000_balance = await self._repo.opening_0000_balance(s)
        r.open_shifts = await self._repo.open_shifts(s, bound)
        r.drafts_in_period = await self._repo.drafts_in_period(s, period, end)
        r.devices_not_synced = await self._repo.devices_not_synced(s, bound)
        r.ledger_stock_mismatches = [
            StockMismatch(a, ledger, stock)
            for a, ledger, stock in await self._repo.ledger_stock_mismatches(s)
        ]
        return r

    # --- 20 #16 ---------------------------------------------------------------------------------------------
    async def readiness(self, actor: Principal, raw_period: str) -> dict[str, Any]:
        period = period_of(raw_period)
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            r = await self.collect(s, actor.tenant_id, period)
        return readiness_json(r)

    # --- 20 #14 ---------------------------------------------------------------------------------------------
    async def page(self, actor: Principal, cursor: str | None, limit: int) -> dict[str, Any]:
        after = _decode(cursor) if cursor else None
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            rows = await self._repo.page(s, after, limit + 1)
        page = rows[:limit]
        return {
            "items": [closing_json(r) for r in page],
            "next_cursor": _encode(page[-1].period) if len(rows) > limit else None,
        }

    # --- 20 #15 ---------------------------------------------------------------------------------------------
    async def close(
        self, actor: Principal, raw_period: str, ip: str | None, *, today: date | None = None
    ) -> dict[str, Any]:
        period = period_of(raw_period)
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            await self._lock(s)
            verdict = close_verdict(
                period,
                today=today or business_today(),
                last_closed=await self._repo.last_closed(s),
                first_activity=await self._repo.first_activity(s),
            )
            if verdict.code == "PERIOD_ALREADY_CLOSED":
                raise AppError(ErrorCode.PERIOD_ALREADY_CLOSED, params={"period": period_label(period)})
            if verdict.code == "PERIOD_CLOSE_OUT_OF_ORDER":
                assert verdict.expected is not None
                raise AppError(
                    ErrorCode.PERIOD_CLOSE_OUT_OF_ORDER,
                    params={
                        "period": period_label(period),
                        "expected_period": period_label(verdict.expected),
                    },
                )
            if verdict.code is not None:
                raise _invalid("period", verdict.code)
            r = await self.collect(s, actor.tenant_id, period)
            if not r.ready:
                raise AppError(
                    ErrorCode.PERIOD_CLOSE_NOT_READY,
                    params={"period": r.label, "blockers": r.blockers},
                )
            row = await self._repo.insert(s, actor.tenant_id, period, actor.user_id)
            body = closing_json(row)
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="period_closing.posted",
                entity=ENTITY,
                entity_id=None,
                ip=ip,
                after={"period": body["period"], "warnings": r.warnings},
            )
            stage_response(body, 201)
        return body

    async def _lock(self, s: AsyncSession) -> None:
        """Exclusive tenant period-close lock — never queued, so a waiting close never blocks new postings
        (no lock-queue deadlock with postings that already hold row locks)."""
        for _ in range(LOCK_ATTEMPTS):
            if await self._repo.lock_exclusive(s):
                return
            await asyncio.sleep(LOCK_PAUSE_S)
        raise AppError(ErrorCode.PERIOD_CLOSE_NOT_READY, params={"blockers": ["postings_in_progress"]})
