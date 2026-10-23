"""``GET/PATCH /stock-settings`` (19 §17; US-M09-06 weight barcodes, US-M04-02/06 warnings).

The values live in ``tenants.settings`` (``weight_barcode_templates``, ``low_stock_check_enabled``,
``expiry_warning_days``); ``version`` = ``tenants.version`` (17 §8 optimistic locking → 409
``VERSION_CONFLICT``). A change bumps ``tenants.version`` and the ``settings`` pull scope digest, so every
POS re-reads the templates on its next pull (16 §1).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.audit import record_audit
from app.core.auth.principal import Principal
from app.core.db.session import tenant_transaction
from app.core.error_codes import ErrorCode
from app.core.errors import AppError, ErrorDetail
from app.core.idempotency import stage_response
from app.modules.inventory.application.ports import StockSettingsRepository, TenantSettingsRow
from app.modules.inventory.domain.stock_settings import stock_settings_view, template_problems


def _body(row: TenantSettingsRow) -> dict[str, Any]:
    return {**stock_settings_view(row.settings), "version": row.version}


class StockSettingsService:
    def __init__(
        self, session_factory: async_sessionmaker[AsyncSession], repo: StockSettingsRepository
    ) -> None:
        self._sf = session_factory
        self._repo = repo

    async def get(self, actor: Principal) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            return _body(await self._repo.read(s, actor.tenant_id))

    async def update(
        self, actor: Principal, version: int, patch: Mapping[str, Any], ip: str | None
    ) -> dict[str, Any]:
        templates = patch.get("weight_barcode_templates")
        if templates is not None:
            problems = template_problems(templates)
            if problems:
                raise AppError(
                    ErrorCode.VALIDATION_ERROR,
                    details=[ErrorDetail(field=p.field, message_key=p.message_key) for p in problems],
                )
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            row = await self._repo.read(s, actor.tenant_id, for_update=True)
            if row.version != version:
                raise AppError(ErrorCode.VERSION_CONFLICT, params={"current_version": row.version})
            before = stock_settings_view(row.settings)
            changes = {k: v for k, v in patch.items() if row.settings.get(k) != v}
            result = row
            if changes:
                new_version = await self._repo.write(s, actor.tenant_id, changes)
                result = TenantSettingsRow({**row.settings, **changes}, new_version)
                after = stock_settings_view(result.settings)
                await record_audit(
                    s, tenant_id=actor.tenant_id, user_id=actor.user_id, action="stock_settings.updated",
                    entity="tenants", entity_id=actor.tenant_id, before=before,
                    after={**after, "changed": sorted(k for k in changes if before.get(k) != after.get(k))},
                    ip=ip,
                )  # fmt: skip
            body = _body(result)
            stage_response(body, 200)
        return body
