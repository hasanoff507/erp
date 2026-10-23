"""Price history and the ``price_changes`` document (19 §4, US-M09-01/02/04, qaror #25).

``post`` compares every line with the current price (branch price, else the
global one) and with the poster's ``prices.approve`` limit:

* all lines within the limit → ``product_prices`` rows, ``status=posted``,
  a ``C-…`` number and ``label_print_queue(reason='price_changed')``;
* any line beyond it → ``approval_requests(kind='price_change')`` and
  ``status=pending_approval`` (``202``); prices do not change yet.

Approve/reject goes through ``/approval-requests`` (18 §9) — not in Bosqich 1.
"""

from __future__ import annotations

import base64
import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
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
from app.core.permissions import BranchScope
from app.modules.pricing.application.ports import PricingRepository
from app.modules.pricing.domain.price_changes import (
    APPROVAL_TTL_MINUTES,
    MAX_LINES,
    PriceChange,
)
from app.modules.pricing.domain.resolution import (
    change_pct,
    effective_price,
    series_history,
    within_limit,
)

ZERO_PRICE = Decimal("0.0000")


@dataclass(frozen=True, slots=True)
class LineInput:
    product_id: UUID
    new_price: Decimal
    valid_from: datetime | None
    branch_id: UUID | None


@dataclass(frozen=True, slots=True)
class PostResult:
    body: dict[str, Any]
    status_code: int  # 200 posted, 202 pending_approval


def _invalid(field: str, key: str) -> AppError:
    return AppError(ErrorCode.VALIDATION_ERROR, details=[ErrorDetail(field=field, message_key=key)])


def _ts(value: datetime | None) -> str | None:
    return None if value is None else value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def price_change_json(doc: PriceChange, approval_request_id: UUID | None = None) -> dict[str, Any]:
    return {
        "id": str(doc.id),
        "status": doc.status,
        "number": doc.number,
        "doc_date": doc.doc_date.isoformat(),
        "branch_id": str(doc.branch_id),
        "comment": doc.comment,
        "posted_at": _ts(doc.posted_at),
        "approval_request_id": str(approval_request_id) if approval_request_id else None,
        "warnings": ["APPROVAL_REQUIRED"] if doc.status == "pending_approval" else [],
        "lines": [
            {
                "id": str(line.id),
                "line_no": line.line_no,
                "product_id": str(line.product_id),
                "branch_id": str(line.branch_id) if line.branch_id else None,
                "old_price": str(line.old_price),
                "new_price": str(line.new_price),
                "valid_from": _ts(line.valid_from),
            }
            for line in doc.lines
        ],
    }


def _encode_cursor(valid_from: datetime, record_id: UUID) -> str:
    raw = json.dumps([valid_from.isoformat(), str(record_id)]).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))
        at, rid = json.loads(raw)
        return datetime.fromisoformat(at), UUID(rid)
    except (ValueError, TypeError) as exc:
        raise _invalid("cursor", "validation.cursor_invalid") from exc


def check_branch(scope: BranchScope, branch_id: UUID | None) -> None:
    """A restricted user (``memberships.branch_ids`` set) prices only own branches, never globally."""
    if scope.unrestricted:
        return
    if branch_id is None or branch_id not in scope.allowed:
        raise AppError(ErrorCode.BRANCH_SCOPE_DENIED)


