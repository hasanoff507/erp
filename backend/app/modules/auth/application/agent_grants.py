"""Store-agent grants of the AS (14 §2.3, 33 §9.2): RFC 8628 device authorization + device-code grant,
and ``client_credentials`` with ``private_key_jwt`` (RFC 7523) for ``onec-agent:<agent_id>``.

Sources: https://www.rfc-editor.org/rfc/rfc8628 (§3.1–§3.5),
https://www.rfc-editor.org/rfc/rfc7523 (§2.2, §3), https://www.rfc-editor.org/rfc/rfc7638, https://www.rfc-editor.org/rfc/rfc8037.

The agent is not a user: its access token (``aud=urn:erp:onec-agent``, 10 min, no refresh token) carries
``tenant_id``/``agent_id``/``device_id`` and the scope ``onec.agent`` only. ``device_code`` is stored as its
SHA-256; the ``auth.onec_device_authorizations`` table is reached only through the 0028 SECURITY DEFINER
functions. Client assertions are single use (``jti`` in Redis, 120 s).
"""

from __future__ import annotations

import hmac
import re
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Final, Protocol
from uuid import UUID

import structlog
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.db.base import uuid7
from app.core.ratelimit import hit
from app.modules.auth.application.compact_jws import (
    JwsError,
    public_key_from_jwk,
    unverified_parts,
    verify_compact,
)
from app.modules.auth.application.keys import AccessTokenCodec
from app.modules.auth.domain.agent_keys import (
    MACHINE_HASH,
    InvalidAgentKeyError,
    device_code_hash,
    display_user_code,
    jwk_thumbprint,
    new_device_code,
    new_user_code,
    parse_public_jwk,
)
from app.modules.auth.domain.constants import AUD_ONEC_AGENT
from app.modules.auth.domain.scopes import scope_to_set

log = structlog.get_logger(__name__)

DEVICE_CODE_GRANT: Final = "urn:ietf:params:oauth:grant-type:device_code"
JWT_BEARER_ASSERTION: Final = "urn:ietf:params:oauth:client-assertion-type:jwt-bearer"
AGENT_CLIENT_ID: Final = "onec-agent"
AGENT_CLIENT_PREFIX: Final = "onec-agent:"
AGENT_SCOPE: Final = "onec.agent"
_PRINTABLE: Final = re.compile(r"^[^\x00-\x1f\x7f]+$")

OAuthResult = tuple[int, dict[str, Any], dict[str, str]]
_NO_STORE: Final = {"Cache-Control": "no-store", "Pragma": "no-cache"}


@dataclass(frozen=True, slots=True)
class DevicePoll:
    status: str  # pending | approved | denied | consumed | expired
    tenant_id: UUID | None
    agent_id: UUID | None
    slow_down: bool


@dataclass(frozen=True, slots=True)
class AgentCredentials:
    tenant_id: UUID
    agent_id: UUID
    device_id: UUID
    public_jwk: dict[str, Any]
    status: str


@dataclass(frozen=True, slots=True)
class SignedArtifact:
    kind: str  # task_keyset | update_manifest
    channel: str | None
    version: str
    body: str
    signature: str | None
    kid: str


class AgentAuthStore(Protocol):
    async def start_device_authorization(self, **params: Any) -> UUID | None: ...

    async def poll_device_code(self, device_code_hash: str) -> DevicePoll | None: ...

    async def agent_credentials(self, client_id: str) -> AgentCredentials | None: ...

    async def tenant_name(self, tenant_id: UUID) -> str | None: ...

    async def signed_artifacts(self, kind: str, channel: str | None) -> list[SignedArtifact]: ...


@dataclass(frozen=True, slots=True)
class AgentGrantPolicy:
    access_ttl_s: int = 600  # 14 §2.3: 10 minutes
    device_code_ttl_s: int = 600  # fixed in app.onec_device_auth_start (10 minutes)
    interval_s: int = 5
    device_auth_per_ip_hour: int = 10  # 14 §12
    assertion_max_lifetime_s: int = 60  # exp ≤ iat + 60
    clock_tolerance_s: int = 120  # 33 §9.1
    expiry_leeway_s: int = 5
    jti_ttl_s: int = 120  # Redis onec:jti:{jti}
    verification_uri: str = ""


def _error(error: str, description: str | None = None, status: int = 400) -> OAuthResult:
    body: dict[str, Any] = {"error": error}
    if description:
        body["error_description"] = description
    return status, body, dict(_NO_STORE)


def _version_key(artifact: SignedArtifact) -> tuple[int, ...]:
    parts = re.findall(r"\d+", artifact.version.split("-", 1)[0].split("+", 1)[0])
    return tuple(int(p) for p in parts[:3]) or (0,)


def latest(artifacts: list[SignedArtifact]) -> SignedArtifact | None:
    return max(artifacts, key=_version_key) if artifacts else None


