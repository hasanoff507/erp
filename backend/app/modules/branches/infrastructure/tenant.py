"""SQL for ``app.tenants`` settings, ``tenant_tax_regimes``, ``consents`` (12 §2.3). Caller's transaction."""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any, Final
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.base import uuid7
from app.modules.branches.application.ports import IntegrationRow, TenantRow

_TENANT_SELECT: Final = (
    "SELECT name, legal_form, go_live_date, accepted_terms_version, accepted_terms_at, settings, version "
    "FROM app.tenants WHERE id = :tenant_id"
)
_GET_TENANT = text(_TENANT_SELECT)
_GET_TENANT_FOR_UPDATE = text(_TENANT_SELECT + " FOR UPDATE")
_TENANT_COLUMNS: Final = frozenset({"name", "legal_form", "settings"})
_TAX_REGIMES = text(
    "SELECT valid_from, regime FROM app.tenant_tax_regimes WHERE tenant_id = :tenant_id ORDER BY valid_from"
)
_UPSERT_TAX_REGIME = text(
    "INSERT INTO app.tenant_tax_regimes (id, tenant_id, valid_from, regime, created_by) "
    "VALUES (:id, :tenant_id, :valid_from, :regime, :created_by) "
    "ON CONFLICT (tenant_id, valid_from) DO UPDATE "
    "SET regime = EXCLUDED.regime, created_by = EXCLUDED.created_by, "
    "created_at = now()"
)
_INTEGRATIONS = text(
    "SELECT kind, cash_register_id, created_at FROM app.tenant_secrets "
    "WHERE tenant_id = :tenant_id AND kind IN ('faktura_uz','crpt','click','payme','uzum','uzqr')"
)
_OFD_CONNECTED = text(
    "SELECT EXISTS (SELECT 1 FROM app.cash_registers WHERE tenant_id = :tenant_id AND archived_at IS NULL "
    "AND ofd_status IN ('registered','active'))"
)
_CURRENT_TERMS = text("SELECT version FROM platform.terms_versions WHERE kind = :kind AND is_current")
_INSERT_CONSENT = text(
    "INSERT INTO app.consents (id, tenant_id, subject, user_id, purpose, terms_version, accepted, ip) "
    "VALUES (:id, :tenant_id, 'tenant', :user_id, :purpose, :terms_version, :accepted, CAST(:ip AS inet)) "
    "RETURNING at"
)


def _settings(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        loaded = json.loads(value)
        return loaded if isinstance(loaded, dict) else {}
    return {}


class SqlTenantSettingsRepository:
    """:class:`app.modules.branches.application.ports.TenantSettingsRepository`."""

    async def get_tenant(
        self, session: AsyncSession, tenant_id: UUID, *, for_update: bool = False
    ) -> TenantRow | None:
        stmt = _GET_TENANT_FOR_UPDATE if for_update else _GET_TENANT
        row = (await session.execute(stmt, {"tenant_id": tenant_id})).first()
        if row is None:
            return None
        return TenantRow(
            name=row.name,
            legal_form=row.legal_form,
            go_live_date=row.go_live_date,
            accepted_terms_version=row.accepted_terms_version,
            accepted_terms_at=row.accepted_terms_at,
            settings=_settings(row.settings),
            version=row.version,
        )

    async def update_tenant(self, session: AsyncSession, tenant_id: UUID, fields: dict[str, Any]) -> int:
        unknown = set(fields) - _TENANT_COLUMNS
        if unknown or not fields:
            raise ValueError(f"cannot update tenants columns {sorted(unknown) or '(none)'}")
        params: dict[str, Any] = {"tenant_id": tenant_id}
        assignments = []
        for column in sorted(fields):
            if column == "settings":
                assignments.append("settings = CAST(:settings AS jsonb)")
                params["settings"] = json.dumps(fields["settings"], ensure_ascii=False)
            else:
                assignments.append(f"{column} = :{column}")
                params[column] = fields[column]
        stmt = text(
            f"UPDATE app.tenants SET {', '.join(assignments)}, version = version + 1, updated_at = now() "  # noqa: S608
            "WHERE id = :tenant_id RETURNING version"
        )
        version: int = (await session.execute(stmt, params)).scalar_one()
        return version

    async def tax_regimes(self, session: AsyncSession, tenant_id: UUID) -> list[tuple[date, str]]:
        rows = (await session.execute(_TAX_REGIMES, {"tenant_id": tenant_id})).all()
        return [(r.valid_from, r.regime) for r in rows]

    async def upsert_tax_regime(
        self, session: AsyncSession, tenant_id: UUID, valid_from: date, regime: str, user_id: UUID
    ) -> None:
        await session.execute(
            _UPSERT_TAX_REGIME,
            {
                "id": uuid7(),
                "tenant_id": tenant_id,
                "valid_from": valid_from,
                "regime": regime,
                "created_by": user_id,
            },
        )

    async def integrations(self, session: AsyncSession, tenant_id: UUID) -> list[IntegrationRow]:
        rows = (await session.execute(_INTEGRATIONS, {"tenant_id": tenant_id})).all()
        return [IntegrationRow(r.kind, r.cash_register_id, r.created_at) for r in rows]

    async def ofd_connected(self, session: AsyncSession, tenant_id: UUID) -> bool:
        return bool((await session.execute(_OFD_CONNECTED, {"tenant_id": tenant_id})).scalar_one())

    async def current_terms_version(self, session: AsyncSession, kind: str) -> str | None:
        value: str | None = (await session.execute(_CURRENT_TERMS, {"kind": kind})).scalar_one_or_none()
        return value

    async def insert_consent(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        user_id: UUID,
        purpose: str,
        terms_version: str,
        accepted: bool,
        ip: str | None,
    ) -> datetime:
        at: datetime = (
            await session.execute(
                _INSERT_CONSENT,
                {
                    "id": uuid7(),
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                    "purpose": purpose,
                    "terms_version": terms_version,
                    "accepted": accepted,
                    "ip": ip,
                },
            )
        ).scalar_one()
        return at
