"""Provider webhooks — ``POST /payments/webhooks/{provider}`` (18 §16.4, 17 §14, 21 §9).

Shared rules: no user session (the provider's own signature/credentials with the **tenant's** merchant keys);
the tenant is resolved only through SECURITY DEFINER functions — Click by ``merchant_trans_id`` (=
``checkout_ref``, ``payments_checkout_by_ref``), dynamic UzQR by ``provider_tx_id``
(``payments_checkout_by_provider_tx``), Payme/Uzum by the Basic-auth credential fingerprint
(``payments_tenant_by_credential``) — then everything runs in that tenant's transaction under RLS with the
checkout row locked (``FOR UPDATE``). Signatures are compared in constant time; an unverified request changes
nothing. Replays are idempotent by ``provider_tx_id`` (``UNIQUE (provider, provider_tx_id)``): a repeated
confirmation answers the stored result and never counts twice. Amount (tiyin) and the checkout's provider are
bound; card data is never stored. Answers follow each provider's protocol (Click/Payme — HTTP 200 + error
code, Uzum — HTTP 400 + ``errorCode``); every state change is audited (``payment_checkout.*``, no user).
"""

from __future__ import annotations

import json
import secrets as pysecrets
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Final
from urllib.parse import parse_qsl

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.audit import record_audit
from app.core.db.session import tenant_transaction
from app.core.money import money
from app.modules.integrations.payments.application.ports import (
    CheckoutRepository,
    CheckoutRow,
    SecretSource,
    TenantLookup,
    UzqrPort,
)
from app.modules.integrations.payments.domain.model import (
    CLICK_COMPLETE,
    CLICK_ERRORS,
    CLICK_FIELDS,
    CLICK_PREPARE,
    DEAD,
    PAID,
    PAYME_ACCOUNT_FIELD,
    PAYME_CANCELLED,
    PAYME_CANCELLED_AFTER,
    PAYME_CREATED,
    PAYME_ERRORS,
    PAYME_PERFORMED,
    PAYME_REASON_TIMEOUT,
    PAYME_TIMEOUT_MS,
    UZUM_ACCESS_DENIED,
    UZUM_ACCOUNT_FIELD,
    UZUM_ALREADY_PAID,
    UZUM_BAD_AMOUNT,
    UZUM_BAD_SERVICE,
    UZUM_CANCELLED,
    UZUM_CANNOT_REVERSE,
    UZUM_CONFIRM_WINDOW_MS,
    UZUM_JSON_ERROR,
    UZUM_MISSING_PARAMS,
    UZUM_NO_ACCOUNT,
    UZUM_OPERATIONS,
    UZUM_TX_CANCELLED,
    UZUM_TX_CONFIRMED,
    UZUM_TX_EXISTS,
    UZUM_TX_NOT_FOUND,
    UZUM_TX_REVERSED,
    basic_credentials,
    click_sign,
    parse_amount,
    parse_ref,
    same,
    to_tiyin,
)
from app.modules.integrations.tenant_keys.domain.providers import PAYME_LOGIN, credential_hash

log = structlog.get_logger(__name__)

ENTITY: Final = "payment_checkouts"
Clock = Callable[[], datetime]


def _now() -> datetime:
    return datetime.now(UTC)


def _ms(at: datetime) -> int:
    return int(at.timestamp() * 1000)


@dataclass(frozen=True, slots=True)
class WebhookReply:
    status_code: int
    body: Any
    headers: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class WebhookRequest:
    headers: Mapping[str, str]  # lower-case names
    body: bytes
    ip: str | None
    content_type: str = ""


class SignatureInvalidError(Exception):
    """Dynamic UzQR: the provider signature did not verify (→ ``403 WEBHOOK_SIGNATURE_INVALID``)."""


