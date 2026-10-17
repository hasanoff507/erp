"""Bank settlements — BO-24 (20 #55a–#55f, #55h; 13 §2.18a; qaror #42, #71). OpenAPI tag ``cash``.

Three-step document (17 §9): ``draft`` (55c manual / 55g statement import; number ``BT-…`` from
``doc_sequences`` on creation) → ``post`` → ``cancel`` (storno). Back-office only, no sync event, no
``cash_moves`` — the money already moved into 5710 with the sale / refund / debt payment / collection; the
transfer 5710 → 5110 lives in ``ledger_entries`` only (:class:`BankSettlementPostingService`).

**Transit balance** (55b, 55c/55e check): ``ledger_entries`` on 5710 per ``branch_id`` ×
``analytics.payment_method``, ``Σ Dt − Σ Kt`` up to the date. ``gross_amount`` may not exceed the smaller of
the balance on ``doc_date`` and the current balance (a later settlement already took its part) →
``422 VALIDATION_ERROR`` (``validation.bank_settlement_exceeds_in_transit``, ``params.available``); the final
check on ``post`` runs under a transaction advisory lock of (tenant, branch, method) after the document row is
locked ``FOR UPDATE``.
"""

from __future__ import annotations

import base64
import json
from dataclasses import replace
from datetime import date
from decimal import Decimal
from typing import Any
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
from app.core.money import money
from app.core.permissions import BranchScope
from app.modules.accounting.wiring import LedgerLine, LedgerPoster, business_today
from app.modules.cash.application.bank_settlements_ports import (
    BankSettlementRepository,
    SettlementFilter,
    SettlementRow,
)
from app.modules.cash.application.common import invalid, m2, scope_branches, ts
from app.modules.cash.domain.bank_settlements import (
    METHODS,
    ZERO,
    Amounts,
    oldest_unsettled,
    posting_lines,
    validate,
)

DOC_TYPE = "bank_settlements"


def settlement_json(row: SettlementRow) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "number": row.number,
        "branch_id": str(row.branch_id),
        "doc_date": row.doc_date.isoformat(),
        "status": row.status,
        "source": row.source,
        "method": row.method,
        "settled_from": row.settled_from.isoformat(),
        "settled_to": row.settled_to.isoformat(),
        "gross_amount": m2(row.gross_amount),
        "commission_amount": m2(row.commission_amount),
        "variance_amount": m2(row.variance_amount),
        "net_amount": m2(row.net_amount),
        "bank_ref": row.bank_ref,
        "attachment_id": None if row.attachment_id is None else str(row.attachment_id),
        "statement_import_id": None if row.statement_import_id is None else str(row.statement_import_id),
        "comment": row.comment,
        "created_by": str(row.created_by),
        "created_at": ts(row.created_at),
        "posted_at": ts(row.posted_at),
        "cancelled_at": ts(row.cancelled_at),
        "cancelled_by": None if row.cancelled_by is None else str(row.cancelled_by),
        "cancel_reason": row.cancel_reason,
        "version": row.version,
    }


def amounts_of(row: SettlementRow) -> Amounts:
    return Amounts(
        method=row.method,
        doc_date=row.doc_date,
        settled_from=row.settled_from,
        settled_to=row.settled_to,
        gross=money(row.gross_amount),
        commission=money(row.commission_amount),
        variance=money(row.variance_amount),
    )


def check_amounts(a: Amounts) -> None:
    violations = validate(a)
    if violations:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            details=[ErrorDetail(field=v.field, message_key=v.message_key) for v in violations],
        )


def exceeds_error(available: Decimal) -> AppError:
    return AppError(
        ErrorCode.VALIDATION_ERROR,
        params={"available": m2(available)},
        details=[
            ErrorDetail(field="gross_amount", message_key="validation.bank_settlement_exceeds_in_transit")
        ],
    )


def require_branch(scope: BranchScope, branch_id: UUID) -> None:
    if not scope.unrestricted and branch_id not in scope.allowed:
        raise AppError(ErrorCode.BRANCH_SCOPE_DENIED)
    if scope.current is not None and branch_id != scope.current:
        raise AppError(ErrorCode.BRANCH_SCOPE_DENIED)


