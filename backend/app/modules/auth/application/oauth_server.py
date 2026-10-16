"""Authlib AuthorizationServer wired to our storage (14 §1 "Nega Authlib").

Authlib supplies the protocol skeleton: request parsing, client authentication
(``client_secret_basic``/``client_secret_post``/``none``), grant dispatch,
redirect-URI and PKCE checks, RFC 6749 §5.2 error bodies and the RFC 7009 /
RFC 7662 endpoints. Its grant classes are synchronous, so the server runs in a
worker thread (``anyio.to_thread``) and every storage hook calls back into the
event loop with ``anyio.from_thread.run`` — one code path, real async DB I/O.

Hardening on top of Authlib's defaults:

* PKCE is mandatory for every client and only ``S256`` is accepted
  (Authlib accepts a missing challenge and defaults to ``plain``);
* ``redirect_uri`` is always explicit and exactly matched;
* tokens are minted by :class:`TokenService` (the JWT needs the ``sid`` that
  ``app.auth_issue_tokens`` creates), not by an Authlib token generator.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable, Mapping
from typing import Any, ClassVar

import anyio.from_thread
import anyio.to_thread
from authlib.oauth2.rfc6749 import (
    AuthorizationServer,
    InvalidRequestError,
    InvalidScopeError,
    OAuth2Payload,
    OAuth2Request,
)
from authlib.oauth2.rfc6749.grants import AuthorizationCodeGrant, RefreshTokenGrant
from authlib.oauth2.rfc7009 import RevocationEndpoint
from authlib.oauth2.rfc7636 import CodeChallenge
from authlib.oauth2.rfc7662 import IntrospectionEndpoint

from app.modules.auth.application.tokens import ClientRegistry, RequestMeta, TokenService
from app.modules.auth.domain.constants import DERIVED_SCOPES_WILDCARD, IMPLICIT_SCOPES
from app.modules.auth.domain.models import AccessCredential, AuthenticatedUser, OAuthClient, RefreshCredential
from app.modules.auth.domain.scopes import scope_to_set

# what the routers turn into a Starlette response
OAuthResponse = tuple[int, Any, list[tuple[str, str]]]

_CLIENT_AUTH = ["client_secret_basic", "client_secret_post", "none"]


def bridge[**P, R](fn: Callable[P, Awaitable[R]], *args: P.args, **kwargs: P.kwargs) -> R:
    """Run an async storage call from Authlib's worker thread on the event loop."""

    async def call() -> R:
        return await fn(*args, **kwargs)

    return anyio.from_thread.run(call)


class ErpPayload(OAuth2Payload):  # type: ignore[misc]
    def __init__(self, items: Iterable[tuple[str, str]]) -> None:
        self._datalist: dict[str, list[str]] = {}
        for key, value in items:
            self._datalist.setdefault(key, []).append(value)
        self._data = {k: v[0] for k, v in self._datalist.items()}

    @property
    def data(self) -> dict[str, str]:
        return self._data

    @property
    def datalist(self) -> dict[str, list[str]]:
        return self._datalist


class ErpOAuth2Request(OAuth2Request):  # type: ignore[misc]
    """Framework-neutral request: built from a Starlette request or in-process by the BFF."""

    def __init__(
        self,
        method: str,
        uri: str,
        headers: Mapping[str, str],
        *,
        query: Iterable[tuple[str, str]] = (),
        form: Iterable[tuple[str, str]] = (),
        meta: RequestMeta,
    ) -> None:
        super().__init__(method, uri, headers=headers)
        self._args = ErpPayload(query)
        self._form = ErpPayload(form)
        # RFC 6749: the authorization request travels in the query (GET) or in
        # the login form (POST); token/revoke/introspect parameters in the body
        self.payload = self._form if method == "POST" else self._args
        self.meta = meta

    @property
    def args(self) -> dict[str, str]:
        return self._args.data

    @property
    def form(self) -> dict[str, str]:
        return self._form.data


