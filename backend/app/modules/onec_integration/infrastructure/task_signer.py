"""Ed25519 compact JWS of a leased task (33 §9.4) with the active ``platform.signing_keys`` key of purpose
``onec_task`` (14 §6 rotation ``next → active → retired``; the ring caches it for 60 s)."""

from __future__ import annotations

from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.modules.auth.application.keys import SigningKeyRing
from app.modules.onec_integration.application.jws import sign_compact
from app.modules.onec_integration.domain.envelope import ALG, TASK_TYP


class RingTaskSigner:
    def __init__(self, ring: SigningKeyRing) -> None:
        self._ring = ring

    async def sign(self, claims: dict[str, Any]) -> tuple[str, str]:
        kid, key = await self._ring.signing_key()
        private = key.private_key
        if not isinstance(private, Ed25519PrivateKey):
            raise RuntimeError("onec_task signing key is not Ed25519")
        return kid, sign_compact({"alg": ALG, "typ": TASK_TYP, "kid": kid}, claims, private)
