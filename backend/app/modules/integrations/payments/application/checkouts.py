"""Shop payment checkouts — ``POST /payments/checkouts`` (18 §16.2), ``GET /payments/checkouts/{ref}`` (§16.3)
and the expiry sweep (qaror #54: 24 h).

* ``sales.create`` or ``debts.payment.accept`` (POS-03 sale, POS-13 debt payment); online only (REST).
* ``checkout_ref`` comes from the device; a repeat with the same provider/register/amount returns the same
  checkout, a different one — ``VALIDATION_ERROR`` (``validation.checkout_ref_reused``).
* The provider must be configured for the tenant (``tenant_secrets``; UzQR — per register with ``api_key``;
  Uzum — with Dynamic QR credentials), else ``VALIDATION_ERROR``
  (``validation.payment_provider_not_configured``).
* Click/Payme links are built locally from the public link formats; Uzum Dynamic QR and dynamic UzQR call the
  provider (outside the DB transaction); a provider failure → ``502 PAYMENT_PROVIDER_ERROR``, nothing stored.
* A checkout only becomes ``confirmed`` through a verified webhook (or, for Uzum Dynamic QR, the provider's
  ``status-by-order`` on poll); the sale/debt-payment posting turns it ``consumed`` exactly once.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, Final
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.audit import record_audit
from app.core.auth.principal import Principal
from app.core.db.session import tenant_transaction
from app.core.error_codes import ErrorCode
from app.core.errors import AppError, ErrorDetail
from app.core.idempotency import stage_response
from app.core.money import money, money_str
from app.core.permissions import BranchScope
from app.modules.integrations.payments.application.ports import (
    CheckoutRepository,
    CheckoutRow,
    PaymentProviderUnavailableError,
    SecretSource,
    UzqrPort,
    UzumQrPort,
)
from app.modules.integrations.payments.domain.model import (
    UZUM_QR_DEAD,
    UZUM_QR_PAID,
    click_pay_url,
    payme_checkout_url,
    to_tiyin,
)

ENTITY: Final = "payment_checkouts"
UZUM_QR_FIELDS: Final = ("dynamic_qr_service_id", "dynamic_qr_user_id", "dynamic_qr_secret_key")
EXPIRE_BATCH: Final = 500

Clock = Callable[[], datetime]


def utc_now() -> datetime:
    return datetime.now(UTC)


def invalid(field: str, key: str) -> AppError:
    return AppError(ErrorCode.VALIDATION_ERROR, details=[ErrorDetail(field=field, message_key=key)])


def iso(value: datetime | None) -> str | None:
    return None if value is None else value.isoformat().replace("+00:00", "Z")


def checkout_json(co: CheckoutRow, *, status: str | None = None) -> dict[str, Any]:
    data = co.provider_data
    return {
        "checkout_ref": str(co.checkout_ref), "provider": co.provider, "provider_tx_id": co.provider_tx_id,
        "status": status or co.status, "amount": money_str(co.amount), "qr_type": co.qr_type,
        "qr_payload": data.get("qr_payload"), "checkout_url": data.get("checkout_url"),
        "confirmed_at": iso(co.confirmed_at), "expires_at": iso(co.expires_at),
    }  # fmt: skip


def effective_status(co: CheckoutRow, now: datetime) -> str:
    """A pending checkout past ``expires_at`` reads as ``expired`` before the sweep writes it."""
    return "expired" if co.status == "pending" and co.expires_at <= now else co.status


class CheckoutService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        repo: CheckoutRepository,
        secrets: SecretSource,
        uzqr: UzqrPort,
        uzum_qr: UzumQrPort,
        *,
        ttl_s: int,
        click_url: str,
        payme_url: str,
        payme_test_url: str,
        clock: Clock = utc_now,
    ) -> None:
        self._sf = session_factory
        self._repo = repo
        self._secrets = secrets
        self._uzqr = uzqr
        self._uzum_qr = uzum_qr
        self._ttl = timedelta(seconds=ttl_s)
        self._click_url = click_url
        self._payme_url = payme_url
        self._payme_test_url = payme_test_url
        self._clock = clock

    async def create(
        self,
        actor: Principal,
        scope: BranchScope,
        *,
        checkout_ref: UUID,
        provider: str,
        cash_register_id: UUID,
        amount: Decimal,
        qr_type: str | None,
        ip: str | None,
    ) -> dict[str, Any]:
        amount = money(amount)
        if amount <= 0:
            raise invalid("amount", "validation.must_be_positive")
        if provider == "uzqr":
            if qr_type is None:
                raise invalid("qr_type", "validation.qr_type_required")
            if qr_type != "dynamic":  # static UzQR has no checkout (18 §16.1)
                raise invalid("qr_type", "validation.invalid_choice")
        elif qr_type is not None:
            raise invalid("qr_type", "validation.qr_type_uzqr_only")
        register_key = cash_register_id if provider == "uzqr" else None
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            register = await self._repo.register(s, cash_register_id)
            if register is None or register.archived:
                raise invalid("cash_register_id", "validation.cash_register_unknown")
            if scope.allowed and register.branch_id not in scope.allowed:
                raise AppError(ErrorCode.BRANCH_SCOPE_DENIED)
            existing = await self._repo.get(s, checkout_ref)
            if existing is not None:
                return self._replay(existing, provider, cash_register_id, amount)
            found = await self._secrets.get(s, actor.tenant_id, provider, cash_register_id=register_key)
        secret = self._usable(provider, found)
        data = await self._provider_checkout(provider, secret, checkout_ref, cash_register_id, amount)
        now = self._clock()
        provider_tx_id = data.pop("provider_tx_id", None)
        row = {
            "checkout_ref": checkout_ref, "tenant_id": actor.tenant_id, "branch_id": register.branch_id,
            "cash_register_id": cash_register_id, "device_id": actor.device_id, "provider": provider,
            "qr_type": qr_type, "amount": amount, "provider_tx_id": provider_tx_id,
            "expires_at": now + self._ttl, "created_by": actor.user_id, "provider_data": data,
        }  # fmt: skip
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            if not await self._repo.insert(s, row):
                raise invalid("checkout_ref", "validation.checkout_ref_reused")  # a parallel twin won
            created = await self._repo.get(s, checkout_ref)
            assert created is not None
            await record_audit(
                s, tenant_id=actor.tenant_id, user_id=actor.user_id, action="payment_checkout.created",
                entity=ENTITY, entity_id=checkout_ref, ip=ip, device_id=actor.device_id,
                after={"provider": provider, "amount": money_str(amount),
                       "cash_register_id": str(cash_register_id)},
            )  # fmt: skip
            await self._secrets.record_result(s, actor.tenant_id, provider, cash_register_id=register_key)
            body = checkout_json(created)
            stage_response(body, 201)
        return body

    def _replay(self, co: CheckoutRow, provider: str, register: UUID, amount: Decimal) -> dict[str, Any]:
        if co.provider != provider or co.cash_register_id != register or money(co.amount) != amount:
            raise invalid("checkout_ref", "validation.checkout_ref_reused")
        body = checkout_json(co, status=effective_status(co, self._clock()))
        stage_response(body, 201)
        return body

    @staticmethod
    def _usable(provider: str, secret: Mapping[str, str] | None) -> Mapping[str, str]:
        ok = secret is not None and (
            (provider != "uzqr" or bool(secret.get("api_key")))
            and (provider != "uzum" or all(secret.get(f) for f in UZUM_QR_FIELDS))
        )
        if not ok or secret is None:
            raise invalid("provider", "validation.payment_provider_not_configured")
        return secret

    async def _provider_checkout(
        self, provider: str, secret: Mapping[str, str], ref: UUID, register: UUID, amount: Decimal
    ) -> dict[str, Any]:
        try:
            if provider == "click":
                url = click_pay_url(self._click_url, service_id=secret["service_id"],
                                    merchant_id=secret["merchant_id"], amount=amount, ref=ref)  # fmt: skip
                return {"checkout_url": url, "qr_payload": url}
            if provider == "payme":
                base = self._payme_test_url if secret.get("test_mode") == "true" else self._payme_url
                url = payme_checkout_url(base, merchant_id=secret["merchant_id"], ref=ref, amount=amount)
                return {"checkout_url": url, "qr_payload": url}
            if provider == "uzum":
                link = await self._uzum_qr.create_order(secret, str(ref), to_tiyin(amount))
                return {"checkout_url": link, "qr_payload": link, "payment_link": link}
            qr = await self._uzqr.create_dynamic_qr(secret, register, to_tiyin(amount), str(ref))
            return {"qr_payload": qr.qr_payload, "checkout_url": None, "provider_tx_id": qr.provider_tx_id}
        except PaymentProviderUnavailableError as exc:
            raise AppError(ErrorCode.PAYMENT_PROVIDER_ERROR, params={"provider": provider}) from exc

    async def get(self, actor: Principal, scope: BranchScope, ref: UUID, ip: str | None) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            co = await self._repo.get(s, ref)
            if co is None or (scope.allowed and co.branch_id not in scope.allowed):
                raise AppError(ErrorCode.NOT_FOUND, params={"resource": "payment_checkouts"})
            secret = None
            if co.provider == "uzum" and co.status == "pending" and co.expires_at > self._clock():
                secret = await self._secrets.get(s, actor.tenant_id, "uzum")
        if secret is not None and all(secret.get(f) for f in UZUM_QR_FIELDS):
            co = await self._poll_uzum(actor.tenant_id, co, secret, ip)
        return checkout_json(co, status=effective_status(co, self._clock()))

    async def _poll_uzum(
        self, tenant_id: UUID, co: CheckoutRow, secret: Mapping[str, str], ip: str | None
    ) -> CheckoutRow:
        """Uzum Dynamic QR has no callback: the POS poll asks ``status-by-order`` (developer.uzumbank.uz)."""
        try:
            order = await self._uzum_qr.order_status(secret, str(co.checkout_ref))
        except PaymentProviderUnavailableError:
            return co  # stays pending; the next poll asks again
        if order.status not in UZUM_QR_PAID and order.status not in UZUM_QR_DEAD:
            return co
        async with self._sf() as s, tenant_transaction(s, tenant_id):
            fresh = await self._repo.get(s, co.checkout_ref, for_update=True)
            if fresh is None or fresh.status != "pending":
                return fresh or co
            if order.status in UZUM_QR_PAID:
                tx = fresh.provider_tx_id or order.payment_id
                await self._repo.update(
                    s, co.checkout_ref, status="confirmed", provider_tx_id=tx, confirmed_at=self._clock(),
                    provider_data={**fresh.provider_data, "qr_status": order.status},
                )  # fmt: skip
                action = "payment_checkout.confirmed"
            else:
                await self._repo.update(
                    s,
                    co.checkout_ref,
                    status="failed",
                    provider_data={**fresh.provider_data, "qr_status": order.status},
                )
                action = "payment_checkout.failed"
            await record_audit(
                s, tenant_id=tenant_id, action=action, entity=ENTITY, entity_id=co.checkout_ref, ip=ip,
                after={"provider": "uzum", "source": "dynamic_qr_status", "provider_status": order.status},
            )  # fmt: skip
            updated = await self._repo.get(s, co.checkout_ref)
        return updated or co


class CheckoutExpirySweep:
    """Cron ``payments_checkout_expire``: ``pending`` past ``expires_at`` → ``expired`` (18 §16.2)."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession], repo: CheckoutRepository) -> None:
        self._sf = session_factory
        self._repo = repo

    async def run(self, tenant_id: UUID, *, now: datetime | None = None) -> int:
        at = now or utc_now()
        async with self._sf() as s, tenant_transaction(s, tenant_id):
            expired = await self._repo.expire_due(s, at, EXPIRE_BATCH)
            for ref in expired:
                await record_audit(s, tenant_id=tenant_id, action="payment_checkout.expired", entity=ENTITY,
                                   entity_id=ref)  # fmt: skip
        return len(expired)
