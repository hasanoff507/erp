"""``MarkingPortProvider`` implementations: the tenant's CRPT adapter (``crpt``) or the shared fake."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.integrations.marking.application.ports import MarkingPort
from app.modules.integrations.marking.infrastructure.crpt_xtrace import CrptXtraceAdapter


class SecretReader(Protocol):
    """``tenant_keys.TenantSecretReader.get`` (contracts/tenant-integrations.md)."""

    async def get(
        self, s: AsyncSession, tenant_id: UUID, kind: str, **kw: Any
    ) -> Mapping[str, str] | None: ...


class StaticPortProvider:
    """Every tenant gets the same adapter (``ERP_MARKING_PROVIDER=fake`` — dev/CI)."""

    def __init__(self, port: MarkingPort) -> None:
        self._port = port

    async def for_tenant(self, s: AsyncSession, tenant_id: UUID) -> MarkingPort | None:
        return self._port


class CrptPortProvider:
    """The tenant's ``crpt_api_key`` (``tenant_secrets(kind='crpt')``, field ``api_key``); none → ``None``."""

    def __init__(self, secrets: SecretReader | None) -> None:
        self._secrets = secrets

    async def for_tenant(self, s: AsyncSession, tenant_id: UUID) -> MarkingPort | None:
        if self._secrets is None:
            return None
        secret = await self._secrets.get(s, tenant_id, "crpt")
        key = (secret or {}).get("api_key")
        return CrptXtraceAdapter(key) if key else None
