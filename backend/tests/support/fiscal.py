"""Helpers for the Bosqich 5 fiscal tests (b5-fiscal slice; 21 §1, §16; 23 §4.2).

* :class:`InMemoryAgentTasks` — an ``AgentTaskPort`` stand-in (PLAN contract 1): checks the agent's
  ``capabilities.fiscal.enabled`` / ``status`` in the caller's transaction (``AGENT_CAPABILITY_DISABLED``), dedupes
  by ``dedupe_key`` and records the tasks; used until b5-agent's queue lands (then the same tests can run on it);
* :func:`add_agent` / :func:`bind_agent` — an ``onec_agents`` row with ``capabilities.fiscal.devices`` and the
  ``cash_registers`` local-bridge binding (SQL — the agent pairing flow belongs to b5-agent);
* :class:`StoreAgentEmulator` — what the Do'kon agenti does for the fiscal tasks: an FM emulator per
  ``local_id`` signs POS receipts (``fiscal_result`` for ``sale.created``) and answers ``fiscal.status`` /
  ``fiscal.resend_unsent`` / ``fiscal.zreport`` with the 21 §16 result bodies;
* :func:`local_env` fixture — the sales env with ``ERP_FISCAL_PROVIDER=multikassa_local``.
"""

from __future__ import annotations

import json
import secrets
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.base import uuid7
from app.core.db.session import Database
from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from app.modules.integrations.fiscal.infrastructure.fm_emulator import FmEmulator, emulator_terminal_id
from tests.conftest import MigratedDb
from tests.support.catalog import Env, catalog_app, catalog_settings
from tests.support.sales import Pos, execute, reset_fake_fm

PAIRED_BY_ROLE = "owner"


@dataclass
class Task:
    id: UUID
    tenant_id: UUID
    agent_id: UUID
    kind: str
    payload: dict[str, Any]
    priority: int
    dedupe_key: str | None
    done: bool = False


@dataclass
class InMemoryAgentTasks:
    tasks: list[Task] = field(default_factory=list)

    async def enqueue(
        self,
        s: AsyncSession,
        tenant_id: UUID,
        agent_id: UUID,
        kind: str,
        payload: dict[str, Any],
        *,
        priority: int = 100,
        not_before: datetime | None = None,
        dedupe_key: str | None = None,
        created_by: UUID | None = None,
        expires_in_s: int | None = 86400,
        timeout_s: int | None = None,
    ) -> UUID:
        row = (
            await s.execute(
                text("SELECT status, capabilities FROM app.onec_agents WHERE id = :id"), {"id": agent_id}
            )
        ).first()
        if row is None:
            raise AppError(ErrorCode.NOT_FOUND, params={"resource": "onec_agent"})
        if row[0] != "active":
            raise AppError(ErrorCode.ONEC_AGENT_REVOKED)
        caps = row[1] if isinstance(row[1], dict) else json.loads(row[1])
        family = kind.split(".", 1)[0]
        if not (caps.get(family) or {}).get("enabled"):
            raise AppError(ErrorCode.AGENT_CAPABILITY_DISABLED, params={"capability": family})
        for t in self.tasks:  # contract 1: dedupe only against queued/leased tasks of the same agent
            if (
                dedupe_key is not None
                and not t.done
                and t.dedupe_key == dedupe_key
                and t.agent_id == agent_id
            ):
                return t.id
        task = Task(uuid7(), tenant_id, agent_id, kind, dict(payload), priority, dedupe_key)
        self.tasks.append(task)
        return task.id

    def of(self, kind: str) -> list[Task]:
        return [t for t in self.tasks if t.kind == kind]


async def add_agent(
    env: Env,
    pos: Pos,
    local_ids: tuple[str, ...] = ("fm-1",),
    *,
    fiscal_enabled: bool = True,
    status: str = "active",
) -> UUID:
    agent_id, device_id = uuid7(), uuid7()
    caps = {
        "onec": {"enabled": False, "version": 0},
        "fiscal": {"enabled": fiscal_enabled, "version": 1, "provider": "multikassa_local",
                   "devices": [{"local_id": lid, "status": "ok"} for lid in local_ids]},
    }  # fmt: skip
    revoked = status == "revoked"
    await execute(
        env.db, pos.tenant_id,
        "INSERT INTO app.devices (id, tenant_id, kind) VALUES (:d, :t, 'onec_agent')",
        d=device_id, t=pos.tenant_id,
    )  # fmt: skip
    await execute(
        env.db, pos.tenant_id,
        "INSERT INTO app.onec_agents (id, tenant_id, device_id, client_id, name, pc_name, machine_hash, public_jwk, "
        "public_key_thumbprint, status, capabilities, paired_by, revoked_at, revoke_reason) VALUES (:id, :t, :d, "
        ":cid, 'Kassa PK', 'KASSA-PC', :mh, CAST(:jwk AS jsonb), :tp, :st, "
        "CAST(:caps AS jsonb), :u, :rat, :rr)",
        id=agent_id, cid=f"onec-agent:{agent_id}", t=pos.tenant_id, d=device_id, mh=secrets.token_hex(32),
        jwk=json.dumps({"kty": "OKP", "crv": "Ed25519", "x": secrets.token_urlsafe(32)}), tp=secrets.token_urlsafe(32),
        st=status, caps=json.dumps(caps), u=pos.shop.user_ids[PAIRED_BY_ROLE],
        rat=datetime.now(UTC) if revoked else None, rr="user" if revoked else None,
    )  # fmt: skip
    return agent_id


