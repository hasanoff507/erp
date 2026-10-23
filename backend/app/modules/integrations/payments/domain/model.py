"""Shop payment checkouts — statuses and provider wire rules (18 §16, 21 §9). Pure Python.

Sources (public partner documentation, 21 «Manbalar»):

* Click SHOP API — https://docs.click.uz/en/shop-api/requests , https://docs.click.uz/en/shop-api/errors ,
  payment link — https://docs.click.uz/en/click-button/
* Payme Merchant API — https://developer.help.paycom.uz/metody-merchant-api/ (methods, errors),
  GET checkout — https://developer.help.paycom.uz/initsializatsiya-platezhey/otpravka-cheka-po-metodu-get
* Uzum Bank Merchant API (webhooks) — https://developer.uzumbank.uz/en/merchant/ ,
  Dynamic QR — https://developer.uzumbank.uz/en/dynamicqr/
"""

from __future__ import annotations

import base64
import hashlib
import hmac
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import Final, Literal
from urllib.parse import urlencode
from uuid import UUID

Provider = Literal["uzqr", "click", "payme", "uzum"]
Status = Literal["pending", "confirmed", "failed", "expired", "consumed"]
PROVIDERS: Final[tuple[str, ...]] = ("uzqr", "click", "payme", "uzum")
PAID: Final = frozenset({"confirmed", "consumed"})  # money is with the shop
DEAD: Final = frozenset({"failed", "expired"})


def to_tiyin(amount: Decimal) -> int:
    return int((amount * 100).to_integral_value())


def parse_ref(raw: object) -> UUID | None:
    try:
        return UUID(str(raw))
    except (TypeError, ValueError):
        return None


def parse_amount(raw: object) -> Decimal | None:
    try:
        value = Decimal(str(raw).strip())
    except (InvalidOperation, ValueError):
        return None
    return value if value.is_finite() else None


def same(a: str, b: str) -> bool:
    """Constant-time comparison of secrets/signatures."""
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


# --- Click SHOP API -----------------------------------------------------------------------------------------

CLICK_PREPARE: Final = "0"
CLICK_COMPLETE: Final = "1"
CLICK_FIELDS: Final = (
    "click_trans_id", "service_id", "click_paydoc_id", "merchant_trans_id", "amount", "action", "error",
    "sign_time", "sign_string",
)  # fmt: skip
CLICK_ERRORS: Final[Mapping[int, str]] = {
    0: "Success",
    -1: "SIGN CHECK FAILED!",
    -2: "Incorrect parameter amount",
    -3: "Action not found",
    -4: "Already paid",
    -5: "User does not exist",
    -6: "Transaction does not exist",
    -7: "Failed to update user",
    -8: "Error in request from click",
    -9: "Transaction cancelled",
}


def click_sign(form: Mapping[str, str], secret_key: str) -> str:
    """``md5(click_trans_id + service_id + SECRET_KEY + merchant_trans_id [+ merchant_prepare_id] + amount +
    action + sign_time)`` — the raw request strings (docs.click.uz SHOP API «Requests»)."""
    prepare_id = form.get("merchant_prepare_id", "") if form.get("action") == CLICK_COMPLETE else ""
    raw = (
        form["click_trans_id"] + form["service_id"] + secret_key + form["merchant_trans_id"] + prepare_id
        + form["amount"] + form["action"] + form["sign_time"]
    )  # fmt: skip
    return hashlib.md5(raw.encode("utf-8"), usedforsecurity=False).hexdigest()


def click_pay_url(base: str, *, service_id: str, merchant_id: str, amount: Decimal, ref: UUID) -> str:
    """Payment link (docs.click.uz «Payment Button»); ``transaction_param`` = ``merchant_trans_id``."""
    query = urlencode({
        "service_id": service_id, "merchant_id": merchant_id, "amount": f"{amount:.2f}",
        "transaction_param": str(ref),
    })  # fmt: skip
    return f"{base}?{query}"


# --- Payme Merchant API -------------------------------------------------------------------------------------

PAYME_TIMEOUT_MS: Final = 43_200_000  # 12 h: a created transaction is cancelled with reason 4
PAYME_ACCOUNT_FIELD: Final = "order_id"  # the account field configured in the merchant cabinet
PAYME_REASON_TIMEOUT: Final = 4
PAYME_CREATED, PAYME_PERFORMED, PAYME_CANCELLED, PAYME_CANCELLED_AFTER = 1, 2, -1, -2


