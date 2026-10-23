"""E-IMZO signing flow, server side (21 §5; 19 §8a, §19, §20; 18 §14a): ``sign-challenge`` → browser
E-IMZO (attached PKCS#7 over the ``document_hash``) → ``submit-signed``.

* A challenge is a random id bound to **tenant + user + entity + document id + action + document_hash**,
  kept ``CHALLENGE_TTL_S`` (10 min) and consumed on first use (single use — a replayed or foreign
  challenge is ``422 EIMZO_SIGN_FAILED``, ``reason='challenge_invalid'``).
* ``submit-signed`` re-reads the document and recomputes the hash: a document changed after the challenge
  is refused (``reason='document_changed'``).
* The PKCS#7 is verified by :class:`SignaturePort` outside the business transaction (E-IMZO-SERVER is an
  external call, 23 §2.1 step 5); an unreachable verifier is ``reason='verification_unavailable'`` — a
  signature is never stored unverified.
"""

from __future__ import annotations

import secrets
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from app.modules.integrations.einvoice.application.ports import SignaturePort, SignatureUnavailableError
from app.modules.integrations.einvoice.domain.documents import (
    CHALLENGE_TTL_S,
    Entity,
    SignAction,
    document_hash,
    signed_content,
)


class ChallengeStore(Protocol):
    async def put(self, challenge_id: str, data: Mapping[str, str], ttl_s: int) -> None: ...
    async def take(self, challenge_id: str) -> dict[str, str] | None:
        """Return and delete atomically (single use); ``None`` — unknown or expired."""
        ...


@dataclass(frozen=True, slots=True)
class VerifiedSignature:
    document_hash: str
    pkcs7: str
    certificate_serial: str | None
    signer_tin: str | None


def sign_failed(reason: str) -> AppError:
    return AppError(ErrorCode.EIMZO_SIGN_FAILED, params={"reason": reason})


class Signer:
    def __init__(self, store: ChallengeStore, verifier: SignaturePort) -> None:
        self._store = store
        self._verifier = verifier

    async def challenge(
        self,
        tenant_id: UUID,
        user_id: UUID,
        entity: Entity,
        entity_id: UUID,
        action: SignAction,
        document: Mapping[str, Any],
    ) -> dict[str, Any]:
        doc_hash = document_hash(entity, str(entity_id), action, document)
        challenge_id = secrets.token_urlsafe(24)
        await self._store.put(
            challenge_id,
            {
                "tenant_id": str(tenant_id),
                "user_id": str(user_id),
                "entity": entity,
                "entity_id": str(entity_id),
                "action": action,
                "document_hash": doc_hash,
            },
            CHALLENGE_TTL_S,
        )
        return {"document_hash": doc_hash, "challenge_id": challenge_id, "expires_in": CHALLENGE_TTL_S}

    async def take(
        self,
        challenge_id: str,
        *,
        tenant_id: UUID,
        user_id: UUID,
        entity: Entity,
        entity_id: UUID,
        action: SignAction,
    ) -> str:
        """Consume the challenge; returns its ``document_hash``."""
        data = await self._store.take(challenge_id)
        expected = {
            "tenant_id": str(tenant_id),
            "user_id": str(user_id),
            "entity": entity,
            "entity_id": str(entity_id),
            "action": action,
        }
        if data is None or any(data.get(k) != v for k, v in expected.items()):
            raise sign_failed("challenge_invalid")
        return data["document_hash"]

    async def verify(self, doc_hash: str, pkcs7_b64: str) -> VerifiedSignature:
        try:
            check = await self._verifier.verify_attached(pkcs7_b64, signed_content(doc_hash))
        except SignatureUnavailableError as exc:
            raise sign_failed("verification_unavailable") from exc
        if not check.valid:
            raise sign_failed(check.reason or "invalid_signature")
        return VerifiedSignature(doc_hash, pkcs7_b64, check.certificate_serial, check.signer_tin)

    @staticmethod
    def check_unchanged(
        signature: VerifiedSignature,
        entity: Entity,
        entity_id: UUID,
        action: SignAction,
        document: Mapping[str, Any],
    ) -> None:
        if document_hash(entity, str(entity_id), action, document) != signature.document_hash:
            raise sign_failed("document_changed")