async def bind_agent(env: Env, pos: Pos, agent_id: UUID, local_id: str = "fm-1") -> None:
    await execute(
        env.db, pos.tenant_id,
        "UPDATE app.cash_registers SET fiscal_agent_id = :a, fiscal_local_device_id = :l WHERE id = :r",
        a=agent_id, l=local_id, r=pos.register_id,
    )  # fmt: skip


@dataclass
class StoreAgentEmulator:
    """The store agent's fiscal bridge: one FM emulator per ``local_id`` (21 §16.1 schemas)."""

    fms: dict[str, FmEmulator] = field(default_factory=dict)

    def fm(self, local_id: str = "fm-1") -> FmEmulator:
        found = self.fms.get(local_id)
        if found is None:
            found = self.fms[local_id] = FmEmulator(emulator_terminal_id(secrets.randbelow(10**12)))
        return found

    def sign(self, total_tiyin: int, local_id: str = "fm-1") -> dict[str, Any]:
        """``POST /v1/fiscal/sale`` → ``FiscalResult`` as the POS puts it into ``sale.created.fiscal_result``."""
        r = self.fm(local_id).sign(str(uuid7()), total_tiyin)
        return {"fm_terminal_id": r.terminal_id, "fm_receipt_seq": r.fm_receipt_seq, "fiscal_sign": r.fiscal_sign,
                "qr_url": r.qr_url, "fiscal_at": r.fiscal_at.isoformat().replace("+00:00", "Z")}  # fmt: skip

    def answer(self, kind: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        fm = self.fm(str(payload.get("local_id") or "fm-1"))
        if kind == "fiscal.status":
            st = fm.status()
            acked = [{"fm_terminal_id": r.terminal_id, "fm_receipt_seq": r.fm_receipt_seq,
                      "acked_at": _iso(r.acked_at)} for r in fm.receipts.values() if r.acked_at]  # fmt: skip
            return {"cash_register_id": payload.get("cash_register_id"), "fm_state": st["fm_state"],
                    "pending_count": st["pending_count"], "oldest_unacked_at": _iso(st["oldest_unacked_at"]),
                    "acked": acked}  # fmt: skip
        if kind == "fiscal.resend_unsent":
            res = fm.resend()
            return {"cash_register_id": payload.get("cash_register_id"), "sent": res["sent"], "failed": res["failed"],
                    "acked": [{**a, "acked_at": _iso(a["acked_at"])} for a in res["acked"]]}  # fmt: skip
        if kind == "fiscal.zreport":
            z = fm.close_shift({"sale": 1200000, "return": 0, "by_payment_form": {"cash": 1200000}})
            return {"cash_register_id": payload.get("cash_register_id"), "shift_id": payload.get("shift_id"),
                    **z, "closed_at": _iso(z["closed_at"])}  # fmt: skip
        raise ValueError(kind)


def _iso(value: datetime | None) -> str | None:
    return None if value is None else value.astimezone(UTC).isoformat().replace("+00:00", "Z")


@pytest.fixture(name="local_env")
async def local_env_fixture(
    oauth_platform: None,
    app_db: Database,
    clean_redis: Redis,
    migrated_db: MigratedDb,
    redis_url: str,
    tmp_path: Path,
) -> AsyncIterator[Env]:
    reset_fake_fm()
    settings = catalog_settings(
        migrated_db,
        redis_url,
        tmp_path / "files",
        fiscal_provider="multikassa_local",
        card_fake_terminals=True,
        einvoice_provider="fake",
    )
    async with catalog_app(settings) as (app, client):
        yield Env(settings, app, client, app_db)
    reset_fake_fm()
