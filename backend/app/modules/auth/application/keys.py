"""Signing keys, JWKS and the access-token codec (14 §5, §6; RFC 9068).

Keys live in ``platform.signing_keys`` (``next → active → retired``); the
private key is envelope-encrypted with the KEK (15 §4.2) and bound to its row
by AAD. The runtime role only reads keys — they are generated and rotated by
the ops CLI (``scripts/auth_ops.py``) as ``erp_migrator`` (12 §5.1).
"""

from __future__ import annotations

import asyncio
import json
import time
import warnings
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Final

from joserfc import jwt
from joserfc.errors import JoseError, SecurityWarning
from joserfc.jwk import ECKey, KeySet, OctKey, OKPKey, RSAKey
from joserfc.jws import extract_compact

from app.core.secrets import EnvelopeCipher
from app.modules.auth.application.ports import AuthStore, SigningKeyRow
from app.modules.auth.domain.constants import ACCESS_ALG, AUD_API, TYP_ACCESS

# 14 §6 mandates "EdDSA" (Ed25519); RFC 9864 deprecates the polymorphic name in
# favour of "Ed25519". We keep the spec's value and silence only that notice.
warnings.filterwarnings("ignore", message="EdDSA is deprecated", category=SecurityWarning)

_ALGORITHMS: Final = [ACCESS_ALG]
_CACHE_TTL_S: Final = 60.0
_FORCED_RELOAD_INTERVAL_S: Final = 5.0
CLOCK_LEEWAY_S: Final = 5
_REQUIRED_CLAIMS: Final = ("iss", "aud", "sub", "client_id", "iat", "exp", "jti", "tenant_id", "scope")


class SigningKeyUnavailableError(RuntimeError):
    """No active signing key for the purpose — run ``auth_ops.py rotate-signing-key``."""