class _Base:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        repo: CheckoutRepository,
        lookup: TenantLookup,
        secrets: SecretSource,
        clock: Clock = _now,
    ) -> None:
        self._sf = session_factory
        self._repo = repo
        self._lookup = lookup
        self._secrets = secrets
        self._clock = clock

    async def _audit(
        self, s: AsyncSession, co: CheckoutRow, action: str, ip: str | None, **after: Any
    ) -> None:
        await record_audit(
            s, tenant_id=co.tenant_id, action=action, entity=ENTITY, entity_id=co.checkout_ref, ip=ip,
            after={"provider": co.provider, "provider_tx_id": after.pop("provider_tx_id", co.provider_tx_id),
                   **after},
        )  # fmt: skip

    async def _confirm(
        self,
        s: AsyncSession,
        co: CheckoutRow,
        ip: str | None,
        *,
        provider_tx_id: str | None,
        data: dict[str, Any],
    ) -> None:
        await self._repo.update(
            s, co.checkout_ref, status="confirmed", provider_tx_id=provider_tx_id, provider_data=data,
            confirmed_at=self._clock(),
        )  # fmt: skip
        await self._audit(s, co, "payment_checkout.confirmed", ip, provider_tx_id=provider_tx_id)

    async def _fail(
        self, s: AsyncSession, co: CheckoutRow, ip: str | None, data: dict[str, Any], reason: str
    ) -> None:
        await self._repo.update(s, co.checkout_ref, status="failed", provider_data=data)
        await self._audit(s, co, "payment_checkout.failed", ip, reason=reason)


# --- Click SHOP API -----------------------------------------------------------------------------------------


def _form(req: WebhookRequest) -> dict[str, str]:
    if "json" in req.content_type:
        try:
            raw = json.loads(req.body or b"{}")
        except ValueError:
            return {}
        return {str(k): str(v) for k, v in raw.items()} if isinstance(raw, dict) else {}
    try:
        text = req.body.decode("utf-8")
    except UnicodeDecodeError:
        return {}
    return dict(parse_qsl(text, keep_blank_values=True))


