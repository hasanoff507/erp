"""Shop payments REST (18 §16; endpoint index #37–#39). Tag ``sales`` (M01).

* ``POST /payments/checkouts`` — ``sales.create`` or ``debts.payment.accept``; ``Idempotency-Key`` required.
* ``GET /payments/checkouts/{checkout_ref}`` — the same permissions; the POS polls it (every 2 s, qaror #54).
* ``POST /payments/webhooks/{provider}`` (``click``, ``payme``, ``uzqr``) and
  ``POST /payments/webhooks/uzum/{operation}`` (``check``/``create``/``confirm``/``reverse``/``status``) —
  called by the provider only: no session/CSRF, authenticated by the provider's signature with the tenant's
  merchant keys, ``Idempotency-Key``-exempt (deduplicated by ``provider_tx_id``), rate-limited per
  (provider, IP), not in the OpenAPI schema.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from redis.exceptions import RedisError

from app.core.auth.dependencies import auth_gateway, require_subscription_ok
from app.core.auth.principal import Principal
from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from app.core.money import MoneyStr, money
from app.core.permissions import BranchScope, current_branch_scope
from app.core.ratelimit import hit
from app.modules.integrations.payments.application.webhooks import (
    SignatureInvalidError,
    WebhookReply,
    WebhookRequest,
)
from app.modules.integrations.payments.wiring import PaymentsModule

log = structlog.get_logger(__name__)

router = APIRouter(tags=["sales"])

Actor = Annotated[Principal, Depends(require_subscription_ok)]
Scope = Annotated[BranchScope, Depends(current_branch_scope)]
CHECKOUT_PERMISSIONS = ("sales.create", "debts.payment.accept")
WINDOW_S = 60


def payments_module(request: Request) -> PaymentsModule:
    module: PaymentsModule | None = getattr(request.app.state, "payments", None)
    if module is None:
        raise RuntimeError("payments module is not wired (app.state.payments)")
    return module


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


async def _require_any(request: Request, principal: Principal) -> None:
    for code in CHECKOUT_PERMISSIONS:
        if principal.has_scope(code.split(".", 1)[0]) and await auth_gateway(request).permission_limits(
            principal, code
        ):
            return
    raise AppError(
        ErrorCode.PERMISSION_DENIED,
        params={"permission": CHECKOUT_PERMISSIONS[0], "any_of": list(CHECKOUT_PERMISSIONS)},
    )


class CheckoutIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    checkout_ref: UUID = Field(description="UUIDv7 from the device — later sale/debt payment checkout_ref")
    provider: Literal["uzqr", "click", "payme", "uzum"]
    cash_register_id: UUID
    amount: MoneyStr
    qr_type: Literal["static", "dynamic"] | None = Field(default=None, description="uzqr: only 'dynamic'")


class CheckoutOut(BaseModel):
    checkout_ref: UUID
    provider: Literal["uzqr", "click", "payme", "uzum"]
    provider_tx_id: str | None
    status: Literal["pending", "confirmed", "consumed", "failed", "expired"]
    amount: str
    qr_type: Literal["dynamic"] | None
    qr_payload: str | None = Field(description="QR content for the customer's phone")
    checkout_url: str | None
    confirmed_at: str | None
    expires_at: str


@router.post(
    "/payments/checkouts",
    operation_id="sales_create_payment_checkout",
    response_model=CheckoutOut,
    status_code=201,
)
async def create_payment_checkout(
    request: Request, body: CheckoutIn, actor: Actor, scope: Scope
) -> dict[str, Any]:
    await _require_any(request, actor)
    return await payments_module(request).checkouts.create(
        actor, scope, checkout_ref=body.checkout_ref, provider=body.provider,
        cash_register_id=body.cash_register_id, amount=money(body.amount), qr_type=body.qr_type,
        ip=_ip(request),
    )  # fmt: skip


@router.get(
    "/payments/checkouts/{checkout_ref}",
    operation_id="sales_get_payment_checkout",
    response_model=CheckoutOut,
)
async def get_payment_checkout(
    request: Request, checkout_ref: UUID, actor: Actor, scope: Scope
) -> dict[str, Any]:
    await _require_any(request, actor)
    return await payments_module(request).checkouts.get(actor, scope, checkout_ref, _ip(request))


# --- provider webhooks --------------------------------------------------------------------------------------


async def _webhook_request(request: Request, provider: str, module: PaymentsModule) -> WebhookRequest:
    ip = _ip(request)
    redis = getattr(request.app.state, "redis", None)
    if redis is not None:
        try:
            state = await hit(redis, f"rl:payments:webhook:{provider}:{ip}", WINDOW_S)
        except RedisError:
            state = None  # limiter unavailable: the signature check still guards every request
        if state is not None and state.count > module.webhook_rate_per_min:
            raise AppError(ErrorCode.RATE_LIMITED, headers={"Retry-After": str(state.retry_after_s)})
    return WebhookRequest(
        headers={k.lower(): v for k, v in request.headers.items()},
        body=await request.body(),
        ip=ip,
        content_type=request.headers.get("content-type", ""),
    )


def _json(reply: WebhookReply) -> JSONResponse:
    return JSONResponse(reply.body, status_code=reply.status_code, headers=dict(reply.headers))


@router.post("/payments/webhooks/uzum/{operation}", include_in_schema=False)
async def uzum_webhook(request: Request, operation: str) -> JSONResponse:
    module = payments_module(request)
    req = await _webhook_request(request, "uzum", module)
    return _json(await module.uzum.handle(operation, req))


@router.post("/payments/webhooks/{provider}", include_in_schema=False)
async def payment_webhook(request: Request, provider: str) -> JSONResponse:
    module = payments_module(request)
    if provider not in ("click", "payme", "uzqr"):
        raise AppError(ErrorCode.NOT_FOUND, params={"resource": "payment_providers"})
    req = await _webhook_request(request, provider, module)
    if provider == "click":
        return _json(await module.click.handle(req))
    if provider == "payme":
        return _json(await module.payme.handle(req))
    try:
        return _json(await module.uzqr.handle(req))
    except SignatureInvalidError:
        raise AppError(ErrorCode.WEBHOOK_SIGNATURE_INVALID) from None