class PriceChangeService:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession], repo: PricingRepository) -> None:
        self._sf = session_factory
        self._repo = repo

    # --- history (GET /products/{id}/prices) ------------------------------------------------------
    async def history(
        self,
        actor: Principal,
        scope: BranchScope,
        product_id: UUID,
        branch_id: UUID | None,
        cursor: str | None,
        limit: int,
    ) -> dict[str, Any]:
        if branch_id is not None:
            check_branch(scope, branch_id)
        after = _decode_cursor(cursor) if cursor else None
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            if not await self._repo.product_exists(s, product_id):
                raise AppError(ErrorCode.NOT_FOUND, params={"resource": "product"})
            entries = series_history(await self._repo.series(s, product_id, branch_id))
            if after is not None:
                entries = [
                    e for e in entries if (e.record.valid_from, e.record.id.int) < (after[0], after[1].int)
                ]
            page = entries[:limit]
            names = await self._repo.user_names(s, [e.record.set_by for e in page if e.record.set_by])
        next_cursor = (
            _encode_cursor(page[-1].record.valid_from, page[-1].record.id) if len(entries) > limit else None
        )
        items = [
            {
                "price": str(e.record.price),
                "valid_from": _ts(e.record.valid_from),
                "valid_to": _ts(e.valid_to),
                "set_by": str(e.record.set_by) if e.record.set_by else None,
                "set_by_name": names.get(e.record.set_by) if e.record.set_by else None,
                "price_change_doc_id": str(e.record.price_change_doc_id)
                if e.record.price_change_doc_id
                else None,
                "branch_id": str(e.record.branch_id) if e.record.branch_id else None,
            }
            for e in page
        ]
        return {"items": items, "next_cursor": next_cursor}

    # --- POST /price-changes ----------------------------------------------------------------------
    async def create(
        self,
        actor: Principal,
        scope: BranchScope,
        doc_date: date,
        lines: Sequence[LineInput],
        comment: str | None,
        ip: str | None,
    ) -> dict[str, Any]:
        if not lines:
            raise _invalid("lines", "validation.required")
        if len(lines) > MAX_LINES:
            raise _invalid("lines", "validation.max_items")
        seen: set[tuple[UUID, UUID | None]] = set()
        for index, line in enumerate(lines):
            if line.new_price <= 0:
                raise _invalid(f"lines[{index}].new_price", "validation.positive")
            key = (line.product_id, line.branch_id)
            if key in seen:
                raise _invalid(f"lines[{index}].product_id", "validation.duplicate")
            seen.add(key)
            check_branch(scope, line.branch_id)
        doc_id = uuid7()
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            branch_id = await self._doc_branch(s, scope)
            await self._check_refs(s, lines)
            now = datetime.now(UTC)
            records = await self._repo.price_records(s, [line.product_id for line in lines])
            await self._repo.insert_price_change(
                s,
                {
                    "id": doc_id,
                    "tenant_id": actor.tenant_id,
                    "branch_id": branch_id,
                    "doc_date": doc_date,
                    "created_by": actor.user_id,
                    "comment": comment,
                },
            )
            await self._repo.insert_lines(
                s,
                [
                    {
                        "id": uuid7(),
                        "tenant_id": actor.tenant_id,
                        "price_change_id": doc_id,
                        "line_no": n,
                        "product_id": line.product_id,
                        "branch_id": line.branch_id,
                        "old_price": effective_price(
                            records, product_id=line.product_id, branch_id=line.branch_id, at=now
                        )
                        or ZERO_PRICE,
                        "new_price": line.new_price,
                        "valid_from": line.valid_from,
                    }
                    for n, line in enumerate(lines, start=1)
                ],
            )
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="price_change_created",
                entity="price_changes",
                entity_id=doc_id,
                after={"lines": len(lines), "doc_date": str(doc_date)},
                ip=ip,
            )
            body = price_change_json(await self._load(s, doc_id))
            stage_response(body, 201)
        return body

    # --- POST /price-changes/{id}/post ------------------------------------------------------------
    async def post(
        self, actor: Principal, scope: BranchScope, doc_id: UUID, limit: Decimal | None, ip: str | None
    ) -> PostResult:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            doc = await self._repo.get_price_change(s, doc_id, lock=True)
            if doc is None:
                raise AppError(ErrorCode.NOT_FOUND, params={"resource": "price_change"})
            if not scope.unrestricted and doc.branch_id not in scope.allowed:
                raise AppError(ErrorCode.BRANCH_SCOPE_DENIED)
            if doc.status == "pending_approval":
                raise AppError(
                    ErrorCode.DOC_INVALID_STATE,
                    params={"expected_status": "draft", "actual_status": doc.status},
                )
            if doc.status != "draft":
                raise AppError(
                    ErrorCode.DOC_NOT_DRAFT, params={"expected_status": "draft", "actual_status": doc.status}
                )
            now = datetime.now(UTC)
            records = await self._repo.price_records(s, [line.product_id for line in doc.lines])
            bases = {
                line.id: effective_price(
                    records, product_id=line.product_id, branch_id=line.branch_id, at=now
                )
                for line in doc.lines
            }
            pcts = {line.id: change_pct(bases[line.id], line.new_price) for line in doc.lines}
            await self._repo.set_old_prices(s, {lid: base or ZERO_PRICE for lid, base in bases.items()})
            over = [lid for lid, pct in pcts.items() if not within_limit(pct, limit)]
            if over:
                return await self._request_approval(s, actor, doc, pcts, ip)
            number = await next_doc_number(
                s,
                tenant_id=actor.tenant_id,
                branch_id=doc.branch_id,
                table="price_changes",
                year=doc.doc_date.year,
            )
            await self.apply(s, actor.tenant_id, actor.user_id, doc, now)
            await self._repo.mark_posted(s, doc.id, number)
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="price_changed",
                entity="price_changes",
                entity_id=doc.id,
                after={
                    "number": number,
                    "lines": [
                        {
                            "product_id": str(ln.product_id),
                            "branch_id": str(ln.branch_id) if ln.branch_id else None,
                            "old_price": str(bases[ln.id] or ZERO_PRICE),
                            "new_price": str(ln.new_price),
                        }
                        for ln in doc.lines
                    ],
                },
                ip=ip,
            )
            body = price_change_json(await self._load(s, doc.id))
            stage_response(body, 200)
        return PostResult(body, 200)

    async def apply(
        self, s: AsyncSession, tenant_id: UUID, user_id: UUID, doc: PriceChange, now: datetime
    ) -> None:
        """Write the document's ``product_prices`` rows and queue the labels (inside the caller's txn)."""
        await self._repo.insert_prices(
            s,
            [
                {
                    "id": uuid7(),
                    "tenant_id": tenant_id,
                    "product_id": line.product_id,
                    "branch_id": line.branch_id,
                    "price": line.new_price,
                    "valid_from": line.valid_from or now,
                    "set_by": user_id,
                    "price_change_doc_id": doc.id,
                }
                for line in doc.lines
            ],
        )
        await self._repo.queue_labels(s, tenant_id, [line.product_id for line in doc.lines], "price_changed")

    async def resolve_approval(
        self, s: AsyncSession, *, tenant_id: UUID, doc_id: UUID, decision: str, resolver_id: UUID
    ) -> None:
        """BO-16 decided the document's ``price_change`` request (18 §10) — inside the approve/reject txn.

        ``approved`` → the ``pending_approval`` document is posted exactly like an in-limit ``post``
        (``product_prices`` rows, ``C-…`` number, labels; prices set by the document's author);
        ``rejected`` → ``status='rejected'``, prices unchanged. Any other document state: no-op.
        """
        doc = await self._repo.get_price_change(s, doc_id, lock=True)
        if doc is None or doc.status != "pending_approval":
            return
        if decision != "approved":
            await self._repo.mark_rejected(s, doc.id)
            await record_audit(
                s,
                tenant_id=tenant_id,
                user_id=resolver_id,
                action="price_change_rejected",
                entity="price_changes",
                entity_id=doc.id,
                before={"status": "pending_approval"},
                after={"status": "rejected"},
            )
            return
        now = datetime.now(UTC)
        number = await next_doc_number(
            s, tenant_id=tenant_id, branch_id=doc.branch_id, table="price_changes", year=doc.doc_date.year
        )
        await self.apply(s, tenant_id, doc.created_by, doc, now)
        await self._repo.mark_posted(s, doc.id, number)
        await record_audit(
            s,
            tenant_id=tenant_id,
            user_id=resolver_id,
            action="price_changed",
            entity="price_changes",
            entity_id=doc.id,
            after={
                "number": number,
                "approved_by": str(resolver_id),
                "lines": [
                    {"product_id": str(ln.product_id), "new_price": str(ln.new_price)} for ln in doc.lines
                ],
            },
        )

    async def approval_expired(self, s: AsyncSession, *, tenant_id: UUID, doc_id: UUID) -> None:
        """The ``price_change`` request expired unanswered (18 §10): ``pending_approval`` → ``draft`` (prices
        unchanged) so the author can ``post`` again and get a new request. Inside the expiry txn."""
        if await self._repo.mark_draft_from_pending(s, doc_id):
            await record_audit(
                s,
                tenant_id=tenant_id,
                action="price_change_approval_expired",
                entity="price_changes",
                entity_id=doc_id,
                before={"status": "pending_approval"},
                after={"status": "draft"},
            )

    async def post_initial_prices(
        self,
        s: AsyncSession,
        tenant_id: UUID,
        user_id: UUID,
        prices: Sequence[tuple[UUID, Decimal]],
        comment: str,
    ) -> UUID | None:
        """Catalog import (US-M04-04): one posted ``price_changes`` doc with the new products' first prices.

        New products have no base price, so no limit check applies (19 §4 formula). Runs in the caller's
        transaction; returns the document id (``None`` when there are no prices).
        """
        if not prices:
            return None
        branch_id = await self._repo.default_branch_id(s)
        if branch_id is None:
            raise _invalid("branch", "validation.default_branch_missing")
        doc_id = uuid7()
        now = datetime.now(UTC)
        await self._repo.insert_price_change(
            s,
            {
                "id": doc_id,
                "tenant_id": tenant_id,
                "branch_id": branch_id,
                "doc_date": now.date(),
                "created_by": user_id,
                "comment": comment,
            },
        )
        await self._repo.insert_lines(
            s,
            [
                {
                    "id": uuid7(),
                    "tenant_id": tenant_id,
                    "price_change_id": doc_id,
                    "line_no": n,
                    "product_id": product_id,
                    "branch_id": None,
                    "old_price": ZERO_PRICE,
                    "new_price": value,
                    "valid_from": None,
                }
                for n, (product_id, value) in enumerate(prices, start=1)
            ],
        )
        doc = await self._load(s, doc_id)
        number = await next_doc_number(
            s, tenant_id=tenant_id, branch_id=branch_id, table="price_changes", year=doc.doc_date.year
        )
        await self.apply(s, tenant_id, user_id, doc, now)
        await self._repo.mark_posted(s, doc_id, number)
        await record_audit(
            s,
            tenant_id=tenant_id,
            user_id=user_id,
            action="price_changed",
            entity="price_changes",
            entity_id=doc_id,
            after={"number": number, "lines": len(prices), "source": "import"},
        )
        return doc_id

    # --- helpers ----------------------------------------------------------------------------------
    async def _request_approval(
        self,
        s: AsyncSession,
        actor: Principal,
        doc: PriceChange,
        pcts: dict[UUID, Decimal | None],
        ip: str | None,
    ) -> PostResult:
        requested = max(p for p in pcts.values() if p is not None)
        approval_id = uuid7()
        await self._repo.insert_approval_request(
            s,
            {
                "id": approval_id,
                "tenant_id": actor.tenant_id,
                "branch_id": doc.branch_id,
                "kind": "price_change",
                "permission_code": "prices.approve",
                "requested_value": requested,
                "context": json.dumps(
                    {
                        "price_change_id": str(doc.id),
                        "lines": [
                            {
                                "product_id": str(ln.product_id),
                                "branch_id": str(ln.branch_id) if ln.branch_id else None,
                                "new_price": str(ln.new_price),
                                "pct": None if pcts[ln.id] is None else str(pcts[ln.id]),
                            }
                            for ln in doc.lines
                        ],
                    }
                ),
                "linked_doc_type": "price_changes",
                "linked_doc_id": doc.id,
                "requested_by": actor.user_id,
                "expires_at": datetime.now(UTC) + timedelta(minutes=APPROVAL_TTL_MINUTES),
            },
        )
        await self._repo.mark_pending(s, doc.id)
        await record_audit(
            s,
            tenant_id=actor.tenant_id,
            user_id=actor.user_id,
            action="price_change_pending_approval",
            entity="price_changes",
            entity_id=doc.id,
            after={"approval_request_id": str(approval_id), "requested_value": str(requested)},
            ip=ip,
        )
        body = price_change_json(await self._load(s, doc.id), approval_id)
        stage_response(body, 202)
        return PostResult(body, 202)

    async def _load(self, s: AsyncSession, doc_id: UUID) -> PriceChange:
        doc = await self._repo.get_price_change(s, doc_id)
        assert doc is not None
        return doc

    async def _doc_branch(self, s: AsyncSession, scope: BranchScope) -> UUID:
        """Doc branch: ``X-Branch-Id``; else the default branch (all-branch users) or the only one."""
        if scope.current is not None:
            branch = scope.current
        elif scope.unrestricted:
            default = await self._repo.default_branch_id(s)
            if default is None:
                raise _invalid("X-Branch-Id", "validation.required")
            branch = default
        elif len(scope.allowed) == 1:
            branch = scope.allowed[0]
        else:
            raise _invalid("X-Branch-Id", "validation.required")
        if branch not in await self._repo.existing_branch_ids(s, [branch]):
            raise AppError(ErrorCode.BRANCH_SCOPE_DENIED)
        return branch

    async def _check_refs(self, s: AsyncSession, lines: Sequence[LineInput]) -> None:
        flags = await self._repo.product_archived_flags(s, [line.product_id for line in lines])
        branches = {line.branch_id for line in lines if line.branch_id is not None}
        known = await self._repo.existing_branch_ids(s, list(branches))
        for index, line in enumerate(lines):
            if line.product_id not in flags:
                raise _invalid(f"lines[{index}].product_id", "validation.product_not_found")
            if flags[line.product_id]:
                raise AppError(
                    ErrorCode.RESOURCE_ARCHIVED,
                    params={"resource": "product"},
                    details=[
                        ErrorDetail(field=f"lines[{index}].product_id", message_key="validation.archived")
                    ],
                )
            if line.branch_id is not None and line.branch_id not in known:
                raise _invalid(f"lines[{index}].branch_id", "validation.branch_not_found")