class ClickWebhook(_Base):
    """Prepare (``action=0``) / Complete (``action=1``); ``sign_string`` MD5 with the tenant's secret key."""

    @staticmethod
    def _error(code: int, form: Mapping[str, str] | None = None) -> WebhookReply:
        body: dict[str, Any] = {"error": code, "error_note": CLICK_ERRORS[code]}
        if form:
            if form.get("click_trans_id", "").isdigit():
                body["click_trans_id"] = int(form["click_trans_id"])
            if form.get("merchant_trans_id"):
                body["merchant_trans_id"] = form["merchant_trans_id"]
        return WebhookReply(200, body)

    async def handle(self, req: WebhookRequest) -> WebhookReply:
        form = _form(req)
        if (
            any(form.get(name) in (None, "") for name in CLICK_FIELDS if name != "error")
            or "error" not in form
        ):
            return self._error(-8, form)
        action = form["action"]
        if action not in (CLICK_PREPARE, CLICK_COMPLETE):
            return self._error(-3, form)
        if action == CLICK_COMPLETE and not form.get("merchant_prepare_id"):
            return self._error(-8, form)
        ref = parse_ref(form["merchant_trans_id"])
        owner = None if ref is None else await self._lookup.by_ref(ref)
        if ref is None or owner is None or owner.provider != "click":
            return self._error(-5, form)
        async with self._sf() as s, tenant_transaction(s, owner.tenant_id):
            secret = await self._secrets.get(s, owner.tenant_id, "click")
            if secret is None or not same(
                click_sign(form, secret["secret_key"]), form["sign_string"].lower()
            ):
                log.warning("click_webhook_sign_failed", checkout_ref=str(ref))
                return self._error(-1, form)
            if form["service_id"] != secret["service_id"]:
                return self._error(-8, form)
            co = await self._repo.get(s, ref, for_update=True)
            if co is None:
                return self._error(-5, form)
            amount = parse_amount(form["amount"])
            if amount is None or money(amount) != money(co.amount):
                return self._error(-2, form)
            if action == CLICK_PREPARE:
                return await self._prepare(s, co, form, req.ip)
            return await self._complete(s, co, form, req.ip)

    async def _prepare(
        self, s: AsyncSession, co: CheckoutRow, form: Mapping[str, str], ip: str | None
    ) -> WebhookReply:
        if co.status in PAID:
            return self._error(-4, form)
        if co.status in DEAD or co.expires_at <= self._clock():
            return self._error(-9, form)
        tx = form["click_trans_id"]
        data = dict(co.provider_data)
        if co.provider_tx_id != tx:  # first Prepare, or Click retries the payment with a new transaction
            if await self._repo.by_provider_tx(s, "click", tx) is not None:
                return self._error(-8, form)
            data.update(
                {"prepare_id": pysecrets.randbelow(2**31 - 2) + 1, "click_paydoc_id": form["click_paydoc_id"]}
            )
            await self._repo.update(s, co.checkout_ref, provider_tx_id=tx, provider_data=data)
            await self._audit(s, co, "payment_checkout.prepared", ip, provider_tx_id=tx)
        return WebhookReply(200, {
            "click_trans_id": int(tx), "merchant_trans_id": form["merchant_trans_id"],
            "merchant_prepare_id": int(data["prepare_id"]), "error": 0, "error_note": CLICK_ERRORS[0],
        })  # fmt: skip

    async def _complete(
        self, s: AsyncSession, co: CheckoutRow, form: Mapping[str, str], ip: str | None
    ) -> WebhookReply:
        tx = form["click_trans_id"]
        prepare_id = co.provider_data.get("prepare_id")
        if co.provider_tx_id != tx or prepare_id is None or str(prepare_id) != form["merchant_prepare_id"]:
            return self._error(-6, form)
        ok = WebhookReply(200, {
            "click_trans_id": int(tx), "merchant_trans_id": form["merchant_trans_id"],
            "merchant_confirm_id": int(prepare_id), "error": 0, "error_note": CLICK_ERRORS[0],
        })  # fmt: skip
        click_error = int(form["error"]) if form["error"].lstrip("-").isdigit() else 0
        if click_error < 0:  # Click reports the payment failed — cancel on our side, answer -9
            if co.status == "pending":
                await self._fail(s, co, ip, dict(co.provider_data), f"click_error:{click_error}")
            return self._error(-9, form)
        if co.status in PAID:
            return self._error(-4, form)
        if co.status == "failed":
            return self._error(-9, form)
        # pending (or expired by our clock while Click was debiting the card): the money is taken — confirm
        await self._confirm(s, co, ip, provider_tx_id=tx, data={**co.provider_data, "completed": True})
        return ok


# --- Payme Merchant API (JSON-RPC) --------------------------------------------------------------------------


