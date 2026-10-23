"""First-party phone + password authentication for ``/oauth/authorize`` (14 §2.1, §4.1, §12).

Brute-force protection (14 §12, qaror #54):

* lock per **(phone, IP) pair** after 5 failures in 15 min, progressive
  1 → 5 → 15 → 60 min — another source with the right password is not locked
  out (anti lockout-DoS);
* independent per-IP limit: 20 failures / hour (credential stuffing);
* every attempt is recorded through ``app.auth_record_login`` (``login_attempts``);
* the error is always the same ``INVALID_CREDENTIALS``; an unknown phone still
  costs one argon2 verification.

If Redis is down the pair counters are unavailable and the DB-side phone lock
(``user_credentials.locked_until``) is enforced instead — fail-safe.
"""

from __future__ import annotations

import contextlib
import hashlib
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Final
from uuid import UUID

import structlog
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.audit import AuditLog
from app.core.error_codes import ErrorCode
from app.core.ratelimit import hit, peek
from app.modules.auth.application.passwords import verify_password
from app.modules.auth.application.ports import AuthStore, MembershipRow
from app.modules.auth.application.subscription import SubscriptionStatusService
from app.modules.auth.domain.constants import LOCKED_SUBSCRIPTION_STATES
from app.modules.auth.domain.models import AuthenticatedUser

log = structlog.get_logger(__name__)

_PHONE: Final = re.compile(r"^\+998\d{9}$")
_LOCK_STEPS_S: Final = (60, 300, 900, 3600)  # 1 → 5 → 15 → 60 min
_LEVEL_TTL_S: Final = 86400


def normalize_phone(raw: str) -> str | None:
    phone = re.sub(r"[\s\-()]", "", raw or "")
    return phone if _PHONE.match(phone) else None


@dataclass(frozen=True, slots=True)
class TenantChoice:
    tenant_id: UUID
    tenant_name: str


class LoginError(Exception):
    def __init__(
        self,
        code: ErrorCode,
        *,
        params: dict[str, Any] | None = None,
        retry_after_s: int | None = None,
        tenants: list[TenantChoice] | None = None,
    ) -> None:
        super().__init__(code.value)
        self.code = code
        self.params = params or {}
        self.retry_after_s = retry_after_s
        self.tenants = tenants or []


@dataclass(frozen=True, slots=True)
class LoginPolicy:
    max_failures: int
    failure_window_s: int
    ip_failures_per_hour: int


