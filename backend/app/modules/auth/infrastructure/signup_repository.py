"""SQL of the signup transaction (14 §20 ``/auth/signup``, 15 §1.5) and Google identities (14 §2.2).

Every ``SignupRepository`` method runs on the caller's session inside the one
``tenant_transaction(new_tenant, user_id=new_user)``: ``tenants``/``users`` RLS WITH CHECK is satisfied
because the transaction's ``app.tenant_id``/``app.user_id`` are the new ids (12 §4.4).
``app.user_identities`` has no ``tenant_id`` (global, no RLS) — it is read by ``provider``/``sub``.
"""

from __future__ import annotations

import json
from datetime import date
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.db.base import uuid7
from app.core.db.session import unscoped_transaction
from app.modules.auth.application.ports import NewTenant

_CURRENT_TERMS = text(
    "SELECT version FROM platform.terms_versions WHERE kind = :kind AND is_current "
    "ORDER BY effective_from DESC LIMIT 1"
)
_INSERT_TENANT = text(
    "INSERT INTO app.tenants (id, name, activity_type, phone, legal_form, accepted_terms_version, "
    "accepted_terms_at, accepted_terms_ip, settings, go_live_date) "
    "VALUES (:id, :name, :activity_type, :phone, :legal_form, :terms, now(), CAST(:ip AS inet), "
    "CAST(:settings AS jsonb), :go_live_date)"
)
_INSERT_USER = text(
    "INSERT INTO app.users (id, phone, name) VALUES (:id, :phone, :name) ON CONFLICT (phone) DO NOTHING "
    "RETURNING id"
)
_INSERT_MEMBERSHIP = text(
    "INSERT INTO app.memberships (id, tenant_id, user_id, role_ids, branch_ids, status) "
    "VALUES (:id, :tenant_id, :user_id, CAST(:role_ids AS uuid[]), '{}', 'active')"
)
_INSERT_VALUATION = text(
    "INSERT INTO app.valuation_method_history (id, tenant_id, valid_from, method, created_by) "
    "VALUES (:id, :tenant_id, :valid_from, 'aveco', :user_id)"
)
_INSERT_CONSENT = text(
    "INSERT INTO app.consents (id, tenant_id, subject, user_id, purpose, terms_version, accepted, ip) "
    "VALUES (:id, :tenant_id, 'tenant', :user_id, :purpose, :version, true, CAST(:ip AS inet))"
)
_INSERT_TAX_SETTING = text(
    "INSERT INTO app.branch_tax_settings (id, tenant_id, branch_id, valid_from, settlement_category, "
    "activity_type, created_by) VALUES (:id, :tenant_id, :branch_id, :valid_from, :settlement, "
    ":activity_type, :user_id) ON CONFLICT (branch_id, valid_from) DO NOTHING"
)
_SET_CREDENTIALS = text("SELECT app.auth_set_credentials(:user_id, :password_hash, NULL)")
_LINK_IDENTITY = text(
    "INSERT INTO app.user_identities (id, user_id, provider, provider_user_id, email, email_verified) "
    "VALUES (:id, :user_id, 'google', :sub, :email, :verified) "
    "ON CONFLICT (provider, provider_user_id) DO NOTHING"
)
_USER_BY_IDENTITY = text(
    "SELECT user_id FROM app.user_identities WHERE provider = :provider AND provider_user_id = :sub"
)
_USER_BY_EMAIL = text(
    "SELECT DISTINCT user_id FROM app.user_identities WHERE provider = :provider AND email_verified "
    "AND lower(email) = lower(:email) LIMIT 2"
)


