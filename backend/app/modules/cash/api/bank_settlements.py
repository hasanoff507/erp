"""Bank settlements — BO-24 (20 #55a–#55h, 13 §2.18a, qaror #42). Tag ``cash``.

Every endpoint needs ``bank_settlements.manage``; writes need ``Idempotency-Key`` (17 §6). The statement
import is ``multipart/form-data`` (its path is in the ``BodyLimitMiddleware`` upload limits).
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, Request, Response, UploadFile
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.core.auth.dependencies import require_subscription_ok
from app.core.auth.principal import Principal
from app.core.error_codes import ErrorCode
from app.core.errors import AppError, ErrorDetail
from app.core.money import MoneyStr
from app.core.permissions import BranchScope, PermissionGrant, current_branch_scope, require_permission
from app.modules.cash.api.deps import cash_module, client_ip
from app.modules.cash.application.bank_import import BankStatementImportService
from app.modules.cash.application.bank_settlements import BankSettlementService

router = APIRouter(tags=["cash"])

Actor = Annotated[Principal, Depends(require_subscription_ok)]
Scope = Annotated[BranchScope, Depends(current_branch_scope)]
CanManage = Annotated[PermissionGrant, Depends(require_permission("bank_settlements.manage"))]
Method = Literal["card", "uzqr", "click", "payme", "uzum", "collection"]
Status = Literal["draft", "posted", "cancelled"]
Source = Literal["manual", "statement_import"]
Text = Annotated[str, StringConstraints(max_length=1000)]
Ref = Annotated[str, StringConstraints(min_length=1, max_length=100)]
_CHUNK = 1024 * 1024


def _bank(request: Request) -> BankSettlementService:
    service = cash_module(request).bank_settlements
    if service is None:
        raise RuntimeError("bank settlements are not configured")
    return service


def _imports(request: Request) -> BankStatementImportService:
    service = cash_module(request).bank_imports
    if service is None:
        raise RuntimeError("bank statement import is not configured")
    return service


# --- schemas --------------------------------------------------------------------------------------
class BankSettlementIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    branch_id: UUID
    doc_date: date = Field(description="Date the money reached the bank account (posting date)")
    method: Method
    settled_from: date
    settled_to: date = Field(description="settled_from ≤ settled_to ≤ doc_date")
    gross_amount: MoneyStr = Field(
        description="> 0 — closed out of 5710; ≤ the 5710 balance of branch × method"
    )
    commission_amount: MoneyStr = Field(default="0.00", description="≥ 0 and < gross_amount")
    variance_amount: MoneyStr = Field(
        default="0.00", description="Only method=collection: < 0 shortage (Dt 5910), > 0 surplus (Kt 9390)"
    )
    bank_ref: Ref | None = None
    attachment_id: UUID | None = Field(
        default=None, description="attachments.kind='import' — the statement file"
    )
    comment: Text | None = None


class BankSettlementPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gross_amount: MoneyStr | None = None
    commission_amount: MoneyStr | None = None
    variance_amount: MoneyStr | None = None
    settled_from: date | None = None
    settled_to: date | None = None
    bank_ref: Ref | None = None
    comment: Text | None = None
    version: int = Field(ge=1)


class BankSettlementCancel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Annotated[str, StringConstraints(min_length=1, max_length=1000)]


class EmptyBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BankSettlementOut(BaseModel):
    id: UUID
    number: str | None
    branch_id: UUID
    doc_date: str
    status: Status
    source: Source
    method: Method
    settled_from: str
    settled_to: str
    gross_amount: str
    commission_amount: str
    variance_amount: str
    net_amount: str
    bank_ref: str | None
    attachment_id: UUID | None
    statement_import_id: UUID | None
    comment: str | None
    created_by: UUID
    created_at: str
    posted_at: str | None
    cancelled_at: str | None
    cancelled_by: UUID | None
    cancel_reason: str | None
    version: int


class LedgerRowOut(BaseModel):
    id: UUID
    entry_date: str
    account_dt: str
    account_kt: str
    amount: str
    analytics: dict[str, Any]
    reversal_of_id: UUID | None


class BankSettlementDetail(BankSettlementOut):
    ledger_entries: list[LedgerRowOut]


class BankSettlementPage(BaseModel):
    items: list[BankSettlementOut]
    next_cursor: str | None


class CardBreakdown(BaseModel):
    integrated: str
    manual: str


class TransitBalance(BaseModel):
    branch_id: UUID
    method: Method
    balance: str
    oldest_unsettled_date: str | None
    card_breakdown: CardBreakdown | None


class TransitBalances(BaseModel):
    as_of: str
    items: list[TransitBalance]


class UnmatchedLine(BaseModel):
    line_no: int
    number: str
    date: str
    amount: str
    payer_name: str | None
    purpose: str
    reason: Literal["no_transit_match", "unknown_method", "branch_ambiguous", "commission_invalid"]


class UnmatchedCardTransaction(BaseModel):
    card_terminal_transaction_id: UUID
    rrn: str
    amount: str
    business_date: str


class BankImportResult(BaseModel):
    import_id: UUID
    file_sha256: str
    account: str
    period_from: str | None
    period_to: str | None
    drafts_created: int
    draft_ids: list[UUID]
    duplicates: int
    ignored_outgoing: int
    unmatched_lines: list[UnmatchedLine]
    unmatched_card_transactions: list[UnmatchedCardTransaction] = Field(
        description="Integrated card purchases of the matched days missing from the acquirer RRN registry"
    )


# --- routes ---------------------------------------------------------------------------------------
@router.get("/bank-settlements", operation_id="cash_list_bank_settlements", response_model=BankSettlementPage)
async def list_bank_settlements(
    request: Request,
    actor: Actor,
    scope: Scope,
    _: CanManage,
    branch_id: UUID | None = None,
    method: Method | None = None,
    status: Status | None = None,
    source: Source | None = None,
    doc_date_gte: Annotated[date | None, Query(alias="doc_date__gte")] = None,
    doc_date_lte: Annotated[date | None, Query(alias="doc_date__lte")] = None,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    return await _bank(request).list_page(
        actor,
        scope,
        branch_id=branch_id,
        method=method,
        status=status,
        source=source,
        date_from=doc_date_gte,
        date_to=doc_date_lte,
        cursor=cursor,
        limit=limit,
    )


@router.get(
    "/bank-settlements/transit-balances",
    operation_id="cash_get_bank_settlement_transit_balances",
    response_model=TransitBalances,
)
async def transit_balances(
    request: Request,
    actor: Actor,
    scope: Scope,
    _: CanManage,
    as_of: date | None = None,
    branch_id: UUID | None = None,
) -> dict[str, Any]:
    return await _bank(request).transit_balances(actor, scope, as_of=as_of, branch_id=branch_id)


@router.post(
    "/bank-settlements",
    operation_id="cash_create_bank_settlement",
    response_model=BankSettlementOut,
    status_code=201,
)
async def create_bank_settlement(
    request: Request, response: Response, body: BankSettlementIn, actor: Actor, scope: Scope, _: CanManage
) -> dict[str, Any]:
    result = await _bank(request).create(actor, scope, body.model_dump(), client_ip(request))
    response.headers["Location"] = f"{request.url.path}/{result['id']}"
    return result


async def _read_limited(upload: UploadFile, limit: int) -> bytes:
    chunks: list[bytes] = []
    size = 0
    while chunk := await upload.read(_CHUNK):
        size += len(chunk)
        if size > limit:
            raise AppError(ErrorCode.FILE_TOO_LARGE, params={"max_bytes": limit})
        chunks.append(chunk)
    return b"".join(chunks)


@router.post(
    "/bank-settlements/imports",
    operation_id="cash_import_bank_statement",
    response_model=BankImportResult,
    status_code=201,
)
async def import_bank_statement(
    request: Request,
    actor: Actor,
    scope: Scope,
    _: CanManage,
    file: Annotated[UploadFile, File(description="1CClientBankExchange .txt (≤ 10 MB, ≤ 20 000 lines)")],
    branch_id: Annotated[UUID | None, Form()] = None,
) -> dict[str, Any]:
    service = _imports(request)
    content = await _read_limited(file, service.limits.max_bytes)
    return await service.upload(
        actor,
        scope,
        filename=file.filename,
        content_type=file.content_type,
        content=content,
        branch_id=branch_id,
        ip=client_ip(request),
    )


@router.get(
    "/bank-settlements/{settlement_id}",
    operation_id="cash_get_bank_settlement",
    response_model=BankSettlementDetail,
)
async def get_bank_settlement(
    request: Request, settlement_id: UUID, actor: Actor, scope: Scope, _: CanManage
) -> dict[str, Any]:
    return await _bank(request).get(actor, scope, settlement_id)


@router.patch(
    "/bank-settlements/{settlement_id}",
    operation_id="cash_update_bank_settlement",
    response_model=BankSettlementOut,
)
async def update_bank_settlement(
    request: Request, settlement_id: UUID, body: BankSettlementPatch, actor: Actor, scope: Scope, _: CanManage
) -> dict[str, Any]:
    changes = body.model_dump(exclude_unset=True)
    for key in ("gross_amount", "commission_amount", "variance_amount", "settled_from", "settled_to"):
        if key in changes and changes[key] is None:
            raise AppError(
                ErrorCode.VALIDATION_ERROR,
                details=[ErrorDetail(field=key, message_key="validation.required")],
            )
    changes["version"] = body.version
    return await _bank(request).update(actor, scope, settlement_id, changes, client_ip(request))


@router.post(
    "/bank-settlements/{settlement_id}/post",
    operation_id="cash_post_bank_settlement",
    response_model=BankSettlementOut,
)
async def post_bank_settlement(
    request: Request,
    settlement_id: UUID,
    actor: Actor,
    scope: Scope,
    _: CanManage,
    body: EmptyBody | None = None,
) -> dict[str, Any]:
    del body
    return await _bank(request).post(actor, scope, settlement_id, client_ip(request))


@router.post(
    "/bank-settlements/{settlement_id}/cancel",
    operation_id="cash_cancel_bank_settlement",
    response_model=BankSettlementOut,
)
async def cancel_bank_settlement(
    request: Request,
    settlement_id: UUID,
    body: BankSettlementCancel,
    actor: Actor,
    scope: Scope,
    _: CanManage,
) -> dict[str, Any]:
    return await _bank(request).cancel(actor, scope, settlement_id, body.reason, client_ip(request))
