"""Integration keys REST (20 #40d/#40e; BO-14). Tag ``branches`` (tenant settings).

``PUT /tenant/integrations/{provider}`` — store/replace the tenant's own merchant/operator credentials,
``DELETE`` — disconnect. ``settings.tenant``, ``Idempotency-Key`` required (17 §6). Secrets are write-only.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.core.auth.dependencies import require_subscription_ok
from app.core.auth.principal import Principal
from app.core.permissions import PermissionGrant, require_permission
from app.modules.integrations.tenant_keys.application.service import (
    IntegrationInput,
    TenantIntegrationsService,
)

router = APIRouter(tags=["branches"])

Actor = Annotated[Principal, Depends(require_subscription_ok)]
CanManage = Annotated[PermissionGrant, Depends(require_permission("settings.tenant"))]
Provider = Literal["faktura-uz", "didox", "crpt", "click", "payme", "uzum", "uzqr"]
Secret = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=512)]
_FLAGS = ("provider_autofiscal_disabled_confirmed", "cash_register_id")


def integrations_module(request: Request) -> TenantIntegrationsService:
    module: TenantIntegrationsService | None = getattr(request.app.state, "tenant_integrations", None)
    if module is None:
        raise RuntimeError("tenant integrations are not wired (app.state.tenant_integrations)")
    return module


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


class IntegrationKeysIn(BaseModel):
    """20 #40d — the fields of the chosen provider only (others → ``VALIDATION_ERROR``)."""

    model_config = ConfigDict(extra="forbid")

    login: Secret | None = None
    password: Secret | None = None
    client_id: Secret | None = None
    client_secret: Secret | None = None
    api_key: Secret | None = None
    merchant_id: Secret | None = None
    service_id: Secret | None = None
    secret_key: Secret | None = None
    merchant_user_id: Secret | None = None
    key: Secret | None = None
    test_mode: bool | None = Field(default=None, description="payme: checkout.test.paycom.uz (sandbox)")
    terminal_id: Secret | None = None
    dynamic_qr_service_id: Secret | None = None
    dynamic_qr_user_id: Secret | None = None
    dynamic_qr_secret_key: Secret | None = None
    cash_register_id: UUID | None = Field(default=None, description="uzqr: per cash register key")
    provider_autofiscal_disabled_confirmed: bool | None = Field(
        default=None, description="click/payme/uzum: provider-side auto-fiscalisation is OFF (must be true)"
    )


class IntegrationOut(BaseModel):
    provider: Provider
    status: Literal["connected"]
    connected_at: str


@router.put(
    "/tenant/integrations/{provider}",
    operation_id="branches_put_tenant_integration",
    response_model=IntegrationOut,
)
async def put_tenant_integration(
    request: Request, provider: str, body: IntegrationKeysIn, actor: Actor, _: CanManage
) -> dict[str, Any]:
    fields = {k: getattr(body, k) for k in body.model_fields_set if k not in _FLAGS}
    data = IntegrationInput(
        fields=fields,
        cash_register_id=body.cash_register_id,
        autofiscal_confirmed=body.provider_autofiscal_disabled_confirmed,
    )
    return await integrations_module(request).put(actor, provider, data, _ip(request))


@router.delete(
    "/tenant/integrations/{provider}",
    operation_id="branches_delete_tenant_integration",
    status_code=204,
    response_class=Response,
)
async def delete_tenant_integration(
    request: Request, provider: str, actor: Actor, _: CanManage, cash_register_id: UUID | None = None
) -> Response:
    await integrations_module(request).delete(actor, provider, cash_register_id, _ip(request))
    return Response(status_code=204)