class InvalidAccessTokenError(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def private_key_aad(kid: str) -> bytes:
    return f"signing_keys:{kid}".encode()


@dataclass(frozen=True, slots=True)
class _Snapshot:
    loaded_at: float
    signing: OKPKey | None
    signing_kid: str | None
    verify: KeySet
    published: list[dict[str, Any]]


class SigningKeyRing:
    def __init__(self, repo: AuthStore, cipher: EnvelopeCipher, *, purpose: str, overlap_s: int) -> None:
        self._repo = repo
        self._cipher = cipher
        self._purpose = purpose
        self._overlap = timedelta(seconds=overlap_s)
        self._snapshot: _Snapshot | None = None
        self._lock = asyncio.Lock()
        self._last_forced = 0.0

    async def _load(self) -> _Snapshot:
        rows = await self._repo.list_signing_keys(self._purpose)
        now = datetime.now(UTC)
        verify: list[OctKey | RSAKey | ECKey | OKPKey] = []
        published: list[dict[str, Any]] = []
        signing: OKPKey | None = None
        signing_kid: str | None = None
        for row in rows:
            if row.status == "retired" and (row.retired_at is None or row.retired_at + self._overlap < now):
                continue
            kid = str(row.kid)
            public = OKPKey.import_key(_public_jwk(row), parameters={"kid": kid})
            verify.append(public)
            if row.status in ("active", "retired"):
                published.append(
                    {**public.as_dict(private=False), "kid": kid, "alg": ACCESS_ALG, "use": "sig"}
                )
            if row.status == "active":
                pem = self._cipher.decrypt(row.private_key_encrypted, private_key_aad(kid))
                signing = OKPKey.import_key(pem, parameters={"kid": kid})
                signing_kid = kid
        return _Snapshot(time.monotonic(), signing, signing_kid, KeySet(verify), published)

    async def snapshot(self, *, force: bool = False) -> _Snapshot:
        snap = self._snapshot
        fresh = snap is not None and time.monotonic() - snap.loaded_at < _CACHE_TTL_S
        if fresh and not force:
            assert snap is not None
            return snap
        async with self._lock:
            snap = self._snapshot
            if snap is not None and not force and time.monotonic() - snap.loaded_at < _CACHE_TTL_S:
                return snap
            if (
                force
                and snap is not None
                and time.monotonic() - self._last_forced < _FORCED_RELOAD_INTERVAL_S
            ):
                return snap
            if force:
                self._last_forced = time.monotonic()
            self._snapshot = await self._load()
            return self._snapshot

    async def signing_key(self) -> tuple[str, OKPKey]:
        snap = await self.snapshot()
        if snap.signing is None or snap.signing_kid is None:
            snap = await self.snapshot(force=True)
        if snap.signing is None or snap.signing_kid is None:
            raise SigningKeyUnavailableError(self._purpose)
        return snap.signing_kid, snap.signing

    async def jwks(self) -> dict[str, Any]:
        return {"keys": (await self.snapshot()).published}

    def invalidate(self) -> None:
        self._snapshot = None


def _public_jwk(row: SigningKeyRow) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(row.public_key)
    return {k: v for k, v in data.items() if k in ("kty", "crv", "x")}


class AccessTokenCodec:
    """Mints and verifies RFC 9068 access tokens (``typ: at+jwt``)."""

    def __init__(self, ring: SigningKeyRing, issuer: str) -> None:
        self._ring = ring
        self._issuer = issuer

    @property
    def issuer(self) -> str:
        return self._issuer

    async def mint(self, claims: dict[str, Any], *, audience: str = AUD_API) -> str:
        """``audience`` — ``urn:erp:api`` (users) or ``urn:erp:onec-agent`` (store agent, 14 §2.3)."""
        kid, key = await self._ring.signing_key()
        header = {"alg": ACCESS_ALG, "typ": TYP_ACCESS, "kid": kid}
        return jwt.encode(
            header, {"iss": self._issuer, "aud": audience, **claims}, key, algorithms=_ALGORITHMS
        )

    async def verify(self, token: str, *, audience: str = AUD_API, verify_exp: bool = True) -> dict[str, Any]:
        try:
            header = extract_compact(token.encode("ascii")).protected
        except (JoseError, ValueError, UnicodeError) as exc:
            raise InvalidAccessTokenError("malformed") from exc
        typ = str(header.get("typ", "")).lower()
        if typ not in (TYP_ACCESS, f"application/{TYP_ACCESS}"):
            raise InvalidAccessTokenError("typ")  # e.g. license+jwt (14 §17) is never an access token
        if header.get("alg") != ACCESS_ALG or not header.get("kid"):
            raise InvalidAccessTokenError("alg")
        decoded = await self._decode(token)
        claims: dict[str, Any] = dict(decoded.claims)
        missing = [c for c in _REQUIRED_CLAIMS if c not in claims]
        if missing:
            raise InvalidAccessTokenError("claims")
        if claims["iss"] != self._issuer:
            raise InvalidAccessTokenError("iss")
        aud = claims["aud"]
        if aud != audience and not (isinstance(aud, list) and aud == [audience]):
            raise InvalidAccessTokenError("aud")
        now = int(time.time())
        if verify_exp and int(claims["exp"]) <= now - CLOCK_LEEWAY_S:
            raise InvalidAccessTokenError("expired")
        if int(claims["iat"]) > now + CLOCK_LEEWAY_S:
            raise InvalidAccessTokenError("iat")
        return claims

    async def _decode(self, token: str) -> jwt.Token:
        for force in (False, True):
            snap = await self._ring.snapshot(force=force)
            try:
                return jwt.decode(token, snap.verify, algorithms=_ALGORITHMS)
            except JoseError as exc:
                if force or exc.error not in ("invalid_key_id",):
                    raise InvalidAccessTokenError("signature") from exc
            except ValueError as exc:
                raise InvalidAccessTokenError("malformed") from exc
        raise InvalidAccessTokenError("signature")


def new_signing_key() -> tuple[OKPKey, dict[str, Any]]:
    """Fresh Ed25519 key pair and its public JWK (for the ops CLI)."""
    key = OKPKey.generate_key("Ed25519")
    public = {k: v for k, v in key.as_dict(private=False).items() if k in ("kty", "crv", "x")}
    return key, public
