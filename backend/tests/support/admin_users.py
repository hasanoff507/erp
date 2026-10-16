"""Helpers for the BO-11 admin-users tests (slice A2) — real app, real Postgres/Redis, no mocks."""

from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import httpx
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.db.base import uuid7
from app.core.db.session import Database, unscoped_transaction
from app.modules.auth.application.passwords import hash_password
from scripts.seed import seed_demo_tenant, seed_demo_user
from tests.support.auth import PASSWORD, bearer, new_phone


@dataclass(frozen=True)
class StaffWorld:
    tenant_id: UUID
    owner_id: UUID
    owner_phone: str
    roles: dict[str, UUID]  # system_code -> role id
    branch_id: UUID  # the default branch


async def make_staff_world(db: Database, admin_engine: AsyncEngine, name: str) -> StaffWorld:
    tenant_id = uuid7()
    await seed_demo_tenant(db, tenant_id=tenant_id, name=name, phone=new_phone())
    owner_phone = new_phone()
    owner = await seed_demo_user(db, tenant_id=tenant_id, phone=owner_phone, name="Egasi", password=PASSWORD)
    async with admin_engine.connect() as conn:
        roles = {
            r.system_code: r.id
            for r in await conn.execute(
                text(
                    "SELECT id, system_code FROM app.roles WHERE tenant_id = :t AND system_code IS NOT NULL"
                ),
                {"t": tenant_id},
            )
        }
        branch = (
            await conn.execute(
                text("SELECT id FROM app.branches WHERE tenant_id = :t ORDER BY is_default DESC LIMIT 1"),
                {"t": tenant_id},
            )
        ).scalar_one()
    return StaffWorld(tenant_id, owner, owner_phone, roles, branch)


async def add_branch(admin_engine: AsyncEngine, tenant_id: UUID, code: str, name: str) -> UUID:
    branch_id = uuid7()
    async with admin_engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO app.branches (id, tenant_id, code, name, settlement_category, activity_type) "
                "VALUES (:id, :t, :code, :name, 'city_100k_plus', 'retail')"
            ),
            {"id": branch_id, "t": tenant_id, "code": code, "name": name},
        )
    return branch_id


async def set_password(db: Database, user_id: UUID, password: str = PASSWORD) -> None:
    """What the invitee does with the invite code (A1's credential-set flow) — here directly."""
    async with db.session_factory() as s, unscoped_transaction(s):
        await s.execute(
            text("SELECT app.auth_set_credentials(:u, :p, NULL)"),
            {"u": user_id, "p": hash_password(password)},
        )


async def credentials(admin_engine: AsyncEngine, user_id: UUID) -> Any:
    async with admin_engine.connect() as conn:
        return (
            await conn.execute(
                text(
                    "SELECT password_hash, pin_hash, must_change_password, must_change_pin "
                    "FROM auth.user_credentials WHERE user_id = :u"
                ),
                {"u": user_id},
            )
        ).first()


async def audit_actions(admin_engine: AsyncEngine, tenant_id: UUID) -> list[str]:
    async with admin_engine.connect() as conn:
        rows = await conn.execute(
            text("SELECT action FROM app.audit_log WHERE tenant_id = :t ORDER BY at, id"), {"t": tenant_id}
        )
        return [r[0] for r in rows]


async def live_sessions(admin_engine: AsyncEngine, user_id: UUID) -> int:
    async with admin_engine.connect() as conn:
        value = (
            await conn.execute(
                text("SELECT count(*) FROM auth.sessions WHERE user_id = :u AND revoked_at IS NULL"),
                {"u": user_id},
            )
        ).scalar()
    return int(value or 0)


def sent_code(app: FastAPI, phone: str) -> tuple[str, str]:
    """(channel, 6-digit code) of the last dev-fake message to ``phone`` (ERP_OTP_DEV_FAKES)."""
    outbox = app.state.auth_module.otp_dev_outbox
    assert outbox is not None, "run the app with otp_dev_fakes=True"
    message = outbox.last_to(phone)
    assert message is not None, f"no OTP sent to {phone}"
    match = re.search(r"\b(\d{6})\b", message.text)
    assert match is not None
    return message.channel, match[1]


def message_texts(app: FastAPI, phone: str) -> list[str]:
    outbox = app.state.auth_module.otp_dev_outbox
    return [m.text for m in outbox.messages if m.destination == phone]


def idem() -> dict[str, str]:
    return {"Idempotency-Key": str(uuid7())}


def owner_headers(token: str) -> dict[str, str]:
    return {**bearer(token), **idem()}


def claims_of(token: str) -> dict[str, Any]:
    raw = token.split(".")[1]
    data: dict[str, Any] = json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
    return data


async def invite(
    client: httpx.AsyncClient,
    token: str,
    *,
    phone: str,
    role_ids: list[UUID],
    branch_ids: list[UUID],
    name: str = "Dilnoza Karimova",
) -> httpx.Response:
    return await client.post(
        "/api/v1/admin/users",
        json={
            "phone": phone,
            "name": name,
            "role_ids": [str(r) for r in role_ids],
            "branch_ids": [str(b) for b in branch_ids],
        },
        headers=owner_headers(token),
    )
