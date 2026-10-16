"""Credential-set session after a one-time code (14 §4.2, §18.2; US-M13 invite/reset; recovery).

A verified ``recovery`` / ``invite`` / ``admin_reset`` / ``pin_reset`` code never returns tokens:
it opens a short "credential-set session" — an opaque single-use ``credential_token`` (Redis, only
its SHA-256 is stored, ``ERP_CREDENTIAL_TOKEN_TTL_S``) that ``POST /auth/credentials`` exchanges for
a new password and/or PIN (``app.auth_set_credentials`` also clears ``must_change_*``). The user then
logs in normally (``/auth/login/start``).

What each purpose may set:

* ``recovery``, ``admin_reset`` — a password (required); all of the user's sessions are revoked
  (a reset password must end sessions an attacker may hold);
* ``pin_reset`` — a PIN (required);
* ``invite`` — a password and/or a PIN (at least one: a cashier may get only a PIN).

``invite`` is redeemed first (:meth:`CredentialService.redeem`): the code is bound to the inviting
tenant, whose ``invited`` membership becomes ``active`` (14 §18.2). An existing account that already
has a password or PIN gets **no** credential session — an invite from one tenant never replaces the
credentials the user shares with his other tenants; he simply logs in with them.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final
from uuid import UUID

import structlog
from redis.asyncio import Redis

from app.core.audit import AuditLog
from app.core.error_codes import ErrorCode
from app.core.errors import AppError, ErrorDetail
from app.modules.auth.application.otp import VerifiedOtp
from app.modules.auth.application.passwords import PASSWORD_MAX, PASSWORD_MIN, hash_password, hash_pin
from app.modules.auth.application.ports import AuthStore
from app.modules.auth.application.revocation import RevocationCache

log = structlog.get_logger(__name__)

CREDENTIAL_PURPOSES: Final[dict[str, frozenset[str]]] = {
    "recovery": frozenset({"password"}),
    "admin_reset": frozenset({"password"}),
    "pin_reset": frozenset({"pin"}),
    "invite": frozenset({"password", "pin"}),
}


@dataclass(frozen=True, slots=True)
class CredentialSession:
    token: str
    expires_in: int
    allowed: frozenset[str]


@dataclass(frozen=True, slots=True)
class CodeRedeemed:
    session: CredentialSession | None
    invite_accepted: bool | None  # ``invite`` only: the inviting tenant's membership is active now


def _key(token: str) -> str:
    return f"auth:cred:{hashlib.sha256(token.encode()).hexdigest()}"


def _invalid(field: str, key: str) -> AppError:
    return AppError(ErrorCode.VALIDATION_ERROR, details=[ErrorDetail(field=field, message_key=key)])


class CredentialService:
    def __init__(
        self,
        store: AuthStore,
        redis: Callable[[], Redis],
        revocation: RevocationCache,
        audit: AuditLog,
        *,
        ttl_s: int,
    ) -> None:
        self._store = store
        self._redis = redis
        self._revocation = revocation
        self._audit = audit
        self._ttl = ttl_s

    async def redeem(self, verified: VerifiedOtp, *, ip: str | None) -> CodeRedeemed:
        """A verified staff/recovery code → credential-set session, and for ``invite`` acceptance."""
        if verified.purpose != "invite":
            return CodeRedeemed(await self.open_session(verified), None)
        user = await self._store.find_user_by_phone(verified.phone)
        if user is None:
            raise AppError(ErrorCode.OTP_INVALID)
        accepted = False
        if verified.tenant_id is not None:
            membership = await self._store.accept_invite(verified.tenant_id, user.user_id)
            accepted = membership is not None and membership.status == "active"
            if membership is not None and membership.accepted_now:
                await self._audit.write(
                    tenant_id=verified.tenant_id, user_id=user.user_id, action="membership_status_changed",
                    entity="memberships", entity_id=membership.membership_id, ip=ip,
                    before={"status": "invited"},
                    after={"status": "active", "user_id": str(user.user_id), "reason": "invite_accepted"},
                )  # fmt: skip
        if user.password_hash is not None or await self._store.has_pin(user.user_id):
            return CodeRedeemed(None, accepted)  # existing credentials stay; a normal login follows
        return CodeRedeemed(await self.open_session(verified), accepted)

    async def open_session(self, verified: VerifiedOtp) -> CredentialSession:
        allowed = CREDENTIAL_PURPOSES.get(verified.purpose)
        if allowed is None:
            raise AppError(ErrorCode.OTP_INVALID)
        user = await self._store.find_user_by_phone(verified.phone)
        if user is None:
            raise AppError(ErrorCode.OTP_INVALID)
        token = secrets.token_urlsafe(32)
        record = json.dumps({"user_id": str(user.user_id), "purpose": verified.purpose})
        await self._redis().set(_key(token), record, ex=self._ttl)
        return CredentialSession(token, self._ttl, allowed)

    async def set_credentials(
        self, token: str, *, password: str | None, pin: str | None, ip: str | None
    ) -> None:
        raw = await self._redis().get(_key(token))
        if not raw:
            raise AppError(ErrorCode.UNAUTHORIZED, params={"reason": "credential_token_invalid"})
        record = json.loads(raw)
        purpose = str(record["purpose"])
        allowed = CREDENTIAL_PURPOSES[purpose]
        self._validate(allowed, password, pin)
        # validated first, consumed second: a typo does not burn the session; a replay finds nothing
        if not await self._redis().getdel(_key(token)):
            raise AppError(ErrorCode.UNAUTHORIZED, params={"reason": "credential_token_invalid"})
        user_id = UUID(str(record["user_id"]))
        await self._store.set_credentials(
            user_id,
            password_hash=hash_password(password) if password is not None else None,
            pin_hash=hash_pin(pin) if pin is not None else None,
        )
        revoked = 0
        if password is not None and purpose in ("recovery", "admin_reset"):
            sids = await self._store.list_user_sessions(user_id, None)
            revoked = await self._store.revoke_user(user_id, None, "password_reset")
            await self._revocation.mark_sessions_revoked(sids)
            await self._revocation.mark_user_revoked(user_id, None)
        actions = []
        if password is not None:
            actions.append("password_reset" if purpose in ("recovery", "admin_reset") else "password_changed")
        if pin is not None:
            actions.append("pin_changed")
        log.info("credentials_set", purpose=purpose, user_id=str(user_id), sessions_revoked=revoked)
        for m in await self._store.list_memberships(user_id):
            for action in actions:
                await self._audit.write(
                    tenant_id=m.tenant_id, user_id=user_id, action=action, entity="users", entity_id=user_id,
                    ip=ip, after={"purpose": purpose, "sessions_revoked": revoked},
                )  # fmt: skip

    @staticmethod
    def _validate(allowed: frozenset[str], password: str | None, pin: str | None) -> None:
        if password is None and pin is None:
            raise _invalid("password" if "password" in allowed else "pin", "validation.required")
        if password is not None:
            if "password" not in allowed:
                raise _invalid("password", "validation.not_allowed")
            if not PASSWORD_MIN <= len(password) <= PASSWORD_MAX:
                raise _invalid("password", "validation.password_length")
        if pin is not None:
            if "pin" not in allowed:
                raise _invalid("pin", "validation.not_allowed")
            if not (4 <= len(pin) <= 6 and pin.isdigit()):
                raise _invalid("pin", "validation.pin_format")
        if allowed == frozenset({"password"}) and password is None:
            raise _invalid("password", "validation.required")
        if allowed == frozenset({"pin"}) and pin is None:
            raise _invalid("pin", "validation.required")
