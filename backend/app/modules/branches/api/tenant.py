"""``/tenant/settings``, ``/tenant/tax-regimes``, ``/tenant/consents`` (20 #40a–#40c, #40h; BO-14)."""

from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from app.core.permissions import PermissionGrant
from app.modules.branches.api.deps import (
    Actor,
    branches_module,
    client_ip,
    has_permission,
    require_owner_permission,
)
from app.modules.branches.application.tenant_settings import TenantPatch

router = APIRouter(tags=["branches"])

TenantOwner = Annotated[PermissionGrant, Depends(require_owner_permission("settings.tenant"))]
StoreName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=100)]
LegalForm = Literal["llc", "jsc", "private_enterprise", "sole_proprietor"]
# vat_diff_tolerance_amount ≥ 0 (20 #40b), money string with 2 decimals (17 §3)
NonNegativeMoney = Annotated[str, StringConstraints(pattern=r"^\d{1,16}\.\d{2}$")]
BankAccount = Annotated[str, StringConstraints(pattern=r"^\d{20}$")]
BankMfo = Annotated[str, StringConstraints(pattern=r"^\d{5}$")]
TermsVersion = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]

SupplierOverpay = Literal["warn", "block"]
MarkingPrecheck = Literal["off", "warn", "block"]
DiscountPosting = Literal["gross_9050", "net"]
OwnerWithdrawalAccount = Literal["4890", "8720"]
CommissionAccount = Literal["9430", "9410"]
TurnoverTaxAccount = Literal["9430", "9820"]
NegativeStockPolicy = Literal["allow", "block"]
CardManualFallback = Literal["allow", "manager_approval", "forbid"]
TransferOverdueHours = Annotated[int, Field(ge=1, le=720, strict=True)]
DebtReceiptSplit = Literal["single", "per_sale"]
CreditSaleReceipt = Literal["none", "credit_type"]

_NON_NULLABLE = (
    "supplier_overpay_policy",
    "vat_diff_tolerance_amount",
    "marking_precheck",
    "discount_posting",
    "owner_withdrawal_account",
    "payment_org_commission_account",
    "turnover_tax_account",
    "negative_stock_policy",
    "ai_training_consent",
    "fiscal_policy",
    "card_manual_fallback",
    "transfer_overdue_hours",
)


def _not_null(value: Any) -> Any:
    if value is None:
        raise ValueError("null is not allowed")
    return value


class FiscalPolicyIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    debt_receipt_split: DebtReceiptSplit | None = None
    credit_sale_receipt: CreditSaleReceipt | None = None

    _check = field_validator("debt_receipt_split", "credit_sale_receipt", mode="before")(_not_null)


class SettingsPatchIn(BaseModel):
    """``tenants.settings`` keys PATCH may change; ``ai_cross_border_enabled`` is rejected (extra=forbid)."""

    model_config = ConfigDict(extra="forbid")

    bank_account: BankAccount | None = None
    bank_mfo: BankMfo | None = None
    supplier_overpay_policy: SupplierOverpay | None = None
    vat_diff_tolerance_amount: NonNegativeMoney | None = None
    marking_precheck: MarkingPrecheck | None = None
    discount_posting: DiscountPosting | None = None
    owner_withdrawal_account: OwnerWithdrawalAccount | None = None
    payment_org_commission_account: CommissionAccount | None = None
    turnover_tax_account: TurnoverTaxAccount | None = None
    negative_stock_policy: NegativeStockPolicy | None = None
    ai_training_consent: bool | None = None
    fiscal_policy: FiscalPolicyIn | None = None
    card_manual_fallback: CardManualFallback | None = None
    transfer_overdue_hours: TransferOverdueHours | None = None

    _check = field_validator(*_NON_NULLABLE, mode="before")(_not_null)


class TenantSettingsPatchIn(BaseModel):
    """``go_live_date``, ``accepted_terms_*``, ``ai_cross_border_enabled`` are not accepted (QT-M17-08)."""

    model_config = ConfigDict(extra="forbid")

    name: StoreName | None = None
    legal_form: LegalForm | None = None
    settings: SettingsPatchIn | None = None
    version: int

    _check = field_validator("name", "legal_form", "settings", mode="before")(_not_null)


class TaxRegimeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    regime: Literal["vat", "turnover"]
    valid_from: date


class ConsentIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    purpose: Literal["ai_cross_border"]
    terms_version: TermsVersion
    accepted: bool


class FiscalPolicyOut(BaseModel):
    debt_receipt_split: DebtReceiptSplit
    credit_sale_receipt: CreditSaleReceipt


