"""Helpers for the OAuth tests — real app, real Postgres/Redis, no mocks (14 §21)."""

from __future__ import annotations

import base64
import hashlib
import itertools
import re
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlsplit
from uuid import UUID

import httpx
from fastapi import FastAPI
from pydantic import SecretStr

from app.core.config import Settings
from app.main import create_app
from tests.conftest import MigratedDb

ISSUER = "https://testserver"
BFF_SECRET = "test-web-bff-secret-0123456789abcdef"
WEB_CALLBACK = f"{ISSUER}/auth/callback"
ANDROID_CALLBACK = f"{ISSUER}/android/callback"
PASSWORD = "Parol-12345"


def auth_settings(migrated_db: MigratedDb, redis_url: str, **overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "_env_file": None,
        "environment": "test",
        "database_url": SecretStr(migrated_db.app_url),
        "redis_url": SecretStr(redis_url),
        "log_json": False,
        "public_base_url": ISSUER,
        "web_bff_client_secret": SecretStr(BFF_SECRET),
        **overrides,
    }
    return Settings(**values)


@asynccontextmanager
async def running_app(
    settings: Settings, *, client_ip: str = "127.0.0.1"
) -> AsyncIterator[tuple[FastAPI, httpx.AsyncClient]]:
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app, client=(client_ip, 50000))
        async with httpx.AsyncClient(transport=transport, base_url=ISSUER) as client:
            yield app, client


def client_at(app: FastAPI, ip: str) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app, client=(ip, 50001)), base_url=ISSUER)


# One run creates thousands of users (``app.users.phone`` is globally UNIQUE): independent random draws from
# 10^7 numbers collide in most full runs (birthday bound), and a collided seed user then fails with
# ``memberships_user_id_fkey`` (seed_demo_user's ON CONFLICT (phone) DO NOTHING keeps the other tenant's
# user, which RLS hides). A random start + a counter keeps the numbers distinct within the process.
_PHONE_SEQ = itertools.count(secrets.randbelow(10**7))


def new_phone() -> str:
    return f"+99890{next(_PHONE_SEQ) % 10**7:07d}"


@dataclass(frozen=True)
class Pkce:
    verifier: str
    challenge: str

    @classmethod
    def new(cls) -> Pkce:
        verifier = secrets.token_urlsafe(48)
        digest = hashlib.sha256(verifier.encode()).digest()
        return cls(verifier, base64.urlsafe_b64encode(digest).decode().rstrip("="))


def authorize_params(
    pkce: Pkce,
    *,
    client_id: str = "android-pos",
    redirect_uri: str = ANDROID_CALLBACK,
    state: str = "st-1",
    method: str | None = "S256",
    **extra: str,
) -> dict[str, str]:
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "state": state,
        "code_challenge": pkce.challenge,
        **extra,
    }
    if method is not None:
        params["code_challenge_method"] = method
    return params


async def login_for_code(
    client: httpx.AsyncClient, phone: str, password: str, params: dict[str, str]
) -> httpx.Response:
    """The browser posts the AS login form (same origin)."""
    return await client.post(
        "/oauth/authorize",
        data={**params, "phone": phone, "password": password},
        headers={"Origin": ISSUER},
    )


def query_of(response: httpx.Response) -> dict[str, str]:
    location = response.headers["location"]
    return {k: v[0] for k, v in parse_qs(urlsplit(location).query).items()}


async def android_code(client: httpx.AsyncClient, phone: str, pkce: Pkce, password: str = PASSWORD) -> str:
    response = await login_for_code(client, phone, password, authorize_params(pkce))
    assert response.status_code == 302, response.text
    query = query_of(response)
    assert query["state"] == "st-1"
    return query["code"]


async def exchange_code(
    client: httpx.AsyncClient, code: str, verifier: str, *, redirect_uri: str = ANDROID_CALLBACK
) -> httpx.Response:
    return await client.post(
        "/oauth/token",
        data={
            "grant_type": "authorization_code",
            "client_id": "android-pos",
            "code": code,
            "redirect_uri": redirect_uri,
            "code_verifier": verifier,
        },
    )


async def android_tokens(client: httpx.AsyncClient, phone: str, password: str = PASSWORD) -> dict[str, Any]:
    pkce = Pkce.new()
    code = await android_code(client, phone, pkce, password)
    response = await exchange_code(client, code, pkce.verifier)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


async def refresh(client: httpx.AsyncClient, refresh_token: str, **extra: str) -> httpx.Response:
    return await client.post(
        "/oauth/token",
        data={
            "grant_type": "refresh_token",
            "client_id": "android-pos",
            "refresh_token": refresh_token,
            **extra,
        },
    )


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def bff_login(
    client: httpx.AsyncClient,
    phone: str,
    password: str = PASSWORD,
    return_to: str = "/",
    *,
    tenant_id: UUID | None = None,
) -> str:
    """Full 14 §2.1 flow: /auth/login/start → AS page → password POST → /auth/callback → cookie.

    ``tenant_id`` preselects the shop of a user with several memberships (no chooser step).
    """
    params = {"return_to": return_to}
    if tenant_id is not None:
        params["tenant_id"] = str(tenant_id)
    start = await client.get("/auth/login/start", params=params)
    assert start.status_code == 302, start.text
    authorize_url = start.headers["location"]
    assert authorize_url.startswith(f"{ISSUER}/oauth/authorize?")
    page = await client.get(authorize_url)
    assert page.status_code == 200, page.text
    hidden = dict(re.findall(r'<input type="hidden" name="([^"]+)" value="([^"]*)">', page.text))
    assert hidden["client_id"] == "web-bff"
    posted = await login_for_code(client, phone, password, {k: _unescape(v) for k, v in hidden.items()})
    assert posted.status_code == 302, posted.text
    callback = posted.headers["location"]
    assert callback.startswith(WEB_CALLBACK)
    done = await client.get(callback)
    assert done.status_code == 302, done.text
    assert done.headers["location"] == return_to
    sid = client.cookies.get("__Host-sid")
    assert sid
    return sid


def _unescape(value: str) -> str:
    return value.replace("&amp;", "&").replace("&quot;", '"').replace("&#x27;", "'").replace("&lt;", "<")


async def csrf_token(client: httpx.AsyncClient) -> str:
    response = await client.get("/api/v1/auth/csrf")
    assert response.status_code == 200, response.text
    token: str = response.json()["csrf_token"]
    return token


def as_uuid(value: str) -> UUID:
    return UUID(value)
