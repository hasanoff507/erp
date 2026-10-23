"""Helpers of the device-auth tests (14 §4.3, §7.2; 16 §9) — real app, Postgres and Redis."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.db.session import Database, unscoped_transaction
from app.modules.auth.application.passwords import hash_pin
from app.modules.auth.domain.pin_verifier import make_pin_verifier
from tests.support.auth import bff_login, csrf_token

DEVICE_COOKIE = "__Host-erp_device"
SID_COOKIE = "__Host-sid"


async def set_pin(
    db: Database, user_id: UUID, pin: str, *, local: bool = True, iterations: int = 1000
) -> str:
    """PIN through the real SECURITY DEFINER path; the local verifier with few iterations (fast tests)."""
    pin_hash = hash_pin(pin)
    async with db.session_factory() as s, unscoped_transaction(s):
        await s.execute(text("SELECT app.auth_set_credentials(:u, NULL, :p)"), {"u": user_id, "p": pin_hash})
        if local:
            await s.execute(
                text("SELECT app.auth_set_pin_local_hash(:u, :p, :l)"),
                {"u": user_id, "p": pin_hash, "l": make_pin_verifier(pin, iterations=iterations)},
            )
    return pin_hash


async def credential_row(admin_engine: AsyncEngine, user_id: UUID) -> Any:
    async with admin_engine.connect() as conn:
        return (
            await conn.execute(
                text(
                    "SELECT pin_hash, pin_local_hash, must_change_pin, pin_updated_at "
                    "FROM auth.user_credentials WHERE user_id = :u"
                ),
                {"u": user_id},
            )
        ).first()


async def one(admin_engine: AsyncEngine, sql: str, **params: Any) -> Any:
    async with admin_engine.connect() as conn:
        return (await conn.execute(text(sql), params)).first()


async def write(admin_engine: AsyncEngine, sql: str, **params: Any) -> None:
    async with admin_engine.begin() as conn:
        await conn.execute(text(sql), params)


async def cookie_write_headers(client: httpx.AsyncClient) -> dict[str, str]:
    return {"X-CSRF-Token": await csrf_token(client)}


async def register_device(
    client: httpx.AsyncClient, cash_register_id: UUID, app_version: str | None = "web-1.0.0"
) -> httpx.Response:
    return await client.post(
        "/auth/devices/register",
        json={"cash_register_id": str(cash_register_id), "app_version": app_version},
        headers=await cookie_write_headers(client),
    )


async def registered_pos(client: httpx.AsyncClient, phone: str, cash_register_id: UUID) -> UUID:
    """Owner/Manager logs in on this browser and registers it as the cash register's web device."""
    await bff_login(client, phone)
    response = await register_device(client, cash_register_id)
    assert response.status_code == 201, response.text
    return UUID(response.json()["id"])


async def pin_verify(client: httpx.AsyncClient, user_id: UUID, pin: str) -> httpx.Response:
    return await client.post(
        "/auth/pin/verify",
        json={"user_id": str(user_id), "pin": pin},
        headers=await cookie_write_headers(client),
    )
