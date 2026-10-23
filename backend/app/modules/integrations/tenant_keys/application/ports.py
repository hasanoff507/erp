"""Ports of the tenant-keys slice (23 §1): SQL repository, envelope cipher, provider credential checks."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True, slots=True)
class SecretRow:
    id: UUID
    kind: str
    cash_register_id: UUID | None
    ciphertext: bytes
    key_version: int
    key_last4: str | None
    created_at: datetime
    rotated_at: datetime | None
    last_ok_at: datetime | None
    last_error: str | None
    last_error_at: datetime | None


@dataclass(frozen=True, slots=True)
class SecretWrite:
    tenant_id: UUID
    kind: str
    cash_register_id: UUID | None
    ciphertext: bytes
    key_version: int
    lookup_hash: bytes | None
    key_last4: str | None


class LookupHashTakenError(Exception):
    """``uq_tenant_secrets_lookup``: the same Payme key / Uzum login+password is already another tenant's."""


class TenantSecretRepository(Protocol):
    async def find(
        self, s: AsyncSession, kind: str, cash_register_id: UUID | None, *, for_update: bool = False
    ) -> SecretRow | None: ...

    async def list_status(self, s: AsyncSession, kinds: tuple[str, ...]) -> list[SecretRow]: ...

    async def upsert(self, s: AsyncSession, row: SecretWrite, existing: SecretRow | None) -> SecretRow: ...

    async def delete(self, s: AsyncSession, secret_id: UUID) -> None: ...

    async def record_result(self, s: AsyncSession, secret_id: UUID, error: str | None) -> None: ...

    async def register_exists(self, s: AsyncSession, cash_register_id: UUID) -> bool: ...

    async def confirm_autofiscal_off(self, s: AsyncSession, tenant_id: UUID, kind: str) -> None: ...


class SecretCipher(Protocol):
    """:class:`app.core.secrets.EnvelopeCipher`."""

    def encrypt(self, plaintext: bytes, aad: bytes) -> str: ...

    def decrypt(self, token: str, aad: bytes) -> bytes: ...


class CredentialVerifier(Protocol):
    """Optional provider check before storing (faktura/didox → edocs, crpt → marking; contract
    ``tenant-integrations.md``). Raises ``AppError`` (``EINVOICE_PROVIDER_UNAVAILABLE`` …)."""

    async def __call__(self, provider_kind: str, secret: Mapping[str, str]) -> None: ...
