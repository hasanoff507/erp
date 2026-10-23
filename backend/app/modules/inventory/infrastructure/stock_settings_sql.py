"""``tenants.settings`` stock keys (19 §17 ``/stock-settings``) — runs inside the caller's tenant txn."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.inventory.application.ports import TenantSettingsRow

_READ = text("SELECT settings, version FROM app.tenants WHERE id = :t")
_READ_FOR_UPDATE = text("SELECT settings, version FROM app.tenants WHERE id = :t FOR UPDATE")


class SqlStockSettingsRepository:
    async def read(self, s: AsyncSession, tenant_id: UUID, *, for_update: bool = False) -> TenantSettingsRow:
        sql = _READ_FOR_UPDATE if for_update else _READ
        row = (await s.execute(sql, {"t": tenant_id})).one()
        raw = row[0]
        settings: dict[str, Any] = raw if isinstance(raw, dict) else json.loads(raw or "{}")
        return TenantSettingsRow(settings, int(row[1]))

    async def write(self, s: AsyncSession, tenant_id: UUID, patch: Mapping[str, Any]) -> int:
        version: int = (
            await s.execute(
                text(
                    "UPDATE app.tenants SET settings = settings || CAST(:p AS jsonb), version = version + 1, "
                    "updated_at = now() WHERE id = :t RETURNING version"
                ),
                {"p": json.dumps(dict(patch), ensure_ascii=False), "t": tenant_id},
            )
        ).scalar_one()
        return version
