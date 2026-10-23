"""Catalog API dependencies."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from app.core.auth.dependencies import require_subscription_ok
from app.core.auth.principal import Principal
from app.core.permissions import PermissionGrant, require_permission
from app.modules.catalog.application.module import CatalogModule

Actor = Annotated[Principal, Depends(require_subscription_ok)]
CanView = Annotated[PermissionGrant, Depends(require_permission("stock.view"))]
CanManage = Annotated[PermissionGrant, Depends(require_permission("catalog.manage"))]


def catalog_module(request: Request) -> CatalogModule:
    module: CatalogModule | None = getattr(request.app.state, "catalog", None)
    if module is None:
        raise RuntimeError("catalog module is not configured (app.state.catalog)")
    return module


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None
