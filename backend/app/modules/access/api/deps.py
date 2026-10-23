"""Module-level dependencies of the access API."""

from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.requests import Request

if TYPE_CHECKING:
    from app.modules.access.wiring import AccessModule


def access_module(request: Request) -> AccessModule:
    module: AccessModule | None = getattr(request.app.state, "access_module", None)
    if module is None:
        raise RuntimeError("access module is not wired (app.state.access_module)")
    return module


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None
