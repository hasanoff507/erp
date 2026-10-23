"""``GET /returns`` / ``GET /returns/{id}`` (18 §7.2); ``without_receipt`` = ``sale_id IS NULL``."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.db.session import tenant_transaction
from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from app.core.permissions import BranchScope
from app.modules.returns.application.ports import ReturnFilter, ReturnsRepository
from app.modules.sales.application.queries import decode_cursor, encode_cursor, in_scope, jsonable


class ReturnQueries:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession], repo: ReturnsRepository) -> None:
        self._sf = session_factory
        self._repo = repo

    async def list_page(
        self, tenant_id: UUID, user_id: UUID, flt: ReturnFilter, cursor: str | None, limit: int
    ) -> dict[str, Any]:
        after = decode_cursor(cursor) if cursor else None
        async with self._sf() as s, tenant_transaction(s, tenant_id, user_id=user_id):
            rows = await self._repo.page(s, flt, after, limit + 1)
        page = rows[:limit]
        next_cursor = encode_cursor(page[-1]["created_at"], page[-1]["id"]) if len(rows) > limit else None
        return {"items": [jsonable(r) for r in page], "next_cursor": next_cursor}

    async def get(
        self, tenant_id: UUID, user_id: UUID, scope: BranchScope, return_id: UUID
    ) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, tenant_id, user_id=user_id):
            found = await self._repo.get(s, return_id)
        if found is None or not in_scope(scope, found["branch_id"]):
            raise AppError(ErrorCode.NOT_FOUND, params={"resource": "return"})
        body: dict[str, Any] = jsonable(found)
        return body
