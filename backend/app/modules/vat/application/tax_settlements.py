"""Tax settlement documents ``tax_settlements`` (code ``ST``; 20 #8a–#8d; 13 §2.26, §4.3; US-M10-01,
US-M10-04; QT-M10-07). Back-office only, standard three-step document (17 §9: ``draft → post → cancel``).

The server computes the amounts — never taken from the body:

* ``vat_offset`` (VAT payer, tenant-wide — 1 tenant = 1 STIR, qaror #31; ``branch_id`` = the default
  branch): ``base_amount`` / ``amount`` = Σ ``vat_moves(kind='input')`` ``base_amount`` / ``vat_amount`` of
  the period —
  the creditable input VAT (a red/``unknown`` invoice's deferred VAT has no ``vat_moves`` yet and is left on
  4410, 13 §2.8); posting ``Dt 6410 / Kt 4410 = amount``;
* ``turnover_tax`` (turnover regime, per branch — SK 468-modda 2-qism): the same figure as
  ``/reports/vat-summary`` (:func:`turnover_figure`); posting ``Dt {expense_account} / Kt 6410 = amount``,
  ``expense_account`` = ``tenants.settings.turnover_tax_account`` (``9430`` default / ``9820``).

A kind is accepted when its regime was in force on any day of the period; in a transition month both are, and
the turnover figure counts only the turnover days (13 §4.3, ACC-06).

One active (``draft``/``posted``) ``vat_offset`` per (tenant, period) and one ``turnover_tax`` per (branch,
period) — the partial unique indexes of 12; a duplicate → ``422 VALIDATION_ERROR`` with
``params.existing_id``.
``post`` recomputes and posts the fresh figures (``recalculated: true`` when they changed). ``cancel``:
draft → ``cancelled``; posted → storno in the first open period (13 §5.2). The tax payment itself is an
``expenses`` document (``tax_payment``, ``Dt 6410 / Kt 5110``, M15) — not this module.
"""

from __future__ import annotations

import calendar
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, Final, Protocol
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
from app.core.money import money, money_str, percent, percent_str
from app.core.permissions import BranchScope
from app.modules.accounting.application.ports import TaxReadiness
from app.modules.accounting.application.posting import LedgerPoster
from app.modules.accounting.domain.calendar import business_today, period_label
from app.modules.accounting.domain.entries import LedgerLine
from app.modules.vat.application.vat import BranchRateReader, VatRepository, parse_period, turnover_figure

DOC_TYPE: Final = "tax_settlements"
ZERO: Final = Decimal("0.00")
OUTPUT_VAT: Final = "6410"
INPUT_VAT: Final = "4410"


@dataclass(frozen=True, slots=True)
class SettlementRow:
    id: UUID
    number: str | None
    branch_id: UUID
    doc_date: date
    status: str
    tax_kind: str
    period: date
    base_amount: Decimal
    rate: Decimal | None
    amount: Decimal
    expense_account: str | None
    comment: str | None
    created_by: UUID
    created_at: datetime
    posted_at: datetime | None
    cancelled_at: datetime | None
    cancel_reason: str | None


@dataclass(frozen=True, slots=True)
class SettlementFilter:
    branch_ids: tuple[UUID, ...] | None
    tax_kind: str | None = None
    period: date | None = None
    status: str | None = None


@dataclass(frozen=True, slots=True)
class Figures:
    base_amount: Decimal
    rate: Decimal | None
    amount: Decimal


class TaxSettlementRepository(Protocol):
    async def vat_input(self, s: AsyncSession, period: date) -> tuple[Decimal, Decimal]: ...  # (base, vat)
    async def default_branch(self, s: AsyncSession) -> UUID: ...
    async def branch_exists(self, s: AsyncSession, branch_id: UUID) -> bool: ...
    async def turnover_account(self, s: AsyncSession) -> str: ...
    async def insert(self, s: AsyncSession, row: Mapping[str, Any]) -> bool: ...  # False → active duplicate
    async def active_id(
        self, s: AsyncSession, tax_kind: str, period: date, branch_id: UUID
    ) -> UUID | None: ...
    async def get(
        self, s: AsyncSession, settlement_id: UUID, *, lock: bool = False
    ) -> SettlementRow | None: ...
    async def list_page(
        self, s: AsyncSession, flt: SettlementFilter, after: UUID | None, limit: int
    ) -> list[SettlementRow]: ...
    async def update(self, s: AsyncSession, settlement_id: UUID, values: Mapping[str, Any]) -> None: ...


