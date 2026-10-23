"""Shared dependencies of the e-documents routers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, Request
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.core.auth.dependencies import auth_gateway, require_subscription_ok
from app.core.auth.principal import Principal
from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from app.modules.integrations.einvoice.wiring import EDocsModule

Reason = Annotated[str, StringConstraints(min_length=1, max_length=1000)]
ChallengeId = Annotated[str, StringConstraints(min_length=1, max_length=128)]
Pkcs7 = Annotated[str, StringConstraints(min_length=1, max_length=2_000_000)]


def edocs(request: Request) -> EDocsModule:
    module: EDocsModule | None = getattr(request.app.state, "edocs", None)
    if module is None:
        raise RuntimeError("e-documents module is not configured (app.state.edocs)")
    return module


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


async def has_permission(request: Request, principal: Principal, code: str) -> bool:
    return principal.has_scope(code.split(".", 1)[0]) and bool(
        await auth_gateway(request).permission_limits(principal, code)
    )


def require_any(*codes: str) -> Callable[..., Awaitable[str]]:
    """``code₁`` **or** ``code₂`` …; returns the first granted code."""

    async def dependency(
        request: Request, principal: Annotated[Principal, Depends(require_subscription_ok)]
    ) -> str:
        for code in codes:
            if await has_permission(request, principal, code):
                return code
        raise AppError(ErrorCode.PERMISSION_DENIED, params={"permission": " | ".join(codes)})

    dependency.__name__ = "require_any_" + "_or_".join(c.replace(".", "_") for c in codes)
    return dependency


async def require(request: Request, principal: Principal, code: str) -> None:
    if not await has_permission(request, principal, code):
        raise AppError(ErrorCode.PERMISSION_DENIED, params={"permission": code})


class EmptyBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SignChallenge(BaseModel):
    document_hash: str = Field(
        description="SHA-256 hex; the browser signs THIS string (attached PKCS#7, 21 §5)"
    )
    challenge_id: str = Field(description="Single use, bound to the user, document and action; 10 min")
    expires_in: int


class SubmitSigned(BaseModel):
    model_config = ConfigDict(extra="forbid")

    challenge_id: ChallengeId
    signature_pkcs7: Pkcs7 = Field(description="base64 attached PKCS#7 from E-IMZO")


class Queued(BaseModel):
    id: str
    status: str
    job_id: str | None = None
