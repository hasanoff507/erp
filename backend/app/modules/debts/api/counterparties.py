"""Counterparties (18 §11.2–11.4 — single source of the resource; 19 §9 supplier view). Tag ``debts`` (M08).

Permissions (18 §11, 19 §9):

* ``GET`` list / one — any of ``sales.create``, ``debts.create``, ``stock.view``, ``purchases.create``;
* ``POST`` — by body: supplier → ``purchases.create``; quick customer (name+phone) → ``debts.create``;
  full customer (STIR, bank, limit) → ``debts.limit.manage``;
* ``PATCH`` — ``debts.limit.manage``, or ``purchases.create`` on a supplier (never limit/discount);
* ``archive``/``unarchive`` — ``debts.limit.manage`` or ``debts.create``; ``purchases.create`` on a supplier
  only (18 §11.4); ``lookup-by-stir`` — ``purchases.create``; ``debt-balance`` — ``stock.view``.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.core.auth.dependencies import auth_gateway, require_subscription_ok
from app.core.auth.principal import Principal
from app.core.error_codes import ErrorCode
from app.core.errors import AppError, ErrorDetail
from app.core.money import MoneyStr, PercentStr
from app.core.permissions import PermissionGrant, require_permission
from app.modules.debts.application.counterparties import WRITE_PERMISSIONS
from app.modules.debts.application.module import DebtsModule
from app.modules.debts.application.ports import CounterpartyFilter
from app.modules.debts.domain.counterparties import search_digits

router = APIRouter(tags=["debts"])

Actor = Annotated[Principal, Depends(require_subscription_ok)]
Name = Annotated[str, StringConstraints(min_length=1, max_length=255)]
Phone = Annotated[str, StringConstraints(max_length=32)]
Stir = Annotated[str, StringConstraints(max_length=32)]
Address = Annotated[str, StringConstraints(max_length=500)]
BankField = Annotated[str, StringConstraints(max_length=64)]
Note = Annotated[str, StringConstraints(max_length=1000)]
Kind = Literal["person", "company"]

READ_PERMISSIONS = ("sales.create", "debts.create", "stock.view", "purchases.create")


async def granted(request: Request, principal: Principal, codes: tuple[str, ...]) -> frozenset[str]:
    """The subset of ``codes`` the caller holds (token scope prefix + live ``role_permissions``, 15 §2)."""
    gateway = auth_gateway(request)
    out: set[str] = set()
    for code in codes:
        if principal.has_scope(code.split(".", 1)[0]) and await gateway.permission_limits(principal, code):
            out.add(code)
    return frozenset(out)


def require_any(*codes: str) -> Callable[..., Awaitable[frozenset[str]]]:
    async def dependency(request: Request, principal: Actor) -> frozenset[str]:
        found = await granted(request, principal, codes)
        if not found:
            raise AppError(
                ErrorCode.PERMISSION_DENIED, params={"permission": codes[0], "any_of": list(codes)}
            )
        return found

    dependency.__name__ = "require_any_" + "_".join(c.replace(".", "_") for c in codes)
    return dependency


CanRead = Annotated[frozenset[str], Depends(require_any(*READ_PERMISSIONS))]
CanWrite = Annotated[frozenset[str], Depends(require_any(*WRITE_PERMISSIONS))]
CanPurchase = Annotated[PermissionGrant, Depends(require_permission("purchases.create"))]
CanViewStock = Annotated[PermissionGrant, Depends(require_permission("stock.view"))]
PageNo = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=200)]


# --- schemas --------------------------------------------------------------------------------------
class CounterpartyOut(BaseModel):
    id: UUID
    kind: Kind
    name: str
    phone: str | None
    stir: str | None
    legal_address: str | None
    bank_account: str | None
    bank_mfo: str | None
    vat_payer: bool | None
    is_customer: bool
    is_supplier: bool
    credit_limit: str | None = Field(description="Money (2 dp); null = no limit")
    standing_discount_pct: str | None
    notify_consent: bool
    notify_consent_at: str | None = Field(description="Set by the server when notify_consent becomes true")
    note: str | None
    archived_at: str | None
    created_at: str
    updated_at: str
    version: int


class CounterpartyListItem(CounterpartyOut):
    receivable_balance: str = Field(description="debt_balances receivable (2 dp), 0.00 without moves")
    payable_balance: str = Field(description="debt_balances payable (2 dp), 0.00 without moves")


class CounterpartyPage(BaseModel):
    items: list[CounterpartyListItem]
    total: int
    page: int
    size: int


class CounterpartyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Kind
    name: Name
    phone: Phone | None = Field(
        default=None, description="Required for a customer (18 §11.2); +998… or E.164"
    )
    stir: Stir | None = Field(default=None, description="9 digits; required for kind=company (19 §9)")
    legal_address: Address | None = None
    bank_account: BankField | None = None
    bank_mfo: BankField | None = None
    vat_payer: bool | None = None
    is_customer: bool | None = Field(default=None, description="Default: true unless is_supplier=true")
    is_supplier: bool = False
    credit_limit: MoneyStr | None = None
    standing_discount_pct: PercentStr | None = None
    notify_consent: bool = False
    note: Note | None = None


class CounterpartyUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(ge=1)
    kind: Kind | None = None
    name: Name | None = None
    phone: Phone | None = None
    stir: Stir | None = None
    legal_address: Address | None = None
    bank_account: BankField | None = None
    bank_mfo: BankField | None = None
    vat_payer: bool | None = None
    is_customer: bool | None = None
    is_supplier: bool | None = None
    credit_limit: MoneyStr | None = None
    standing_discount_pct: PercentStr | None = None
    notify_consent: bool | None = None
    note: Note | None = None


class ArchiveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Note | None = None


class DebtBalanceOut(BaseModel):
    payable: str
    receivable: str


class StirLookupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stir: Annotated[str, StringConstraints(min_length=1, max_length=32)]


class StirLookupOut(BaseModel):
    stir: str
    kind: Literal["company"]
    name: str
    legal_address: str | None
    bank_account: str | None
    bank_mfo: str | None
    vat_payer: bool | None
    director_name: str | None
    existing_counterparty_id: UUID | None = Field(
        description="This tenant's counterparty with the same STIR, if any (suggestion only; nothing saved)"
    )


_NOT_NULL_ON_PATCH = frozenset({"kind", "name", "is_customer", "is_supplier", "notify_consent"})
_DECIMAL_FIELDS = frozenset({"credit_limit", "standing_discount_pct"})


def debts_module(request: Request) -> DebtsModule:
    module: DebtsModule | None = getattr(request.app.state, "debts", None)
    if module is None:
        raise RuntimeError("debts module is not configured (app.state.debts)")
    return module


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _decimals(values: dict[str, Any]) -> dict[str, Any]:
    return {k: (Decimal(v) if k in _DECIMAL_FIELDS and v is not None else v) for k, v in values.items()}


# --- routes ---------------------------------------------------------------------------------------
@router.get("/counterparties", operation_id="debts_list_counterparties", response_model=CounterpartyPage)
async def list_counterparties(
    request: Request,
    actor: Actor,
    _: CanRead,
    search: Annotated[str | None, Query(max_length=255)] = None,
    kind: Kind | None = None,
    is_supplier: bool | None = None,
    is_customer: bool | None = None,
    archived: bool = False,
    page: PageNo = 1,
    size: PageSize = 50,
) -> dict[str, Any]:
    query = (search or "").strip() or None
    flt = CounterpartyFilter(
        search=query,
        search_digits=search_digits(query) if query else None,
        kind=kind,
        is_supplier=is_supplier,
        is_customer=is_customer,
        archived=archived,
    )
    result = await debts_module(request).counterparties.list_page(actor, flt, page, size)
    return result.as_json()


@router.post(
    "/counterparties",
    operation_id="debts_create_counterparty",
    response_model=CounterpartyOut,
    status_code=201,
)
async def create_counterparty(
    request: Request, response: Response, body: CounterpartyCreate, actor: Actor, grants: CanWrite
) -> dict[str, Any]:
    created = await debts_module(request).counterparties.create(
        actor, _decimals(body.model_dump()), grants, _ip(request)
    )
    response.headers["Location"] = f"{request.url.path}/{created['id']}"
    return created


@router.post(
    "/counterparties/lookup-by-stir",
    operation_id="debts_lookup_counterparty_by_stir",
    response_model=StirLookupOut,
    responses={503: {"description": "EINVOICE_PROVIDER_UNAVAILABLE — the e-invoice operator did not answer"}},
)
async def lookup_by_stir(
    request: Request, body: StirLookupRequest, actor: Actor, _: CanPurchase
) -> dict[str, Any]:
    return await debts_module(request).counterparties.lookup_by_stir(actor, body.stir)


@router.get(
    "/counterparties/{counterparty_id}", operation_id="debts_get_counterparty", response_model=CounterpartyOut
)
async def get_counterparty(
    request: Request, counterparty_id: UUID, actor: Actor, _: CanRead
) -> dict[str, Any]:
    return await debts_module(request).counterparties.get(actor, counterparty_id)


@router.patch(
    "/counterparties/{counterparty_id}",
    operation_id="debts_update_counterparty",
    response_model=CounterpartyOut,
)
async def update_counterparty(
    request: Request, counterparty_id: UUID, body: CounterpartyUpdate, actor: Actor, grants: CanWrite
) -> dict[str, Any]:
    changes = {k: getattr(body, k) for k in body.model_fields_set if k != "version"}
    for field in sorted(_NOT_NULL_ON_PATCH & changes.keys()):
        if changes[field] is None:
            raise AppError(
                ErrorCode.VALIDATION_ERROR,
                details=[ErrorDetail(field=field, message_key="validation.required")],
            )
    return await debts_module(request).counterparties.update(
        actor, counterparty_id, body.version, _decimals(changes), grants, _ip(request)
    )


@router.post(
    "/counterparties/{counterparty_id}/archive",
    operation_id="debts_archive_counterparty",
    response_model=CounterpartyOut,
)
async def archive_counterparty(
    request: Request,
    counterparty_id: UUID,
    actor: Actor,
    grants: CanWrite,
    body: ArchiveRequest | None = None,
) -> dict[str, Any]:
    return await debts_module(request).counterparties.set_archived(
        actor, counterparty_id, True, body.reason if body else None, grants, _ip(request)
    )


@router.post(
    "/counterparties/{counterparty_id}/unarchive",
    operation_id="debts_unarchive_counterparty",
    response_model=CounterpartyOut,
)
async def unarchive_counterparty(
    request: Request,
    counterparty_id: UUID,
    actor: Actor,
    grants: CanWrite,
    body: ArchiveRequest | None = None,
) -> dict[str, Any]:
    return await debts_module(request).counterparties.set_archived(
        actor, counterparty_id, False, body.reason if body else None, grants, _ip(request)
    )


@router.get(
    "/counterparties/{counterparty_id}/debt-balance",
    operation_id="debts_get_counterparty_debt_balance",
    response_model=DebtBalanceOut,
)
async def get_debt_balance(
    request: Request, counterparty_id: UUID, actor: Actor, _: CanViewStock
) -> dict[str, str]:
    return await debts_module(request).counterparties.debt_balance(actor, counterparty_id)
