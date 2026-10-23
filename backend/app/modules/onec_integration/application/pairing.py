"""Pairing of a store agent — the back-office half of the RFC 8628 device grant (33 §9.2, §10.3 W-03/W-04;
14 §2.3). ``auth.onec_device_authorizations`` is reached only through the 0028 SECURITY DEFINER functions;
the agent + device rows are created under RLS in the same transaction as ``app.onec_device_auth_approve``."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit
from app.core.db.base import uuid7
from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from app.modules.auth.domain.agent_keys import normalize_user_code
from app.modules.onec_integration.application.agents import AgentService
from app.modules.onec_integration.application.ports import AgentNotifier, AgentStore


@dataclass(frozen=True, slots=True)
class PairingRequest:
    id: UUID
    pc_name: str
    os_version: str | None
    agent_version: str | None
    request_ip: str | None
    created_at: datetime
    expires_at: datetime
    public_jwk: dict[str, Any]
    public_key_thumbprint: str
    machine_hash: str


class PairingStore(Protocol):
    async def lookup(self, s: AsyncSession, user_code: str) -> PairingRequest | None: ...

    async def approve(
        self, s: AsyncSession, user_code: str, tenant_id: UUID, user_id: UUID, agent_id: UUID
    ) -> str: ...

    async def deny(self, s: AsyncSession, user_code: str, user_id: UUID) -> str: ...

    async def probe(self, s: AsyncSession, user_code: str, tenant_id: UUID, user_id: UUID) -> str:
        """``approve`` with a random agent id inside a savepoint that is rolled back: tells an expired
        code (``expired``) from an unknown/used one without changing anything."""
        ...


def _invalid() -> AppError:
    return AppError(ErrorCode.ONEC_PAIRING_CODE_INVALID)


def _expired() -> AppError:
    return AppError(ErrorCode.ONEC_PAIRING_CODE_EXPIRED)


def _map(outcome: str) -> AppError:
    return _expired() if outcome == "expired" else _invalid()


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class PairingService:
    def __init__(
        self, store: AgentStore, pairing: PairingStore, agents: AgentService, notify: AgentNotifier
    ) -> None:
        self._store = store
        self._pairing = pairing
        self._agents = agents
        self._notify = notify

    @staticmethod
    def code(raw: str) -> str:
        code = normalize_user_code(raw)
        if code is None:
            raise _invalid()
        return code

    async def lookup(self, s: AsyncSession, raw_code: str, tenant_id: UUID, user_id: UUID) -> dict[str, Any]:
        """W-03: what computer asks to be paired (anti-phishing card)."""
        code = self.code(raw_code)
        request = await self._pairing.lookup(s, code)
        if request is None:
            raise _map(await self._pairing.probe(s, code, tenant_id, user_id))
        return {
            "pc_name": request.pc_name,
            "os_version": request.os_version,
            "agent_version": request.agent_version,
            "request_ip": request.request_ip,
            "created_at": _iso(request.created_at),
            "expires_at": _iso(request.expires_at),
        }

    async def pair(
        self,
        s: AsyncSession,
        raw_code: str,
        name: str | None,
        *,
        tenant_id: UUID,
        user_id: UUID,
        ip: str | None,
    ) -> dict[str, Any]:
        """W-04: ``onec_agents`` + ``devices(kind='onec_agent')`` + ``pending → approved`` (one txn)."""
        code = self.code(raw_code)
        request = await self._pairing.lookup(s, code)
        if request is None:
            raise _map(await self._pairing.probe(s, code, tenant_id, user_id))
        agent_id, device_id = uuid7(), uuid7()
        await self._store.create_device(s, device_id, tenant_id, request.agent_version)
        await self._store.create_agent(
            s,
            {
                "id": agent_id,
                "tenant_id": tenant_id,
                "device_id": device_id,
                "client_id": f"onec-agent:{agent_id}",
                "name": (name or "").strip() or request.pc_name,
                "pc_name": request.pc_name,
                "machine_hash": request.machine_hash,
                "os_version": request.os_version,
                "agent_version": request.agent_version,
                "public_jwk": {**_public(request.public_jwk), "kid": request.public_key_thumbprint},
                "thumbprint": request.public_key_thumbprint,
                "paired_by": user_id,
                "paired_ip": ip,
            },
        )
        outcome = await self._pairing.approve(s, code, tenant_id, user_id, agent_id)
        if outcome != "approved":
            raise _map(outcome)  # the route's transaction rolls the agent/device rows back
        await record_audit(
            s,
            tenant_id=tenant_id,
            user_id=user_id,
            action="onec.agent.paired",
            entity="onec_agents",
            entity_id=agent_id,
            ip=ip,
            after={"pc_name": request.pc_name, "request_ip": request.request_ip, "device_id": str(device_id)},
        )
        agent = await self._store.get_agent(s, agent_id)
        assert agent is not None
        await self._notify(
            s,
            tenant_id,
            "onec_agent_paired",
            {"agent_id": str(agent_id), "name": agent.name, "state": "connected", "user_id": str(user_id)},
        )
        return await self._agents.agent_json(s, agent)

    async def deny(self, s: AsyncSession, raw_code: str, *, user_id: UUID) -> None:
        """W-04 «Rad etish»: the agent's next token poll gets ``access_denied``."""
        outcome = await self._pairing.deny(s, self.code(raw_code), user_id)
        if outcome != "denied":
            raise _map(outcome)


def _public(jwk: Mapping[str, Any]) -> dict[str, Any]:
    return {k: jwk[k] for k in ("kty", "crv", "x") if k in jwk}
