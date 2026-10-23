"""M10 read side: ``GET /reports/vat-summary`` and ``GET /vat-moves`` (20 #1–#2, 13 §4.1–§4.3, §2.26).

Summary of a period (``YYYY-MM``):

* ``regime`` — ``tenant_tax_regimes`` row in force on the last day of the period (no row → ``vat``);
* ``regime=vat``: ``output_vat`` / ``input_vat`` = Σ ``vat_moves.vat_amount`` by kind in the period,
  ``net_vat = output − input`` (13 §4.2). VAT is a tenant figure (1 tenant = 1 STIR, qaror #31) —
  ``branch_id`` does not narrow it. ``pending_credit_red_invoices`` — incoming e-invoices of the period
  with ``risk_flag IN ('red','unknown')`` and VAT whose credit is not (fully) opened yet (13 §2.8 — the
  pending part = invoice VAT − Σ its input ``vat_moves``); ``pending_credit_pct`` = that pending VAT ÷
  (input VAT + pending VAT) × 100; ``pending_credit_invoices[]`` — the invoices themselves, shown
  separately with ``credit_status`` ``pending``/``partial`` (US-M10-03, QT-M10-04, BO-07);
* ``regime=turnover``: per branch ``base = (9020 − 9040 − 9050) + 9390 + 8530`` of the period's ledger
  (13 §4.3); the tobacco share (9020/9040/9050 lines of ``turnover_tax_group='tobacco'`` products) at the
  ``tobacco`` rate, the rest at the branch rate (``branches.wiring.turnover_rate_on``; YaTT — the whole base
  at ``sole_proprietor``); ``turnover_rate_pct`` — the branch rate when one branch is summed without a
  tobacco share, else the effective rate ``amount ÷ base × 100``;
* transition month (both regimes in force, 13 §4.3): ``regime`` is still the last day's, but the other
  regime's figures are filled too — the turnover figure counts only the turnover days (ACC-06);
* ``tax_settlement_id`` — the period's ``posted`` ``tax_settlements`` (``vat_offset`` / ``turnover_tax``).
"""

from __future__ import annotations

import base64
import calendar
import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
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


RegimeRange = tuple[date, date, str]  # (from, to inclusive, 'vat' | 'turnover')


@dataclass(frozen=True, slots=True)
class PendingCreditInvoice:
    """Incoming red/``unknown`` e-invoice whose VAT credit is not (fully) opened yet (13 §2.8, US-M10-03)."""

    einvoice_id: UUID
    number: str | None
    doc_date: date | None
    counterparty_id: UUID
    counterparty_name: str
    risk_flag: str
    total_amount: Decimal
    vat_amount: Decimal
    credited_vat: Decimal

    @property
    def pending_vat(self) -> Decimal:
        return self.vat_amount - self.credited_vat


class VatRepository(Protocol):
    async def regime_on(self, s: AsyncSession, on: date) -> str: ...

    async def regime_ranges(self, s: AsyncSession, start: date, end: date) -> list[RegimeRange]: ...

    async def legal_form(self, s: AsyncSession) -> str: ...

    async def vat_totals(self, s: AsyncSession, period: date) -> tuple[Decimal, Decimal]: ...

    async def pending_credit_invoices(
        self, s: AsyncSession, start: date, end: date
    ) -> list[PendingCreditInvoice]: ...

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


def split_regimes(changes: Sequence[tuple[date, str]], start: date, end: date) -> list[RegimeRange]:
    """Sub-ranges of ``[start, end]`` per tax regime (13 §4.3, ACC-06). ``changes`` = the
    ``tenant_tax_regimes`` rows ``(valid_from, regime)`` with ``valid_from ≤ end``; before the first row
    the tenant is a VAT payer. Adjacent days of one regime are merged."""
    current = "vat"
    starts: list[tuple[date, str]] = []
    for valid_from, regime in sorted(changes):
        norm = "turnover" if regime == "turnover" else "vat"
        if valid_from <= start:
            current = norm
        elif valid_from <= end:
            starts.append((valid_from, norm))
    out: list[RegimeRange] = []
    begin = start
    for valid_from, regime in starts:
        if regime != current:
            out.append((begin, valid_from - timedelta(days=1), current))
            begin, current = valid_from, regime
    out.append((begin, end, current))
    return out


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


@dataclass(frozen=True, slots=True)
class TurnoverFigure:
    """13 §4.3 turnover tax of a period for the given branches (``None`` = every branch)."""

    base: Decimal
    amount: Decimal
    rate_pct: Decimal | None


