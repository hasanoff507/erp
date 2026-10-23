"""Online PIN check — ``POST /auth/pin/verify`` and the server-side PIN of approvals (14 §4.3, §12, §13).

A PIN is never a grant: it identifies "who pressed" on a device whose OAuth session already
authorizes the API calls. The check here:

1. **lockout** (qaror #54, 14 §12): 5 wrong PINs per ``(tenant, user, device)`` within 15 min lock that
   triple progressively 1 → 5 → 15 → 60 min; independently 20 wrong PINs per ``(tenant, user)`` a day
   across all devices lock the user's PIN in the tenant for 60 min (distributed guessing). Counters
   live in Redis; **without Redis the online check refuses** (``RATE_LIMITED``, fail-closed) — the POS
   falls back to its local verifier;
2. **eligibility**: an active membership in the tenant and, with a device, access to the device's
   branch — otherwise the same ``PIN_INVALID`` as a wrong PIN (no enumeration), counted as a failure;
3. **reset state**: no PIN, ``must_change_pin`` (global reset) or a tenant-local reset
   (``memberships.pin_reset_at`` set; a new PIN clears it, 16 §9) →
   ``PIN_INVALID`` ``reason=must_change_pin``;
4. argon2id verification of ``pin_hash``; on success the PBKDF2 verifier for offline checks
   (``pin_local_hash``, decision D1) is produced when missing or produced with other parameters.

Audit: ``pin_verified`` / ``pin_failed`` / ``account_locked`` with ``device_id``.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final
from uuid import UUID

import structlog
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.audit import AuditLog
from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from app.core.ratelimit import hit
from app.modules.auth.application.passwords import verify_password
from app.modules.auth.application.ports import AuthStore, PinState, SessionProfileRow
from app.modules.auth.domain.pin_verifier import ITERATIONS, make_pin_verifier, verifier_iterations

log = structlog.get_logger(__name__)

_LOCK_STEPS_S: Final = (60, 300, 900, 3600)  # 1 → 5 → 15 → 60 min (qaror #54)
_LEVEL_TTL_S: Final = 86400
_USER_LOCK_S: Final = 3600
_PIN_MAX_LEN: Final = 6


@dataclass(frozen=True, slots=True)
class PinPolicy:
    max_failures: int = 5
    failure_window_s: int = 900
    user_failures_per_day: int = 20


@dataclass(frozen=True, slots=True)
class PinVerified:
    user_id: UUID
    full_name: str
    roles: tuple[str, ...]
    permissions: tuple[str, ...]
    verified_at: datetime
    pin_local_hash: str | None


def _locked(retry_after_s: int) -> AppError:
    return AppError(
        ErrorCode.ACCOUNT_LOCKED,
        params={"retry_after_s": retry_after_s},
        headers={"Retry-After": str(retry_after_s)},
    )


def _invalid() -> AppError:
    return AppError(ErrorCode.PIN_INVALID)


def _must_change() -> AppError:
    return AppError(ErrorCode.PIN_INVALID, params={"reason": "must_change_pin"})


def pin_reset_pending(state: PinState, tenant_reset_at: datetime | None) -> bool:
    """No usable PIN in this tenant: none set, a global reset, or a newer tenant-local reset (16 §9)."""
    # the marker is cleared by app.auth_set_credentials when a new PIN is set — no clock comparison
    return state.pin_hash is None or state.must_change_pin or tenant_reset_at is not None


class PinService:
    def __init__(
        self, repo: AuthStore, redis: Callable[[], Redis], audit: AuditLog, policy: PinPolicy
    ) -> None:
        self._repo = repo
        self._redis = redis
        self._audit = audit
        self._policy = policy

    async def verify(
        self, *, tenant_id: UUID, user_id: UUID, pin: str, device_id: UUID | None, ip: str | None
    ) -> PinVerified:
        """Raise ``PIN_INVALID`` / ``ACCOUNT_LOCKED`` / ``RATE_LIMITED``; return the verified user."""
        pair = f"{tenant_id}:{user_id}:{device_id or '-'}"
        user_key = f"{tenant_id}:{user_id}"
        await self._check_locks(pair, user_key)

        profile = await self._repo.session_profile(tenant_id, user_id)
        if profile is None or not await self._eligible(profile, tenant_id, device_id):
            await self._on_failure(
                tenant_id, user_id, device_id, ip, pair, user_key, await self._reserve(pair, user_key),
                member=profile,
            )  # fmt: skip
            raise _invalid()
        state = await self._repo.pin_state(tenant_id, user_id)
        tenant_reset_at = await self._repo.pin_reset_at(tenant_id, user_id)
        if state is None or pin_reset_pending(state, tenant_reset_at):
            raise _must_change()
        # SEC-06: the attempt is reserved (INCR) BEFORE argon2 — parallel guesses cannot all slip through
        reserved = await self._reserve(pair, user_key)
        ok = len(pin) <= _PIN_MAX_LEN and pin.isdigit() and verify_password(state.pin_hash, pin)
        if not ok:
            await self._on_failure(
                tenant_id, user_id, device_id, ip, pair, user_key, reserved, member=profile
            )
            raise _invalid()

        with contextlib.suppress(RedisError):
            async with self._redis().pipeline(transaction=False) as pipe:
                pipe.delete(f"auth:pin:fail:{pair}", f"auth:pin:level:{pair}")
                pipe.decr(f"auth:pin:ufail:{user_key}")  # the reservation of a correct PIN is undone
                await pipe.execute()
        local = await self._ensure_local_verifier(user_id, state, pin)
        await self._audit.write(
            tenant_id=tenant_id, user_id=user_id, action="pin_verified", entity="users", entity_id=user_id,
            ip=ip, device_id=device_id,
        )  # fmt: skip
        return PinVerified(
            user_id=user_id,
            full_name=profile.full_name,
            roles=profile.membership.role_codes,
            permissions=tuple(sorted(profile.membership.permission_codes)),
            verified_at=datetime.now(UTC),
            pin_local_hash=local,
        )

    async def check(
        self, *, tenant_id: UUID, user_id: UUID, pin: str, device_id: UUID | None, ip: str | None
    ) -> bool:
        """``pin_verifier`` contract for other modules: ``False`` = wrong PIN (already counted/audited)."""
        try:
            await self.verify(tenant_id=tenant_id, user_id=user_id, pin=pin, device_id=device_id, ip=ip)
        except AppError as exc:
            if exc.code is ErrorCode.PIN_INVALID and not exc.params.get("reason"):
                return False
            raise
        return True

    # --- helpers ---------------------------------------------------------------------------------
    async def _eligible(self, profile: SessionProfileRow, tenant_id: UUID, device_id: UUID | None) -> bool:
        membership = profile.membership
        if membership.status != "active":
            return False
        if device_id is None or not membership.branch_ids:
            return True
        binding = await self._repo.device_binding(tenant_id, device_id)
        return binding is not None and binding.branch_id in membership.branch_ids

    async def _check_locks(self, pair: str, user_key: str) -> None:
        try:
            redis = self._redis()
            pair_ttl = int(await redis.ttl(f"auth:pin:lock:{pair}"))
            user_ttl = int(await redis.ttl(f"auth:pin:ulock:{user_key}"))
        except RedisError as exc:
            log.warning("pin_rate_limit_redis_unavailable")
            raise AppError(ErrorCode.RATE_LIMITED, headers={"Retry-After": "30"}) from exc
        locked_for = max(pair_ttl, user_ttl)
        if locked_for > 0:
            raise _locked(locked_for)

    async def _reserve(self, pair: str, user_key: str) -> tuple[int, int]:
        """Count the attempt up front; beyond the limit it is refused without reaching argon2 (SEC-06)."""
        try:
            redis = self._redis()
            fails = await hit(redis, f"auth:pin:fail:{pair}", self._policy.failure_window_s)
            daily = await hit(redis, f"auth:pin:ufail:{user_key}", 86400)
            # a lock set by a parallel attempt after our own lock check (its counter was reset) wins
            locked_for = max(
                int(await redis.ttl(f"auth:pin:lock:{pair}")),
                int(await redis.ttl(f"auth:pin:ulock:{user_key}")),
            )
            if locked_for > 0:
                await redis.decr(f"auth:pin:fail:{pair}")
                await redis.decr(f"auth:pin:ufail:{user_key}")
        except RedisError as exc:
            log.warning("pin_rate_limit_redis_unavailable")
            raise AppError(ErrorCode.RATE_LIMITED, headers={"Retry-After": "30"}) from exc
        if locked_for > 0:
            raise _locked(locked_for)
        if fails.count > self._policy.max_failures:
            raise _locked(fails.retry_after_s)
        if daily.count > self._policy.user_failures_per_day:
            raise _locked(daily.retry_after_s)
        return fails.count, daily.count

    async def _on_failure(
        self,
        tenant_id: UUID,
        user_id: UUID,
        device_id: UUID | None,
        ip: str | None,
        pair: str,
        user_key: str,
        reserved: tuple[int, int],
        *,
        member: SessionProfileRow | None,
    ) -> None:
        locked_for: int | None = None
        fails_count, daily_count = reserved
        try:
            redis = self._redis()
            if fails_count >= self._policy.max_failures:
                level = await hit(redis, f"auth:pin:level:{pair}", _LEVEL_TTL_S)
                locked_for = _LOCK_STEPS_S[min(level.count, len(_LOCK_STEPS_S)) - 1]
                await redis.set(f"auth:pin:lock:{pair}", "1", ex=locked_for)
                await redis.delete(f"auth:pin:fail:{pair}")
            if daily_count >= self._policy.user_failures_per_day:
                await redis.set(f"auth:pin:ulock:{user_key}", "1", ex=_USER_LOCK_S)
                await redis.delete(f"auth:pin:ufail:{user_key}")
                locked_for = max(locked_for or 0, _USER_LOCK_S)
        except RedisError:
            log.warning("pin_rate_limit_redis_unavailable")
        if member is None:
            return  # not a member of this tenant: nothing to audit there
        await self._audit.write(
            tenant_id=tenant_id, user_id=user_id, action="pin_failed", entity="users", entity_id=user_id,
            ip=ip, device_id=device_id,
        )  # fmt: skip
        if locked_for is not None:
            await self._audit.write(
                tenant_id=tenant_id, user_id=user_id, action="account_locked", entity="users",
                entity_id=user_id, ip=ip, device_id=device_id,
                after={"locked_for_s": locked_for, "scope": "pin"},
            )  # fmt: skip

    async def _ensure_local_verifier(self, user_id: UUID, state: PinState, pin: str) -> str | None:
        current = state.pin_local_hash
        if current is not None and verifier_iterations(current) == ITERATIONS:
            return current
        assert state.pin_hash is not None
        verifier = await asyncio.to_thread(make_pin_verifier, pin)
        if await self._repo.set_pin_local_hash(user_id, state.pin_hash, verifier):
            return verifier
        return current  # the PIN changed meanwhile — the stored verifier (if any) belongs to the new PIN
