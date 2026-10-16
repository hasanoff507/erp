"""structlog setup (23 §8, 32 §5.2): JSON logs with request/tenant/user ids, PII redacted."""

from __future__ import annotations

import logging
import re
import sys
from collections.abc import Mapping, MutableMapping
from typing import Any

import structlog
from structlog.typing import EventDict, WrappedLogger

from app.core.context import request_id_var, tenant_id_var, user_id_var

REDACTED = "[redacted]"

_SENSITIVE_TOKENS = frozenset(
    {
        "phone", "stir", "inn", "pinfl", "jshshir", "password", "passwd", "pin", "secret", "token",
        "authorization", "cookie", "pan", "cvv", "cvc", "track", "otp", "address",
    }
)  # fmt: skip
_SENSITIVE_KEYS = frozenset({"api_key", "private_key", "code_hash", "set-cookie", "x-csrf-token"})
# +998 XX XXX XX XX / 998XXXXXXXXX and 13–19 digit card-like numbers
_PHONE = re.compile(r"\+?998[\s-]?\d{2}[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}")
_CARD = re.compile(r"\b(?:\d[ -]?){13,19}\b")
_PINFL = re.compile(r"\b\d{14}\b")
# secrets that travel inside URLs/strings (SEC-06): the Telegram bot token is a path segment
# (``/bot<id>:<secret>/sendMessage``); bearer tokens may end up in exception texts
_BOT_TOKEN = re.compile(r"/bot\d+:[A-Za-z0-9_-]+")
_BEARER = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+")

_SAFE_KEYS = frozenset({"request_id", "tenant_id", "user_id", "event", "level", "timestamp", "logger"})


def is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    if lowered in _SENSITIVE_KEYS:
        return True
    return any(token in _SENSITIVE_TOKENS for token in re.split(r"[_\-.]", lowered))


def scrub_url(value: str) -> str:
    """Strip credentials that are part of a URL (Telegram ``/bot<token>/``) — span/breadcrumb URLs."""
    return _BOT_TOKEN.sub("/bot***", value)


def _scrub_text(value: str) -> str:
    value = scrub_url(value)
    value = _BEARER.sub(f"Bearer {REDACTED}", value)
    value = _PHONE.sub(REDACTED, value)
    value = _CARD.sub(REDACTED, value)
    return _PINFL.sub(REDACTED, value)


def _scrub(value: Any, key: str | None = None) -> Any:
    if key is not None and key not in _SAFE_KEYS and is_sensitive_key(key):
        return REDACTED
    if isinstance(value, str):
        return _scrub_text(value)
    if isinstance(value, Mapping):
        return {k: _scrub(v, str(k)) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_scrub(v) for v in value]
    return value


def redact_pii(_: WrappedLogger, __: str, event_dict: EventDict) -> EventDict:
    return {k: _scrub(v, k) for k, v in event_dict.items()}


def add_request_context(_: WrappedLogger, __: str, event_dict: EventDict) -> EventDict:
    for key, var in (("request_id", request_id_var), ("tenant_id", tenant_id_var), ("user_id", user_id_var)):
        value = var.get()
        if value is not None:
            event_dict.setdefault(key, str(value))
    return event_dict


def configure_logging(level: str = "INFO", *, json: bool = True) -> None:
    renderer: Any = structlog.processors.JSONRenderer() if json else structlog.dev.ConsoleRenderer()
    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        add_request_context,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        redact_pii,
        renderer,
    ]
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelNamesMapping()[level.upper()]),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )
    logging.basicConfig(level=level.upper(), stream=sys.stdout, format="%(message)s")


def scrub_mapping(data: MutableMapping[str, Any]) -> dict[str, Any]:
    """Redact a mapping the same way log events are redacted (for Sentry tags etc.)."""
    return {k: _scrub(v, k) for k, v in data.items()}
