"""Authlib model adapters (ClientMixin, AuthorizationCodeMixin, TokenMixin) over our rows."""

from __future__ import annotations

import hmac
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from authlib.oauth2.rfc6749 import AuthorizationCodeMixin, ClientMixin, TokenMixin

from app.modules.auth.domain.constants import BFF_CLIENT_IDS, GRANT_AUTHORIZATION_CODE
from app.modules.auth.domain.scopes import client_scope_ceiling

_CONFIDENTIAL_METHODS = frozenset({"client_secret_basic", "client_secret_post"})


@dataclass(frozen=True, slots=True, eq=False)
class OAuthClient(ClientMixin):  # type: ignore[misc]
    id: UUID
    client_id: str
    client_type: str  # confidential | public
    name: str
    secret: str | None = field(repr=False)
    redirect_uris: tuple[str, ...]
    grant_types: tuple[str, ...]
    scopes: tuple[str, ...]

    @property
    def is_public(self) -> bool:
        return self.client_type == "public"

    @property
    def is_bff(self) -> bool:
        return self.client_id in BFF_CLIENT_IDS

    def get_client_id(self) -> str:
        return self.client_id

    def get_default_redirect_uri(self) -> str | None:
        # OAuth 2.1: redirect_uri is always explicit and exactly matched
        return None

    def get_allowed_scope(self, scope: str | None) -> str:
        return client_scope_ceiling(self.scopes, scope)

    def check_redirect_uri(self, redirect_uri: str) -> bool:
        return redirect_uri in self.redirect_uris

    def check_client_secret(self, client_secret: str) -> bool:
        if self.is_public or not self.secret:
            return False
        return hmac.compare_digest(self.secret.encode(), client_secret.encode())

    def check_endpoint_auth_method(self, method: str, endpoint: str) -> bool:
        if self.is_public:
            # public clients may not introspect (14 §20: confidential only)
            return method == "none" and endpoint != "introspection"
        return method in _CONFIDENTIAL_METHODS

    def check_response_type(self, response_type: str) -> bool:
        return response_type == "code" and GRANT_AUTHORIZATION_CODE in self.grant_types

    def check_grant_type(self, grant_type: str) -> bool:
        return grant_type in self.grant_types


@dataclass(frozen=True, slots=True)
class AuthenticatedUser:
    """Resource owner after the first-party login (phone + password)."""

    user_id: UUID
    tenant_id: UUID
    device_id: UUID | None = None  # device-bound login (14 §7.2)

    def get_user_id(self) -> UUID:
        return self.user_id


@dataclass(frozen=True, slots=True)
class AuthorizationCode(AuthorizationCodeMixin):  # type: ignore[misc]
    client_db_id: UUID
    user_id: UUID
    tenant_id: UUID | None
    code_challenge: str
    code_challenge_method: str
    redirect_uri: str
    scope: str
    device_id: UUID | None = None  # device-bound login (14 §7.2)

    def get_redirect_uri(self) -> str:
        return self.redirect_uri

    def get_scope(self) -> str:
        return self.scope


@dataclass(frozen=True, slots=True)
class RefreshCredential(TokenMixin):  # type: ignore[misc]
    """A presented refresh token (looked up by hash, never stored in clear)."""

    token: str = field(repr=False)
    token_hash: str
    client_db_id: UUID
    user_id: UUID
    tenant_id: UUID | None
    scope: str
    expires_at: datetime
    revoked: bool
    family_issued_at: datetime
    session_id: UUID | None

    def check_client(self, client: OAuthClient) -> bool:
        return client.id == self.client_db_id

    def get_scope(self) -> str:
        return self.scope

    def get_expires_in(self) -> int:
        return max(0, int(self.expires_at.timestamp() - time.time()))

    def is_expired(self) -> bool:
        return self.expires_at.timestamp() <= time.time()

    def is_revoked(self) -> bool:
        return self.revoked


@dataclass(frozen=True, slots=True)
class AccessCredential(TokenMixin):  # type: ignore[misc]
    """A presented, signature-verified access token (RFC 9068 claims)."""

    token: str = field(repr=False)
    claims: dict[str, Any]
    client_db_id: UUID | None
    revoked: bool

    def check_client(self, client: OAuthClient) -> bool:
        return self.claims.get("client_id") == client.client_id

    def get_scope(self) -> str:
        return str(self.claims.get("scope", ""))

    def get_expires_in(self) -> int:
        return max(0, int(self.claims["exp"]) - int(time.time()))

    def is_expired(self) -> bool:
        return int(self.claims["exp"]) <= int(time.time())

    def is_revoked(self) -> bool:
        return self.revoked
