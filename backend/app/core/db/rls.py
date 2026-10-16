"""Row-Level Security helpers (12 §4, §6.2; 15 §3).

The checks here are the CI gate from 12 §6.2: every ``tenant_id`` table must
have RLS enabled + forced + a policy, ``erp_app`` must have no grant on
``auth.*``, and the SECURITY DEFINER functions of the applied revisions must exist.
"""

from __future__ import annotations

from typing import Final
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

RLS_EXEMPT_TABLES: Final[tuple[str, ...]] = (
    "platform.plans", "platform.addons", "platform.units",
    "platform.oauth_clients", "platform.signing_keys", "platform.platform_admins",
    "platform.label_templates", "platform.fx_rates", "platform.terms_versions",
    "platform.marking_product_groups", "platform.turnover_tax_rates", "platform.card_bin_rules",
    "auth.user_credentials", "auth.otp_challenges", "auth.login_attempts",
    "auth.authorization_codes", "auth.refresh_tokens", "auth.sessions",
    "auth.onec_device_authorizations",
    "app.user_identities",
)  # fmt: skip

# 0027 — 29 functions (12 §4.5, §6.2); 0028 adds 6 and 0029 adds 1 in later stages
SECURITY_DEFINER_FUNCTIONS_0027: Final[tuple[str, ...]] = (
    "auth_find_user_by_phone", "auth_list_memberships",
    "list_active_tenant_ids", "billing_tenant_by_payment",
    "auth_consume_code", "auth_rotate_refresh",
    "auth_revoke_tenant", "auth_suspend_tenant",
    "payments_checkout_by_provider_tx", "payments_checkout_by_ref",
    "billing_payment_by_id", "public_statement_by_token",
    "auth_issue_code", "auth_issue_tokens", "auth_session_by_id", "auth_touch_session",
    "auth_otp_create", "auth_otp_verify", "auth_record_login", "auth_set_credentials",
    "auth_reset_credentials", "auth_get_pin_hash", "auth_revoke_session", "auth_revoke_user",
    "auth_list_user_sessions", "auth_telegram_chat_by_phone",
    "auth_lookup_refresh", "auth_revoke_refresh_family", "auth_purge_login_attempts",
)  # fmt: skip

_TABLES_WITHOUT_RLS = text(
    """
    SELECT n.nspname || '.' || c.relname AS table_name
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    LEFT JOIN (SELECT polrelid, COUNT(*) AS policy_count FROM pg_policy GROUP BY polrelid) p
      ON p.polrelid = c.oid
    WHERE n.nspname IN ('app', 'auth', 'platform')
      AND c.relkind = 'r'
      AND NOT ((n.nspname || '.' || c.relname) = ANY (CAST(:exempt AS text[])))
      AND (NOT c.relrowsecurity OR NOT c.relforcerowsecurity OR COALESCE(p.policy_count, 0) = 0)
    ORDER BY 1
    """
)

_APP_GRANTS_ON_AUTH = text(
    "SELECT table_name, privilege_type FROM information_schema.table_privileges "
    "WHERE grantee = 'erp_app' AND table_schema = 'auth' ORDER BY 1, 2"
)

_SECURITY_DEFINER_PRESENT = text(
    """
    SELECT p.proname FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE n.nspname = 'app' AND p.prosecdef AND p.proname = ANY (CAST(:names AS text[]))
    ORDER BY 1
    """
)


async def tables_without_rls(conn: AsyncConnection | AsyncSession) -> list[str]:
    result = await conn.execute(_TABLES_WITHOUT_RLS, {"exempt": list(RLS_EXEMPT_TABLES)})
    return [row[0] for row in result]


async def app_grants_on_auth(conn: AsyncConnection | AsyncSession) -> list[tuple[str, str]]:
    result = await conn.execute(_APP_GRANTS_ON_AUTH)
    return [(row[0], row[1]) for row in result]


async def missing_security_definer_functions(
    conn: AsyncConnection | AsyncSession, expected: tuple[str, ...] = SECURITY_DEFINER_FUNCTIONS_0027
) -> list[str]:
    result = await conn.execute(_SECURITY_DEFINER_PRESENT, {"names": list(expected)})
    present = {row[0] for row in result}
    return sorted(set(expected) - present)


async def db_tenant_id(session: AsyncSession) -> UUID | None:
    """Tenant id as PostgreSQL sees it (``app.current_tenant_id()``)."""
    value = (await session.execute(text("SELECT app.current_tenant_id()"))).scalar_one()
    return value if isinstance(value, UUID) else None
