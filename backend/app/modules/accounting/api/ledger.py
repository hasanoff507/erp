"""Ledger entries (20 #9). Tag ``accounting`` (17 §11, M11)."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from app.core.auth.dependencies import require_subscription_ok
from app.core.auth.principal import Principal
from app.core.permissions import BranchScope, PermissionGrant, current_branch_scope, require_permission
from app.modules.accounting.application.module import AccountingModule
from app.modules.accounting.application.ports import JournalFilter

router = APIRouter(tags=["accounting"])

Actor = Annotated[Principal, Depends(require_subscription_ok)]
Scope = Annotated[BranchScope, Depends(current_branch_scope)]
CanPost = Annotated[PermissionGrant, Depends(require_permission("accounting.post"))]
Account = Annotated[str | None, Query(pattern=r"^[0-9]{4}$")]


class LedgerEntryOut(BaseModel):
    id: UUID
    entry_date: date
    account_dt: str
    account_kt: str
    amount: str = Field(description="Decimal string, 2 dp (always > 0)")
    branch_id: UUID | None
    doc_type: str
    doc_id: UUID
    doc_number: str | None = Field(description="Number of the source document (BO-08), null for drafts")
    analytics: dict[str, Any]
    reversal_of_id: UUID | None


class LedgerEntryPage(BaseModel):
    items: list[LedgerEntryOut]
    next_cursor: str | None


def accounting_module(request: Request) -> AccountingModule:
    module: AccountingModule | None = getattr(request.app.state, "accounting", None)
    if module is None:
        raise RuntimeError("accounting module is not configured (app.state.accounting)")
    return module


@router.get("/ledger-entries", operation_id="accounting_list_ledger_entries", response_model=LedgerEntryPage)
async def list_ledger_entries(
    request: Request,
    actor: Actor,
    scope: Scope,
    _: CanPost,
    account_dt: Account = None,
    account_kt: Account = None,
    entry_date__gte: date | None = None,
    entry_date__lte: date | None = None,
    branch_id: UUID | None = None,
    doc_type: Annotated[str | None, Query(max_length=64)] = None,
    doc_id: UUID | None = None,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    flt = JournalFilter(
        entry_date_gte=entry_date__gte,
        entry_date_lte=entry_date__lte,
        account_dt=account_dt,
        account_kt=account_kt,
        doc_type=doc_type,
        doc_id=doc_id,
    )
    return await accounting_module(request).journal.page(actor, scope, flt, branch_id, cursor, limit)