class SettingsOut(BaseModel):
    bank_account: str | None
    bank_mfo: str | None
    supplier_overpay_policy: SupplierOverpay
    vat_diff_tolerance_amount: str
    marking_precheck: MarkingPrecheck
    discount_posting: DiscountPosting
    owner_withdrawal_account: OwnerWithdrawalAccount
    payment_org_commission_account: CommissionAccount
    turnover_tax_account: TurnoverTaxAccount
    negative_stock_policy: NegativeStockPolicy
    ai_training_consent: bool
    ai_cross_border_enabled: bool
    card_manual_fallback: CardManualFallback
    transfer_overdue_hours: int = Field(
        description="QT-M06-05: a sent transfer is overdue after this many hours"
    )
    fiscal_policy: FiscalPolicyOut


class TenantSettingsOut(BaseModel):
    name: str
    legal_form: LegalForm
    go_live_date: date | None
    accepted_terms_version: str | None
    accepted_terms_at: datetime | None
    settings: SettingsOut
    version: int


class TaxRegimeOut(BaseModel):
    regime: Literal["vat", "turnover"]
    valid_from: date


class TaxRegimeBlockOut(BaseModel):
    current: Literal["vat", "turnover"] | None
    history: list[TaxRegimeOut]


class IntegrationOut(BaseModel):
    status: Literal["connected", "not_connected"]
    connected_at: datetime | None


class OfdOut(BaseModel):
    status: Literal["connected", "not_connected"]


class CrptOut(BaseModel):
    status: Literal["connected", "not_connected"]
    key_last4: str | None


class UzqrOut(IntegrationOut):
    cash_register_ids: list[str]


class IntegrationsOut(BaseModel):
    ofd: OfdOut
    faktura_uz: IntegrationOut
    crpt: CrptOut
    click: IntegrationOut
    payme: IntegrationOut
    uzum: IntegrationOut
    uzqr: UzqrOut


class TenantSettingsFullOut(TenantSettingsOut):
    tax_regime: TaxRegimeBlockOut
    integrations: IntegrationsOut


class ConsentOut(BaseModel):
    purpose: Literal["ai_cross_border"]
    terms_version: str
    accepted: bool
    at: datetime | None
    ai_cross_border_enabled: bool


@router.get("/tenant/settings", operation_id="tenant_settings_get", response_model=TenantSettingsFullOut)
async def get_tenant_settings(request: Request, _: TenantOwner, actor: Actor) -> TenantSettingsFullOut:
    body = await branches_module(request).tenant_settings.get(actor)
    return TenantSettingsFullOut.model_validate(body)


@router.patch("/tenant/settings", operation_id="tenant_settings_update", response_model=TenantSettingsOut)
async def update_tenant_settings(
    request: Request, body: TenantSettingsPatchIn, actor: Actor
) -> TenantSettingsOut:
    # 20 #40b: settings.tenant (owner only); only vat_diff_tolerance_amount — tax.compare.review too
    if not await has_permission(request, actor, "settings.tenant"):
        only_tolerance = (
            body.model_fields_set == {"settings", "version"}
            and body.settings is not None
            and body.settings.model_fields_set == {"vat_diff_tolerance_amount"}
        )
        if not (only_tolerance and await has_permission(request, actor, "tax.compare.review")):
            raise AppError(ErrorCode.OWNER_ONLY, params={"permission": "settings.tenant"})
    settings = None
    if body.settings is not None:
        settings = body.settings.model_dump(exclude_unset=True)
        if body.settings.fiscal_policy is not None:
            settings["fiscal_policy"] = body.settings.fiscal_policy.model_dump(exclude_unset=True)
    patch = TenantPatch(version=body.version, name=body.name, legal_form=body.legal_form, settings=settings)
    result = await branches_module(request).tenant_settings.update(actor, patch, client_ip(request))
    return TenantSettingsOut.model_validate(result)


@router.post(
    "/tenant/tax-regimes",
    operation_id="tenant_tax_regimes_create",
    status_code=201,
    response_model=TaxRegimeOut,
)
async def create_tax_regime(
    request: Request, body: TaxRegimeIn, _: TenantOwner, actor: Actor
) -> TaxRegimeOut:
    result = await branches_module(request).tenant_settings.schedule_tax_regime(
        actor, body.regime, body.valid_from, client_ip(request)
    )
    return TaxRegimeOut.model_validate(asdict(result))


@router.post(
    "/tenant/consents", operation_id="tenant_consents_create", status_code=201, response_model=ConsentOut
)
async def create_consent(request: Request, body: ConsentIn, _: TenantOwner, actor: Actor) -> ConsentOut:
    result = await branches_module(request).tenant_settings.record_consent(
        actor, body.purpose, body.terms_version, body.accepted, client_ip(request)
    )
    return ConsentOut.model_validate(asdict(result))
