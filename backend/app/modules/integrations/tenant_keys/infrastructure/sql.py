"""SQL for ``app.tenant_secrets`` (12 §2.9) — caller's tenant transaction (RLS)."""

from __future__ import annotations

from typing import Any, Final
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.base import uuid7
from app.modules.integrations.tenant_keys.application.ports import (
    LookupHashTakenError,
    SecretRow,
    SecretWrite,
)

_COLUMNS: Final = (
    "id, kind, cash_register_id, ciphertext, key_version, key_last4, created_at, rotated_at, last_ok_at, "
    "last_error, last_error_at"
)
_FIND = text(
    f"SELECT {_COLUMNS} FROM app.tenant_secrets WHERE kind = :kind AND branch_id IS NULL "  # noqa: S608
    "AND cash_register_id IS NOT DISTINCT FROM :reg"
)
_FIND_FOR_UPDATE = text(_FIND.text + " FOR UPDATE")
_LIST = text(f"SELECT {_COLUMNS} FROM app.tenant_secrets WHERE kind = ANY(:kinds) ORDER BY kind, id")  # noqa: S608
_INSERT = text(
    "INSERT INTO app.tenant_secrets (id, tenant_id, branch_id, cash_register_id, kind, ciphertext, "  # noqa: S608
    "key_version, lookup_hash, key_last4) VALUES (:id, :tenant_id, NULL, :reg, :kind, :ciphertext, "
    f":key_version, :lookup_hash, :key_last4) RETURNING {_COLUMNS}"
)
_UPDATE = text(
    "UPDATE app.tenant_secrets SET ciphertext = :ciphertext, key_version = :key_version, "  # noqa: S608
    "lookup_hash = :lookup_hash, key_last4 = :key_last4, rotated_at = now(), updated_at = now(), "
    "last_ok_at = NULL, last_error = NULL, "
    f"last_error_at = NULL WHERE id = :id RETURNING {_COLUMNS}"
)
_DELETE = text("DELETE FROM app.tenant_secrets WHERE id = :id")
_RESULT_OK = text(
    "UPDATE app.tenant_secrets SET last_ok_at = now(), last_error = NULL, last_error_at = NULL WHERE id = :id"
)
_RESULT_ERROR = text(
    "UPDATE app.tenant_secrets SET last_error = :error, last_error_at = now() WHERE id = :id"
)
_REGISTER = text("SELECT EXISTS (SELECT 1 FROM app.cash_registers WHERE id = :id AND archived_at IS NULL)")
# 20 #40d: settings.payment_providers.<kind>.autofiscal_off_confirmed_at = now() (BO-14 onboarding check)
_AUTOFISCAL = text(
    "UPDATE app.tenants SET settings = jsonb_set("
    "  jsonb_set(COALESCE(settings, '{}'::jsonb), '{payment_providers}', "
    "            COALESCE(settings->'payment_providers', '{}'::jsonb), true), "
    "  ARRAY['payment_providers', CAST(:kind AS text)], "
    "  COALESCE(settings->'payment_providers'->CAST(:kind AS text), '{}'::jsonb) "
    "    || jsonb_build_object('autofiscal_off_confirmed_at', to_char(now() AT TIME ZONE 'UTC', "
    '                          \'YYYY-MM-DD"T"HH24:MI:SS"Z"\')), true), '
    "  version = version + 1, updated_at = now() WHERE id = :tenant_id"
)


def _row(r: Any) -> SecretRow:
    return SecretRow(
        id=r.id, kind=r.kind, cash_register_id=r.cash_register_id, ciphertext=bytes(r.ciphertext),
        key_version=r.key_version, key_last4=r.key_last4, created_at=r.created_at, rotated_at=r.rotated_at,
        last_ok_at=r.last_ok_at, last_error=r.last_error, last_error_at=r.last_error_at,
    )  # fmt: skip


class SqlTenantSecretRepository:
    """:class:`app.modules.integrations.tenant_keys.application.ports.TenantSecretRepository`."""

    async def find(
        self, s: AsyncSession, kind: str, cash_register_id: UUID | None, *, for_update: bool = False
    ) -> SecretRow | None:
        stmt = _FIND_FOR_UPDATE if for_update else _FIND
        found = (await s.execute(stmt, {"kind": kind, "reg": cash_register_id})).first()
        return None if found is None else _row(found)

    async def list_status(self, s: AsyncSession, kinds: tuple[str, ...]) -> list[SecretRow]:
        return [_row(r) for r in (await s.execute(_LIST, {"kinds": list(kinds)})).all()]

    async def upsert(self, s: AsyncSession, row: SecretWrite, existing: SecretRow | None) -> SecretRow:
        params = {
            "ciphertext": row.ciphertext, "key_version": row.key_version, "lookup_hash": row.lookup_hash,
            "key_last4": row.key_last4,
        }  # fmt: skip
        try:
            async with s.begin_nested():
                if existing is None:
                    result = await s.execute(
                        _INSERT,
                        {**params, "id": uuid7(), "tenant_id": row.tenant_id, "reg": row.cash_register_id,
                         "kind": row.kind},
                    )  # fmt: skip
                else:
                    result = await s.execute(_UPDATE, {**params, "id": existing.id})
                return _row(result.one())
        except IntegrityError as exc:
            if "uq_tenant_secrets_lookup" in str(exc.orig):
                raise LookupHashTakenError from None
            raise

    async def delete(self, s: AsyncSession, secret_id: UUID) -> None:
        await s.execute(_DELETE, {"id": secret_id})

    async def record_result(self, s: AsyncSession, secret_id: UUID, error: str | None) -> None:
        if error is None:
            await s.execute(_RESULT_OK, {"id": secret_id})
        else:
            await s.execute(_RESULT_ERROR, {"id": secret_id, "error": error})

    async def register_exists(self, s: AsyncSession, cash_register_id: UUID) -> bool:
        return bool((await s.execute(_REGISTER, {"id": cash_register_id})).scalar_one())

    async def confirm_autofiscal_off(self, s: AsyncSession, tenant_id: UUID, kind: str) -> None:
        await s.execute(_AUTOFISCAL, {"tenant_id": tenant_id, "kind": kind})
