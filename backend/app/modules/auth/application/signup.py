"""Self-service signup (US-M17-01, 14 §20 ``/auth/signup``, 15 §1.5, 07 BO-21 ①②).

One ``tenant_transaction`` creates everything a new tenant needs — a failure anywhere rolls all of
it back (no half tenant): ``tenants`` (+ terms acceptance), ``users`` + ``user_credentials``
(argon2id via ``app.auth_set_credentials``, same session), the owner ``memberships`` (all
branches), the 5 system roles with the default matrix, default branch ``01`` + warehouse + cash
register, the standard expense categories, ``subscriptions(trial, 30 days)``,
``valuation_method_history(aveco)``, ``consents`` and, for the Google path, ``user_identities``.

The phone is proven by a verified ``purpose=signup`` OTP challenge: its single-use ticket is bound
to (phone, purpose) and is consumed right before COMMIT, so a failed signup does not burn it and a
replay cannot create a second tenant.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Final, Literal
from uuid import UUID

import structlog
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.audit import record_audit
from app.core.db.base import uuid7
from app.core.db.session import tenant_transaction
from app.core.error_codes import ErrorCode
from app.core.errors import AppError, ErrorDetail
from app.core.ratelimit import hit
from app.modules.auth.application.otp import OtpService
from app.modules.auth.application.passwords import hash_password
from app.modules.auth.application.ports import (
    AuthStore,
    GoogleIdentity,
    NewTenant,
    SignupStore,
    TenantProvisioning,
)
from app.modules.branches.domain.model import tashkent_today

log = structlog.get_logger(__name__)

LegalForm = Literal["llc", "jsc", "private_enterprise", "sole_proprietor"]
# 07 BO-21 "Faoliyat turi — ro'yxatdan biri": the list is not in the spec — the branch activity
# types (12 branches.activity_type) are used until it is (proposed spec edit)
BusinessType = Literal["retail", "other"]
DEFAULT_BRANCH_NAME: Final = "Asosiy filial"
# signup asks no settlement category (07 BO-21): the highest retail turnover-tax rate (4 %, 13 §4.3)
# until the owner sets the real one — never under-reports tax (proposed spec edit)
DEFAULT_SETTLEMENT: Final = "city_100k_plus"
OWNER_ROLE: Final = "owner"


@dataclass(frozen=True, slots=True)
class SignupCommand:
    otp_challenge_id: UUID
    password: str | None
    owner_name: str
    store_name: str
    business_type: BusinessType
    legal_form: LegalForm
    accepted_terms_version: str
    ai_cross_border_consent: bool
    ip: str | None
    google: GoogleIdentity | None = None


@dataclass(frozen=True, slots=True)
class SignupResult:
    tenant_id: UUID
    user_id: UUID
    trial_ends_at: datetime


def _invalid(field: str, key: str) -> AppError:
    return AppError(ErrorCode.VALIDATION_ERROR, details=[ErrorDetail(field=field, message_key=key)])


class SignupService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        store: SignupStore,
        provisioning: TenantProvisioning,
        otp: OtpService,
        auth_store: AuthStore,
        redis: Callable[[], Redis],
        *,
        per_ip_hour: int,
    ) -> None:
        self._sf = session_factory
        self._store = store
        self._prov = provisioning
        self._otp = otp
        self._auth = auth_store
        self._redis = redis
        self._per_ip_hour = per_ip_hour

    async def signup(self, cmd: SignupCommand) -> SignupResult:
        await self._rate_limit(cmd.ip)
        if cmd.password is None and cmd.google is None:
            raise _invalid("password", "validation.required")  # phone path: no account without a password
        ticket = await self._otp.peek_verified(cmd.otp_challenge_id, "signup")
        if ticket is None:
            raise AppError(
                ErrorCode.OTP_INVALID,
                details=[ErrorDetail(field="otp_challenge_id", message_key="validation.otp_not_verified")],
            )
        phone = ticket.phone
        if await self._auth.find_user_by_phone(phone) is not None:
            raise _invalid("phone", "validation.phone_taken")
        password_hash = hash_password(cmd.password) if cmd.password is not None else None
        today = tashkent_today()  # business dates are Tashkent dates (UTC+5), not the UTC day
        t = NewTenant(
            tenant_id=uuid7(), user_id=uuid7(), phone=phone, owner_name=cmd.owner_name.strip(),
            store_name=cmd.store_name.strip(), business_type=cmd.business_type, legal_form=cmd.legal_form,
            terms_version=cmd.accepted_terms_version, ip=cmd.ip,
            ai_cross_border_consent=cmd.ai_cross_border_consent, password_hash=password_hash,
            valuation_valid_from=date(today.year, 1, 1), signup_date=today,
        )  # fmt: skip
        async with self._sf() as s, tenant_transaction(s, t.tenant_id, user_id=t.user_id):
            current = await self._store.current_terms_version(s, "terms")
            if current is None or current != cmd.accepted_terms_version:
                raise _invalid("accepted_terms_version", "validation.terms_version_not_current")
            trial_ends = await self._provision(s, t, current, cmd.google)
            # single use: the verified ticket goes with this COMMIT (a concurrent replay gets nothing)
            if await self._otp.consume_verified(cmd.otp_challenge_id, "signup") is None:
                raise AppError(ErrorCode.OTP_INVALID)
        log.info("signup_completed", tenant_id=str(t.tenant_id), google=cmd.google is not None)
        return SignupResult(t.tenant_id, t.user_id, trial_ends)

    async def _provision(
        self, s: AsyncSession, t: NewTenant, terms_version: str, google: GoogleIdentity | None
    ) -> datetime:
        await self._store.insert_tenant(s, t)
        if not await self._store.insert_user(s, t):
            raise _invalid("phone", "validation.phone_taken")
        roles = await self._prov.provision_roles(s, t.tenant_id)
        await self._store.insert_owner_membership(s, t, roles[OWNER_ROLE])
        # business_type → branches.activity_type and the first branch_tax_settings row (other → general rate)
        branch_id = await self._prov.ensure_default_branch(
            s, t.tenant_id, DEFAULT_BRANCH_NAME, DEFAULT_SETTLEMENT, t.business_type
        )
        # go_live_date is set later in onboarding: the signup month (Tashkent)
        valid_from = t.signup_date.replace(day=1)
        await self._store.insert_branch_tax_setting(s, t, branch_id, valid_from, DEFAULT_SETTLEMENT)
        await self._prov.ensure_default_cash_register(s, t.tenant_id, branch_id)
        await self._prov.create_default_categories(s, t.tenant_id)
        trial_ends = await self._prov.start_trial(s, t.tenant_id)
        await self._store.insert_valuation_method(s, t)
        await self._store.insert_consent(s, t, "terms", terms_version)
        await record_audit(
            s, tenant_id=t.tenant_id, user_id=t.user_id, action="terms_accepted", entity="tenants",
            entity_id=t.tenant_id, after={"version": terms_version}, ip=t.ip,
        )  # fmt: skip
        if t.ai_cross_border_consent:
            ai_version = await self._store.current_terms_version(s, "ai_cross_border") or terms_version
            await self._store.insert_consent(s, t, "ai_cross_border", ai_version)
            await record_audit(
                s, tenant_id=t.tenant_id, user_id=t.user_id, action="consent.ai_cross_border_changed",
                entity="tenants", entity_id=t.tenant_id, after={"accepted": True, "version": ai_version},
                ip=t.ip,
            )  # fmt: skip
        await self._store.set_credentials(s, t.user_id, t.password_hash)
        if google is not None:  # 14 §2.2: the Google account is linked in the same transaction
            await self._store.link_identity(s, t.user_id, google.sub, google.email, google.email_verified)
        return trial_ends

    async def _rate_limit(self, ip: str | None) -> None:
        state = await hit(self._redis(), f"auth:signup:ip:{ip or '-'}", 3600)
        if state.count > self._per_ip_hour:
            raise AppError(
                ErrorCode.RATE_LIMITED,
                params={"retry_after_s": state.retry_after_s},
                headers={"Retry-After": str(state.retry_after_s)},
            )