async def turnover_figure(
    repo: VatRepository,
    branch_rate: BranchRateReader,
    s: AsyncSession,
    tenant_id: UUID,
    period: date,
    branches: tuple[UUID, ...] | None,
    branch_id: UUID | None,
) -> TurnoverFigure:
    """One source of truth for ``/reports/vat-summary`` and ``tax_settlements(turnover_tax)`` (20 #1, #8b):
    per branch ``(base − tobacco) × branch rate + tobacco × tobacco rate`` (YaTT — the whole base at the
    branch's ``sole_proprietor`` rate); ``rate_pct`` — the branch rate for one branch without a tobacco share,
    else the effective rate ``amount ÷ base × 100``. Only the days the turnover regime was in force count
    (13 §4.3 transition month: turnover up to the VAT ``valid_from``, ACC-06); rates are taken on the last
    day of each turnover sub-range."""
    end = _month_end(period)
    legal_form = await repo.legal_form(s)
    ranges = [(a, b) for a, b, regime in await repo.regime_ranges(s, period, end) if regime == "turnover"]
    items: list[tuple[BranchBase, Decimal, Decimal]] = []  # (base, branch rate, tobacco part)
    total_base = ZERO
    total_amount = ZERO
    for start, stop in ranges:
        tobacco_rate = await repo.tobacco_rate(s, stop)
        for b in await repo.turnover_bases(s, start, stop, branches):
            rate = (await branch_rate(s, tenant_id, b.branch_id, stop)).rate_pct or ZERO
            tobacco = ZERO if legal_form == "sole_proprietor" else b.tobacco_base
            t_rate = tobacco_rate if tobacco_rate is not None else rate
            amount = ((b.base - tobacco) * rate / 100 + tobacco * t_rate / 100).quantize(CENT, ROUND_HALF_UP)
            total_base += b.base
            total_amount += amount
            items.append((b, rate, tobacco))
    single_rate: Decimal | None = None
    if len(items) == 1 and items[0][2] == 0:
        single_rate = items[0][1]
    if single_rate is None and not items and branch_id is not None:
        single_rate = (await branch_rate(s, tenant_id, branch_id, end)).rate_pct
    if single_rate is not None:
        rate_pct: Decimal | None = single_rate
    elif total_base > 0:
        rate_pct = total_amount * 100 / total_base
    else:
        rate_pct = None
    return TurnoverFigure(total_base, total_amount, rate_pct)


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
            in_force = {r for _, _, r in await self._repo.regime_ranges(s, period, end)}
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
                "pending_credit_invoices": None,
                "turnover_base": None,
                "turnover_rate_pct": None,
                "turnover_amount": None,
                "tax_settlement_id": None,
            }
            # a transition month (13 §4.3, ACC-06) shows both figures; the tenant-wide VAT one only to an
            # unrestricted user
            if regime == "vat" or ("vat" in in_force and not restricted):
                output, input_ = await self._repo.vat_totals(s, period)
                invoices = await self._repo.pending_credit_invoices(s, period, end)
                count = len(invoices)
                pending = sum((i.pending_vat for i in invoices), ZERO)
                denominator = input_ + pending
                pct = ZERO if denominator <= 0 else (pending * 100 / denominator)
                body.update(
                    output_vat=_m2(output),
                    input_vat=_m2(input_),
                    net_vat=_m2(output - input_),
                    pending_credit_red_invoices=count,
                    pending_credit_pct=_m2(pct),
                    pending_credit_invoices=[
                        {
                            "einvoice_id": str(i.einvoice_id),
                            "number": i.number,
                            "doc_date": None if i.doc_date is None else i.doc_date.isoformat(),
                            "counterparty_id": str(i.counterparty_id),
                            "counterparty_name": i.counterparty_name,
                            "risk_flag": i.risk_flag,
                            "total_amount": _m2(i.total_amount),
                            "vat_amount": _m2(i.vat_amount),
                            "credited_vat": _m2(i.credited_vat),
                            "pending_vat": _m2(i.pending_vat),
                            "credit_status": "partial" if i.credited_vat > 0 else "pending",
                        }
                        for i in invoices
                    ],
                )
            if regime == "vat":
                settlement = await self._repo.settlement_id(s, period, "vat_offset", None)
            else:
                settlement = await self._repo.settlement_id(s, period, "turnover_tax", branch_id)
            if regime == "turnover" or "turnover" in in_force:  # transition month: both figures (ACC-06)
                figure = await turnover_figure(
                    self._repo, self._branch_rate, s, actor.tenant_id, period, branches, branch_id
                )
                body.update(
                    turnover_base=_m2(figure.base),
                    turnover_amount=_m2(figure.amount),
                    turnover_rate_pct=None if figure.rate_pct is None else _m2(figure.rate_pct),
                )
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
