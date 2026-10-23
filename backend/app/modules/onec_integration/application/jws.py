"""Compact JWS helpers of the agent artefacts (33 §9.4) — shared with the auth module's assertion check."""

from __future__ import annotations

from app.modules.auth.application.compact_jws import (
    JwsError,
    public_jwk_of,
    public_key_from_jwk,
    root_kid,
    sign_compact,
    sign_detached_b64,
    unverified_parts,
    verify_compact,
)

__all__ = [
    "JwsError",
    "public_jwk_of",
    "public_key_from_jwk",
    "root_kid",
    "sign_compact",
    "sign_detached_b64",
    "unverified_parts",
    "verify_compact",
]
