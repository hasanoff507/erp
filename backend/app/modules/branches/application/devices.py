"""Tenant devices — BO-11 "Qurilmalar" (20 #29a/#29b, qaror #56, 16 §9).

Revoking sets ``devices.revoked_at``/``revoked_by``; the RS gateway (auth module)
rejects tokens bound to a revoked device. Users who worked on the device in the
last ``PIN_REVOKE_LOOKBACK_DAYS`` get their PIN reset (16 §9) in the same transaction.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from typing import Final
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.audit import record_audit
from app.core.auth.principal import Principal
from app.core.db.session import tenant_transaction
from app.core.idempotency import stage_response
from app.modules.branches.application.common import (
    archived,
    check_branch_scope,
    invalid,
    iso,
    not_found,
)
from app.modules.branches.application.ports import DeviceFilter, DeviceRepository, DeviceRow

PIN_REVOKE_LOOKBACK_DAYS: Final = 30  # 16 §9 (PIN_REVOKE_LOOKBACK_DAYS, standart 30)

# called after the revoke commits: the RS (auth module) starts refusing the device's tokens at once
DeviceRevokedHook = Callable[[UUID], Awaitable[None]]


async def _no_hook(_: UUID) -> None:
    return None


@dataclass(frozen=True, slots=True)
class DeviceView:
    id: UUID
    kind: str
    app_version: str | None
    cash_register_id: UUID | None
    cash_register_name: str | None
    branch_id: UUID | None
    last_seen_at: str | None
    last_sync_at: str | None
    outbox_pending_count: int | None
    outbox_oldest_pending_at: str | None
    has_pending: bool
    revoked_at: str | None


@dataclass(frozen=True, slots=True)
class DevicePage:
    items: list[DeviceView]
    total: int
    page: int
    size: int


@dataclass(frozen=True, slots=True)
class DeviceRevoked:
    id: UUID
    revoked_at: str | None
    outbox_pending_count: int | None


def _pending(row: DeviceRow) -> int:
    return row.outbox_pending_count or 0


def _view(row: DeviceRow) -> DeviceView:
    return DeviceView(
        id=row.id,
        kind=row.kind,
        app_version=row.app_version,
        cash_register_id=row.cash_register_id,
        cash_register_name=row.cash_register_name,
        branch_id=row.branch_id,
        last_seen_at=iso(row.last_seen_at),
        last_sync_at=iso(row.last_sync_at),
        outbox_pending_count=row.outbox_pending_count,
        outbox_oldest_pending_at=iso(row.outbox_oldest_pending_at),
        has_pending=_pending(row) > 0,
        revoked_at=iso(row.revoked_at),
    )


class DevicesService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        devices: DeviceRepository,
        on_revoked: DeviceRevokedHook = _no_hook,
    ) -> None:
        self._sf = session_factory
        self._devices = devices
        self._on_revoked = on_revoked

    async def list_devices(
        self,
        actor: Principal,
        allowed: tuple[UUID, ...],
        *,
        branch_id: UUID | None,
        kind: str | None,
        include_revoked: bool,
        page: int,
        size: int,
    ) -> DevicePage:
        if branch_id is not None:
            check_branch_scope(allowed, branch_id)
        flt = DeviceFilter(allowed, branch_id, kind, include_revoked)
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            rows, total = await self._devices.list_devices(
                s, actor.tenant_id, flt, offset=(page - 1) * size, limit=size
            )
        return DevicePage([_view(r) for r in rows], total, page, size)

    async def revoke(
        self,
        actor: Principal,
        allowed: tuple[UUID, ...],
        device_id: UUID,
        reason: str,
        confirm_pending_loss: bool,
        ip: str | None,
    ) -> DeviceRevoked:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            row = await self._devices.get_device(s, actor.tenant_id, device_id, for_update=True)
            if row is None:
                raise not_found("devices")
            if allowed:
                check_branch_scope(allowed, row.branch_id)
            if row.kind == "onec_agent":
                # 20 #29a: Do'kon agenti devices are only listed here; they are revoked via 33 §10 (W-05)
                raise invalid("id", "validation.onec_agent_device")
            if row.revoked_at is not None:
                raise archived("devices")
            pending = _pending(row)
            if pending > 0 and not confirm_pending_loss:
                raise invalid(
                    "confirm_pending_loss",
                    "validation.pending_events_unconfirmed",
                    outbox_pending_count=pending,
                )
            revoked_at = await self._devices.revoke(s, device_id, actor.user_id)
            since = datetime.now(UTC) - timedelta(days=PIN_REVOKE_LOOKBACK_DAYS)
            users = await self._devices.recent_device_users(s, actor.tenant_id, device_id, since)
            for user_id in users:
                await self._devices.force_pin_reset(s, user_id)
                await record_audit(
                    s,
                    tenant_id=actor.tenant_id,
                    user_id=actor.user_id,
                    action="pin_reset_forced",
                    entity="users",
                    entity_id=user_id,
                    after={"reason": "device_revoked"},
                    ip=ip,
                    device_id=device_id,
                )
            result = DeviceRevoked(device_id, iso(revoked_at), row.outbox_pending_count)
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="device_revoked",
                entity="devices",
                entity_id=device_id,
                before={"revoked_at": None},
                after={
                    "revoked_at": result.revoked_at,
                    "reason": reason,
                    "outbox_pending_count": pending,
                    "confirm_pending_loss": confirm_pending_loss,
                    "pin_reset_users": [str(u) for u in users],
                },
                ip=ip,
                device_id=device_id,
            )
            stage_response(asdict(result))
        await self._on_revoked(device_id)
        return result