class StrictS256CodeChallenge(CodeChallenge):  # type: ignore[misc]
    """PKCE required for every client, ``S256`` only (14 §3, QT-OAUTH-01)."""

    DEFAULT_CODE_CHALLENGE_METHOD = "S256"
    SUPPORTED_CODE_CHALLENGE_METHOD: ClassVar[list[str]] = ["S256"]

    def validate_code_challenge(self, grant: Any, redirect_uri: str) -> None:
        data = grant.request.payload.data
        if not data.get("code_challenge"):
            raise InvalidRequestError("Missing 'code_challenge'")
        if data.get("code_challenge_method") != "S256":
            raise InvalidRequestError("'code_challenge_method' must be 'S256'")
        super().validate_code_challenge(grant, redirect_uri)


class ErpAuthorizationCodeGrant(AuthorizationCodeGrant):  # type: ignore[misc]
    TOKEN_ENDPOINT_AUTH_METHODS = _CLIENT_AUTH

    @property
    def tokens(self) -> TokenService:
        server: ErpAuthorizationServer = self.server
        return server.tokens

    def save_authorization_code(self, code: str, request: ErpOAuth2Request) -> None:
        user: AuthenticatedUser = request.user
        bridge(
            self.tokens.save_code,
            code,
            request.client,
            user,
            request.payload.data["code_challenge"],
            request.payload.redirect_uri,
            request.scope or "",
        )

    def query_authorization_code(self, code: str, client: OAuthClient) -> Any:
        return bridge(self.tokens.consume_code, code, client)

    def delete_authorization_code(self, authorization_code: Any) -> None:
        """Already consumed atomically by ``app.auth_consume_code``."""

    def authenticate_user(self, authorization_code: Any) -> AuthenticatedUser:
        return AuthenticatedUser(authorization_code.user_id, authorization_code.tenant_id)

    def create_token_response(self) -> OAuthResponse:
        token = bridge(
            self.tokens.issue_for_code,
            self.request.client,
            self.request.authorization_code,
            self.request.meta,
        )
        return 200, token, list(self.TOKEN_RESPONSE_HEADER)


class ErpRefreshTokenGrant(RefreshTokenGrant):  # type: ignore[misc]
    TOKEN_ENDPOINT_AUTH_METHODS = _CLIENT_AUTH

    @property
    def tokens(self) -> TokenService:
        server: ErpAuthorizationServer = self.server
        return server.tokens

    def authenticate_refresh_token(self, refresh_token: str) -> RefreshCredential | None:
        return bridge(self.tokens.lookup_refresh, refresh_token)

    def _validate_token_scope(self, token: RefreshCredential) -> None:
        requested = scope_to_set(self.request.payload.scope)
        if not requested:
            return
        ceiling = scope_to_set(token.get_scope())
        wildcard = DERIVED_SCOPES_WILDCARD in ceiling
        for scope in requested:
            if scope in ceiling or (wildcard and scope not in IMPLICIT_SCOPES):
                continue
            raise InvalidScopeError()

    def authenticate_user(self, refresh_token: RefreshCredential) -> AuthenticatedUser | None:
        if refresh_token.tenant_id is None:
            return None
        return AuthenticatedUser(refresh_token.user_id, refresh_token.tenant_id)

    def revoke_old_credential(self, refresh_token: RefreshCredential) -> None:
        """Rotation happens atomically in ``app.auth_rotate_refresh``."""

    def create_token_response(self) -> OAuthResponse:
        token = bridge(
            self.tokens.refresh,
            self.request.client,
            self.request.refresh_token,
            self.request.payload.scope,
            self.request.meta,
        )
        return 200, token, list(self.TOKEN_RESPONSE_HEADER)


