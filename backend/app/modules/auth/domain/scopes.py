"""``scope`` claim = unique permission-code prefixes (14 §10).

The scope is only the fast first filter on the RS; the final decision is
always ``require_permission`` against ``role_permissions``.
"""

from __future__ import annotations

from collections.abc import Iterable

from app.modules.auth.domain.constants import DERIVED_SCOPES_WILDCARD, IMPLICIT_SCOPES


def permission_prefix(code: str) -> str:
    return code.split(".", 1)[0]


def derive_scopes(permission_codes: Iterable[str]) -> frozenset[str]:
    return frozenset(permission_prefix(c) for c in permission_codes if c)


def scope_to_set(scope: str | None) -> frozenset[str]:
    return frozenset((scope or "").split())


def scope_to_str(scopes: Iterable[str]) -> str:
    return " ".join(sorted(set(scopes)))


def client_scope_ceiling(allowed_scopes: Iterable[str], requested: str | None) -> str:
    """Scope a client may ask for at the authorization endpoint.

    ``*`` in ``oauth_clients.allowed_scopes`` stands for "all derived prefixes"
    (they are only known per user, at token time). An empty request means
    "everything the client is allowed".
    """
    allowed = set(allowed_scopes)
    requested_set = scope_to_set(requested)
    if not requested_set:
        return scope_to_str(allowed)
    if DERIVED_SCOPES_WILDCARD in allowed:
        explicit_only = {s for s in requested_set if s in IMPLICIT_SCOPES and s not in allowed}
        return scope_to_str(requested_set - explicit_only)
    return scope_to_str(requested_set & allowed)


def effective_scopes(ceiling: str, permission_codes: Iterable[str]) -> frozenset[str]:
    """Scopes of one access token: the stored ceiling ∩ the user's current permissions."""
    ceiling_set = scope_to_set(ceiling)
    derived = derive_scopes(permission_codes)
    out: set[str] = set()
    if DERIVED_SCOPES_WILDCARD in ceiling_set:
        out |= derived
    out |= {s for s in ceiling_set if s in derived}
    out |= {s for s in ceiling_set if s in IMPLICIT_SCOPES}
    return frozenset(out)
