"""``POST /marking-codes/verify`` — pre-sale marking code check (18 §15; B5-EP-18#36).

Tag ``sales``, US-M01-03.

Permission ``sales.create``; ``Idempotency-Key`` (a POS REST write: the ``warn`` audit). Synchronous, CRPT
timeout 3 s, no retry; nothing about the code is stored (21 §4.1).
"""

from __future__ import annotations

from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from app.core.auth.dependencies import require_subscription_ok
from app.core.auth.principal import Principal
from app.core.permissions import PermissionGrant, require_permission
from app.modules.integrations.marking.wiring import MarkingModule, VerifyRequest

router = APIRouter(tags=["sales"])

Actor = Annotated[Principal, Depends(require_subscription_ok)]
CanSell = Annotated[PermissionGrant, Depends(require_permission("sales.create"))]


class MarkingVerifyIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(
        min_length=1, max_length=512, description="DataMatrix raw value, GS (\\u001d) kept as is"
    )
    product_id: UUID | None = None


class MarkingVerifyDetails(BaseModel):
    gtin: str | None
    serial: str | None
    reason: (
        Literal["already_sold", "expired", "not_found", "written_off", "returned_to_supplier", "not_owner"]
        | None
    ) = None


class MarkingVerifyOut(BaseModel):
    valid: bool | None = Field(
        description="true — valid; false — CRPT rejected it; null — CRPT did not answer"
    )
    status: str | None
    details: MarkingVerifyDetails
    warnings: list[str]


def marking_module(request: Request) -> MarkingModule:
    module: MarkingModule | None = getattr(request.app.state, "marking", None)
    if module is None:
        raise RuntimeError("marking module is not configured (app.state.marking)")
    return module


@router.post(
    "/marking-codes/verify",
    operation_id="sales_verify_marking_code",
    response_model=MarkingVerifyOut,
    responses={
        409: {"description": "MARKING_CODE_ALREADY_SOLD / MARKING_VERIFY_FAILED (block)"},
        422: {"description": "MARKING_CODE_INVALID / VALIDATION_ERROR"},
        503: {"description": "MARKING_VERIFY_UNAVAILABLE (block)"},
    },
)
async def verify_marking_code(
    request: Request, body: MarkingVerifyIn, actor: Actor, _: CanSell
) -> dict[str, Any]:
    return await marking_module(request).verify.verify(actor, VerifyRequest(body.code, body.product_id))
