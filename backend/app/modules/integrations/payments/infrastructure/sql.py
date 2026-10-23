"""SQL for ``app.payment_checkouts`` (12 §2.5, 0028a ``provider_data``) and the tenant-less webhook lookups
(SECURITY DEFINER, 12 §4.5)."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from typing import Any, Final
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.db.session import unscoped_transaction
from app.modules.integrations.payments.application.ports import CheckoutRow, RefOwner, RegisterRow

_COLUMNS: Final = (
    "checkout_ref, tenant_id, branch_id, cash_register_id, provider, qr_type, amount, provider_tx_id, "
    "status, confirmed_at, expires_at, created_at, provider_data"
)
_GET = text(f"SELECT {_COLUMNS} FROM app.payment_checkouts WHERE checkout_ref = :ref")  # noqa: S608
_GET_FOR_UPDATE = text(_GET.text + " FOR UPDATE")
_BY_TX = text(
    f"SELECT {_COLUMNS} FROM app.payment_checkouts WHERE provider = :p AND provider_tx_id = :tx"  # noqa: S608
)
_BY_TX_FOR_UPDATE = text(_BY_TX.text + " FOR UPDATE")
_INSERT = text(
    "INSERT INTO app.payment_checkouts (checkout_ref, tenant_id, branch_id, cash_register_id, device_id, "
    "provider, qr_type, amount, provider_tx_id, status, expires_at, created_by, provider_data) VALUES ("
    ":checkout_ref, :tenant_id, :branch_id, :cash_register_id, :device_id, :provider, :qr_type, :amount, "
    ":provider_tx_id, "
    "'pending', :expires_at, :created_by, CAST(:provider_data AS jsonb)) ON CONFLICT DO NOTHING RETURNING 1"
)
_STATEMENT = text(
    f"SELECT {_COLUMNS} FROM app.payment_checkouts WHERE provider = 'payme' AND provider_tx_id IS NOT NULL "  # noqa: S608
    "AND (provider_data->>'time')::bigint BETWEEN :f AND :t "
    "ORDER BY (provider_data->>'time')::bigint, checkout_ref"
)
_EXPIRE = text(
    "UPDATE app.payment_checkouts SET status = 'expired', updated_at = now() WHERE checkout_ref IN ("
    "  SELECT checkout_ref FROM app.payment_checkouts WHERE status = 'pending' AND expires_at <= :now "
    "  ORDER BY expires_at, checkout_ref LIMIT :lim FOR UPDATE SKIP LOCKED) RETURNING checkout_ref"
)
_REGISTER = text(
    "SELECT id, branch_id, archived_at IS NOT NULL AS archived FROM app.cash_registers WHERE id = :id"
)
_BY_REF = text("SELECT tenant_id, provider FROM app.payments_checkout_by_ref(:ref)")
_BY_PROVIDER_TX = text("SELECT tenant_id FROM app.payments_checkout_by_provider_tx(:p, :tx)")
_BY_CREDENTIAL = text("SELECT tenant_id FROM app.payments_tenant_by_credential(:kind, :hash)")


def _data(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        loaded = json.loads(value)
        return loaded if isinstance(loaded, dict) else {}
    return {}


def _row(r: Any) -> CheckoutRow:
    return CheckoutRow(
        checkout_ref=r.checkout_ref, tenant_id=r.tenant_id, branch_id=r.branch_id,
        cash_register_id=r.cash_register_id, provider=r.provider, qr_type=r.qr_type, amount=r.amount,
        provider_tx_id=r.provider_tx_id, status=r.status, confirmed_at=r.confirmed_at,
        expires_at=r.expires_at,
        created_at=r.created_at, provider_data=_data(r.provider_data),
    )  # fmt: skip


class SqlCheckoutRepository:
    """:class:`app.modules.integrations.payments.application.ports.CheckoutRepository`."""

    async def register(self, s: AsyncSession, cash_register_id: UUID) -> RegisterRow | None:
        found = (await s.execute(_REGISTER, {"id": cash_register_id})).first()
        return None if found is None else RegisterRow(found.id, found.branch_id, bool(found.archived))

    async def insert(self, s: AsyncSession, row: Mapping[str, Any]) -> bool:
        params = {**row, "provider_data": json.dumps(row.get("provider_data") or {}, ensure_ascii=False)}
        return (await s.execute(_INSERT, params)).first() is not None

    async def get(self, s: AsyncSession, ref: UUID, *, for_update: bool = False) -> CheckoutRow | None:
        found = (await s.execute(_GET_FOR_UPDATE if for_update else _GET, {"ref": ref})).first()
        return None if found is None else _row(found)

    async def by_provider_tx(
        self, s: AsyncSession, provider: str, provider_tx_id: str, *, for_update: bool = False
    ) -> CheckoutRow | None:
        stmt = _BY_TX_FOR_UPDATE if for_update else _BY_TX
        found = (await s.execute(stmt, {"p": provider, "tx": provider_tx_id})).first()
        return None if found is None else _row(found)

    async def update(
        self,
        s: AsyncSession,
        ref: UUID,
        *,
        status: str | None = None,
        provider_tx_id: str | None = None,
        provider_data: Mapping[str, Any] | None = None,
        confirmed_at: datetime | None = None,
    ) -> None:
        sets = ["updated_at = now()"]
        params: dict[str, Any] = {"ref": ref}
        if status is not None:
            sets.append("status = :status")
            params["status"] = status
        if provider_tx_id is not None:
            sets.append("provider_tx_id = :tx")
            params["tx"] = provider_tx_id
        if provider_data is not None:
            sets.append("provider_data = CAST(:data AS jsonb)")
            params["data"] = json.dumps(dict(provider_data), ensure_ascii=False)
        if confirmed_at is not None:
            sets.append("confirmed_at = :confirmed_at")
            params["confirmed_at"] = confirmed_at
        await s.execute(
            text(f"UPDATE app.payment_checkouts SET {', '.join(sets)} WHERE checkout_ref = :ref"),  # noqa: S608
            params,
        )

    async def payme_statement(self, s: AsyncSession, from_ms: int, to_ms: int) -> list[CheckoutRow]:
        return [_row(r) for r in (await s.execute(_STATEMENT, {"f": from_ms, "t": to_ms})).all()]

    async def expire_due(self, s: AsyncSession, now: datetime, limit: int) -> list[UUID]:
        return [r[0] for r in (await s.execute(_EXPIRE, {"now": now, "lim": limit})).all()]


class SqlTenantLookup:
    """:class:`app.modules.integrations.payments.application.ports.TenantLookup` — ``unscoped_transaction``:
    only the SECURITY DEFINER functions see across tenants (RLS is fail-closed otherwise)."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def by_ref(self, ref: UUID) -> RefOwner | None:
        async with self._sf() as s, unscoped_transaction(s):
            found = (await s.execute(_BY_REF, {"ref": ref})).first()
        return None if found is None else RefOwner(found.tenant_id, found.provider)

    async def by_provider_tx(self, provider: str, provider_tx_id: str) -> UUID | None:
        async with self._sf() as s, unscoped_transaction(s):
            found = (await s.execute(_BY_PROVIDER_TX, {"p": provider, "tx": provider_tx_id})).first()
        return None if found is None else UUID(str(found.tenant_id))

    async def by_credential(self, kind: str, lookup_hash: bytes) -> UUID | None:
        async with self._sf() as s, unscoped_transaction(s):
            found = (await s.execute(_BY_CREDENTIAL, {"kind": kind, "hash": lookup_hash})).first()
        return None if found is None else UUID(str(found.tenant_id))
