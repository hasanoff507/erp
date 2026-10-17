"""``GET /ledger-entries`` — the accounting journal (20 #9, US-M11-01, BO-08).

Newest first (``entry_date DESC, id DESC``), cursor pagination. Branch scope: an explicit
``branch_id`` must be one of the user's branches (``403 BRANCH_SCOPE_DENIED``); a branch-restricted
user without ``branch_id`` sees only the rows of their branches; an unrestricted user sees every
row. Each item also carries ``doc_number`` (``Sotuv #K-000154`` in BO-08) — one batched lookup per
document type of the page.
"""

from __future__ import annotations

import base64
import json
from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.auth.principal import Principal
from app.core.db.session import tenant_transaction
from app.core.error_codes import ErrorCode
from app.core.errors import AppError, ErrorDetail
from app.core.permissions import BranchScope
from app.modules.accounting.application.ports import JournalFilter, LedgerRepository, StoredEntry


def _invalid(field: str, key: str) -> AppError:
    return AppError(ErrorCode.VALIDATION_ERROR, details=[ErrorDetail(field=field, message_key=key)])


def encode_cursor(day: date, entry_id: UUID) -> str:
    raw = json.dumps([day.isoformat(), str(entry_id)]).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str) -> tuple[date, UUID]:
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))
        day, eid = json.loads(raw)
        return date.fromisoformat(day), UUID(eid)
    except (ValueError, TypeError) as exc:
        raise _invalid("cursor", "validation.cursor_invalid") from exc


def entry_json(e: StoredEntry, number: str | None) -> dict[str, Any]:
    return {
        "id": str(e.id),
        "entry_date": e.entry_date.isoformat(),
        "account_dt": e.account_dt,
        "account_kt": e.account_kt,
        "amount": format(e.amount, "f"),
        "branch_id": str(e.branch_id) if e.branch_id else None,
        "doc_type": e.doc_type,
        "doc_id": str(e.doc_id),
        "doc_number": number,
        "analytics": e.analytics,
        "reversal_of_id": str(e.reversal_of_id) if e.reversal_of_id else None,
    }


class JournalService:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession], repo: LedgerRepository) -> None:
        self._sf = session_factory
        self._repo = repo

    async def page(
        self,
        actor: Principal,
        scope: BranchScope,
        flt: JournalFilter,
        branch_id: UUID | None,
        cursor: str | None,
        limit: int,
    ) -> dict[str, Any]:
        if flt.entry_date_gte and flt.entry_date_lte and flt.entry_date_gte > flt.entry_date_lte:
            raise _invalid("entry_date__gte", "validation.date_range")
        if branch_id is not None:
            if not scope.unrestricted and branch_id not in scope.allowed:
                raise AppError(ErrorCode.BRANCH_SCOPE_DENIED)
            branches: tuple[UUID, ...] | None = (branch_id,)
        else:
            branches = None if scope.unrestricted else scope.allowed
        flt = JournalFilter(
            entry_date_gte=flt.entry_date_gte,
            entry_date_lte=flt.entry_date_lte,
            account_dt=flt.account_dt,
            account_kt=flt.account_kt,
            doc_type=flt.doc_type,
            doc_id=flt.doc_id,
            branch_ids=branches,
        )
        after = decode_cursor(cursor) if cursor else None
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            rows = await self._repo.journal(s, flt, after, limit + 1)
            page = rows[:limit]
            refs: dict[str, list[UUID]] = {}
            for e in page:
                refs.setdefault(e.doc_type, []).append(e.doc_id)
            numbers = await self._repo.doc_numbers(s, refs)
        next_cursor = encode_cursor(page[-1].entry_date, page[-1].id) if len(rows) > limit else None
        return {"items": [entry_json(e, numbers.get(e.doc_id)) for e in page], "next_cursor": next_cursor}