class LoginService:
    def __init__(
        self,
        repo: AuthStore,
        redis: Callable[[], Redis],
        subscriptions: SubscriptionStatusService,
        audit: AuditLog,
        policy: LoginPolicy,
    ) -> None:
        self._repo = repo
        self._redis = redis
        self._subs = subscriptions
        self._audit = audit
        self._policy = policy

    async def authenticate(
        self, raw_phone: str, password: str, ip: str | None, tenant_id: UUID | None
    ) -> AuthenticatedUser:
        phone = normalize_phone(raw_phone)
        if phone is None:
            verify_password(None, password)  # same cost as a real attempt
            raise LoginError(ErrorCode.INVALID_CREDENTIALS)
        pair = hashlib.sha256(f"{phone}|{ip or '-'}".encode()).hexdigest()[:32]
        redis_ok = await self._check_limits(pair, ip)

        user = await self._repo.find_user_by_phone(phone)
        if not redis_ok and user and user.locked_until and user.locked_until > datetime.now(UTC):
            raise LoginError(ErrorCode.ACCOUNT_LOCKED)
        ok = verify_password(user.password_hash if user else None, password)
        if not ok or user is None:
            await self._on_failure(phone, pair, ip, user.user_id if user else None, redis_ok)
            raise LoginError(ErrorCode.INVALID_CREDENTIALS)

        await self._repo.record_login(phone, ip, True, None)
        await self._reset(pair)
        memberships = await self._repo.list_memberships(user.user_id)
        chosen = self._choose_tenant(memberships, tenant_id)
        status = await self._subs.status(chosen.tenant_id)
        if status in LOCKED_SUBSCRIPTION_STATES:
            # 14 §16.1.2: identity confirmed, but no token; pay link comes with billing (Bosqich 6)
            raise LoginError(
                ErrorCode.SUBSCRIPTION_RESTRICTED,
                params={"tenant_id": str(chosen.tenant_id), "status": status},
            )
        await self._audit.write(
            tenant_id=chosen.tenant_id, user_id=user.user_id, action="login_success", entity="users",
            entity_id=user.user_id, ip=ip,
        )  # fmt: skip
        return AuthenticatedUser(user.user_id, chosen.tenant_id)

    # --- helpers ---------------------------------------------------------------------------------
    @staticmethod
    def _choose_tenant(memberships: list[MembershipRow], tenant_id: UUID | None) -> MembershipRow:
        if not memberships:
            raise LoginError(ErrorCode.PERMISSION_DENIED, params={"reason": "no_active_membership"})
        if tenant_id is not None:
            for m in memberships:
                if m.tenant_id == tenant_id:
                    return m
            raise LoginError(ErrorCode.PERMISSION_DENIED, params={"reason": "not_a_member"})
        if len(memberships) == 1:
            return memberships[0]
        raise LoginError(
            ErrorCode.VALIDATION_ERROR,
            params={"reason": "tenant_required"},
            tenants=[TenantChoice(m.tenant_id, m.tenant_name) for m in memberships],
        )

    async def _check_limits(self, pair: str, ip: str | None) -> bool:
        """Raise when locked; return False when Redis is unavailable."""
        try:
            redis = self._redis()
            lock_ttl = int(await redis.ttl(f"auth:login:lock:{pair}"))
            ip_state = await peek(redis, f"auth:login:ipfail:{ip or '-'}")
        except RedisError:
            log.warning("login_rate_limit_redis_unavailable")
            return False
        if lock_ttl > 0:
            raise LoginError(ErrorCode.ACCOUNT_LOCKED, retry_after_s=lock_ttl)
        if ip_state.count >= self._policy.ip_failures_per_hour:
            raise LoginError(ErrorCode.RATE_LIMITED, retry_after_s=ip_state.retry_after_s)
        return True

    async def _on_failure(
        self, phone: str, pair: str, ip: str | None, user_id: UUID | None, redis_ok: bool
    ) -> None:
        await self._repo.record_login(phone, ip, False, "invalid_credentials" if user_id else "unknown_phone")
        locked_for: int | None = None
        if redis_ok:
            try:
                redis = self._redis()
                await hit(redis, f"auth:login:ipfail:{ip or '-'}", 3600)
                fails = await hit(redis, f"auth:login:fail:{pair}", self._policy.failure_window_s)
                if fails.count >= self._policy.max_failures:
                    level = await hit(redis, f"auth:login:level:{pair}", _LEVEL_TTL_S)
                    locked_for = _LOCK_STEPS_S[min(level.count, len(_LOCK_STEPS_S)) - 1]
                    await redis.set(f"auth:login:lock:{pair}", "1", ex=locked_for)
                    await redis.delete(f"auth:login:fail:{pair}")
            except RedisError:
                log.warning("login_rate_limit_redis_unavailable")
        if user_id is None:
            return
        for m in await self._repo.list_memberships(user_id):
            await self._audit.write(
                tenant_id=m.tenant_id, user_id=user_id, action="login_failed", entity="users",
                entity_id=user_id, ip=ip,
            )  # fmt: skip
            if locked_for is not None:
                await self._audit.write(
                    tenant_id=m.tenant_id, user_id=user_id, action="account_locked", entity="users",
                    entity_id=user_id, ip=ip, after={"locked_for_s": locked_for, "scope": "phone_ip_pair"},
                )  # fmt: skip

    async def _reset(self, pair: str) -> None:
        with contextlib.suppress(RedisError):
            await self._redis().delete(f"auth:login:fail:{pair}", f"auth:login:level:{pair}")
