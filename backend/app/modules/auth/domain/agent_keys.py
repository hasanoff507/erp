"""Store-agent pairing primitives (14 §2.3, 33 §9.2, 34 §5.1). Pure Python.

* ``public_jwk`` — Ed25519 OKP JWK of the agent (RFC 8037), only ``kty``/``crv``/``x`` are kept;
* RFC 7638 thumbprint — ``kid`` of the agent's client assertions and ``onec_agents.public_key_thumbprint``;
* RFC 8628 ``user_code`` — 8 letters of ``BCDFGHJKLMNPQRSTVWXZ`` (20^8 ≈ 2.6·10^10), shown ``XXXX-XXXX``;
* ``device_code`` — 256 random bits, base64url (43 chars); only its SHA-256 is stored.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
import secrets
from typing import Any, Final

USER_CODE_ALPHABET: Final = "BCDFGHJKLMNPQRSTVWXZ"
USER_CODE_LENGTH: Final = 8
_USER_CODE = re.compile(rf"^[{USER_CODE_ALPHABET}]{{{USER_CODE_LENGTH}}}$")
MACHINE_HASH = re.compile(r"^[0-9a-f]{64}$")
ED25519_PUBLIC_LEN: Final = 32


class InvalidAgentKeyError(ValueError):
    pass


def b64url_decode(value: str) -> bytes:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]*", value):
        raise InvalidAgentKeyError("not base64url")
    try:
        return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except (binascii.Error, ValueError) as exc:
        raise InvalidAgentKeyError("not base64url") from exc


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def parse_public_jwk(raw: str | dict[str, Any]) -> dict[str, str]:
    """Canonical ``{"kty":"OKP","crv":"Ed25519","x":…}``; raises :class:`InvalidAgentKeyError`.

    A ``kid`` member, if present, must equal the RFC 7638 thumbprint; private members (``d``) are refused.
    """
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
    except ValueError as exc:
        raise InvalidAgentKeyError("public_jwk is not JSON") from exc
    if not isinstance(data, dict):
        raise InvalidAgentKeyError("public_jwk is not an object")
    if "d" in data:
        raise InvalidAgentKeyError("private key material")
    if data.get("kty") != "OKP" or data.get("crv") != "Ed25519":
        raise InvalidAgentKeyError("not an Ed25519 OKP key")
    x = data.get("x")
    if not isinstance(x, str) or len(b64url_decode(x)) != ED25519_PUBLIC_LEN or b64url(b64url_decode(x)) != x:
        raise InvalidAgentKeyError("x")
    jwk = {"kty": "OKP", "crv": "Ed25519", "x": x}
    kid = data.get("kid")
    if kid is not None and kid != jwk_thumbprint(jwk):
        raise InvalidAgentKeyError("kid")
    return jwk


def jwk_thumbprint(jwk: dict[str, str]) -> str:
    """RFC 7638 §3 for OKP (RFC 8037 §2): SHA-256 of ``{"crv","kty","x"}`` in that order, base64url."""
    canonical = json.dumps(
        {"crv": jwk["crv"], "kty": jwk["kty"], "x": jwk["x"]}, separators=(",", ":"), sort_keys=True
    )
    return b64url(hashlib.sha256(canonical.encode("utf-8")).digest())


def new_device_code() -> str:
    return b64url(secrets.token_bytes(32))


def device_code_hash(device_code: str) -> str:
    return hashlib.sha256(device_code.encode("ascii", "replace")).hexdigest()


def new_user_code() -> str:
    return "".join(secrets.choice(USER_CODE_ALPHABET) for _ in range(USER_CODE_LENGTH))


def normalize_user_code(raw: str) -> str | None:
    """User input (``wdjb-mjht``, ``WDJB MJHT``) → ``WDJBMJHT``; ``None`` when it cannot be a code."""
    value = "".join(ch for ch in (raw or "")[:32] if ch not in "- \t").upper()
    return value if _USER_CODE.fullmatch(value) else None


def display_user_code(code: str) -> str:
    return f"{code[:4]}-{code[4:]}"