class _PaymeError(Exception):
    def __init__(self, code: int, data: str | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.data = data


def _payme_tx(co: CheckoutRow) -> dict[str, Any]:
    d = co.provider_data
    return {
        "create_time": int(d.get("create_time", 0)), "perform_time": int(d.get("perform_time", 0)),
        "cancel_time": int(d.get("cancel_time", 0)), "transaction": str(co.checkout_ref),
        "state": int(d.get("state", PAYME_CREATED)), "reason": d.get("reason"),
    }  # fmt: skip


class PaymeWebhook(_Base):
    """JSON-RPC 2.0 over one URL; ``Authorization: Basic Paycom:<key>`` (tenant's cash key)."""

    async def handle(self, req: WebhookRequest) -> WebhookReply:
        rpc_id: Any = None
        try:
            payload = json.loads(req.body)
        except ValueError:
            return self._reply(None, error=_PaymeError(-32700))
        if not isinstance(payload, dict):
            return self._reply(None, error=_PaymeError(-32600))
        rpc_id = payload.get("id")
        method, params = payload.get("method"), payload.get("params")
        creds = basic_credentials(req.headers.get("authorization"))
        tenant_id = None
        if creds is not None and creds[0] == PAYME_LOGIN:
            tenant_id = await self._lookup.by_credential(
                "payme", credential_hash("payme", creds[0], creds[1])
            )
        if tenant_id is None or creds is None:
            return self._reply(rpc_id, error=_PaymeError(-32504))
        if not isinstance(method, str) or not isinstance(params, dict):
            return self._reply(rpc_id, error=_PaymeError(-32600))
        handler = {
            "CheckPerformTransaction": self._check_perform, "CreateTransaction": self._create,
            "PerformTransaction": self._perform, "CancelTransaction": self._cancel,
            "CheckTransaction": self._check, "GetStatement": self._statement,
        }.get(method)  # fmt: skip
        if handler is None:
            return self._reply(rpc_id, error=_PaymeError(-32601, method))
        try:
            async with self._sf() as s, tenant_transaction(s, tenant_id):
                secret = await self._secrets.get(s, tenant_id, "payme")
                if secret is None or not same(secret["key"], creds[1]):
                    raise _PaymeError(-32504)
                result = await handler(s, params, req.ip)
        except _PaymeError as exc:  # raised — nothing was written (the transaction rolled back)
            return self._reply(rpc_id, error=exc)
        except (KeyError, TypeError, ValueError):
            return self._reply(rpc_id, error=_PaymeError(-32600))
        if isinstance(result, _PaymeError):  # returned — a state change (timeout cancel) was committed
            return self._reply(rpc_id, error=result)
        return self._reply(rpc_id, result=result)

    @staticmethod
    def _reply(rpc_id: Any, *, result: Any = None, error: _PaymeError | None = None) -> WebhookReply:
        if error is None:
            return WebhookReply(200, {"jsonrpc": "2.0", "id": rpc_id, "result": result})
        err: dict[str, Any] = {
            "code": error.code,
            "message": PAYME_ERRORS.get(error.code, PAYME_ERRORS[-32400]),
        }
        if error.data is not None:
            err["data"] = error.data
        return WebhookReply(200, {"jsonrpc": "2.0", "id": rpc_id, "error": err})

    async def _order(self, s: AsyncSession, params: Mapping[str, Any], *, lock: bool) -> CheckoutRow:
        account = params.get("account")
        ref = parse_ref(account.get(PAYME_ACCOUNT_FIELD)) if isinstance(account, dict) else None
        co = None if ref is None else await self._repo.get(s, ref, for_update=lock)
        if co is None or co.provider != "payme":
            raise _PaymeError(-31050, PAYME_ACCOUNT_FIELD)
        amount = params.get("amount")
        if not isinstance(amount, int) or isinstance(amount, bool) or amount != to_tiyin(co.amount):
            raise _PaymeError(-31001)
        return co

    def _payable(self, co: CheckoutRow) -> None:
        if co.status != "pending" or co.expires_at <= self._clock():
            raise _PaymeError(-31051, PAYME_ACCOUNT_FIELD)

    async def _check_perform(self, s: AsyncSession, params: Mapping[str, Any], ip: str | None) -> Any:
        co = await self._order(s, params, lock=False)
        self._payable(co)
        if co.provider_tx_id is not None and co.provider_data.get("state") == PAYME_CREATED:
            raise _PaymeError(-31051, PAYME_ACCOUNT_FIELD)  # one order — one transaction in progress
        return {"allow": True}

    async def _timed_out(self, s: AsyncSession, co: CheckoutRow, ip: str | None) -> bool:
        now = _ms(self._clock())
        if now - int(co.provider_data.get("create_time", now)) <= PAYME_TIMEOUT_MS:
            return False
        data = {
            **co.provider_data,
            "state": PAYME_CANCELLED,
            "cancel_time": now,
            "reason": PAYME_REASON_TIMEOUT,
        }
        await self._fail(s, co, ip, data, "payme_timeout")
        return True

    async def _create(self, s: AsyncSession, params: Mapping[str, Any], ip: str | None) -> Any:
        tx = str(params["id"])
        existing = await self._repo.by_provider_tx(s, "payme", tx, for_update=True)
        if existing is not None:
            if existing.provider_data.get("state") != PAYME_CREATED:
                raise _PaymeError(-31008)
            if await self._timed_out(s, existing, ip):
                return _PaymeError(-31008)
            out = _payme_tx(existing)
            return {
                "create_time": out["create_time"],
                "transaction": out["transaction"],
                "state": out["state"],
            }
        co = await self._order(s, params, lock=True)
        self._payable(co)
        if co.provider_tx_id is not None and co.provider_data.get("state") == PAYME_CREATED:
            raise _PaymeError(-31051, PAYME_ACCOUNT_FIELD)
        created = _ms(self._clock())
        data = {
            **co.provider_data,
            "state": PAYME_CREATED,
            "time": int(params["time"]),
            "create_time": created,
        }
        await self._repo.update(s, co.checkout_ref, provider_tx_id=tx, provider_data=data)
        await self._audit(s, co, "payment_checkout.prepared", ip, provider_tx_id=tx)
        return {"create_time": created, "transaction": str(co.checkout_ref), "state": PAYME_CREATED}

    async def _by_id(self, s: AsyncSession, params: Mapping[str, Any]) -> CheckoutRow:
        co = await self._repo.by_provider_tx(s, "payme", str(params["id"]), for_update=True)
        if co is None:
            raise _PaymeError(-31003)
        return co

    async def _perform(self, s: AsyncSession, params: Mapping[str, Any], ip: str | None) -> Any:
        co = await self._by_id(s, params)
        state = co.provider_data.get("state")
        if state == PAYME_CREATED:
            if await self._timed_out(s, co, ip):
                return _PaymeError(-31008)
            if co.status != "pending":  # failed by us / expired without a Payme cancel
                raise _PaymeError(-31008)
            performed = _ms(self._clock())
            data = {**co.provider_data, "state": PAYME_PERFORMED, "perform_time": performed}
            await self._confirm(s, co, ip, provider_tx_id=co.provider_tx_id, data=data)
            return {"transaction": str(co.checkout_ref), "perform_time": performed, "state": PAYME_PERFORMED}
        if state == PAYME_PERFORMED:
            return {"transaction": str(co.checkout_ref),
                    "perform_time": int(co.provider_data["perform_time"]),
                    "state": PAYME_PERFORMED}  # fmt: skip
        raise _PaymeError(-31008)

    async def _cancel(self, s: AsyncSession, params: Mapping[str, Any], ip: str | None) -> Any:
        co = await self._by_id(s, params)
        state = co.provider_data.get("state")
        reason = params.get("reason")
        now = _ms(self._clock())
        if state == PAYME_CREATED:
            data = {**co.provider_data, "state": PAYME_CANCELLED, "cancel_time": now, "reason": reason}
            await self._fail(s, co, ip, data, f"payme_cancel:{reason}")
            return {"transaction": str(co.checkout_ref), "cancel_time": now, "state": PAYME_CANCELLED}
        if state == PAYME_PERFORMED:
            if co.status == "consumed":  # the receipt is issued, the goods are with the customer
                raise _PaymeError(-31007)
            data = {**co.provider_data, "state": PAYME_CANCELLED_AFTER, "cancel_time": now, "reason": reason}
            await self._fail(s, co, ip, data, f"payme_cancel:{reason}")
            return {"transaction": str(co.checkout_ref), "cancel_time": now, "state": PAYME_CANCELLED_AFTER}
        return {"transaction": str(co.checkout_ref),
                "cancel_time": int(co.provider_data.get("cancel_time", 0)),
                "state": int(state or PAYME_CANCELLED)}  # fmt: skip

    async def _check(self, s: AsyncSession, params: Mapping[str, Any], ip: str | None) -> Any:
        return _payme_tx(await self._by_id(s, params))

    async def _statement(self, s: AsyncSession, params: Mapping[str, Any], ip: str | None) -> Any:
        rows = await self._repo.payme_statement(s, int(params["from"]), int(params["to"]))
        out = []
        for co in rows:
            item = _payme_tx(co)
            out.append({
                "id": co.provider_tx_id, "time": int(co.provider_data.get("time", 0)),
                "amount": to_tiyin(co.amount),
                "account": {PAYME_ACCOUNT_FIELD: str(co.checkout_ref)}, **item, "receivers": None,
            })  # fmt: skip
        return {"transactions": out}


# --- Uzum Bank Merchant API ---------------------------------------------------------------------------------


class UzumWebhook(_Base):
    """``/check``, ``/create``, ``/confirm``, ``/reverse``, ``/status`` — JSON + Basic auth."""

    def _fail_reply(self, body: Mapping[str, Any], code: str, **extra: Any) -> WebhookReply:
        out: dict[str, Any] = {"serviceId": body.get("serviceId"), "status": "FAILED", "errorCode": code}
        if "transId" in body:
            out["transId"] = body.get("transId")
        if "timestamp" in body and "transId" not in body:
            out["timestamp"] = _ms(self._clock())
        out.update(extra)
        return WebhookReply(400, out)

    async def handle(self, operation: str, req: WebhookRequest) -> WebhookReply:
        if operation not in UZUM_OPERATIONS:
            return WebhookReply(400, {"status": "FAILED", "errorCode": "10003"})
        try:
            body = json.loads(req.body)
        except ValueError:
            return WebhookReply(400, {"status": "FAILED", "errorCode": UZUM_JSON_ERROR})
        if not isinstance(body, dict):
            return WebhookReply(400, {"status": "FAILED", "errorCode": UZUM_JSON_ERROR})
        creds = basic_credentials(req.headers.get("authorization"))
        tenant_id = None if creds is None else await self._lookup.by_credential(
            "uzum", credential_hash("uzum", creds[0], creds[1])
        )  # fmt: skip
        if tenant_id is None or creds is None:
            return self._fail_reply(body, UZUM_ACCESS_DENIED)
        needs = {
            "check": ("serviceId", "timestamp", "params"),
            "create": ("serviceId", "timestamp", "transId", "params", "amount"),
            "confirm": ("serviceId", "timestamp", "transId"),
            "reverse": ("serviceId", "timestamp", "transId"),
            "status": ("serviceId", "timestamp", "transId"),
        }
        if any(body.get(k) in (None, "") for k in needs[operation]):
            return self._fail_reply(body, UZUM_MISSING_PARAMS)
        async with self._sf() as s, tenant_transaction(s, tenant_id):
            secret = await self._secrets.get(s, tenant_id, "uzum")
            if secret is None or not (same(secret["login"], creds[0]) and same(secret["password"], creds[1])):
                return self._fail_reply(body, UZUM_ACCESS_DENIED)
            if str(body["serviceId"]) != secret["merchant_id"]:
                return self._fail_reply(body, UZUM_BAD_SERVICE)
            handler = {"check": self._check, "create": self._create, "confirm": self._confirm_op,
                       "reverse": self._reverse, "status": self._status}[operation]  # fmt: skip
            return await handler(s, body, req.ip)

    async def _account(self, s: AsyncSession, body: Mapping[str, Any], *, lock: bool) -> CheckoutRow | None:
        params = body.get("params")
        ref = parse_ref(params.get(UZUM_ACCOUNT_FIELD)) if isinstance(params, dict) else None
        co = None if ref is None else await self._repo.get(s, ref, for_update=lock)
        return co if co is not None and co.provider == "uzum" else None

    def _closed(self, co: CheckoutRow, body: Mapping[str, Any]) -> WebhookReply | None:
        if co.status in PAID:
            return self._fail_reply(body, UZUM_ALREADY_PAID)
        if co.status in DEAD or co.expires_at <= self._clock():
            return self._fail_reply(body, UZUM_CANCELLED)
        return None

    def _busy(self, co: CheckoutRow, tx: str | None) -> bool:
        if co.provider_tx_id is None or co.provider_tx_id == tx or co.provider_data.get("state") != "CREATED":
            return False
        return _ms(self._clock()) - int(co.provider_data.get("trans_time", 0)) <= UZUM_CONFIRM_WINDOW_MS

    async def _check(self, s: AsyncSession, body: Mapping[str, Any], ip: str | None) -> WebhookReply:
        co = await self._account(s, body, lock=False)
        if co is None:
            return self._fail_reply(body, UZUM_NO_ACCOUNT)
        closed = self._closed(co, body)
        if closed is not None:
            return closed
        if self._busy(co, None):
            return self._fail_reply(body, UZUM_ALREADY_PAID)
        return WebhookReply(200, {
            "serviceId": body["serviceId"], "timestamp": _ms(self._clock()), "status": "OK",
            "data": {UZUM_ACCOUNT_FIELD: {"value": str(co.checkout_ref)}},
        })  # fmt: skip

    async def _create(self, s: AsyncSession, body: Mapping[str, Any], ip: str | None) -> WebhookReply:
        tx = str(body["transId"])
        if await self._repo.by_provider_tx(s, "uzum", tx) is not None:
            return self._fail_reply(body, UZUM_TX_EXISTS)
        co = await self._account(s, body, lock=True)
        if co is None:
            return self._fail_reply(body, UZUM_NO_ACCOUNT)
        closed = self._closed(co, body)
        if closed is not None:
            return closed
        if self._busy(co, tx):
            return self._fail_reply(body, UZUM_ALREADY_PAID)
        amount = body.get("amount")
        if not isinstance(amount, int) or isinstance(amount, bool) or amount != to_tiyin(co.amount):
            return self._fail_reply(body, UZUM_BAD_AMOUNT)
        now = _ms(self._clock())
        data = {**co.provider_data, "state": "CREATED", "trans_time": now}
        await self._repo.update(s, co.checkout_ref, provider_tx_id=tx, provider_data=data)
        await self._audit(s, co, "payment_checkout.prepared", ip, provider_tx_id=tx)
        return WebhookReply(200, {
            "serviceId": body["serviceId"], "transId": tx, "status": "CREATED", "transTime": now,
            "data": {UZUM_ACCOUNT_FIELD: {"value": str(co.checkout_ref)}}, "amount": amount,
        })  # fmt: skip

    async def _tx(self, s: AsyncSession, body: Mapping[str, Any]) -> CheckoutRow | None:
        return await self._repo.by_provider_tx(s, "uzum", str(body["transId"]), for_update=True)

    async def _confirm_op(self, s: AsyncSession, body: Mapping[str, Any], ip: str | None) -> WebhookReply:
        co = await self._tx(s, body)
        if co is None:
            return self._fail_reply(body, UZUM_TX_NOT_FOUND)
        state = co.provider_data.get("state")
        if state == "CONFIRMED" or co.status in PAID:
            return self._fail_reply(body, UZUM_TX_CONFIRMED)
        if state == "REVERSED" or co.status == "failed":
            return self._fail_reply(body, UZUM_TX_CANCELLED)
        now = _ms(self._clock())
        if now - int(co.provider_data.get("trans_time", now)) > UZUM_CONFIRM_WINDOW_MS:
            await self._fail(s, co, ip, {**co.provider_data, "state": "FAILED"}, "uzum_confirm_window")
            return self._fail_reply(body, UZUM_TX_CANCELLED)
        source = body.get("paymentSource")
        data = {**co.provider_data, "state": "CONFIRMED", "confirm_time": now,
                "payment_source": source if isinstance(source, str) else None}  # fmt: skip
        await self._confirm(s, co, ip, provider_tx_id=co.provider_tx_id, data=data)
        return WebhookReply(200, {
            "serviceId": body["serviceId"], "transId": co.provider_tx_id, "status": "CONFIRMED",
            "confirmTime": now,
            "data": {UZUM_ACCOUNT_FIELD: {"value": str(co.checkout_ref)}}, "amount": to_tiyin(co.amount),
        })  # fmt: skip

    async def _reverse(self, s: AsyncSession, body: Mapping[str, Any], ip: str | None) -> WebhookReply:
        co = await self._tx(s, body)
        if co is None:
            return self._fail_reply(body, UZUM_TX_NOT_FOUND)
        if co.provider_data.get("state") == "REVERSED":
            return self._fail_reply(body, UZUM_TX_REVERSED)
        if co.status == "consumed":
            return self._fail_reply(body, UZUM_CANNOT_REVERSE)
        now = _ms(self._clock())
        await self._fail(
            s, co, ip, {**co.provider_data, "state": "REVERSED", "reverse_time": now}, "uzum_reverse"
        )
        return WebhookReply(200, {
            "serviceId": body["serviceId"], "transId": co.provider_tx_id, "status": "REVERSED",
            "reverseTime": now,
            "data": {UZUM_ACCOUNT_FIELD: {"value": str(co.checkout_ref)}}, "amount": to_tiyin(co.amount),
        })  # fmt: skip

    async def _status(self, s: AsyncSession, body: Mapping[str, Any], ip: str | None) -> WebhookReply:
        co = await self._tx(s, body)
        if co is None:
            return self._fail_reply(body, UZUM_TX_NOT_FOUND)
        d = co.provider_data
        state = d.get("state")
        if state not in ("CREATED", "CONFIRMED", "REVERSED"):
            return self._fail_reply(body, UZUM_TX_CANCELLED, transTime=d.get("trans_time"))
        return WebhookReply(200, {
            "serviceId": body["serviceId"], "transId": co.provider_tx_id, "status": state,
            "transTime": d.get("trans_time"), "confirmTime": d.get("confirm_time"),
            "reverseTime": d.get("reverse_time"),
            "data": {UZUM_ACCOUNT_FIELD: {"value": str(co.checkout_ref)}},
            "amount": to_tiyin(co.amount),
        })  # fmt: skip


# --- dynamic bank UzQR (UzqrPort; real protocol ⛔ 26 #49) ------------------------------------------------


class UzqrWebhook(_Base):
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        repo: CheckoutRepository,
        lookup: TenantLookup,
        secrets: SecretSource,
        port: UzqrPort,
        clock: Clock = _now,
    ) -> None:
        super().__init__(session_factory, repo, lookup, secrets, clock)
        self._port = port

    async def handle(self, req: WebhookRequest) -> WebhookReply:
        event = self._port.webhook_transaction(req.headers, req.body)
        if event is None:
            raise SignatureInvalidError
        tenant_id = await self._lookup.by_provider_tx("uzqr", event.provider_tx_id)
        if tenant_id is None:
            raise SignatureInvalidError
        async with self._sf() as s, tenant_transaction(s, tenant_id):
            co = await self._repo.by_provider_tx(s, "uzqr", event.provider_tx_id, for_update=True)
            if co is None:
                raise SignatureInvalidError
            secret = await self._secrets.get(s, tenant_id, "uzqr", cash_register_id=co.cash_register_id)
            if secret is None or not self._port.verify_webhook(req.headers, req.body, secret):
                log.warning("uzqr_webhook_signature_failed", checkout_ref=str(co.checkout_ref))
                raise SignatureInvalidError
            if event.status == "paid":
                if co.status in PAID:
                    return WebhookReply(200, {"status": "ok", "duplicate": True})
                if event.amount_tiyin is not None and event.amount_tiyin != to_tiyin(Decimal(co.amount)):
                    await self._audit(s, co, "payment_checkout.amount_mismatch", req.ip,
                                      amount_tiyin=event.amount_tiyin)  # fmt: skip
                    return WebhookReply(200, {"status": "rejected", "reason": "amount_mismatch"})
                if co.status == "failed":
                    return WebhookReply(200, {"status": "rejected", "reason": "checkout_failed"})
                await self._confirm(
                    s, co, req.ip, provider_tx_id=co.provider_tx_id, data=dict(co.provider_data)
                )
            elif event.status == "failed" and co.status == "pending":
                await self._fail(s, co, req.ip, dict(co.provider_data), "uzqr_failed")
        return WebhookReply(200, {"status": "ok"})
