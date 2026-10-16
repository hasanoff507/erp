"""Protocol constants of our AS/RS (14 §5, §6, §10)."""

from __future__ import annotations

from typing import Final

AUD_API: Final = "urn:erp:api"  # tenant API (14 §5)
AUD_PLATFORM: Final = "urn:erp:platform"  # admin-bff (14 §18.1) — Bosqich 1+
AUD_ONEC_AGENT: Final = "urn:erp:onec-agent"  # 1C/store agent (14 §2.3) — Bosqich 5
TYP_ACCESS: Final = "at+jwt"  # RFC 9068
ACCESS_ALG: Final = "EdDSA"  # 14 §6 (Ed25519)
PURPOSE_ACCESS: Final = "access"

GRANT_AUTHORIZATION_CODE: Final = "authorization_code"
GRANT_REFRESH_TOKEN: Final = "refresh_token"  # noqa: S105 — grant type name, not a secret

SCOPE_SYNC_DRAIN: Final = "sync.drain"  # 14 §16.4
# implicit scopes that are not permission prefixes (14 §10); granted only if the client lists them
IMPLICIT_SCOPES: Final = frozenset({"sync", "pos"})
# client allowed_scopes wildcard: "every prefix derived from the user's permission codes"
DERIVED_SCOPES_WILDCARD: Final = "*"

SID_COOKIE: Final = "__Host-sid"
LOGIN_COOKIE: Final = "__Host-erp_login"
CSRF_HEADER: Final = "x-csrf-token"

WEB_BFF_CLIENT_ID: Final = "web-bff"
BFF_CLIENT_IDS: Final = frozenset({"web-bff", "admin-bff"})

# subscription states that lock the tenant out (14 §16, qaror #70)
LOCKED_SUBSCRIPTION_STATES: Final = frozenset({"restricted", "closed"})
