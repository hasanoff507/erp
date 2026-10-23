"""Notification settings and the delivery log (20 #69–#71, 07 BO-20).

Settings are per user (``notification_settings (tenant_id, user_id, kind)``): GET/PATCH read and write the
caller's own rows. A kind without a row is enabled (BO-20 "default barcha yoqilgan"); ``time`` is only for
``daily_report`` (default 21:00 Asia/Tashkent). PATCH is one transaction with the
``notification_settings_updated`` audit row and the Idempotency-Key journal.
"""

from __future__ import annotations

import base64
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import time
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.audit import record_audit
from app.core.auth.principal import Principal
from app.core.db.session import tenant_transaction
from app.core.error_codes import ErrorCode
from app.core.errors import AppError, ErrorDetail
from app.core.idempotency import stage_response
from app.core.money import money_str
from app.modules.notifications.application.ports import LogRow, NotificationRepository, SettingRow
from app.modules.notifications.domain.policy import (
    DAILY_REPORT,
    DEFAULT_DAILY_TIME,
    KIND_ORDER,
    format_hhmm,
    parse_hhmm,
)


@dataclass(frozen=True, slots=True)
class SettingIn:
    kind: str
    enabled: bool
    time: str | None


def _invalid(details: Sequence[ErrorDetail]) -> AppError:
    return AppError(ErrorCode.VALIDATION_ERROR, details=details)


def settings_json(rows: Sequence[SettingRow]) -> dict[str, Any]:
    by_kind = {r.kind: r for r in rows}
    items = []
    for kind in KIND_ORDER:
        row = by_kind.get(kind)
        at: time | None = None
        if kind == DAILY_REPORT:
            at = row.time if row is not None and row.time is not None else DEFAULT_DAILY_TIME
        items.append(
            {
                "kind": kind,
                "enabled": True if row is None else row.enabled,
                "time": format_hhmm(at) if at is not None else None,
            }
        )
    return {"items": items}


def log_json(row: LogRow) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "channel": row.channel,
        "recipient": row.recipient,
        "template": row.template,
        "status": row.status,
        "cost": money_str(row.cost) if row.cost is not None else None,
        "created_at": row.created_at.isoformat(),
    }


def _encode(row_id: UUID) -> str:
    return base64.urlsafe_b64encode(row_id.bytes).decode().rstrip("=")


def _decode(cursor: str) -> UUID:
    try:
        return UUID(bytes=base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
    except (ValueError, TypeError):
        raise _invalid([ErrorDetail(field="cursor", message_key="validation.cursor_invalid")]) from None


class NotificationSettingsService:
    def __init__(
        self, session_factory: async_sessionmaker[AsyncSession], repo: NotificationRepository
    ) -> None:
        self._sf = session_factory
        self._repo = repo

    async def get(self, actor: Principal) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            return settings_json(await self._repo.settings(s, actor.tenant_id, actor.user_id))

    async def update(self, actor: Principal, items: Sequence[SettingIn], ip: str | None) -> dict[str, Any]:
        parsed = self._validate(items)
        changes = [{"kind": k, "enabled": e, "time": format_hhmm(t) if t else None} for k, e, t in parsed]
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            before = settings_json(await self._repo.settings(s, actor.tenant_id, actor.user_id))
            for kind, enabled, at in parsed:
                await self._repo.upsert_setting(s, actor.tenant_id, actor.user_id, kind, enabled, at)
            body = settings_json(await self._repo.settings(s, actor.tenant_id, actor.user_id))
            await record_audit(
                s, tenant_id=actor.tenant_id, user_id=actor.user_id, action="notification_settings_updated",
                entity="notification_settings", entity_id=actor.user_id, ip=ip,
                before=before, after={"items": changes},
            )  # fmt: skip
            stage_response(body)
        return body

    @staticmethod
    def _validate(items: Sequence[SettingIn]) -> list[tuple[str, bool, time | None]]:
        details: list[ErrorDetail] = []
        seen: set[str] = set()
        out: list[tuple[str, bool, time | None]] = []
        for i, item in enumerate(items):
            if item.kind not in KIND_ORDER:
                details.append(ErrorDetail(field=f"items[{i}].kind", message_key="validation.invalid_choice"))
                continue
            if item.kind in seen:
                details.append(ErrorDetail(field=f"items[{i}].kind", message_key="validation.duplicate"))
                continue
            seen.add(item.kind)
            at: time | None = None
            if item.time is not None:
                if item.kind != DAILY_REPORT:
                    details.append(
                        ErrorDetail(field=f"items[{i}].time", message_key="validation.not_allowed")
                    )
                    continue
                at = parse_hhmm(item.time)
                if at is None:
                    details.append(
                        ErrorDetail(field=f"items[{i}].time", message_key="validation.invalid_format")
                    )
                    continue
            out.append((item.kind, item.enabled, at))
        if details:
            raise _invalid(details)
        return out

    async def log_page(
        self, actor: Principal, *, channel: str | None, status: str | None, cursor: str | None, limit: int
    ) -> dict[str, Any]:
        before = _decode(cursor) if cursor else None
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            rows = await self._repo.log_page(
                s, channel=channel, status=status, before=before, limit=limit + 1
            )
        page = rows[:limit]
        return {
            "items": [log_json(r) for r in page],
            "next_cursor": _encode(page[-1].id) if len(rows) > limit else None,
        }
