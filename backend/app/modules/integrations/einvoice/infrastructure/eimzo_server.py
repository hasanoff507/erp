"""E-IMZO-SERVER verification adapter (21 §5) — ⛔ 26 #118.

Server-side PKCS#7 verification goes through E-IMZO-SERVER (Java, licence + written contract, VPN key to
``vpn.e-imzo.uz:3443`` from Uzbek IPs only); its API is distributed through a closed channel with the
contract, so there is no public wire protocol to implement. Until the contract exists every verification
raises :class:`SignatureUnavailableError` and ``submit-signed`` answers ``422 EIMZO_SIGN_FAILED``
(``params.reason='verification_unavailable'``) — a signature is never accepted unverified.
"""

from __future__ import annotations

from app.modules.integrations.einvoice.application.ports import SignatureCheck, SignatureUnavailableError


class EImzoServerVerifier:
    async def verify_attached(self, pkcs7_b64: str, expected_content: bytes) -> SignatureCheck:
        raise SignatureUnavailableError("E-IMZO-SERVER is not contracted yet (26 #118)")
