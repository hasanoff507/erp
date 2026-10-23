"""The 0028 SECURITY DEFINER pairing functions (12 §4.5 / 33 §5.18), called inside the W-03/W-04 tenant
transaction (``approve``/``deny`` check ``app.current_tenant_id()``/``app.current_user_id()`` themselves)."""

from __future__ import annotations

import json
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.base import uuid7
from app.modules.onec_integration.application.pairing import PairingRequest

_LOOKUP = text(
    "SELECT id, pc_name, os_version, agent_version, host(request_ip), created_at, expires_at, public_jwk, "
    "public_key_thumbprint, machine_hash FROM app.onec_device_auth_lookup(:code)"
)
_APPROVE = text("SELECT app.onec_device_auth_approve(:code, :tenant_id, :user_id, :agent_id)")
_DENY = text("SELECT app.onec_device_auth_deny(:code, :user_id)")


class _RollbackError(Exception):
    def __init__(self, outcome: str) -> None:
        super().__init__(outcome)
        self.outcome = outcome


class SqlPairingStore:
    async def lookup(self, s: AsyncSession, user_code: str) -> PairingRequest | None:
        row = (await s.execute(_LOOKUP, {"code": user_code})).first()
        if row is None:
            return None
        jwk = row[7] if isinstance(row[7], dict) else json.loads(row[7])
        return PairingRequest(
            id=row[0],
            pc_name=row[1],
            os_version=row[2],
            agent_version=row[3],
            request_ip=row[4],
            created_at=row[5],
            expires_at=row[6],
            public_jwk=jwk,
            public_key_thumbprint=row[8],
            machine_hash=row[9],
        )

    async def approve(
        self, s: AsyncSession, user_code: str, tenant_id: UUID, user_id: UUID, agent_id: UUID
    ) -> str:
        params = {"code": user_code, "tenant_id": tenant_id, "user_id": user_id, "agent_id": agent_id}
        return str((await s.execute(_APPROVE, params)).scalar_one())

    async def deny(self, s: AsyncSession, user_code: str, user_id: UUID) -> str:
        return str((await s.execute(_DENY, {"code": user_code, "user_id": user_id})).scalar_one())

    async def probe(self, s: AsyncSession, user_code: str, tenant_id: UUID, user_id: UUID) -> str:
        try:
            async with s.begin_nested():
                outcome = await self.approve(s, user_code, tenant_id, user_id, uuid7())
                raise _RollbackError(outcome)  # undo the pending → expired flip of the probe
        except _RollbackError as rolled:
            return rolled.outcome
