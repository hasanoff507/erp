"""M10 read side: ``GET /reports/vat-summary`` and ``GET /vat-moves`` (20 #1–#2, 13 §4.1–§4.3, §2.26).

Summary of a period (``YYYY-MM``):

* ``regime`` — ``tenant_tax_regimes`` row in force on the last day of the period (no row → ``vat``);
* ``regime=vat``: ``output_vat`` / ``input_vat`` = Σ ``vat_moves.vat_amount`` by kind in the period,
  ``net_vat = output − input`` (13 §4.2). VAT is a tenant figure (1 tenant = 1 STIR, qaror #31) —
  ``branch_id`` does not narrow it. ``pending_credit_red_invoices`` — incoming e-invoices of the period
  with ``risk_flag IN ('red','unknown')`` and VAT whose credit is not opened yet (no ``vat_moves`` row,
  13 §2.8); ``pending_credit_pct`` = that pending VAT ÷ (input VAT + pending VAT) × 100;
* ``regime=turnover``: per branch ``base = (9020 − 9040 − 9050) + 9390 + 8530`` of the period's ledger
  (13 §4.3); the tobacco share (9020/9040/9050 lines of ``turnover_tax_group='tobacco'`` products) at the
  ``tobacco`` rate, the rest at the branch rate (``branches.wiring.turnover_rate_on``; YaTT — the whole base
  at ``sole_proprietor``); ``turnover_rate_pct`` — the branch rate when one branch is summed without a
  tobacco share, else the effective rate ``amount ÷ base × 100``;
* ``tax_settlement_id`` — the period's ``posted`` ``tax_settlements`` (``vat_offset`` / ``turnover_tax``).
"""

from __future__ import annotations

import base64
import calendar
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.auth.principal import Principal
from app.core.db.session import tenant_transaction
from app.core.error_codes import ErrorCode
from app.core.errors import AppError, ErrorDetail
from app.core.permissions import BranchScope

ZERO = Decimal("0.00")
CENT = Decimal("0.01")


@dataclass(frozen=True, slots=True)
class BranchBase:
    branch_id: UUID
    base: Decimal
    tobacco_base: Decimal


@dataclass(frozen=True, slots=True)
class VatMoveRow:
    id: UUID
    kind: str
    period: date
    base_amount: Decimal
    vat_amount: Decimal
    doc_type: str
    doc_id: UUID
    einvoice_id: UUID | None
    created_at: datetime


class VatRepository(Protocol):
    async def regime_on(self, s: AsyncSession, on: date) -> str: ...

    async def legal_form(self, s: AsyncSession) -> str: ...

    async def vat_totals(self, s: AsyncSession, period: date) -> tuple[Decimal, Decimal]: ...

    async def pending_credit(self, s: AsyncSession, start: date, end: date) -> tuple[int, Decimal]: ...

    async def turnover_bases(
        self, s: AsyncSession, start: date, end: date, branch_ids: tuple[UUID, ...] | None
    ) -> list[BranchBase]: ...

    async def tobacco_rate(self, s: AsyncSession, on: date) -> Decimal | None: ...

    async def settlement_id(
        self, s: AsyncSession, period: date, kind: str, branch_id: UUID | None
    ) -> UUID | None: ...

    async def list_moves(
        self,
        s: AsyncSession,
        *,
        kind: str | None,
        period: date | None,
        doc_type: str | None,
        einvoice_id: UUID | None,
        cursor: tuple[datetime, UUID] | None,
        limit: int,
    ) -> list[VatMoveRow]: ...


class BranchRateReader(Protocol):
    async def __call__(self, session: AsyncSession, tenant_id: UUID, branch_id: UUID, on: date) -> Any: ...


def _m2(value: Decimal) -> str:
    return format(value.quantize(CENT, rounding=ROUND_HALF_UP), "f")


def parse_period(raw: str) -> date:
    try:
        year, month = raw.split("-")
        if len(year) != 4 or len(month) != 2:
            raise ValueError(raw)
        return date(int(year), int(month), 1)
    except ValueError:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            details=[ErrorDetail(field="period", message_key="validation.period_format")],
        ) from None


def _month_end(first: date) -> date:
    return first.replace(day=calendar.monthrange(first.year, first.month)[1])


def _encode(at: datetime, row_id: UUID) -> str:
    return base64.urlsafe_b64encode(json.dumps([at.isoformat(), str(row_id)]).encode()).decode().rstrip("=")


def _decode(cursor: str | None) -> tuple[datetime, UUID] | None:
    if not cursor:
        return None
    try:
        at, row_id = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
        return datetime.fromisoformat(at), UUID(row_id)
    except (ValueError, TypeError):
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            details=[ErrorDetail(field="cursor", message_key="validation.cursor_invalid")],
        ) from None