class ErpRevocationEndpoint(RevocationEndpoint):  # type: ignore[misc]
    CLIENT_AUTH_METHODS = _CLIENT_AUTH

    def query_token(self, token_string: str, token_type_hint: str | None) -> Any:
        server: ErpAuthorizationServer = self.server
        return bridge(server.tokens.query_token, token_string, token_type_hint)

    def revoke_token(self, token: AccessCredential | RefreshCredential, request: ErpOAuth2Request) -> None:
        server: ErpAuthorizationServer = self.server
        bridge(server.tokens.revoke, token, request.meta)


class ErpIntrospectionEndpoint(IntrospectionEndpoint):  # type: ignore[misc]
    CLIENT_AUTH_METHODS: ClassVar[list[str]] = ["client_secret_basic", "client_secret_post"]  # 14 §20

    def query_token(self, token_string: str, token_type_hint: str | None) -> Any:
        server: ErpAuthorizationServer = self.server
        return bridge(server.tokens.query_token, token_string, token_type_hint)

    def check_permission(self, token: Any, client: OAuthClient, request: ErpOAuth2Request) -> bool:
        # a client may introspect only its own tokens (no resource-server clients yet)
        return bool(token.check_client(client))

    def introspect_token(self, token: AccessCredential | RefreshCredential) -> dict[str, Any]:
        server: ErpAuthorizationServer = self.server
        return server.tokens.introspect(token)


class ErpAuthorizationServer(AuthorizationServer):  # type: ignore[misc]
    def __init__(self, clients: ClientRegistry, tokens: TokenService) -> None:
        super().__init__(scopes_supported=None)
        self.clients = clients
        self.tokens = tokens
        self.register_grant(ErpAuthorizationCodeGrant, [StrictS256CodeChallenge(required=True)])
        self.register_grant(ErpRefreshTokenGrant)
        self.register_endpoint(ErpRevocationEndpoint)
        self.register_endpoint(ErpIntrospectionEndpoint)

        def _no_generator(**_: Any) -> dict[str, Any]:
            raise RuntimeError("tokens are minted by TokenService")

        self.register_token_generator("default", _no_generator)

    # Authlib hooks -------------------------------------------------------------------------------
    def query_client(self, client_id: str) -> OAuthClient | None:
        # in-memory registry, refreshed by the async caller before entering the thread
        return self.clients.get(client_id)

    def save_token(self, token: dict[str, Any], request: OAuth2Request) -> None:
        raise RuntimeError("tokens are persisted by TokenService")

    def send_signal(self, name: str, *args: Any, **kwargs: Any) -> None:
        return None

    def create_oauth2_request(self, request: OAuth2Request) -> OAuth2Request:
        return request

    def create_json_request(self, request: Any) -> Any:
        raise NotImplementedError

    def handle_response(self, status: int, body: Any, headers: list[tuple[str, str]]) -> OAuthResponse:
        return status, body, list(headers)

    # async facade for the routers ----------------------------------------------------------------
    async def consent_grant(self, request: ErpOAuth2Request) -> Any:
        """Validate an authorization request; raises ``OAuth2Error``."""
        await self.clients.refresh()
        return await anyio.to_thread.run_sync(self.get_consent_grant, request)

    async def authorize(
        self, request: ErpOAuth2Request, grant: Any, user: AuthenticatedUser
    ) -> OAuthResponse:
        await self.clients.refresh()
        result: OAuthResponse = await anyio.to_thread.run_sync(
            lambda: self.create_authorization_response(request, grant_user=user, grant=grant)
        )
        return result

    async def token(self, request: ErpOAuth2Request) -> OAuthResponse:
        await self.clients.refresh()
        result: OAuthResponse = await anyio.to_thread.run_sync(self.create_token_response, request)
        return result

    async def endpoint(self, name: str, request: ErpOAuth2Request) -> OAuthResponse:
        await self.clients.refresh()
        result: OAuthResponse = await anyio.to_thread.run_sync(self.create_endpoint_response, name, request)
        return result

    def error_response(self, request: ErpOAuth2Request, error: Any) -> OAuthResponse:
        result: OAuthResponse = self.handle_error_response(request, error)
        return result