def _encode_cursor(day: date, row_id: UUID) -> str:
    raw = json.dumps([day.isoformat(), str(row_id)]).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _decode_cursor(cursor: str | None) -> tuple[date, UUID] | None:
    if not cursor:
        return None
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))
        day, row_id = json.loads(raw)
        return date.fromisoformat(day), UUID(row_id)
    except (ValueError, TypeError) as exc:
        raise invalid("cursor", "validation.cursor_invalid") from exc


class BankSettlementPostingService:
    """Registers of one settlement inside the caller's transaction: transit check, ledger, links, storno."""

    def __init__(self, repo: BankSettlementRepository, poster: LedgerPoster) -> None:
        self._repo = repo
        self._poster = poster

    async def available(self, s: AsyncSession, branch_id: UUID, method: str, doc_date: date) -> Decimal:
        """5710 balance usable by a settlement dated ``doc_date`` (min of that day's / current balance)."""
        on_day = await self._repo.transit_balance(s, branch_id, method, doc_date)
        now = await self._repo.transit_balance(s, branch_id, method, None)
        return min(on_day, now)

    async def check_available(self, s: AsyncSession, a: Amounts, branch_id: UUID) -> None:
        available = await self.available(s, branch_id, a.method, a.doc_date)
        if a.gross > available:
            raise exceeds_error(max(available, ZERO))

    async def post(self, s: AsyncSession, tenant_id: UUID, row: SettlementRow) -> None:
        await self._poster.assert_period_open(s, row.doc_date)
        await self._repo.lock_transit(s, row.branch_id, row.method)
        a = amounts_of(row)
        check_amounts(a)
        await self.check_available(s, a, row.branch_id)
        _, provider_account = await self._repo.tenant_bank(s)
        analytics: dict[str, Any] = {"bank_settlement_id": str(row.id)}
        if row.bank_ref:
            analytics["bank_ref"] = row.bank_ref
        lines = posting_lines(a, provider_account=provider_account, analytics=analytics)
        await self._poster.post(
            s,
            tenant_id,
            DOC_TYPE,
            row.id,
            [
                LedgerLine(row.doc_date, row.branch_id, x.account_dt, x.account_kt, x.amount, x.analytics)
                for x in lines
            ],
        )
        if row.method == "card":
            await self._repo.link_terminal_batches(s, row)
        await self._repo.mark_posted(s, row.id)

    async def cancel(self, s: AsyncSession, tenant_id: UUID, row: SettlementRow) -> None:
        if row.status == "posted":
            await self._poster.reverse_document(s, tenant_id, DOC_TYPE, row.id)
        await self._repo.unlink(s, row.id)


