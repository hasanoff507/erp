"""Helpers for the B5 devices slice tests (cloud printers, agent card capability, bank RRN matching).

Real app + PostgreSQL/Redis (the card env: ``ERP_CARD_FAKE_TERMINALS=true``). Printers are driven through the
real ``/print/*`` routes with HTTP Basic; Do'kon agents are inserted straight into ``app.onec_agents`` (the
A-API pairing belongs to the agent slice) and tasks go through an in-memory :class:`FakeAgentTasks`.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.base import uuid7
from app.core.db.session import tenant_transaction
from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from tests.support.card import API, CardShop
from tests.support.catalog import Env, Shop

# --- cloud printers ---------------------------------------------------------------------------------


async def create_printer(
    client: httpx.AsyncClient, shop: Shop, *, protocol: str = "star_cloudprnt", name: str = "Star-1"
) -> dict[str, Any]:
    r = await client.post(
        f"{API}/cloud-printers",
        json={"branch_id": str(shop.branch_id), "name": name, "protocol": protocol, "model": "Star TSP143IV"},
        headers=shop.h("owner"),
    )
    assert r.status_code == 201, r.text
    created: dict[str, Any] = r.json()
    return created


def basic(printer: dict[str, Any], secret: str | None = None) -> dict[str, str]:
    token = base64.b64encode(f"{printer['id']}:{secret or printer['secret']}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def raster(width: int = 16, height: int = 3, fill: int = 0xF0) -> dict[str, Any]:
    data = bytes([fill]) * (((width + 7) // 8) * height)
    return {"width_dots": width, "height_dots": height, "data_base64": base64.b64encode(data).decode()}


async def submit_job(
    client: httpx.AsyncClient,
    shop: Shop,
    printer: dict[str, Any],
    *,
    job_id: UUID | None = None,
    role: str = "cashier",
    kind: str = "receipt",
    body_raster: dict[str, Any] | None = None,
) -> httpx.Response:
    body = {
        "id": str(job_id or uuid7()), "cloud_printer_id": printer["id"], "kind": kind,
        "raster": body_raster or raster(),
    }  # fmt: skip
    return await client.post(f"{API}/print-jobs", json=body, headers=shop.h(role))


async def star_poll(client: httpx.AsyncClient, printer: dict[str, Any], **status: Any) -> httpx.Response:
    body = {
        "printerMAC": "00:11:62:aa:bb:cc",
        "statusCode": "200%20OK",
        "printingInProgress": False,
        **status,
    }
    return await client.post("/print/cloudprnt", content=json.dumps(body), headers=basic(printer))


async def sdp_post(client: httpx.AsyncClient, printer: dict[str, Any], **form: str) -> httpx.Response:
    return await client.post(
        "/print/epson-sdp",
        data=form,
        headers=basic(printer),
    )


async def job_row(env: Env, tenant_id: UUID, job_id: UUID) -> dict[str, Any]:
    async with env.db.session_factory() as s, tenant_transaction(s, tenant_id):
        row = (
            (
                await s.execute(
                    text("SELECT status, result_code, data IS NULL AS purged, attempts FROM app.print_jobs "
                         "WHERE id = :id"),
                    {"id": job_id},
                )
            )
            .mappings()
            .one()
        )  # fmt: skip
        return dict(row)


# --- Do'kon agent (card_terminal capability) ----------------------------------------------------------


def card_capabilities(*devices: dict[str, Any], enabled: bool = True) -> dict[str, Any]:
    return {
        "onec": {"enabled": False, "version": 0},
        "card_terminal": {"enabled": enabled, "version": 1, "devices": list(devices)},
    }


async def insert_agent(
    env: Env, cs: CardShop, *, capabilities: dict[str, Any], status: str = "active"
) -> UUID:
    """A paired agent row (``devices.kind='onec_agent'`` + ``onec_agents``) — pairing itself is b5-agent's."""
    agent_id, device_id = uuid7(), uuid7()
    async with env.db.session_factory() as s, tenant_transaction(s, cs.tenant_id):
        await s.execute(
            text("INSERT INTO app.devices (id, tenant_id, kind) VALUES (:id, :t, 'onec_agent')"),
            {"id": device_id, "t": cs.tenant_id},
        )
        await s.execute(
            text(
                "INSERT INTO app.onec_agents (id, tenant_id, device_id, client_id, name, pc_name, machine_hash, "
                "public_jwk, public_key_thumbprint, status, capabilities, paired_by, revoked_at, revoke_reason) "
                "VALUES (:id, :t, :d, :c, 'Kassa PK', 'KASSA-PC', :mh, CAST(:jwk AS jsonb), 'thumb', :st, "
                "CAST(:caps AS jsonb), :u, :ra, :rr)"
            ),
            {
                "id": agent_id, "t": cs.tenant_id, "d": device_id, "c": f"onec-agent:{agent_id}", "mh": "a" * 64,
                "jwk": json.dumps({"kty": "OKP", "crv": "Ed25519", "x": "AAAA"}), "st": status,
                "caps": json.dumps(capabilities), "u": cs.uid("owner"),
                "ra": datetime.now(UTC) if status == "revoked" else None,
                "rr": "user" if status == "revoked" else None,
            },
        )  # fmt: skip
    return agent_id


