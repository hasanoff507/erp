"""Google OpenID Connect adapter (14 §2.2, 21 §9.3) — implements ``GoogleOidcPort``.

* authorization redirect: Authorization Code + PKCE (S256) + ``nonce``, ``scope=openid email profile``;
* code exchange at the token endpoint (confidential: our Google client secret);
* ID token check, never trusting the token endpoint alone: RS256 signature against Google's JWKS
  (cached for an hour; refetched early only when the token's ``kid`` is not in the cached set, at most
  once per 60 s — a flood of forged tokens cannot turn into a flood of JWKS requests), ``iss`` ∈
  Google issuers, ``aud`` ∈ our client ids (web + Android), ``exp``/``iat`` with 60 s skew, ``nonce``
  when one was sent.

Every failure is a :class:`GoogleAuthError` (→ ``GOOGLE_AUTH_FAILED``); the raw tokens are never
logged or returned.
"""

from __future__ import annotations

import base64
import json
import time
from collections.abc import Callable, Sequence
from typing import Any, Final
from urllib.parse import urlencode

import httpx
import structlog
from joserfc import jwt
from joserfc.errors import JoseError
from joserfc.jwk import KeySet

from app.modules.auth.application.ports import GoogleAuthError, GoogleIdentity

log = structlog.get_logger(__name__)

_SKEW_S: Final = 60
_JWKS_TTL_S: Final = 3600
_JWKS_REFETCH_COOLDOWN_S: Final = 60


def _header_kid(id_token: str) -> str | None:
    try:
        segment = id_token.split(".", 1)[0]
        header = json.loads(base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4)))
    except (ValueError, UnicodeDecodeError) as exc:
        raise GoogleAuthError("malformed_token") from exc
    kid = header.get("kid") if isinstance(header, dict) else None
    return kid if isinstance(kid, str) else None


class GoogleOidcAdapter:
    def __init__(
        self,
        http: Callable[[], httpx.AsyncClient],
        *,
        client_id: str,
        client_secret: str | None,
        audiences: Sequence[str],
        issuers: Sequence[str],
        auth_url: str,
        token_url: str,
        jwks_url: str,
    ) -> None:
        self._http = http
        self._client_id = client_id
        self._client_secret = client_secret
        self._audiences = frozenset(a for a in (client_id, *audiences) if a)
        self._issuers = frozenset(issuers)
        self._auth_url = auth_url
        self._token_url = token_url
        self._jwks_url = jwks_url
        self._keys: KeySet | None = None
        self._keys_at = 0.0

    def build_auth_url(self, *, state: str, code_challenge: str, nonce: str, redirect_uri: str) -> str:
        params = {
            "client_id": self._client_id,
            "response_type": "code",
            "scope": "openid email profile",
            "redirect_uri": redirect_uri,
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "nonce": nonce,
            "prompt": "select_account",
        }
        return f"{self._auth_url}?{urlencode(params)}"

    async def exchange_code(
        self, *, code: str, code_verifier: str, redirect_uri: str, nonce: str
    ) -> GoogleIdentity:
        form = {
            "grant_type": "authorization_code",
            "code": code,
            "code_verifier": code_verifier,
            "redirect_uri": redirect_uri,
            "client_id": self._client_id,
            "client_secret": self._client_secret or "",
        }
        try:
            async with self._http() as client:
                response = await client.post(self._token_url, data=form)
            body: Any = response.json() if response.content else {}
        except (httpx.HTTPError, ValueError) as exc:
            log.warning("google_token_exchange_failed", error=type(exc).__name__)
            raise GoogleAuthError("token_exchange_failed") from exc
        id_token = body.get("id_token") if isinstance(body, dict) else None
        if response.status_code != 200 or not isinstance(id_token, str):
            log.warning("google_token_exchange_rejected", status=response.status_code)
            raise GoogleAuthError("token_exchange_rejected")
        return await self.verify_id_token(id_token, nonce=nonce)

    async def verify_id_token(self, id_token: str, *, nonce: str | None = None) -> GoogleIdentity:
        claims = await self._decode(id_token)
        now = int(time.time())
        if claims.get("iss") not in self._issuers:
            raise GoogleAuthError("bad_issuer")
        aud = claims.get("aud")
        audiences = set(aud) if isinstance(aud, list) else {aud}
        if not audiences & self._audiences:
            raise GoogleAuthError("bad_audience")
        exp, iat = claims.get("exp"), claims.get("iat")
        if not isinstance(exp, int) or exp + _SKEW_S < now:
            raise GoogleAuthError("expired")
        if isinstance(iat, int) and iat - _SKEW_S > now:
            raise GoogleAuthError("issued_in_future")
        if nonce is not None and claims.get("nonce") != nonce:
            raise GoogleAuthError("bad_nonce")
        sub = claims.get("sub")
        if not isinstance(sub, str) or not sub:
            raise GoogleAuthError("no_subject")
        verified = claims.get("email_verified")
        email = claims.get("email")
        name = claims.get("name")
        return GoogleIdentity(
            sub=sub,
            email=email if isinstance(email, str) else None,
            email_verified=verified is True or verified == "true",
            name=name if isinstance(name, str) else None,
        )

    async def _decode(self, id_token: str) -> dict[str, Any]:
        kid = _header_kid(id_token)
        keys = await self._key_set(force=False)
        if (
            kid is not None
            and kid not in {k.kid for k in keys.keys}
            and time.monotonic() - self._keys_at >= _JWKS_REFETCH_COOLDOWN_S
        ):
            keys = await self._key_set(force=True)  # Google rotated its keys
        try:
            token = jwt.decode(id_token, keys, algorithms=["RS256"])
        except (ValueError, JoseError) as exc:
            raise GoogleAuthError("bad_signature") from exc
        claims: dict[str, Any] = dict(token.claims)
        return claims

    async def _key_set(self, *, force: bool) -> KeySet:
        if self._keys is not None and not force and time.monotonic() - self._keys_at < _JWKS_TTL_S:
            return self._keys
        try:
            async with self._http() as client:
                response = await client.get(self._jwks_url)
            data = response.json()
            keys = KeySet.import_key_set(data)
        except (httpx.HTTPError, ValueError, JoseError) as exc:
            log.warning("google_jwks_unavailable", error=type(exc).__name__)
            raise GoogleAuthError("jwks_unavailable") from exc
        self._keys, self._keys_at = keys, time.monotonic()
        return keys
