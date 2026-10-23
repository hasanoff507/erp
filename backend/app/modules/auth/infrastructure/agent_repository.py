"""SQL of the store-agent grants (14 §2.3, 33 §5.18): ``auth.onec_device_authorizations`` only through the
0028 SECURITY DEFINER functions, agent credentials without a tenant, and the pre-signed agent artefacts
(``platform.agent_signed_artifacts``, 0028a — written by ``scripts/auth_ops.py``, read here)."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.db.session import tenant_transaction, unscoped_transaction
from app.modules.auth.application.agent_grants import AgentCredentials, DevicePoll, SignedArtifact

_START = text(
    "SELECT app.onec_device_auth_start(:hash, :user_code, CAST(:jwk AS jsonb), :thumb, :machine_hash, "
    ":pc_name, :os, :agent_version, CAST(:ip AS inet))"
)
_POLL = text("SELECT status, tenant_id, agent_id, slow_down FROM app.onec_device_auth_poll(:hash)")
_CREDENTIALS = text(
    "SELECT tenant_id, agent_id, device_id, public_jwk, status FROM app.onec_agent_credentials(:client_id)"
)
_TENANT_NAME = text("SELECT name FROM app.tenants WHERE id = :t")
_ARTIFACTS = text(
    "SELECT kind, channel, version, body, signature, kid FROM platform.agent_signed_artifacts "
    "WHERE kind = :kind AND channel IS NOT DISTINCT FROM :channel"
)


class AgentAuthRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def start_device_authorization(self, **params: Any) -> UUID | None:
        """``None`` when the ``user_code`` collides with a pending one (caller retries with a new code)."""
        values = {**params, "jwk": json.dumps(params["jwk"])}
        try:
            async with self._sf() as s, unscoped_transaction(s):
                value = (await s.execute(_START, values)).scalar()
        except IntegrityError:
            return None
        return value if isinstance(value, UUID) else UUID(str(value))

    async def poll_device_code(self, device_code_hash: str) -> DevicePoll | None:
        async with self._sf() as s, unscoped_transaction(s):
            row = (await s.execute(_POLL, {"hash": device_code_hash})).first()
        if row is None:
            return None
        return DevicePoll(status=row[0], tenant_id=row[1], agent_id=row[2], slow_down=bool(row[3]))

    async def agent_credentials(self, client_id: str) -> AgentCredentials | None:
        async with self._sf() as s, unscoped_transaction(s):
            row = (await s.execute(_CREDENTIALS, {"client_id": client_id})).first()
        if row is None:
            return None
        jwk = row[3] if isinstance(row[3], dict) else json.loads(row[3])
        return AgentCredentials(
            tenant_id=row[0], agent_id=row[1], device_id=row[2], public_jwk=jwk, status=row[4]
        )

    async def tenant_name(self, tenant_id: UUID) -> str | None:
        async with self._sf() as s, tenant_transaction(s, tenant_id):
            value = (await s.execute(_TENANT_NAME, {"t": tenant_id})).scalar()
        return str(value) if value is not None else None

    async def signed_artifacts(self, kind: str, channel: str | None) -> list[SignedArtifact]:
        async with self._sf() as s, unscoped_transaction(s):
            rows = (await s.execute(_ARTIFACTS, {"kind": kind, "channel": channel})).all()
        return [
            SignedArtifact(kind=r[0], channel=r[1], version=r[2], body=r[3], signature=r[4], kid=r[5])
            for r in rows
        ]