@dataclass
class FakeAgentTasks:
    """In-memory ``AgentTaskPort`` (contracts/agent-tasks.md §4): records enqueues, honours capabilities
    and dedupe like the real port."""

    calls: list[dict[str, Any]] = field(default_factory=list)

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
        caps = (
            await s.execute(text("SELECT capabilities FROM app.onec_agents WHERE id = :id"), {"id": agent_id})
        ).scalar_one_or_none()
        if caps is None:
            raise AppError(ErrorCode.NOT_FOUND, params={"resource": "onec_agent"})
        if not (caps.get("card_terminal") or {}).get("enabled"):
            raise AppError(
                ErrorCode.AGENT_CAPABILITY_DISABLED, params={"agent_id": str(agent_id), "kind": kind}
            )
        for call in self.calls:
            if dedupe_key is not None and call["agent_id"] == agent_id and call["dedupe_key"] == dedupe_key:
                existing: UUID = call["id"]
                return existing
        task_id = uuid7()
        self.calls.append({
            "id": task_id, "tenant_id": tenant_id, "agent_id": agent_id, "kind": kind,
            "payload": json.loads(json.dumps(payload)), "dedupe_key": dedupe_key, "created_by": created_by,
        })  # fmt: skip
        return task_id


@dataclass(frozen=True)
class TaskStub:
    """``AgentTaskView`` shape (contracts/agent-tasks.md §2)."""

    id: UUID
    kind: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class ResultStub:
    outcome: str
    data: dict[str, Any] = field(default_factory=dict)
    error: dict[str, Any] | None = None
    late: bool = False


AGENT_DEVICE = {
    "local_id": "ecr-1",
    "driver": "fake",
    "host": "192.168.1.60",
    "tid": "T0000001",
    "status": "online",
}


async def agent_terminal(
    env: Env,
    cs: CardShop,
    agent_id: UUID,
    *,
    local_id: str = "ecr-1",
    host: str = "192.168.1.60",
    tid: str = "T0000001",
    default: bool = True,
) -> dict[str, Any]:
    """BO-12: bind an ``agent_ecr`` terminal of Kassa-1 to the agent's ``local_id``."""
    body = {
        "branch_id": str(cs.branch_id), "cash_register_id": str(cs.register1), "name": f"ECR {local_id}",
        "vendor": "rahmat", "adapter": "agent_ecr", "driver": "fake_ecr", "agent_id": str(agent_id),
        "local_id": local_id, "host": host, "port": 8080, "tid": tid, "is_default": default,
    }  # fmt: skip
    r = await env.client.post(f"{API}/card-terminals", json=body, headers=cs.h("owner"))
    assert r.status_code == 201, r.text
    created: dict[str, Any] = r.json()
    return created
