"""Compact JWS (RFC 7515) with Ed25519 (RFC 8037 ``EdDSA``): store-agent client assertions (14 §2.3) and
agent artefacts — task envelopes, task keyset, update manifest (33 §9.4).

Written directly on ``cryptography`` so the exact bytes are under our control (the agent verifies the
received ``seg0.seg1`` ASCII bytes, never a re-serialisation) and the shared vectors are reproducible.
"""

from __future__ import annotations

import base64
import json
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from app.modules.auth.domain.agent_keys import b64url, b64url_decode, jwk_thumbprint


class JwsError(ValueError):
    pass


def _json_bytes(value: dict[str, Any]) -> bytes:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sign_compact(header: dict[str, Any], claims: dict[str, Any], key: Ed25519PrivateKey) -> str:
    signing_input = b64url(_json_bytes(header)) + "." + b64url(_json_bytes(claims))
    return signing_input + "." + b64url(key.sign(signing_input.encode("ascii")))


def verify_compact(token: str, public_key: Ed25519PublicKey) -> tuple[dict[str, Any], dict[str, Any]]:
    """Signature check only (claims are the caller's job); raises :class:`JwsError`."""
    try:
        seg0, seg1, seg2 = token.split(".")
        header = json.loads(b64url_decode(seg0))
        claims = json.loads(b64url_decode(seg1))
        signature = b64url_decode(seg2)
    except (ValueError, UnicodeError) as exc:
        raise JwsError("malformed") from exc
    if not isinstance(header, dict) or not isinstance(claims, dict) or header.get("alg") != "EdDSA":
        raise JwsError("header")
    try:
        public_key.verify(signature, f"{seg0}.{seg1}".encode("ascii"))
    except InvalidSignature as exc:
        raise JwsError("signature") from exc
    return header, claims


def unverified_parts(token: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Header and claims without a signature check (to pick the key); raises :class:`JwsError`."""
    try:
        seg0, seg1, _ = token.split(".")
        header = json.loads(b64url_decode(seg0))
        claims = json.loads(b64url_decode(seg1))
    except (ValueError, UnicodeError) as exc:
        raise JwsError("malformed") from exc
    if not isinstance(header, dict) or not isinstance(claims, dict):
        raise JwsError("malformed")
    return header, claims


def public_jwk_of(key: Ed25519PublicKey) -> dict[str, str]:
    raw = key.public_bytes(Encoding.Raw, PublicFormat.Raw)
    return {"kty": "OKP", "crv": "Ed25519", "x": b64url(raw)}


def public_key_from_jwk(jwk: dict[str, Any]) -> Ed25519PublicKey:
    if jwk.get("kty") != "OKP" or jwk.get("crv") != "Ed25519" or not isinstance(jwk.get("x"), str):
        raise JwsError("jwk")
    try:
        return Ed25519PublicKey.from_public_bytes(b64url_decode(jwk["x"]))
    except ValueError as exc:
        raise JwsError("jwk") from exc


def root_kid(key: Ed25519PublicKey) -> str:
    """``agent_update`` root key id = RFC 7638 thumbprint of its public JWK (contracts/agent-wire.md §4)."""
    return jwk_thumbprint(public_jwk_of(key))


def sign_detached_b64(data: bytes, key: Ed25519PrivateKey) -> str:
    """Update-manifest signature: standard base64 of the Ed25519 signature over the exact bytes."""
    return base64.b64encode(key.sign(data)).decode("ascii")
