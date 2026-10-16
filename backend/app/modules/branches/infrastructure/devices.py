"""SQL for ``app.devices`` (12 §2.3, 16 §9). Runs inside the caller's tenant transaction."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Final
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.branches.application.ports import DeviceFilter, DeviceRow

_DEVICE_SELECT: Final = (
    "SELECT d.id, d.kind, d.app_version, d.cash_register_id, cr.name AS cash_register_name, "
    "cr.branch_id, d.last_seen_at, d.last_sync_at, d.outbox_pending_count, d.outbox_oldest_pending_at, "
    "d.revoked_at FROM app.devices d "
    "LEFT JOIN app.cash_registers cr ON cr.id = d.cash_register_id AND cr.tenant_id = d.tenant_id "
)
# restricted callers (15 §2.4) see only devices of their branches; devices without a cash register
# (Do'kon agenti) belong to no branch and are listed to unrestricted callers only
_DEVICE_FILTER: Final = (
    "WHERE d.tenant_id = :tenant_id "
    "AND (cardinality(CAST(:allowed AS uuid[])) = 0 OR cr.branch_id = ANY(CAST(:allowed AS uuid[]))) "
    "AND (CAST(:branch_id AS uuid) IS NULL OR cr.branch_id = CAST(:branch_id AS uuid)) "
    "AND (CAST(:kind AS text) IS NULL OR d.kind = CAST(:kind AS text)) "
    "AND (CAST(:include_revoked AS boolean) OR d.revoked_at IS NULL) "
)
_LIST_DEVICES = text(
    _DEVICE_SELECT
    + _DEVICE_FILTER
    + "ORDER BY d.revoked_at NULLS FIRST, d.last_seen_at DESC NULLS LAST, d.id "
    "OFFSET :offset LIMIT :limit"
)
_COUNT_DEVICES = text(
    "SELECT count(*) FROM app.devices d "  # noqa: S608 — static fragments only
    "LEFT JOIN app.cash_registers cr ON cr.id = d.cash_register_id AND cr.tenant_id = d.tenant_id "
    + _DEVICE_FILTER
)
_GET_DEVICE = text(_DEVICE_SELECT + "WHERE d.tenant_id = :tenant_id AND d.id = :id")
_GET_DEVICE_FOR_UPDATE = text(
    _DEVICE_SELECT + "WHERE d.tenant_id = :tenant_id AND d.id = :id FOR UPDATE OF d"
)
_REVOKE = text(
    "UPDATE app.devices SET revoked_at = now(), revoked_by = :user_id, updated_at = now() "
    "WHERE id = :id RETURNING revoked_at"
)
# 16 §9: everyone who worked on the device recently — shifts opened/closed there and logins/PIN
# checks the auth module audited with this device_id; only members of this tenant
_RECENT_USERS = text(
    "SELECT DISTINCT x.user_id FROM ("
    "  SELECT opened_by AS user_id FROM app.shifts WHERE device_id = :device_id AND opened_at >= :since "
    "  UNION SELECT closed_by FROM app.shifts "
    "    WHERE device_id = :device_id AND closed_by IS NOT NULL AND closed_at >= :since "
    "  UNION SELECT user_id FROM app.audit_log WHERE device_id = :device_id AND at >= :since "
    "    AND user_id IS NOT NULL AND action IN ('login_success', 'pin_verified', 'pin_login')"
    ") x JOIN app.memberships m ON m.user_id = x.user_id AND m.tenant_id = :tenant_id "
    "ORDER BY x.user_id"
)
_FORCE_PIN_RESET = text("SELECT app.auth_reset_credentials(:user_id, false, true)")


def _device(row: Any) -> DeviceRow:
    return DeviceRow(
        id=row.id,
        kind=row.kind,
        app_version=row.app_version,
        cash_register_id=row.cash_register_id,
        cash_register_name=row.cash_register_name,
        branch_id=row.branch_id,
        last_seen_at=row.last_seen_at,
        last_sync_at=row.last_sync_at,
        outbox_pending_count=row.outbox_pending_count,
        outbox_oldest_pending_at=row.outbox_oldest_pending_at,
        revoked_at=row.revoked_at,
    )


class SqlDeviceRepository:
    """:class:`app.modules.branches.application.ports.DeviceRepository`."""

    async def list_devices(
        self, session: AsyncSession, tenant_id: UUID, flt: DeviceFilter, *, offset: int, limit: int
    ) -> tuple[list[DeviceRow], int]:
        params = {
            "tenant_id": tenant_id,
            "allowed": [str(b) for b in flt.allowed_branches],
            "branch_id": flt.branch_id,
            "kind": flt.kind,
            "include_revoked": flt.include_revoked,
        }
        rows = (await session.execute(_LIST_DEVICES, {**params, "offset": offset, "limit": limit})).all()
        total = (await session.execute(_COUNT_DEVICES, params)).scalar_one()
        return [_device(r) for r in rows], int(total)

    async def get_device(
        self, session: AsyncSession, tenant_id: UUID, device_id: UUID, *, for_update: bool = False
    ) -> DeviceRow | None:
        stmt = _GET_DEVICE_FOR_UPDATE if for_update else _GET_DEVICE
        row = (await session.execute(stmt, {"tenant_id": tenant_id, "id": device_id})).first()
        return None if row is None else _device(row)

    async def revoke(self, session: AsyncSession, device_id: UUID, user_id: UUID) -> datetime:
        value: datetime = (await session.execute(_REVOKE, {"id": device_id, "user_id": user_id})).scalar_one()
        return value

    async def recent_device_users(
        self, session: AsyncSession, tenant_id: UUID, device_id: UUID, since: datetime
    ) -> list[UUID]:
        params = {"tenant_id": tenant_id, "device_id": device_id, "since": since}
        return [r[0] for r in (await session.execute(_RECENT_USERS, params)).all()]

    async def force_pin_reset(self, session: AsyncSession, user_id: UUID) -> None:
        # SECURITY DEFINER (12 §4.5): PIN hash NULL + must_change_pin; sessions stay (password untouched)
        await session.execute(_FORCE_PIN_RESET, {"user_id": user_id})