class AgentGrantService:
    def __init__(
        self,
        store: AgentAuthStore,
        codec: AccessTokenCodec,
        redis: Callable[[], Redis],
        policy: AgentGrantPolicy,
        *,
        issuer: str,
    ) -> None:
        self._store = store
        self._codec = codec
        self._redis = redis
        self._policy = policy
        self._token_endpoint = f"{issuer.rstrip('/')}/oauth/token"

    @property
    def policy(self) -> AgentGrantPolicy:
        return self._policy

    # --- artefacts (A-08/A-09, hello, device grant response) --------------------------------------
    async def task_keyset(self) -> SignedArtifact | None:
        return latest(await self._store.signed_artifacts("task_keyset", None))

    async def update_manifest(self, channel: str) -> SignedArtifact | None:
        return latest(await self._store.signed_artifacts("update_manifest", channel))

    # --- RFC 8628 §3.1 device authorization request ------------------------------------------------
    async def device_authorization(self, form: Mapping[str, str], ip: str | None) -> OAuthResult:
        try:
            state = await hit(self._redis(), f"onec:rl:device_auth:{ip or '-'}", 3600)
        except RedisError:
            state = None
        if state is not None and state.count > self._policy.device_auth_per_ip_hour:
            status, body, headers = _error("slow_down", "rate_limited", 429)
            headers["Retry-After"] = str(state.retry_after_s)
            return status, body, headers
        if form.get("client_id") != AGENT_CLIENT_ID:
            return _error("invalid_client", "unknown_client")
        if scope_to_set(form.get("scope")) != {AGENT_SCOPE}:
            return _error("invalid_scope")
        try:
            jwk = parse_public_jwk(form.get("public_jwk") or "")
        except InvalidAgentKeyError:
            return _error("invalid_request", "public_jwk")
        machine_hash = form.get("machine_hash") or ""
        if not MACHINE_HASH.fullmatch(machine_hash):
            return _error("invalid_request", "machine_hash")
        pc_name = (form.get("pc_name") or "").strip()
        if not 1 <= len(pc_name) <= 64 or not _PRINTABLE.fullmatch(pc_name):
            return _error("invalid_request", "pc_name")
        optional: dict[str, str | None] = {}
        for name in ("os_version", "agent_version"):
            value = (form.get(name) or "").strip() or None
            if value is not None and (len(value) > 64 or not _PRINTABLE.fullmatch(value)):
                return _error("invalid_request", name)
            optional[name] = value
        device_code = new_device_code()
        for _ in range(5):
            user_code = new_user_code()
            started = await self._store.start_device_authorization(
                hash=device_code_hash(device_code),
                user_code=user_code,
                jwk=jwk,
                thumb=jwk_thumbprint(jwk),
                machine_hash=machine_hash,
                pc_name=pc_name,
                os=optional["os_version"],
                agent_version=optional["agent_version"],
                ip=ip,
            )
            if started is not None:
                break
        else:  # five collisions in a row: practically impossible with 20^8 codes
            return _error("temporarily_unavailable", "user_code", 503)
        uri = self._policy.verification_uri
        return (
            200,
            {
                "device_code": device_code,
                "user_code": display_user_code(user_code),
                "verification_uri": uri,
                "verification_uri_complete": f"{uri}?user_code={user_code}",
                "expires_in": self._policy.device_code_ttl_s,
                "interval": self._policy.interval_s,
            },
            dict(_NO_STORE),
        )

    # --- /oauth/token ------------------------------------------------------------------------------
    @staticmethod
    def handles(form: Mapping[str, str]) -> bool:
        """The token request belongs to the agent (Authlib serves every other grant)."""
        grant = form.get("grant_type")
        if grant == DEVICE_CODE_GRANT:
            return True
        client_id = form.get("client_id") or ""
        return grant == "client_credentials" and (
            client_id.startswith(AGENT_CLIENT_PREFIX)
            or form.get("client_assertion_type") == JWT_BEARER_ASSERTION
        )

    async def token(self, form: Mapping[str, str]) -> OAuthResult:
        if form.get("grant_type") == DEVICE_CODE_GRANT:
            return await self._device_code(form)
        return await self._client_credentials(form)

    async def _device_code(self, form: Mapping[str, str]) -> OAuthResult:
        if form.get("client_id") != AGENT_CLIENT_ID:
            return _error("invalid_client", "unknown_client", 401)
        device_code = form.get("device_code") or ""
        if not device_code or len(device_code) > 128:
            return _error("invalid_request", "device_code")
        poll = await self._store.poll_device_code(device_code_hash(device_code))
        if poll is None:
            return _error("invalid_grant")
        if poll.slow_down:
            return _error("slow_down")
        if poll.status == "pending":
            return _error("authorization_pending")
        if poll.status == "denied":
            return _error("access_denied")
        if poll.status == "expired":
            return _error("expired_token")
        if poll.status != "approved" or poll.agent_id is None or poll.tenant_id is None:
            return _error("invalid_grant")  # consumed: the token was already issued once
        creds = await self._store.agent_credentials(f"{AGENT_CLIENT_PREFIX}{poll.agent_id}")
        if creds is None or creds.status != "active" or creds.tenant_id != poll.tenant_id:
            return _error("invalid_grant")
        status, body, headers = await self._issue(creds)
        keyset = await self.task_keyset()
        body.update(
            {
                "agent_id": str(creds.agent_id),
                "agent_client_id": f"{AGENT_CLIENT_PREFIX}{creds.agent_id}",
                "tenant_name": await self._store.tenant_name(creds.tenant_id),
                "task_keyset": keyset.body if keyset else None,
            }
        )
        log.info("onec_agent_device_grant", agent_id=str(creds.agent_id), tenant_id=str(creds.tenant_id))
        return status, body, headers

    async def _client_credentials(self, form: Mapping[str, str]) -> OAuthResult:
        client_id = form.get("client_id") or ""
        agent_part = (
            client_id[len(AGENT_CLIENT_PREFIX) :] if client_id.startswith(AGENT_CLIENT_PREFIX) else ""
        )
        try:
            UUID(agent_part)
        except ValueError:
            return _error("invalid_client", None, 401)
        if form.get("client_assertion_type") != JWT_BEARER_ASSERTION or not form.get("client_assertion"):
            return _error("invalid_client", "client_assertion_required", 401)
        requested = scope_to_set(form.get("scope"))
        if requested and requested != {AGENT_SCOPE}:
            return _error("invalid_scope")
        assertion = form["client_assertion"]
        if len(assertion) > 4096:
            return _error("invalid_client", "assertion", 401)
        creds = await self._store.agent_credentials(client_id)
        if creds is None:
            return _error("invalid_client", None, 401)
        verdict = self._verify_assertion(assertion, client_id, creds)
        if verdict is not None:
            return _error("invalid_client", verdict, 401)
        if creds.status != "active":
            return _error("invalid_client", "agent_revoked", 401)
        _, claims = unverified_parts(assertion)  # signature already verified above
        try:
            fresh = await self._redis().set(
                f"onec:jti:{claims['jti']}", "1", ex=self._policy.jti_ttl_s, nx=True
            )
        except RedisError:
            log.warning("onec_agent_jti_store_unavailable", agent_id=str(creds.agent_id))
            return _error("temporarily_unavailable", "replay_check_unavailable", 503)
        if not fresh:
            log.warning("onec_agent_assertion_replayed", agent_id=str(creds.agent_id))
            return _error("invalid_client", "assertion_replayed", 401)
        return await self._issue(creds)

    def _verify_assertion(self, assertion: str, client_id: str, creds: AgentCredentials) -> str | None:
        """RFC 7523 §3 checks; ``None`` = valid, otherwise the reason (logged, generic to the caller)."""
        try:
            header, _ = unverified_parts(assertion)
            expected_kid = jwk_thumbprint(creds.public_jwk)
            kid = header.get("kid")
            if header.get("alg") != "EdDSA" or not isinstance(kid, str):
                return "assertion"
            if not hmac.compare_digest(kid.encode(), expected_kid.encode()):
                return "assertion"
            _, claims = verify_compact(assertion, public_key_from_jwk(creds.public_jwk))
        except (JwsError, KeyError, TypeError):
            return "assertion"
        now = int(time.time())
        aud = claims.get("aud")
        audiences = aud if isinstance(aud, list) else [aud]
        iat, exp, jti = claims.get("iat"), claims.get("exp"), claims.get("jti")
        if claims.get("iss") != client_id or claims.get("sub") != client_id:
            return "assertion"
        if self._token_endpoint not in audiences:
            return "assertion"
        if (
            not isinstance(iat, int)
            or not isinstance(exp, int)
            or isinstance(iat, bool)
            or isinstance(exp, bool)
        ):
            return "assertion"
        if exp - iat > self._policy.assertion_max_lifetime_s or exp < iat:
            return "assertion_lifetime"
        if exp <= now - self._policy.expiry_leeway_s or iat > now + self._policy.clock_tolerance_s:
            return "assertion_expired"
        if not isinstance(jti, str) or not 1 <= len(jti) <= 128:
            return "assertion"
        return None

    async def _issue(self, creds: AgentCredentials) -> OAuthResult:
        now = int(time.time())
        client_id = f"{AGENT_CLIENT_PREFIX}{creds.agent_id}"
        claims = {
            "sub": client_id,
            "client_id": client_id,
            "tenant_id": str(creds.tenant_id),
            "agent_id": str(creds.agent_id),
            "device_id": str(creds.device_id),
            "scope": AGENT_SCOPE,
            "iat": now,
            "exp": now + self._policy.access_ttl_s,
            "jti": str(uuid7()),
        }
        token = await self._codec.mint(claims, audience=AUD_ONEC_AGENT)
        body = {
            "access_token": token,
            "token_type": "Bearer",
            "expires_in": self._policy.access_ttl_s,
            "scope": AGENT_SCOPE,
        }
        return 200, body, dict(_NO_STORE)
