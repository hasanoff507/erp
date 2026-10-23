"""Integration keys — ``PUT/DELETE /tenant/integrations/{provider}`` (20 #40d/#40e), the secret reader other
slices use (contract ``tenant-integrations.md``) and the BO-14 status read model (20 #40a).

Rules: ``settings.tenant``; unknown provider / field, missing field → ``VALIDATION_ERROR``;
``click``/``payme``/``uzum`` need ``provider_autofiscal_disabled_confirmed: true`` (server writes
``tenants.settings.payment_providers.<kind>.autofiscal_off_confirmed_at``); ``uzqr`` may name a cash register
(``NOT_FOUND`` when it is not the tenant's), the dynamic-QR ``api_key`` only with one. The value is a
canonical JSON object, envelope-encrypted (15 §4.2) with the row-binding ``aad``; it is never returned or
logged — audit ``tenant_integration.connected|updated|disconnected`` carries only the provider and the field
names.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.audit import record_audit
from app.core.auth.principal import Principal
from app.core.db.session import tenant_transaction
from app.core.error_codes import ErrorCode
from app.core.errors import AppError, ErrorDetail
from app.core.idempotency import stage_response
from app.core.secrets import SecretDecryptionError
from app.modules.integrations.tenant_keys.application.ports import (
    CredentialVerifier,
    LookupHashTakenError,
    SecretCipher,
    SecretRow,
    SecretWrite,
    TenantSecretRepository,
)
from app.modules.integrations.tenant_keys.domain.providers import (
    DIGITS,
    MAX_FIELD,
    PROVIDERS,
    STATUS_KINDS,
    ProviderSpec,
    lookup_hash,
    secret_aad,
)

log = structlog.get_logger(__name__)

ENTITY: Final = "tenant_secrets"
MAX_ERROR: Final = 500


def _invalid(field: str, key: str, **params: Any) -> AppError:
    return AppError(
        ErrorCode.VALIDATION_ERROR, params=params or None, details=[ErrorDetail(field=field, message_key=key)]
    )


def _iso(value: Any) -> str | None:
    return None if value is None else value.isoformat().replace("+00:00", "Z")


@dataclass(frozen=True, slots=True)
class IntegrationInput:
    fields: Mapping[str, Any]  # only the fields present in the body (secret values, flags)
    cash_register_id: UUID | None = None
    autofiscal_confirmed: bool | None = None


def provider_spec(slug: str) -> ProviderSpec:
    spec = PROVIDERS.get(slug)
    if spec is None:
        raise _invalid("provider", "validation.invalid_choice", allowed=sorted(PROVIDERS))
    return spec


def build_secret(spec: ProviderSpec, data: IntegrationInput) -> dict[str, str]:
    """Validate the body against the provider's field list (20 #40d) → the plaintext secret object."""
    for name in data.fields:
        if name not in spec.fields:
            raise _invalid(name, "validation.extra_forbidden")
    secret: dict[str, str] = {}
    for name in spec.fields:
        raw = data.fields.get(name)
        if raw is None:
            continue
        if name in spec.flags:
            if not isinstance(raw, bool):
                raise _invalid(name, "validation.boolean")
            secret[name] = "true" if raw else "false"
            continue
        value = str(raw).strip()
        if not value:
            raise _invalid(name, "validation.required")
        if len(value) > MAX_FIELD:
            raise _invalid(name, "validation.max_length", max=MAX_FIELD)
        if name in spec.digits and not DIGITS.match(value):
            raise _invalid(name, "validation.invalid_format")
        secret[name] = value
    for name in spec.required:
        if name not in secret:
            raise _invalid(name, "validation.required")
    for group in spec.groups:
        present = [n for n in group if n in secret]
        if present and len(present) != len(group):
            missing = next(n for n in group if n not in secret)
            raise _invalid(missing, "validation.required")
    if spec.autofiscal and data.autofiscal_confirmed is not True:
        raise _invalid(
            "provider_autofiscal_disabled_confirmed", "validation.autofiscal_confirmation_required"
        )
    if not spec.autofiscal and data.autofiscal_confirmed is not None:
        raise _invalid("provider_autofiscal_disabled_confirmed", "validation.extra_forbidden")
    if not spec.per_register and data.cash_register_id is not None:
        raise _invalid("cash_register_id", "validation.extra_forbidden")
    if spec.per_register and "api_key" in secret and data.cash_register_id is None:
        raise _invalid("cash_register_id", "validation.required")
    return secret


