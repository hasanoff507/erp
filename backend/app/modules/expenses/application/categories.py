"""Expense categories (20 #45–#47; 13 §2.17 seed map; 12 ``expense_categories``).

The tenant may rename, re-account and archive categories (US-M15-01); a new ``default_account`` only
affects later postings. A category never moves between an expense account (94xx) and ``6410`` (tax
payment to the budget — ``tax_type`` semantics, 13 §2.26): ``422 validation.not_allowed``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.audit import record_audit
from app.core.auth.principal import Principal
from app.core.db.base import uuid7
from app.core.db.session import tenant_transaction
from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from app.core.idempotency import stage_response
from app.modules.expenses.application.expenses import invalid, ts
from app.modules.expenses.application.ports import CategoryRow, ExpenseStore
from app.modules.expenses.domain.expenses import crosses_tax_boundary


def category_json(row: CategoryRow) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "code": row.code,
        "name": row.name,
        "default_account": row.default_account,
        "source_ref": row.source_ref,
        "is_system": row.is_system,
        "archived_at": ts(row.archived_at),
        "version": row.version,
    }


class CategoryService:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession], repo: ExpenseStore) -> None:
        self._sf = session_factory
        self._repo = repo

    async def list(self, actor: Principal, *, include_archived: bool) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            rows = await self._repo.list_categories(s, include_archived=include_archived)
        return {"items": [category_json(r) for r in rows]}

    async def create(
        self, actor: Principal, name: str, default_account: str, ip: str | None
    ) -> dict[str, Any]:
        name = name.strip()
        if not name:
            raise invalid("name", "validation.required")
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            if await self._repo.category_name_taken(s, name, None):
                raise invalid("name", "validation.duplicate")
            category_id = uuid7()
            await self._repo.insert_category(
                s,
                {
                    "id": category_id,
                    "tenant_id": actor.tenant_id,
                    "name": name,
                    "default_account": default_account,
                },
            )
            row = await self._repo.get_category(s, category_id)
            assert row is not None
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="expense_category.created",
                entity="expense_categories",
                entity_id=category_id,
                ip=ip,
                device_id=actor.device_id,
                after={"name": name, "default_account": default_account},
            )
            body = category_json(row)
            stage_response(body, 201)
        return body

    async def update(
        self, actor: Principal, category_id: UUID, version: int, changes: Mapping[str, Any], ip: str | None
    ) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            current = await self._repo.get_category(s, category_id, lock=True)
            if current is None:
                raise AppError(ErrorCode.NOT_FOUND, params={"resource": "expense_category"})
            if current.version != version:
                raise AppError(ErrorCode.VERSION_CONFLICT, params={"current_version": current.version})
            patch = dict(changes)
            if "name" in patch:
                patch["name"] = str(patch["name"]).strip()
                if not patch["name"]:
                    raise invalid("name", "validation.required")
                if await self._repo.category_name_taken(s, patch["name"], category_id):
                    raise invalid("name", "validation.duplicate")
            account = patch.get("default_account")
            if account is not None and crosses_tax_boundary(current.default_account, account):
                raise invalid("default_account", "validation.not_allowed")
            if patch and not await self._repo.update_category(s, category_id, version, patch):
                raise AppError(ErrorCode.VERSION_CONFLICT, params={"current_version": current.version})
            row = await self._repo.get_category(s, category_id)
            assert row is not None
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="expense_category.updated",
                entity="expense_categories",
                entity_id=category_id,
                ip=ip,
                device_id=actor.device_id,
                before={
                    "name": current.name,
                    "default_account": current.default_account,
                    "archived": current.archived_at is not None,
                },
                after=dict(patch),
            )
            body = category_json(row)
            stage_response(body, 200)
        return body
