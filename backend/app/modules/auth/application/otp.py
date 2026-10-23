"""One-time codes (14 §4.2, qaror #34): signup, recovery, staff invite and owner-forced resets.

Cross-slice CONTRACT (Bosqich 1): ``OtpPurpose``, ``OtpChannel``, ``OtpIssued`` and ``OtpIssuer``
below are used by the BO-11 admin-users service; the implementation (channel selection Telegram →
SMS, rate limits, ``app.auth_otp_create``/``app.auth_otp_verify``) lives next to them and is exposed
as ``AuthModule.otp``. Do not change these signatures without updating every caller.

Implementation notes (14 §4.2, §12, §14):

* channel: Telegram first when ``app.auth_telegram_chat_by_phone`` finds a linked chat, SMS (Eskiz)
  when there is none or the Telegram delivery failed; each channel has its own limits (Redis fixed
  windows, ``app/core/ratelimit.py``) and its own challenge row (``otp_challenges.channel``);
* the code is 6 digits, stored only as an HMAC (server key, phone and purpose bound) — a leaked
  ``otp_challenges`` table cannot be brute-forced offline;
* ``verify`` maps ``app.auth_otp_verify`` to ``OTP_INVALID`` / ``OTP_EXPIRED`` / ``OTP_MAX_ATTEMPTS``
  and, on success, leaves a short-lived single-use "verified" ticket bound to (phone, purpose) for
  the step that needs a verified phone (signup, data export);
* test-number path (qaror #34, local/test only): for ``ERP_OTP_TEST_PHONES`` the real flow runs
  (limits, challenge row, hash, verify) but the code is ``ERP_OTP_TEST_CODE`` and no message is sent;
* events ``otp_requested`` / ``otp_verified`` / ``otp_failed``: always a structured log line; when the
  phone belongs to a user with memberships, also ``audit_log`` of each of those tenants.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final, Literal, Protocol, cast
from uuid import UUID

import structlog
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.audit import AuditLog
from app.core.db.base import uuid7
from app.core.error_codes import ErrorCode
from app.core.errors import AppError, ErrorDetail
from app.core.ratelimit import hit, peek
from app.modules.auth.application.login import normalize_phone
from app.modules.auth.application.ports import MessageSender, OtpOutcome, OtpStore

OtpPurpose = Literal["signup", "recovery", "invite", "admin_reset", "pin_reset", "data_export"]
OtpChannel = Literal["telegram", "sms"]


@dataclass(frozen=True, slots=True)
class OtpIssued:
    challenge_id: UUID
    channel_used: OtpChannel
    expires_at: datetime


class OtpIssuer(Protocol):
    async def issue(
        self, phone: str, purpose: OtpPurpose, *, ip: str | None, tenant_id: UUID | None = None
    ) -> OtpIssued:
        """Create the challenge and deliver the code — Telegram first, SMS fallback (14 §4.2).

        ``tenant_id`` binds an ``invite`` code to the inviting tenant: redeeming it accepts exactly
        that tenant's ``invited`` membership (14 §18.2).

        Raises ``AppError(OTP_CHANNEL_UNAVAILABLE)`` when no channel delivered the code and
        ``AppError(RATE_LIMITED)`` when a 14 §12 limit is hit. The plain code never leaves this call.
        """
        ...


# ------------------------------------------------------------------------------------------------------
log = structlog.get_logger(__name__)

OTP_PURPOSES: Final[frozenset[str]] = frozenset(
    {"signup", "recovery", "invite", "admin_reset", "pin_reset", "data_export"}
)
# purposes a phone owner may start without a session (14 §20 /auth/otp/request)
PUBLIC_PURPOSES: Final[frozenset[str]] = frozenset({"signup", "recovery"})
# codes the owner triggers in BO-11: the message carries only the code, so the staff member proves
# it with the phone (the latest open challenge of that phone and purpose, 14 §4.2)
STAFF_CODE_PURPOSES: Final[frozenset[str]] = frozenset({"invite", "admin_reset", "pin_reset"})
_TENANT_KNOWN: Final[frozenset[str]] = OTP_PURPOSES - {"signup"}
# auth.otp_challenges.max_attempts — the recovery decoy (unknown phone) mirrors it in Redis (14 §12)
MAX_VERIFY_ATTEMPTS: Final = 5


@dataclass(frozen=True, slots=True)
class OtpPolicy:
    ttl_s: int = 300
    verified_ttl_s: int = 900
    telegram_per_phone_day: int = 10
    telegram_per_ip_hour: int = 20
    sms_per_phone_day: int = 5
    sms_per_ip_hour: int = 20
    sms_daily_budget: int = 2000
    verify_per_ip_hour: int = 60
    verify_fail_per_phone_day: int = 10
    recovery_min_response_s: float = 1.5
    test_phones: frozenset[str] = frozenset()
    test_code: str | None = None
    brand: str = "ERP"


@dataclass(frozen=True, slots=True)
class VerifiedOtp:
    challenge_id: UUID
    phone: str
    purpose: OtpPurpose
    tenant_id: UUID | None = None  # the inviting tenant of an ``invite`` code


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:32]


def mask_phone(phone: str) -> str:
    return f"{phone[:6]}*****{phone[-2:]}" if len(phone) > 8 else "***"


def _rate_limited(retry_after_s: int, **params: str) -> AppError:
    return AppError(
        ErrorCode.RATE_LIMITED,
        params={**params, "retry_after_s": retry_after_s},
        headers={"Retry-After": str(retry_after_s)},
    )


def require_phone(raw: str, field: str = "phone") -> str:
    phone = normalize_phone(raw)
    if phone is None:  # 14 §12: only +998 numbers
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            details=[ErrorDetail(field=field, message_key="validation.phone_uz")],
        )
    return phone


class OtpService:
    """``AuthModule.otp`` — implements :class:`OtpIssuer` plus verification."""

    def __init__(
        self,
        store: OtpStore,
        redis: Callable[[], Redis],
        audit: AuditLog,
        *,
        telegram: MessageSender | None,
        sms: MessageSender,
        policy: OtpPolicy,
        hash_key: bytes,
    ) -> None:
        self._store = store
        self._redis = redis
        self._audit = audit
        self._telegram = telegram
        self._sms = sms
        self._policy = policy
        self._key = hashlib.sha256(b"erp-otp-v1|" + hash_key).digest()

    @property
    def policy(self) -> OtpPolicy:
        return self._policy

    # --- issue ---------------------------------------------------------------------------------------
    async def issue(
        self, phone: str, purpose: OtpPurpose, *, ip: str | None, tenant_id: UUID | None = None
    ) -> OtpIssued:
        phone = require_phone(phone)
        if purpose not in OTP_PURPOSES:
            raise AppError(
                ErrorCode.VALIDATION_ERROR,
                details=[ErrorDetail(field="purpose", message_key="validation.enum")],
            )
        issued = await self._deliver(phone, purpose, ip, tenant_id)
        await self._event("otp_requested", phone, purpose, ip, {"channel": issued.channel_used})
        return issued

    async def request(self, raw_phone: str, purpose: OtpPurpose, *, ip: str | None) -> OtpIssued:
        """Public ``POST /auth/otp/request`` (signup, recovery).

        Recovery is enumeration-safe (14 §12): an unknown phone gets the same response shape after
        the same limits and a stabilised response time (``recovery_min_response_s``, ≥ 1.5 s — longer
        than a real Telegram/SMS delivery), but no challenge and no message; its decoy id then answers
        ``/auth/otp/verify`` exactly like a real challenge (5 × ``OTP_INVALID``, then
        ``OTP_MAX_ATTEMPTS``).
        """
        phone = require_phone(raw_phone)
        if purpose not in PUBLIC_PURPOSES:
            raise AppError(
                ErrorCode.VALIDATION_ERROR,
                details=[ErrorDetail(field="purpose", message_key="validation.enum")],
            )
        if purpose != "recovery":
            return await self.issue(phone, purpose, ip=ip)
        started = time.monotonic()
        try:
            if await self._store.find_user_by_phone(phone) is None:
                return await self._decoy(phone, ip)
            return await self.issue(phone, purpose, ip=ip)
        finally:
            remaining = self._policy.recovery_min_response_s - (time.monotonic() - started)
            if remaining > 0:
                await asyncio.sleep(remaining)

    async def _deliver(
        self, phone: str, purpose: str, ip: str | None, tenant_id: UUID | None = None
    ) -> OtpIssued:
        test_number = phone in self._policy.test_phones
        chat_id = await self._store.telegram_chat_by_phone(phone) if self._telegram else None
        if chat_id and self._telegram is not None:
            await self._limit("telegram", phone, ip)
            code = self._new_code(test_number)
            issued = await self._challenge(phone, purpose, "telegram", code, tenant_id)
            if test_number or await self._telegram.send(chat_id, self._telegram_text(code)):
                return issued
            log.warning("otp_telegram_failed_fallback_sms", purpose=purpose)
        await self._limit("sms", phone, ip)
        code = self._new_code(test_number)
        issued = await self._challenge(phone, purpose, "sms", code, tenant_id)
        if test_number:
            return issued  # no message leaves: the global SMS budget is not spent
        if await self._sms.send(phone, self._sms_text(code)):
            await self._spend_sms_budget()
            return issued
        log.error("otp_channel_unavailable", purpose=purpose)
        raise AppError(ErrorCode.OTP_CHANNEL_UNAVAILABLE)

    async def _decoy(self, phone: str, ip: str | None) -> OtpIssued:
        # the same limits as a real SMS (the budget is only checked: no message, nothing spent)
        await self._limit("sms", phone, ip)
        challenge_id = uuid7()
        expires = datetime.now(UTC) + timedelta(seconds=self._policy.ttl_s)
        await self._remember(challenge_id, phone, "recovery", decoy_expires=expires)
        log.info("otp_requested", purpose="recovery", known_phone=False, phone=mask_phone(phone))
        return OtpIssued(challenge_id, "sms", expires)

    async def _challenge(
        self, phone: str, purpose: str, channel: OtpChannel, code: str, tenant_id: UUID | None = None
    ) -> OtpIssued:
        challenge_id = await self._store.create_challenge(
            phone, purpose, channel, self._hash(phone, purpose, code), self._policy.ttl_s
        )
        await self._remember(challenge_id, phone, purpose, tenant_id=tenant_id)
        return OtpIssued(challenge_id, channel, datetime.now(UTC) + timedelta(seconds=self._policy.ttl_s))

    async def _remember(
        self,
        challenge_id: UUID,
        phone: str,
        purpose: str,
        *,
        tenant_id: UUID | None = None,
        decoy_expires: datetime | None = None,
    ) -> None:
        data: dict[str, object] = {"phone": phone, "purpose": purpose}
        if tenant_id is not None:
            data["tenant_id"] = str(tenant_id)
        if decoy_expires is not None:
            data["decoy_exp"] = decoy_expires.timestamp()
        record = json.dumps(data)
        try:
            await self._redis().set(f"otp:ch:{challenge_id}", record, ex=self._policy.ttl_s + 60)
            if purpose in STAFF_CODE_PURPOSES:
                # auth_otp_create expires older open challenges of (phone, purpose): latest = the open one
                await self._redis().set(
                    self._latest_key(phone, purpose), str(challenge_id), ex=self._policy.ttl_s + 60
                )
        except RedisError as exc:
            raise AppError(ErrorCode.OTP_CHANNEL_UNAVAILABLE) from exc

    # --- verify --------------------------------------------------------------------------------------
    async def verify(self, challenge_id: UUID, code: str, *, ip: str | None) -> VerifiedOtp:
        """14 §12: a per-IP attempt limit and a per-phone daily cap of wrong codes (all challenges)."""
        await self._verify_ip_limit(ip)
        return await self._verify(challenge_id, code, ip)

    async def _verify(self, challenge_id: UUID, code: str, ip: str | None) -> VerifiedOtp:
        try:
            raw = await self._redis().get(f"otp:ch:{challenge_id}")
        except RedisError as exc:
            raise AppError(ErrorCode.OTP_CHANNEL_UNAVAILABLE) from exc
        if not raw:
            raise AppError(ErrorCode.OTP_EXPIRED)
        record = json.loads(raw)
        phone, purpose = str(record["phone"]), cast(OtpPurpose, record["purpose"])
        fail_key = f"otp:verify:fail:phone:{_digest(phone)}"
        try:
            failed = await peek(self._redis(), fail_key)
        except RedisError as exc:
            raise AppError(ErrorCode.OTP_CHANNEL_UNAVAILABLE) from exc
        if failed.count >= self._policy.verify_fail_per_phone_day:
            raise _rate_limited(failed.retry_after_s, scope="otp_verify_phone")
        candidate = code if len(code) == 6 and code.isdigit() else "-"
        outcome = await self._store.verify_challenge(challenge_id, self._hash(phone, purpose, candidate))
        if "decoy_exp" in record:
            # unknown recovery phone: there is no row (the DB call above keeps the timing) — attempts
            # are counted in Redis with the same 5-attempt rule
            outcome = await self._decoy_outcome(challenge_id, float(record["decoy_exp"]))
        if outcome != "ok":
            if outcome == "invalid":
                try:
                    await hit(self._redis(), fail_key, 86400)
                except RedisError as exc:
                    raise AppError(ErrorCode.OTP_CHANNEL_UNAVAILABLE) from exc
            await self._event("otp_failed", phone, purpose, ip, {"outcome": outcome})
            if outcome == "expired":
                raise AppError(ErrorCode.OTP_EXPIRED)
            if outcome == "locked":
                raise AppError(ErrorCode.OTP_MAX_ATTEMPTS)
            raise AppError(ErrorCode.OTP_INVALID)
        await self._redis().set(
            f"otp:ok:{challenge_id}", raw, ex=self._policy.verified_ttl_s
        )  # single-use ticket for signup/export
        await self._event("otp_verified", phone, purpose, ip, None)
        tenant = record.get("tenant_id")
        return VerifiedOtp(challenge_id, phone, purpose, UUID(str(tenant)) if tenant else None)

    async def _decoy_outcome(self, challenge_id: UUID, expires_at: float) -> OtpOutcome:
        """``auth_otp_verify`` semantics without a row: locked after 5 wrong codes, then expiry."""
        key = f"otp:decoy:att:{challenge_id}"
        try:
            redis = self._redis()
            if int(await redis.get(key) or 0) >= MAX_VERIFY_ATTEMPTS:
                return "locked"
            if time.time() >= expires_at:
                return "expired"
            async with redis.pipeline(transaction=True) as pipe:
                pipe.incr(key)
                pipe.expire(key, self._policy.ttl_s + 60)
                await pipe.execute()
        except RedisError as exc:
            raise AppError(ErrorCode.OTP_CHANNEL_UNAVAILABLE) from exc
        return "invalid"

    async def _verify_ip_limit(self, ip: str | None) -> None:
        try:
            state = await hit(self._redis(), f"otp:verify:ip:{ip or '-'}", 3600)
        except RedisError as exc:
            raise AppError(ErrorCode.OTP_CHANNEL_UNAVAILABLE) from exc
        if state.count > self._policy.verify_per_ip_hour:
            raise _rate_limited(state.retry_after_s, scope="otp_verify_ip")

    async def verify_by_phone(
        self, raw_phone: str, purpose: OtpPurpose, code: str, *, ip: str | None
    ) -> VerifiedOtp:
        """Staff codes (invite / admin_reset / pin_reset): the latest open challenge of the phone.

        An unknown phone, a wrong purpose or no open challenge all answer ``OTP_EXPIRED`` (no
        enumeration); attempts still count against that challenge (5, then ``OTP_MAX_ATTEMPTS``).
        """
        phone = require_phone(raw_phone)
        if purpose not in STAFF_CODE_PURPOSES:
            raise AppError(
                ErrorCode.VALIDATION_ERROR,
                details=[ErrorDetail(field="purpose", message_key="validation.enum")],
            )
        await self._verify_ip_limit(ip)
        try:
            raw_id = await self._redis().get(self._latest_key(phone, purpose))
        except RedisError as exc:
            raise AppError(ErrorCode.OTP_CHANNEL_UNAVAILABLE) from exc
        if not raw_id:
            await self._event("otp_failed", phone, purpose, ip, {"outcome": "no_challenge"})
            raise AppError(ErrorCode.OTP_EXPIRED)
        return await self._verify(UUID(str(raw_id)), code, ip)

    @staticmethod
    def _latest_key(phone: str, purpose: str) -> str:
        digest = hashlib.sha256(f"{phone}|{purpose}".encode()).hexdigest()
        return f"otp:latest:{digest}"

    async def peek_verified(self, challenge_id: UUID, purpose: OtpPurpose) -> VerifiedOtp | None:
        """The verified ticket without using it (validate first, consume right before COMMIT)."""
        raw = await self._redis().get(f"otp:ok:{challenge_id}")
        if not raw:
            return None
        record = json.loads(raw)
        if record.get("purpose") != purpose:
            return None
        return VerifiedOtp(challenge_id, str(record["phone"]), purpose)

    async def consume_verified(self, challenge_id: UUID, purpose: OtpPurpose) -> VerifiedOtp | None:
        """The verified ticket, once (GETDEL) — the next step proves the phone with it."""
        raw = await self._redis().getdel(f"otp:ok:{challenge_id}")
        if not raw:
            return None
        record = json.loads(raw)
        if record.get("purpose") != purpose:
            return None
        return VerifiedOtp(challenge_id, str(record["phone"]), purpose)

    # --- helpers -------------------------------------------------------------------------------------
    def _hash(self, phone: str, purpose: str, code: str) -> str:
        return hmac.new(self._key, f"{phone}|{purpose}|{code}".encode(), hashlib.sha256).hexdigest()

    def _new_code(self, test_number: bool) -> str:
        if test_number and self._policy.test_code:
            return self._policy.test_code
        return f"{secrets.randbelow(10**6):06d}"

    def _telegram_text(self, code: str) -> str:
        return f"Tasdiqlash kodingiz: {code}\nКод подтверждения: {code}"

    def _sms_text(self, code: str) -> str:
        return f"Kod: {code}. {self._policy.brand} tizimiga kirish. Hech kimga bermang."

    async def _limit(self, channel: OtpChannel, phone: str, ip: str | None) -> None:
        """Per-phone and per-IP first; the global SMS budget is only checked here (14 §12).

        The budget counts messages actually sent (``_spend_sms_budget`` after a delivered SMS), so
        requests refused by the per-phone/IP limits — and recovery decoys — never consume it.
        """
        p = self._policy
        per_phone, per_ip = (
            (p.telegram_per_phone_day, p.telegram_per_ip_hour)
            if channel == "telegram"
            else (p.sms_per_phone_day, p.sms_per_ip_hour)
        )
        try:
            redis = self._redis()
            checks = [
                (await hit(redis, f"otp:send:{channel}:phone:{_digest(phone)}", 86400), per_phone),
                (await hit(redis, f"otp:send:{channel}:ip:{ip or '-'}", 3600), per_ip),
            ]
        except RedisError as exc:
            raise AppError(ErrorCode.OTP_CHANNEL_UNAVAILABLE) from exc
        for state, limit in checks:
            if state.count > limit:
                raise _rate_limited(state.retry_after_s, channel=channel)
        if channel != "sms":
            return
        try:
            budget = await peek(self._redis(), self._budget_key())
        except RedisError as exc:
            raise AppError(ErrorCode.OTP_CHANNEL_UNAVAILABLE) from exc
        if budget.count >= p.sms_daily_budget:
            # 14 §12: SMS pumping guard — alert; no CAPTCHA yet, so the request is refused
            log.error("otp_sms_daily_budget_exceeded", count=budget.count)
            raise _rate_limited(budget.retry_after_s, channel=channel)

    async def _spend_sms_budget(self) -> None:
        try:
            await hit(self._redis(), self._budget_key(), 86400)
        except RedisError:
            log.warning("otp_sms_budget_not_counted")  # the SMS is already out: do not fail the request

    @staticmethod
    def _budget_key() -> str:
        return f"otp:send:sms:budget:{datetime.now(UTC).strftime('%Y%m%d')}"

    async def _event(
        self, action: str, phone: str, purpose: str, ip: str | None, extra: dict[str, str] | None
    ) -> None:
        log.info(action, purpose=purpose, phone=mask_phone(phone), **(extra or {}))
        if purpose not in _TENANT_KNOWN:
            return  # no tenant yet (signup): the structured log is the record (15 §6.1)
        user = await self._store.find_user_by_phone(phone)
        if user is None:
            return
        for m in await self._store.list_memberships(user.user_id):
            await self._audit.write(
                tenant_id=m.tenant_id, user_id=user.user_id, action=action, entity="users",
                entity_id=user.user_id, ip=ip, after={"purpose": purpose, **(extra or {})},
            )  # fmt: skip
