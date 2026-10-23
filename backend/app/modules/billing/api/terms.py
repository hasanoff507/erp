"""``GET /auth/terms`` — current Terms of Use / consent versions (public, no session).

The spec names no read endpoint, but ``/auth/signup`` (14 §20) and ``POST /tenant/consents``
(20 #40h) reject anything but the current version, so the SPA must be able to read it.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.core.db.session import Database
from app.modules.billing.wiring import current_terms

router = APIRouter(tags=["auth"])

TermsKind = Literal["terms", "privacy", "ai_cross_border"]


class TermsVersionOut(BaseModel):
    kind: TermsKind
    version: str
    text_url: str
    text_sha256: str
    effective_from: datetime


class TermsListOut(BaseModel):
    items: list[TermsVersionOut]


@router.get("/auth/terms", operation_id="auth_terms_current", response_model=TermsListOut)
async def terms_current(request: Request) -> TermsListOut:
    db: Database = request.app.state.db
    rows = await current_terms(db.session_factory)
    return TermsListOut(
        items=[
            TermsVersionOut(
                kind=r.kind,
                version=r.version,
                text_url=r.text_url,
                text_sha256=r.text_sha256,
                effective_from=r.effective_from,
            )
            for r in rows
        ]
    )
