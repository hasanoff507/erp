"""Reader of the tenant's Faktura.uz credentials (``tenant_secrets(kind='faktura_uz')``, 21 §2, 15 §4.2).

The secret is written by the tenant-keys slice (``PUT /tenant/integrations/faktura-uz``, contract
``tenant-integrations.md``: ``login``, ``password``, ``client_id``, ``client_secret``) and read here
through its
``TenantSecretReader`` in a short own transaction — never inside a business transaction (the operator call
follows). ``company_inn`` (``CompanyInn`` of the Faktura.uz API) is the tenant's STIR (``tenants.stir``).
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.db.session import tenant_transaction
from app.modules.integrations.einvoice.infrastructure.faktura_uz import FakturaCredentials

KIND = "faktura_uz"


class SecretReader(Protocol):
    async def get(
        self, s: AsyncSession, tenant_id: UUID, kind: str, *, cash_register_id: UUID | None = None
    ) -> dict[str, str] | None: ...


class SqlFakturaCredentialsReader:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession], secrets: SecretReader) -> None:
        self._sf = session_factory
        self._secrets = secrets

    async def read(self, tenant_id: UUID) -> FakturaCredentials | None:
        async with self._sf() as s, tenant_transaction(s, tenant_id):
            secret = await self._secrets.get(s, tenant_id, KIND)
            stir = (
                await s.execute(text("SELECT stir FROM app.tenants WHERE id = app.current_tenant_id()"))
            ).scalar_one_or_none()
        if secret is None:
            return None
        try:
            return FakturaCredentials(
                login=secret["login"],
                password=secret["password"],
                client_id=secret["client_id"],
                client_secret=secret["client_secret"],
                company_inn=str(stir or ""),
            )
        except KeyError:
            return None