@dataclass(frozen=True, slots=True)
class SettlementInput:
    tax_kind: str
    period: str
    branch_id: UUID | None = None
    doc_date: date | None = None
    comment: str | None = None


def _invalid(field: str, key: str, **params: Any) -> AppError:
    return AppError(
        ErrorCode.VALIDATION_ERROR, params=params or None, details=[ErrorDetail(field=field, message_key=key)]
    )


def _ts(value: datetime | None) -> str | None:
    return None if value is None else value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def month_end(first: date) -> date:
    return first.replace(day=calendar.monthrange(first.year, first.month)[1])


def not_found() -> AppError:
    return AppError(ErrorCode.NOT_FOUND, params={"resource": "tax_settlement"})


def settlement_json(row: SettlementRow) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "number": row.number,
        "branch_id": str(row.branch_id),
        "doc_date": row.doc_date.isoformat(),
        "status": row.status,
        "tax_kind": row.tax_kind,
        "period": period_label(row.period),
        "base_amount": money_str(row.base_amount),
        "rate": None if row.rate is None else percent_str(row.rate),
        "amount": money_str(row.amount),
        "expense_account": row.expense_account,
        "comment": row.comment,
        "created_by": str(row.created_by),
        "created_at": _ts(row.created_at),
        "posted_at": _ts(row.posted_at),
        "cancelled_at": _ts(row.cancelled_at),
        "cancel_reason": row.cancel_reason,
    }


def settlement_lines(row: SettlementRow, figures: Figures) -> list[LedgerLine]:
    """13 §2.26 / §4.3 posting of one settlement."""
    label = period_label(row.period)
    if row.tax_kind == "vat_offset":
        return [
            LedgerLine(
                row.doc_date,
                row.branch_id,
                OUTPUT_VAT,
                INPUT_VAT,
                figures.amount,
                {"tax_type": "vat", "period": label},
            )
        ]
    assert row.expense_account is not None
    return [
        LedgerLine(
            row.doc_date,
            row.branch_id,
            row.expense_account,
            OUTPUT_VAT,
            figures.amount,
            {"tax_type": "turnover", "period": label},
        )
    ]