class BankSettlementService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        repo: BankSettlementRepository,
        poster: LedgerPoster,
    ) -> None:
        self._sf = session_factory
        self._repo = repo
        self._poster = poster
        self.posting = BankSettlementPostingService(repo, poster)

    # --- 55c ------------------------------------------------------------------------------------------
    async def create(
        self, actor: Principal, scope: BranchScope, values: dict[str, Any], ip: str | None
    ) -> dict[str, Any]:
        require_branch(scope, values["branch_id"])
        a = Amounts(
            method=values["method"],
            doc_date=values["doc_date"],
            settled_from=values["settled_from"],
            settled_to=values["settled_to"],
            gross=money(values["gross_amount"]),
            commission=money(values.get("commission_amount") or ZERO),
            variance=money(values.get("variance_amount") or ZERO),
        )
        if a.doc_date > business_today():
            raise invalid("doc_date", "validation.doc_date_in_future")
        check_amounts(a)
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            if values["branch_id"] not in await self._repo.branch_ids(s):
                raise AppError(ErrorCode.NOT_FOUND, params={"resource": "branch"})
            if values.get("attachment_id") is not None and not await self._repo.attachment_exists(
                s, values["attachment_id"]
            ):
                raise AppError(ErrorCode.NOT_FOUND, params={"resource": "attachment"})
            await self._poster.assert_period_open(s, a.doc_date)
            await self.posting.check_available(s, a, values["branch_id"])
            row = await self.insert_draft(
                s,
                actor,
                branch_id=values["branch_id"],
                a=a,
                source="manual",
                bank_ref=values.get("bank_ref"),
                attachment_id=values.get("attachment_id"),
                statement_import_id=None,
                comment=values.get("comment"),
                ip=ip,
            )
            body = settlement_json(row)
            stage_response(body, 201)
        return body

    async def insert_draft(
        self,
        s: AsyncSession,
        actor: Principal,
        *,
        branch_id: UUID,
        a: Amounts,
        source: str,
        bank_ref: str | None,
        attachment_id: UUID | None,
        statement_import_id: UUID | None,
        comment: str | None,
        ip: str | None,
    ) -> SettlementRow:
        settlement_id = uuid7()
        number = await next_doc_number(
            s, tenant_id=actor.tenant_id, branch_id=branch_id, table=DOC_TYPE, year=a.doc_date.year
        )
        await self._repo.insert(
            s,
            {
                "id": settlement_id,
                "tenant_id": actor.tenant_id,
                "branch_id": branch_id,
                "number": number,
                "doc_date": a.doc_date,
                "source": source,
                "method": a.method,
                "settled_from": a.settled_from,
                "settled_to": a.settled_to,
                "gross_amount": a.gross,
                "commission_amount": a.commission,
                "variance_amount": a.variance,
                "bank_ref": bank_ref,
                "statement_import_id": statement_import_id,
                "attachment_id": attachment_id,
                "created_by": actor.user_id,
                "comment": comment,
            },
        )
        row = await self._repo.get(s, settlement_id)
        assert row is not None
        await record_audit(
            s,
            tenant_id=actor.tenant_id,
            user_id=actor.user_id,
            action="bank_settlement_created",
            entity=DOC_TYPE,
            entity_id=settlement_id,
            ip=ip,
            after=_audit_after(row),
        )
        return row

    # --- 55h ------------------------------------------------------------------------------------------
    async def update(
        self,
        actor: Principal,
        scope: BranchScope,
        settlement_id: UUID,
        changes: dict[str, Any],
        ip: str | None,
    ) -> dict[str, Any]:
        version = changes.pop("version")
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            row = await self._load(s, scope, settlement_id, lock=True)
            if row.status != "draft":
                raise AppError(ErrorCode.DOC_NOT_DRAFT, params={"status": row.status})
            if row.version != version:
                raise AppError(ErrorCode.VERSION_CONFLICT, params={"current_version": row.version})
            a = amounts_of(row)
            a = replace(
                a,
                settled_from=changes.get("settled_from", a.settled_from),
                settled_to=changes.get("settled_to", a.settled_to),
                gross=money(changes["gross_amount"]) if "gross_amount" in changes else a.gross,
                commission=money(changes["commission_amount"])
                if "commission_amount" in changes
                else a.commission,
                variance=money(changes["variance_amount"]) if "variance_amount" in changes else a.variance,
            )
            check_amounts(a)
            await self.posting.check_available(s, a, row.branch_id)
            values: dict[str, Any] = {
                "settled_from": a.settled_from,
                "settled_to": a.settled_to,
                "gross_amount": a.gross,
                "commission_amount": a.commission,
                "variance_amount": a.variance,
                "bank_ref": changes.get("bank_ref", row.bank_ref),
                "comment": changes.get("comment", row.comment),
            }
            await self._repo.update_draft(s, row.id, values)
            after = await self._repo.get(s, row.id)
            assert after is not None
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="bank_settlement_updated",
                entity=DOC_TYPE,
                entity_id=row.id,
                ip=ip,
                before=_audit_after(row),
                after=_audit_after(after),
            )
            body = settlement_json(after)
            stage_response(body, 200)
        return body

    # --- 55e / 55f ------------------------------------------------------------------------------------
    async def post(
        self, actor: Principal, scope: BranchScope, settlement_id: UUID, ip: str | None
    ) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            row = await self._load(s, scope, settlement_id, lock=True)
            if row.status != "draft":
                raise AppError(ErrorCode.DOC_NOT_DRAFT, params={"status": row.status})
            await self.posting.post(s, actor.tenant_id, row)
            after = await self._repo.get(s, row.id)
            assert after is not None
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="bank_settlement_posted",
                entity=DOC_TYPE,
                entity_id=row.id,
                ip=ip,
                before={"status": "draft"},
                after=_audit_after(after),
            )
            body = settlement_json(after)
            stage_response(body, 200)
        return body

    async def cancel(
        self, actor: Principal, scope: BranchScope, settlement_id: UUID, reason: str, ip: str | None
    ) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            row = await self._load(s, scope, settlement_id, lock=True)
            if row.status == "cancelled":
                raise AppError(ErrorCode.DOC_ALREADY_CANCELLED, params={"id": str(row.id)})
            await self.posting.cancel(s, actor.tenant_id, row)
            await self._repo.mark_cancelled(s, row.id, actor.user_id, reason)
            after = await self._repo.get(s, row.id)
            assert after is not None
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="bank_settlement_cancelled",
                entity=DOC_TYPE,
                entity_id=row.id,
                ip=ip,
                before={"status": row.status},
                after={**_audit_after(after), "reason": reason},
            )
            body = settlement_json(after)
            stage_response(body, 200)
        return body

    # --- reads (55a, 55b, 55d) ------------------------------------------------------------------------
    async def get(self, actor: Principal, scope: BranchScope, settlement_id: UUID) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            row = await self._load(s, scope, settlement_id)
            entries = await self._repo.ledger_rows(s, row.id)
        return {**settlement_json(row), "ledger_entries": entries}

    async def list_page(
        self,
        actor: Principal,
        scope: BranchScope,
        *,
        branch_id: UUID | None,
        method: str | None,
        status: str | None,
        source: str | None,
        date_from: date | None,
        date_to: date | None,
        cursor: str | None,
        limit: int,
    ) -> dict[str, Any]:
        branches = scope_branches(scope)
        if branch_id is not None:
            require_branch(scope, branch_id)
            branches = (branch_id,)
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            rows = await self._repo.list_settlements(
                s,
                SettlementFilter(
                    branches, method, status, source, date_from, date_to, _decode_cursor(cursor), limit + 1
                ),
            )
        more = len(rows) > limit
        rows = rows[:limit]
        return {
            "items": [settlement_json(r) for r in rows],
            "next_cursor": _encode_cursor(rows[-1].doc_date, rows[-1].id) if more and rows else None,
        }

    async def transit_balances(
        self, actor: Principal, scope: BranchScope, *, as_of: date | None, branch_id: UUID | None
    ) -> dict[str, Any]:
        day = as_of or business_today()
        branches = scope_branches(scope)
        if branch_id is not None:
            require_branch(scope, branch_id)
            branches = (branch_id,)
        items: list[dict[str, Any]] = []
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            balances = await self._repo.transit_balances(s, day, branches)
            integrated = await self._repo.integrated_card(s, day, branches)
            for branch, method, balance in sorted(balances, key=lambda x: (str(x[0]), METHODS.index(x[1]))):
                if balance == 0:
                    continue
                inflows = await self._repo.daily_inflows(s, branch, method, day)
                breakdown = None
                if method == "card":
                    part = min(max(integrated.get(branch, ZERO), ZERO), max(balance, ZERO))
                    breakdown = {"integrated": m2(part), "manual": m2(balance - part)}
                oldest = oldest_unsettled(inflows, balance)
                items.append(
                    {
                        "branch_id": str(branch),
                        "method": method,
                        "balance": m2(balance),
                        "oldest_unsettled_date": None if oldest is None else oldest.isoformat(),
                        "card_breakdown": breakdown,
                    }
                )
        return {"as_of": day.isoformat(), "items": items}

    # --- helpers --------------------------------------------------------------------------------------
    async def _load(
        self, s: AsyncSession, scope: BranchScope, settlement_id: UUID, *, lock: bool = False
    ) -> SettlementRow:
        row = await self._repo.get(s, settlement_id, lock=lock)
        if row is None:
            raise AppError(ErrorCode.NOT_FOUND, params={"resource": "bank_settlement"})
        require_branch(scope, row.branch_id)
        return row


def _audit_after(row: SettlementRow) -> dict[str, Any]:
    """15 §6.1: ``method``, ``gross_amount``, ``commission_amount``, ``bank_ref`` (+ status, number)."""
    return {
        "status": row.status,
        "number": row.number,
        "method": row.method,
        "source": row.source,
        "gross_amount": m2(row.gross_amount),
        "commission_amount": m2(row.commission_amount),
        "variance_amount": m2(row.variance_amount),
        "bank_ref": row.bank_ref,
    }
