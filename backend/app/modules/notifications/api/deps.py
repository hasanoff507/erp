"""Shared API dependencies of the notifications module."""

from __future__ import annotations

from fastapi import Request

from app.modules.notifications.wiring import NotificationsModule


def notifications_module(request: Request) -> NotificationsModule:
    module: NotificationsModule | None = getattr(request.app.state, "notifications", None)
    if module is None:
        raise RuntimeError("notifications module is not configured (app.state.notifications)")
    return module


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None