class TaxSettlementService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        repo: TaxSettlementRepository,
        vat_repo: VatRepository,
        branch_rate: BranchRateReader,
        poster: LedgerPoster,
    ) -> None:
        self._sf = session_factory
        self._repo = repo
        self._vat = vat_repo
        self._branch_rate = branch_rate
        self._poster = poster

    # --- reads ------------------------------------------------------------------------------------
    async def list_page(
        self, actor: Principal, flt: SettlementFilter, cursor: str | None, limit: int
    ) -> dict[str, Any]:
        after: UUID | None = None
        if cursor:
            try:
                after = UUID(cursor)
            except ValueError:
                raise _invalid("cursor", "validation.cursor_invalid") from None
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            rows = await self._repo.list_page(s, flt, after, limit + 1)
        page = rows[:limit]
        return {
            "items": [settlement_json(r) for r in page],
            "next_cursor": str(page[-1].id) if len(rows) > limit else None,
        }

    async def get(self, actor: Principal, scope: BranchScope, settlement_id: UUID) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            row = await self._repo.get(s, settlement_id)
            if row is None:
                raise not_found()
            _check_scope(scope, row.branch_id)
        return settlement_json(row)

    # --- create -----------------------------------------------------------------------------------
    async def create(
        self, actor: Principal, scope: BranchScope, data: SettlementInput, ip: str | None
    ) -> dict[str, Any]:
        period = parse_period(data.period)
        end = month_end(period)
        doc_date = data.doc_date or end
        if not period <= doc_date <= end:
            raise _invalid("doc_date", "validation.doc_date_outside_period")
        if doc_date > business_today():
            raise _invalid("doc_date", "validation.doc_date_in_future")
        if data.tax_kind == "vat_offset":
            if data.branch_id is not None:
                raise _invalid("branch_id", "validation.branch_not_allowed_for_vat_offset")
            if not scope.unrestricted:  # a tenant-wide figure (qaror #31, SEC-11)
                raise AppError(ErrorCode.PERMISSION_DENIED, params={"reason": "tenant_wide_vat"})
        elif data.branch_id is None:
            raise _invalid("branch_id", "validation.required")
        else:
            _check_scope(scope, data.branch_id)
        settlement_id = uuid7()
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            # ACC-06: allowed when its regime was in force on any day of the period (13 §4.3 transition
            # month — turnover tax up to the VAT valid_from, VAT offset from it)
            in_force = {r for _, _, r in await self._vat.regime_ranges(s, period, end)}
            needed = "vat" if data.tax_kind == "vat_offset" else "turnover"
            if needed not in in_force:
                regime = await self._vat.regime_on(s, end)
                raise _invalid("tax_kind", "validation.tax_kind_regime_mismatch", regime=regime)
            if data.branch_id is not None and not await self._repo.branch_exists(s, data.branch_id):
                raise _invalid("branch_id", "validation.branch_not_found")
            branch_id = data.branch_id or await self._repo.default_branch(s)
            await self._poster.assert_period_open(s, doc_date)
            figures = await self._figures(s, actor.tenant_id, data.tax_kind, period, branch_id)
            account = await self._repo.turnover_account(s) if data.tax_kind == "turnover_tax" else None
            inserted = await self._repo.insert(
                s,
                {
                    "id": settlement_id, "tenant_id": actor.tenant_id, "branch_id": branch_id,
                    "doc_date": doc_date, "tax_kind": data.tax_kind, "period": period,
                    "base_amount": figures.base_amount, "rate": figures.rate, "amount": figures.amount,
                    "expense_account": account, "created_by": actor.user_id, "comment": data.comment,
                },
            )  # fmt: skip
            if not inserted:
                existing = await self._repo.active_id(s, data.tax_kind, period, branch_id)
                raise _invalid(
                    "period",
                    "validation.tax_settlement_exists",
                    existing_id=None if existing is None else str(existing),
                )
            await record_audit(
                s, tenant_id=actor.tenant_id, user_id=actor.user_id, action="tax_settlement.created",
                entity=DOC_TYPE, entity_id=settlement_id, ip=ip,
                after={"tax_kind": data.tax_kind, "period": period_label(period), "branch_id": str(branch_id),
                       "base_amount": money_str(figures.base_amount), "amount": money_str(figures.amount)},
            )  # fmt: skip
            body = settlement_json(await self._load(s, settlement_id))
            stage_response(body, 201)
        return body

    # --- post -------------------------------------------------------------------------------------
    async def post(
        self, actor: Principal, scope: BranchScope, settlement_id: UUID, ip: str | None
    ) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            row = await self._locked(s, scope, settlement_id)
            if row.status != "draft":
                raise AppError(
                    ErrorCode.DOC_NOT_DRAFT, params={"expected_status": "draft", "actual_status": row.status}
                )
            await self._poster.assert_period_open(s, row.doc_date)
            figures = await self._figures(s, actor.tenant_id, row.tax_kind, row.period, row.branch_id)
            recalculated = (figures.base_amount, figures.rate, figures.amount) != (
                row.base_amount, row.rate, row.amount,
            )  # fmt: skip
            await self._poster.post(s, actor.tenant_id, DOC_TYPE, row.id, settlement_lines(row, figures))
            number = await next_doc_number(
                s, tenant_id=actor.tenant_id, branch_id=row.branch_id, table=DOC_TYPE, year=row.doc_date.year
            )
            await self._repo.update(
                s, row.id,
                {"status": "posted", "number": number, "posted_at": datetime.now(UTC),
                 "base_amount": figures.base_amount, "rate": figures.rate, "amount": figures.amount},
            )  # fmt: skip
            await record_audit(
                s, tenant_id=actor.tenant_id, user_id=actor.user_id, action="tax_settlement.posted",
                entity=DOC_TYPE, entity_id=row.id, ip=ip,
                before={"status": row.status, "amount": money_str(row.amount)},
                after={"status": "posted", "number": number, "amount": money_str(figures.amount),
                       "recalculated": recalculated},
            )  # fmt: skip
            body = settlement_json(await self._load(s, row.id)) | {"recalculated": recalculated}
            stage_response(body)
        return body

    # --- cancel -----------------------------------------------------------------------------------
    async def cancel(
        self, actor: Principal, scope: BranchScope, settlement_id: UUID, reason: str, ip: str | None
    ) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            row = await self._locked(s, scope, settlement_id)
            if row.status == "cancelled":
                raise AppError(ErrorCode.DOC_ALREADY_CANCELLED, params={"id": str(row.id)})
            if row.status == "posted":
                await self._poster.reverse_document(s, actor.tenant_id, DOC_TYPE, row.id)
            await self._repo.update(
                s, row.id,
                {"status": "cancelled", "cancelled_at": datetime.now(UTC), "cancelled_by": actor.user_id,
                 "cancel_reason": reason},
            )  # fmt: skip
            await record_audit(
                s, tenant_id=actor.tenant_id, user_id=actor.user_id, action="tax_settlement.cancelled",
                entity=DOC_TYPE, entity_id=row.id, ip=ip, before={"status": row.status},
                after={"status": "cancelled", "reason": reason},
            )  # fmt: skip
            body = settlement_json(await self._load(s, row.id))
            stage_response(body)
        return body

    # --- B5-T16: period-closing readiness (13 §5.1, §2.26; 20 #16) ----------------------------------------
    async def readiness(self, s: AsyncSession, tenant_id: UUID, period: date) -> TaxReadiness:
        """``tax_settlement_missing`` — a regime in force in the month has no ``posted`` settlement where
        one is due (VAT: the period has creditable input VAT; turnover: a branch has a non-zero base);
        ``tax_settlement_stale`` — a ``posted`` settlement whose amount ≠ the figure recomputed now (a
        document dated in the month was posted or cancelled afterwards; the Accountant re-creates it)."""
        end = month_end(period)
        posted = await self._repo.list_page(
            s, SettlementFilter(branch_ids=None, period=period, status="posted"), None, 1000
        )
        stale: list[tuple[UUID, str, UUID | None, Decimal, Decimal]] = []
        for row in posted:
            current = await self._figures(s, tenant_id, row.tax_kind, period, row.branch_id)
            if current.amount != row.amount:
                branch = None if row.tax_kind == "vat_offset" else row.branch_id
                stale.append((row.id, row.tax_kind, branch, row.amount, current.amount))
        ranges = await self._vat.regime_ranges(s, period, end)
        missing = False
        if any(r == "vat" for _, _, r in ranges) and not any(x.tax_kind == "vat_offset" for x in posted):
            _, vat = await self._repo.vat_input(s, period)
            missing = vat > 0
        settled = {x.branch_id for x in posted if x.tax_kind == "turnover_tax"}
        for start, stop, regime in ranges:
            if regime != "turnover" or missing:
                continue
            for b in await self._vat.turnover_bases(s, start, stop, None):
                if b.base != 0 and b.branch_id not in settled:
                    missing = True
        return TaxReadiness(missing=missing, stale=stale)

    # --- helpers ----------------------------------------------------------------------------------
    async def _figures(
        self, s: AsyncSession, tenant_id: UUID, tax_kind: str, period: date, branch_id: UUID
    ) -> Figures:
        if tax_kind == "vat_offset":
            base, vat = await self._repo.vat_input(s, period)
            return Figures(money(max(base, ZERO)), None, money(max(vat, ZERO)))
        figure = await turnover_figure(
            self._vat, self._branch_rate, s, tenant_id, period, (branch_id,), branch_id
        )
        rate = percent(figure.rate_pct if figure.rate_pct is not None else ZERO)
        return Figures(money(max(figure.base, ZERO)), rate, money(max(figure.amount, ZERO)))

    async def _load(self, s: AsyncSession, settlement_id: UUID) -> SettlementRow:
        row = await self._repo.get(s, settlement_id)
        assert row is not None
        return row

    async def _locked(self, s: AsyncSession, scope: BranchScope, settlement_id: UUID) -> SettlementRow:
        row = await self._repo.get(s, settlement_id, lock=True)
        if row is None:
            raise not_found()
        _check_scope(scope, row.branch_id)
        if row.tax_kind == "vat_offset" and not scope.unrestricted:
            raise AppError(ErrorCode.PERMISSION_DENIED, params={"reason": "tenant_wide_vat"})
        return row


def _check_scope(scope: BranchScope, branch_id: UUID) -> None:
    if not scope.unrestricted and branch_id not in scope.allowed:
        raise AppError(ErrorCode.BRANCH_SCOPE_DENIED)
