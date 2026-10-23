"""M18 notifications REST (20 #66–#71) and the Telegram bot webhook. Tag ``notifications``.

Writes need ``Idempotency-Key`` (17 §6). The webhook is called by Telegram only: it is authenticated by the
``X-Telegram-Bot-Api-Secret-Token`` header (``setWebhook secret_token``), not by our tokens, and is not
part of the OpenAPI schema.
"""

from __future__ import annotations

import hmac
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from app.core.auth.dependencies import require_subscription_ok
from app.core.auth.principal import Principal
from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from app.core.permissions import PermissionGrant, require_permission
from app.modules.notifications.api.deps import client_ip, notifications_module
from app.modules.notifications.application.settings import SettingIn

router = APIRouter(tags=["notifications"])

Actor = Annotated[Principal, Depends(require_subscription_ok)]
CanLink = Annotated[PermissionGrant, Depends(require_permission("telegram.link"))]
CanManage = Annotated[PermissionGrant, Depends(require_permission("notifications.manage"))]
SECRET_HEADER = "X-Telegram-Bot-Api-Secret-Token"  # noqa: S105 — a header name


class LinkStartOut(BaseModel):
    link_code: str = Field(description="One-time code, 10 minutes (qaror #54)")
    bot_url: str = Field(description="https://t.me/<bot>?start=<link_code>")
    expires_at: datetime


class TelegramStatusOut(BaseModel):
    linked: bool
    chat_id: str | None
    linked_at: datetime | None


class SettingItemIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str = Field(max_length=64)
    enabled: bool
    time: str | None = Field(default=None, max_length=5, description='"HH:mm", only for daily_report')


class NotificationSettingsPatchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[SettingItemIn] = Field(min_length=1, max_length=50)


class SettingItemOut(BaseModel):
    kind: str
    enabled: bool
    time: str | None


class NotificationSettingsOut(BaseModel):
    items: list[SettingItemOut]


class LogItemOut(BaseModel):
    id: str
    channel: Literal["telegram", "sms"]
    recipient: str
    template: str
    status: str
    cost: str | None
    created_at: datetime


class LogPageOut(BaseModel):
    items: list[LogItemOut]
    next_cursor: str | None


# --- Telegram link (#66–#68) ----------------------------------------------------------------------
@router.post(
    "/notifications/telegram/link-start",
    operation_id="notifications_start_telegram_link",
    response_model=LinkStartOut,
    status_code=201,
)
async def start_telegram_link(request: Request, actor: Actor, _: CanLink) -> dict[str, Any]:
    started = await notifications_module(request).links.start(actor)
    return started.as_json()


@router.get(
    "/notifications/telegram/status",
    operation_id="notifications_get_telegram_status",
    response_model=TelegramStatusOut,
)
async def get_telegram_status(request: Request, actor: Actor, _: CanLink) -> dict[str, Any]:
    return await notifications_module(request).links.status(actor)


@router.delete(
    "/notifications/telegram/link",
    operation_id="notifications_delete_telegram_link",
    status_code=204,
    response_class=Response,
)
async def delete_telegram_link(request: Request, actor: Actor, _: CanLink) -> Response:
    await notifications_module(request).links.unlink(actor, client_ip(request))
    return Response(status_code=204)


# --- settings (#69, #70) --------------------------------------------------------------------------
@router.get(
    "/notification-settings",
    operation_id="notifications_get_settings",
    response_model=NotificationSettingsOut,
)
async def get_notification_settings(request: Request, actor: Actor, _: CanManage) -> dict[str, Any]:
    return await notifications_module(request).settings.get(actor)


@router.patch(
    "/notification-settings",
    operation_id="notifications_update_settings",
    response_model=NotificationSettingsOut,
)
async def update_notification_settings(
    request: Request, body: NotificationSettingsPatchIn, actor: Actor, _: CanManage
) -> dict[str, Any]:
    items = [SettingIn(i.kind, i.enabled, i.time) for i in body.items]
    return await notifications_module(request).settings.update(actor, items, client_ip(request))


# --- log (#71) ------------------------------------------------------------------------------------
@router.get("/notifications-log", operation_id="notifications_list_log", response_model=LogPageOut)
async def list_notifications_log(
    request: Request,
    actor: Actor,
    _: CanManage,
    channel: Literal["telegram", "sms"] | None = None,
    status: Annotated[str | None, Query(max_length=32)] = None,
    cursor: Annotated[str | None, Query(max_length=128)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    return await notifications_module(request).settings.log_page(
        actor, channel=channel, status=status, cursor=cursor, limit=limit
    )


# --- Telegram webhook -------------------------------------------------------------------------------
@router.post("/notifications/telegram/webhook", include_in_schema=False)
async def telegram_webhook(request: Request) -> JSONResponse:
    module = notifications_module(request)
    given = request.headers.get(SECRET_HEADER, "")
    if module.webhook_secret is None or not hmac.compare_digest(
        given.encode(), module.webhook_secret.encode()
    ):
        raise AppError(ErrorCode.WEBHOOK_SIGNATURE_INVALID)
    try:
        update = await request.json()
    except ValueError:
        return JSONResponse({})
    if not isinstance(update, dict):
        return JSONResponse({})
    return JSONResponse(await module.links.handle_update(update))
