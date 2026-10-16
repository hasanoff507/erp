"""Product categories (19 §2) and units (19 §3)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.audit import record_audit
from app.core.auth.principal import Principal
from app.core.db.base import uuid7
from app.core.db.session import tenant_transaction
from app.core.error_codes import ErrorCode
from app.core.errors import AppError, ErrorDetail
from app.core.idempotency import stage_response
from app.modules.catalog.application.ports import CatalogRepository
from app.modules.catalog.application.presenters import category_json, unit_json
from app.modules.catalog.application.products import Page
from app.modules.catalog.domain.products import Category

_FIELD_ERROR = ErrorCode.VALIDATION_ERROR


def _invalid(field: str, key: str) -> AppError:
    return AppError(_FIELD_ERROR, details=[ErrorDetail(field=field, message_key=key)])


def _not_found() -> AppError:
    return AppError(ErrorCode.NOT_FOUND, params={"resource": "product_category"})


class CategoryService:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession], repo: CatalogRepository) -> None:
        self._sf = session_factory
        self._repo = repo

    async def list_page(self, actor: Principal, parent_id: UUID | None, page: int, size: int) -> Page:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            items, total = await self._repo.list_categories(s, parent_id, (page - 1) * size, size)
        return Page([category_json(c) for c in items], total, page, size)

    async def list_units(self, actor: Principal) -> list[dict[str, Any]]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            return [unit_json(u) for u in await self._repo.list_units(s)]

    async def create(
        self, actor: Principal, name: str, parent_id: UUID | None, ip: str | None
    ) -> dict[str, Any]:
        name = name.strip()
        if not name:
            raise _invalid("name", "validation.required")
        category_id = uuid7()
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            if parent_id is not None:
                await self._active_parent(s, parent_id)
            await self._repo.insert_category(s, actor.tenant_id, category_id, name, parent_id)
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="product_category_created",
                entity="product_categories",
                entity_id=category_id,
                after={"name": name, "parent_id": str(parent_id) if parent_id else None},
                ip=ip,
            )
            body = category_json(await self._load(s, category_id))
            stage_response(body, 201)
        return body

    async def update(
        self, actor: Principal, category_id: UUID, version: int, changes: dict[str, Any], ip: str | None
    ) -> dict[str, Any]:
        if "name" in changes:
            changes["name"] = (changes["name"] or "").strip()
            if not changes["name"]:
                raise _invalid("name", "validation.required")
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            current = await self._repo.get_category(s, category_id, lock=True)
            if current is None:
                raise _not_found()
            if current.archived_at is not None:
                raise AppError(ErrorCode.RESOURCE_ARCHIVED, params={"resource": "product_category"})
            if current.version != version:
                raise AppError(ErrorCode.VERSION_CONFLICT, params={"current_version": current.version})
            parent_id = changes.get("parent_id")
            if parent_id is not None:
                await self._active_parent(s, parent_id)
                # a category cannot become its own ancestor (tree, 11 §4)
                if parent_id == category_id or category_id in await self._repo.category_ancestors(
                    s, parent_id
                ):
                    raise _invalid("parent_id", "validation.category_cycle")
            if changes and not await self._repo.update_category(s, category_id, version, changes):
                raise AppError(ErrorCode.VERSION_CONFLICT, params={"current_version": current.version})
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="product_category_updated",
                entity="product_categories",
                entity_id=category_id,
                before={
                    "name": current.name,
                    "parent_id": str(current.parent_id) if current.parent_id else None,
                },
                after={k: (str(v) if isinstance(v, UUID) else v) for k, v in changes.items()},
                ip=ip,
            )
            body = category_json(await self._load(s, category_id))
            stage_response(body)
        return body

    async def archive(self, actor: Principal, category_id: UUID, ip: str | None) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            current = await self._repo.get_category(s, category_id, lock=True)
            if current is None:
                raise _not_found()
            if current.archived_at is None:
                if await self._repo.category_has_active_products(s, category_id):
                    raise AppError(ErrorCode.CATEGORY_HAS_PRODUCTS)
                if await self._repo.category_has_active_children(s, category_id):
                    raise _invalid("id", "validation.category_has_children")
                await self._repo.set_category_archived(s, category_id)
                await record_audit(
                    s,
                    tenant_id=actor.tenant_id,
                    user_id=actor.user_id,
                    action="product_category_archived",
                    entity="product_categories",
                    entity_id=category_id,
                    ip=ip,
                )
            body = category_json(await self._load(s, category_id))
            stage_response(body)
        return body

    async def _load(self, s: AsyncSession, category_id: UUID) -> Category:
        category = await self._repo.get_category(s, category_id)
        assert category is not None
        return category

    async def _active_parent(self, s: AsyncSession, parent_id: UUID) -> None:
        parent = await self._repo.get_category(s, parent_id)
        if parent is None or parent.archived_at is not None:
            raise _invalid("parent_id", "validation.category_not_found")