def _plaintext(secret: Mapping[str, str]) -> bytes:
    return json.dumps(dict(secret), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


class TenantIntegrationsService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        repo: TenantSecretRepository,
        cipher: SecretCipher,
        key_version: int,
        verifiers: Mapping[str, CredentialVerifier],
    ) -> None:
        self._sf = session_factory
        self._repo = repo
        self._cipher = cipher
        self._key_version = key_version
        self._verifiers = verifiers

    async def put(
        self, actor: Principal, slug: str, data: IntegrationInput, ip: str | None
    ) -> dict[str, Any]:
        spec = provider_spec(slug)
        secret = build_secret(spec, data)
        verifier = self._verifiers.get(spec.kind)
        if verifier is not None:  # provider round-trip (Faktura.uz token, CRPT key) before anything is stored
            await verifier(spec.kind, secret)
        register = data.cash_register_id if spec.per_register else None
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            if register is not None and not await self._repo.register_exists(s, register):
                raise AppError(ErrorCode.NOT_FOUND, params={"resource": "cash_registers"})
            existing = await self._repo.find(s, spec.kind, register, for_update=True)
            token = self._cipher.encrypt(_plaintext(secret), secret_aad(actor.tenant_id, spec.kind, register))
            last4 = secret[spec.last4_field][-4:] if spec.last4_field else None
            write = SecretWrite(
                tenant_id=actor.tenant_id, kind=spec.kind, cash_register_id=register,
                ciphertext=token.encode("ascii"), key_version=self._key_version,
                lookup_hash=lookup_hash(spec.kind, secret), key_last4=last4,
            )  # fmt: skip
            try:
                row = await self._repo.upsert(s, write, existing)
            except LookupHashTakenError:
                raise _invalid(
                    "key" if spec.kind == "payme" else "login", "validation.integration_key_in_use"
                ) from None
            if spec.autofiscal:
                await self._repo.confirm_autofiscal_off(s, actor.tenant_id, spec.kind)
            await record_audit(
                s, tenant_id=actor.tenant_id, user_id=actor.user_id,
                action="tenant_integration.updated" if existing else "tenant_integration.connected",
                entity=ENTITY, entity_id=row.id, ip=ip, device_id=actor.device_id,
                after={"provider": slug, "cash_register_id": None if register is None else str(register),
                       "fields": sorted(secret)},
            )  # fmt: skip
            body = {"provider": slug, "status": "connected", "connected_at": _iso(row.created_at)}
            stage_response(body, 200)
        return body

    async def delete(
        self, actor: Principal, slug: str, cash_register_id: UUID | None, ip: str | None
    ) -> None:
        spec = provider_spec(slug)
        register = cash_register_id if spec.per_register else None
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            existing = await self._repo.find(s, spec.kind, register, for_update=True)
            if existing is None:
                raise AppError(ErrorCode.NOT_FOUND, params={"resource": "tenant_integrations"})
            await self._repo.delete(s, existing.id)
            await record_audit(
                s, tenant_id=actor.tenant_id, user_id=actor.user_id, action="tenant_integration.disconnected",
                entity=ENTITY, entity_id=existing.id, ip=ip, device_id=actor.device_id,
                after={"provider": slug, "cash_register_id": None if register is None else str(register)},
            )  # fmt: skip
            stage_response(None, 204)


class TenantSecretReader:
    """Read by other slices inside their own ``tenant_transaction`` (``tenant-integrations.md``)."""

    def __init__(self, repo: TenantSecretRepository, cipher: SecretCipher) -> None:
        self._repo = repo
        self._cipher = cipher

    async def get(
        self, s: AsyncSession, tenant_id: UUID, kind: str, *, cash_register_id: UUID | None = None
    ) -> dict[str, str] | None:
        row = await self._repo.find(s, kind, cash_register_id)
        if row is None:
            return None
        try:
            raw = self._cipher.decrypt(
                row.ciphertext.decode("ascii"), secret_aad(tenant_id, kind, cash_register_id)
            )
            value = json.loads(raw)
        except (SecretDecryptionError, UnicodeDecodeError, ValueError):
            log.warning("tenant_secret_undecryptable", kind=kind, secret_id=str(row.id))
            return None
        return {str(k): str(v) for k, v in value.items()} if isinstance(value, dict) else None

    async def record_result(
        self,
        s: AsyncSession,
        tenant_id: UUID,
        kind: str,
        *,
        cash_register_id: UUID | None = None,
        error: str | None = None,
    ) -> None:
        """BO-14: ``error=None`` — the key worked (``last_ok_at``); else ``last_error`` (no secrets!)."""
        row = await self._repo.find(s, kind, cash_register_id)
        if row is not None:
            await self._repo.record_result(s, row.id, None if error is None else error[:MAX_ERROR])


def status_entry(rows: list[SecretRow]) -> dict[str, Any]:
    if not rows:
        return {"status": "not_connected", "connected_at": None, "last_ok_at": None, "last_error": None,
                "last_error_at": None}  # fmt: skip
    errors = [r for r in rows if r.last_error is not None]
    oks = [r.last_ok_at for r in rows if r.last_ok_at is not None]
    worst = max(errors, key=lambda r: r.last_error_at or r.created_at) if errors else None
    return {
        "status": "connected",
        "connected_at": _iso(min(r.created_at for r in rows)),
        "last_ok_at": _iso(max(oks)) if oks else None,
        "last_error": None if worst is None else worst.last_error,
        "last_error_at": None if worst is None else _iso(worst.last_error_at),
    }


async def integration_status(repo: TenantSecretRepository, s: AsyncSession) -> dict[str, Any]:
    """BO-14 read model (20 #40a ``integrations``): configured or not, last call result — never a secret."""
    by_kind: dict[str, list[SecretRow]] = {}
    for row in await repo.list_status(s, STATUS_KINDS):
        by_kind.setdefault(row.kind, []).append(row)
    out: dict[str, Any] = {}
    for kind in STATUS_KINDS:
        rows = by_kind.get(kind, [])
        entry = status_entry(rows)
        if kind == "crpt":
            entry["key_last4"] = rows[0].key_last4 if rows else None
        if kind == "uzqr":
            entry["cash_register_ids"] = sorted(str(r.cash_register_id) for r in rows if r.cash_register_id)
        out[kind] = entry
    return out