class VatService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        repo: VatRepository,
        branch_rate: BranchRateReader,
    ) -> None:
        self._sf = session_factory
        self._repo = repo
        self._branch_rate = branch_rate

    async def summary(
        self, actor: Principal, period_raw: str, branch_id: UUID | None, scope: BranchScope | None = None
    ) -> dict[str, Any]:
        """Branch scope (SEC-11): a restricted user may only name one of their branches; without
        ``branch_id`` the turnover sums only their branches; the tenant-wide VAT figure needs an unrestricted
        scope (``PERMISSION_DENIED``)."""
        period = parse_period(period_raw)
        end = _month_end(period)
        restricted = scope is not None and not scope.unrestricted
        if restricted and branch_id is not None and scope is not None and branch_id not in scope.allowed:
            raise AppError(ErrorCode.PERMISSION_DENIED, params={"reason": "branch_scope"})
        branches: tuple[UUID, ...] | None = None
        if branch_id is not None:
            branches = (branch_id,)
        elif restricted and scope is not None:
            branches = scope.allowed
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            regime = await self._repo.regime_on(s, end)
            if regime == "vat" and restricted:
                raise AppError(ErrorCode.PERMISSION_DENIED, params={"reason": "tenant_wide_vat"})
            body: dict[str, Any] = {
                "period": f"{period.year:04d}-{period.month:02d}",
                "regime": regime,
                "output_vat": None,
                "input_vat": None,
                "net_vat": None,
                "pending_credit_red_invoices": None,
                "pending_credit_pct": None,
                "turnover_base": None,
                "turnover_rate_pct": None,
                "turnover_amount": None,
                "tax_settlement_id": None,
            }
            if regime == "vat":
                output, input_ = await self._repo.vat_totals(s, period)
                count, pending = await self._repo.pending_credit(s, period, end)
                denominator = input_ + pending
                pct = ZERO if denominator <= 0 else (pending * 100 / denominator)
                body.update(
                    output_vat=_m2(output),
                    input_vat=_m2(input_),
                    net_vat=_m2(output - input_),
                    pending_credit_red_invoices=count,
                    pending_credit_pct=_m2(pct),
                )
                settlement = await self._repo.settlement_id(s, period, "vat_offset", None)
            else:
                legal_form = await self._repo.legal_form(s)
                bases = await self._repo.turnover_bases(s, period, end, branches)
                tobacco_rate = await self._repo.tobacco_rate(s, end)
                total_base = ZERO
                total_amount = ZERO
                single_rate: Decimal | None = None
                for b in bases:
                    rate = (await self._branch_rate(s, actor.tenant_id, b.branch_id, end)).rate_pct or ZERO
                    tobacco = ZERO if legal_form == "sole_proprietor" else b.tobacco_base
                    t_rate = tobacco_rate if tobacco_rate is not None else rate
                    amount = ((b.base - tobacco) * rate / 100 + tobacco * t_rate / 100).quantize(
                        CENT, ROUND_HALF_UP
                    )
                    total_base += b.base
                    total_amount += amount
                    single_rate = rate if len(bases) == 1 and tobacco == 0 else None
                if single_rate is None and not bases and branch_id is not None:
                    single_rate = (await self._branch_rate(s, actor.tenant_id, branch_id, end)).rate_pct
                if single_rate is not None:
                    rate_pct: Decimal | None = single_rate
                elif total_base > 0:
                    rate_pct = total_amount * 100 / total_base
                else:
                    rate_pct = None
                body.update(
                    turnover_base=_m2(total_base),
                    turnover_amount=_m2(total_amount),
                    turnover_rate_pct=None if rate_pct is None else _m2(rate_pct),
                )
                settlement = await self._repo.settlement_id(s, period, "turnover_tax", branch_id)
            body["tax_settlement_id"] = None if settlement is None else str(settlement)
        return body

    async def moves(
        self,
        actor: Principal,
        *,
        kind: str | None,
        period_raw: str | None,
        doc_type: str | None,
        einvoice_id: UUID | None,
        cursor: str | None,
        limit: int,
    ) -> dict[str, Any]:
        period = None if period_raw is None else parse_period(period_raw)
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            rows = await self._repo.list_moves(
                s,
                kind=kind,
                period=period,
                doc_type=doc_type,
                einvoice_id=einvoice_id,
                cursor=_decode(cursor),
                limit=limit + 1,
            )
        more = len(rows) > limit
        rows = rows[:limit]
        return {
            "items": [
                {
                    "id": str(r.id),
                    "kind": r.kind,
                    "period": f"{r.period.year:04d}-{r.period.month:02d}",
                    "base_amount": _m2(r.base_amount),
                    "vat_amount": _m2(r.vat_amount),
                    "doc_type": r.doc_type,
                    "doc_id": str(r.doc_id),
                    "einvoice_id": None if r.einvoice_id is None else str(r.einvoice_id),
                    "created_at": r.created_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
                }
                for r in rows
            ],
            "next_cursor": _encode(rows[-1].created_at, rows[-1].id) if more and rows else None,
        }