class SignupRepository:
    async def current_terms_version(self, session: AsyncSession, kind: str) -> str | None:
        value = (await session.execute(_CURRENT_TERMS, {"kind": kind})).scalar()
        return str(value) if value is not None else None

    async def insert_tenant(self, session: AsyncSession, t: NewTenant) -> None:
        settings = {"ai_cross_border_enabled": t.ai_cross_border_consent}
        await session.execute(
            _INSERT_TENANT,
            {
                "id": t.tenant_id, "name": t.store_name, "activity_type": t.business_type, "phone": t.phone,
                "legal_form": t.legal_form, "terms": t.terms_version, "ip": t.ip,
                "settings": json.dumps(settings),
                # 13 §2.21/§5.5: openings are dated go_live_date − 1; the tenant starts on its signup day
                "go_live_date": t.signup_date,
            },
        )  # fmt: skip

    async def insert_user(self, session: AsyncSession, t: NewTenant) -> bool:
        params = {"id": t.user_id, "phone": t.phone, "name": t.owner_name}
        return (await session.execute(_INSERT_USER, params)).first() is not None

    async def insert_owner_membership(self, session: AsyncSession, t: NewTenant, owner_role_id: UUID) -> None:
        params = {
            "id": uuid7(), "tenant_id": t.tenant_id, "user_id": t.user_id, "role_ids": [str(owner_role_id)],
        }  # fmt: skip
        await session.execute(_INSERT_MEMBERSHIP, params)

    async def insert_valuation_method(self, session: AsyncSession, t: NewTenant) -> None:
        params = {
            "id": uuid7(), "tenant_id": t.tenant_id, "valid_from": t.valuation_valid_from,
            "user_id": t.user_id,
        }  # fmt: skip
        await session.execute(_INSERT_VALUATION, params)

    async def insert_branch_tax_setting(
        self, session: AsyncSession, t: NewTenant, branch_id: UUID, valid_from: date, settlement_category: str
    ) -> None:
        params = {
            "id": uuid7(), "tenant_id": t.tenant_id, "branch_id": branch_id, "valid_from": valid_from,
            "settlement": settlement_category, "activity_type": t.business_type, "user_id": t.user_id,
        }  # fmt: skip
        await session.execute(_INSERT_TAX_SETTING, params)

    async def insert_consent(self, session: AsyncSession, t: NewTenant, purpose: str, version: str) -> None:
        params = {
            "id": uuid7(), "tenant_id": t.tenant_id, "user_id": t.user_id, "purpose": purpose,
            "version": version, "ip": t.ip,
        }  # fmt: skip
        await session.execute(_INSERT_CONSENT, params)

    async def set_credentials(self, session: AsyncSession, user_id: UUID, password_hash: str | None) -> None:
        # SECURITY DEFINER on the same session: the credentials row commits (or not) with the tenant
        await session.execute(_SET_CREDENTIALS, {"user_id": user_id, "password_hash": password_hash})

    async def link_identity(
        self, session: AsyncSession, user_id: UUID, sub: str, email: str | None, email_verified: bool
    ) -> None:
        params = {"id": uuid7(), "user_id": user_id, "sub": sub, "email": email, "verified": email_verified}
        await session.execute(_LINK_IDENTITY, params)


class IdentityRepository:
    """``app.user_identities`` outside a tenant (Google login, 14 §2.2)."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def user_by_identity(self, provider: str, sub: str) -> UUID | None:
        async with self._sf() as s, unscoped_transaction(s):
            value = (await s.execute(_USER_BY_IDENTITY, {"provider": provider, "sub": sub})).scalar()
        return value if isinstance(value, UUID) else None

    async def user_by_verified_email(self, provider: str, email: str) -> UUID | None:
        async with self._sf() as s, unscoped_transaction(s):
            rows = (await s.execute(_USER_BY_EMAIL, {"provider": provider, "email": email})).all()
        return rows[0].user_id if len(rows) == 1 else None  # ambiguous → never link automatically

    async def link_identity(self, user_id: UUID, sub: str, email: str | None, email_verified: bool) -> None:
        async with self._sf() as s, unscoped_transaction(s):
            await SignupRepository().link_identity(s, user_id, sub, email, email_verified)