def payme_message(ru: str, uz: str, en: str) -> dict[str, str]:
    return {"ru": ru, "uz": uz, "en": en}


PAYME_ERRORS: Final[Mapping[int, dict[str, str]]] = {
    -32700: payme_message("Ошибка разбора JSON", "JSON tahlil xatosi", "JSON parse error"),
    -32600: payme_message("Неверный RPC-запрос", "Noto'g'ri RPC so'rov", "Invalid RPC request"),
    -32601: payme_message("Метод не найден", "Metod topilmadi", "Method not found"),
    -32504: payme_message("Недостаточно привилегий", "Ruxsat yetarli emas", "Insufficient privileges"),
    -32400: payme_message("Системная ошибка", "Tizim xatosi", "System error"),
    -31001: payme_message("Неверная сумма", "Noto'g'ri summa", "Invalid amount"),
    -31003: payme_message("Транзакция не найдена", "Tranzaksiya topilmadi", "Transaction not found"),
    -31007: payme_message(
        "Невозможно отменить транзакцию: товар отпущен",
        "Tranzaksiyani bekor qilib bo'lmaydi: tovar berilgan",
        "Unable to cancel: the goods were delivered",
    ),
    -31008: payme_message(
        "Невозможно выполнить операцию", "Amalni bajarib bo'lmaydi", "Unable to perform operation"
    ),
    # -31050..-31099 — account (order) errors
    -31050: payme_message("Заказ не найден", "Buyurtma topilmadi", "Order not found"),
    -31051: payme_message(
        "Заказ недоступен для оплаты", "Buyurtmani to'lab bo'lmaydi", "Order is not available for payment"
    ),
}  # fmt: skip


def payme_checkout_url(base: str, *, merchant_id: str, ref: UUID, amount: Decimal) -> str:
    """GET checkout: ``<base>/base64("m=<merchant>;ac.order_id=<ref>;a=<tiyin>")``."""
    params = f"m={merchant_id};ac.{PAYME_ACCOUNT_FIELD}={ref};a={to_tiyin(amount)}"
    return f"{base.rstrip('/')}/{base64.b64encode(params.encode()).decode('ascii')}"


def basic_credentials(header: str | None) -> tuple[str, str] | None:
    """``Authorization: Basic base64(login:password)`` → ``(login, password)``."""
    if not header:
        return None
    scheme, _, token = header.strip().partition(" ")
    if scheme.lower() != "basic" or not token:
        return None
    try:
        decoded = base64.b64decode(token.strip(), validate=True).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None
    login, sep, password = decoded.partition(":")
    return (login, password) if sep else None


# --- Uzum Bank Merchant API ---------------------------------------------------------------------------------

UZUM_OPERATIONS: Final = ("check", "create", "confirm", "reverse", "status")
UZUM_CONFIRM_WINDOW_MS: Final = 30 * 60 * 1000  # no /confirm within 30 min of /create → FAILED
UZUM_ACCOUNT_FIELD: Final = "account"
UZUM_ACCESS_DENIED: Final = "10001"
UZUM_JSON_ERROR: Final = "10002"
UZUM_MISSING_PARAMS: Final = "10005"
UZUM_BAD_SERVICE: Final = "10006"
UZUM_NO_ACCOUNT: Final = "10007"
UZUM_ALREADY_PAID: Final = "10008"
UZUM_CANCELLED: Final = "10009"
UZUM_TX_EXISTS: Final = "10010"
UZUM_BAD_AMOUNT: Final = "10011"
UZUM_TX_NOT_FOUND: Final = "10014"
UZUM_TX_CANCELLED: Final = "10015"
UZUM_TX_CONFIRMED: Final = "10016"
UZUM_CANNOT_REVERSE: Final = "10017"
UZUM_TX_REVERSED: Final = "10018"
UZUM_INTERNAL: Final = "99999"

# Uzum Dynamic QR ``status-by-order`` → checkout status
UZUM_QR_PAID: Final = frozenset({"SUCCESS"})
UZUM_QR_DEAD: Final = frozenset({"FAILED", "REVERSED", "CANCELLED", "PARTIAL_CANCELLED"})
