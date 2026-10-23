"""Module-level dependencies of the auth API."""

from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.requests import Request

if TYPE_CHECKING:
    from app.modules.auth.wiring import AuthModule


def auth_module(request: Request) -> AuthModule:
    module: AuthModule | None = getattr(request.app.state, "auth_module", None)
    if module is None:
        raise RuntimeError("auth module is not wired (app.state.auth_module)")
    return module
