"""Slice A1 test helpers: a local stub of the external HTTP APIs + signup/OTP flow helpers.

The real adapters (Telegram Bot API, Eskiz, Google OIDC) talk real HTTP to a uvicorn server on
127.0.0.1 (no mocks of our code; 23 §6, qaror #34). The stub records what it received, so a test
reads the OTP exactly where a user would: in the Telegram message / SMS text.
"""

from __future__ import annotations

import re
import socket
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

import httpx
import uvicorn
from joserfc import jwt
from joserfc.jwk import KeySet, RSAKey
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from tests.support.auth import ISSUER

BOT_TOKEN = "123456:stub-bot-token"
GOOGLE_CLIENT_ID = "web-client.apps.googleusercontent.com"
GOOGLE_ANDROID_CLIENT_ID = "android-client.apps.googleusercontent.com"
GOOGLE_ISSUER = "https://accounts.google.com"
TERMS_VERSION = "v1-test"
STRONG_PASSWORD = "Yangi-Parol-2026"


@dataclass
class StubState:
    telegram: list[dict[str, Any]] = field(default_factory=list)
    sms: list[dict[str, str]] = field(default_factory=list)
    telegram_fail: bool = False
    sms_fail: bool = False
    eskiz_logins: int = 0
    google_codes: dict[str, dict[str, Any]] = field(default_factory=dict)
    google_token_fail: bool = False
    google_key: RSAKey = field(
        default_factory=lambda: RSAKey.generate_key(2048, parameters={"kid": "stub-1"})
    )

    def reset(self) -> None:
        self.telegram.clear()
        self.sms.clear()
        self.telegram_fail = self.sms_fail = self.google_token_fail = False
        self.google_codes.clear()

    def id_token(self, claims: dict[str, Any], key: RSAKey | None = None) -> str:
        now = int(time.time())
        payload = {"iss": GOOGLE_ISSUER, "aud": GOOGLE_CLIENT_ID, "iat": now, "exp": now + 600, **claims}
        signing = key or self.google_key
        return jwt.encode({"alg": "RS256", "kid": signing.kid}, payload, signing)


def _code(text_: str) -> str:
    match = re.search(r"\b(\d{6})\b", text_)
    assert match is not None, text_
    return match[1]


class Stub:
    def __init__(self, base_url: str, state: StubState) -> None:
        self.base_url = base_url
        self.state = state

    def telegram_code(self, chat_id: str) -> str:
        for message in reversed(self.state.telegram):
            if str(message["chat_id"]) == chat_id:
                return _code(str(message["text"]))
        raise AssertionError(f"no telegram message to {chat_id}")

    def sms_code(self, phone: str) -> str:
        for message in reversed(self.state.sms):
            if message["mobile_phone"] == phone.lstrip("+"):
                return _code(message["message"])
        raise AssertionError(f"no sms to {phone}")


def _app(state: StubState) -> Starlette:
    async def send_message(request: Request) -> JSONResponse:
        if request.path_params["token"] != BOT_TOKEN:
            return JSONResponse({"ok": False, "description": "Unauthorized"}, status_code=401)
        body = await request.json()
        if state.telegram_fail:
            return JSONResponse({"ok": False, "description": "Forbidden: bot was blocked by the user"}, 403)
        state.telegram.append(body)
        return JSONResponse({"ok": True, "result": {"message_id": len(state.telegram)}})

    async def eskiz_login(request: Request) -> JSONResponse:
        form = await request.form()
        if form.get("email") != "eskiz@test.uz":
            return JSONResponse({"message": "invalid"}, status_code=401)
        state.eskiz_logins += 1
        return JSONResponse({"message": "token_generated", "data": {"token": "eskiz-token"}})

    async def eskiz_send(request: Request) -> JSONResponse:
        if request.headers.get("authorization") != "Bearer eskiz-token":
            return JSONResponse({"message": "Unauthorized"}, status_code=401)
        if state.sms_fail:
            return JSONResponse({"message": "Service unavailable"}, status_code=503)
        form = await request.form()
        state.sms.append({k: str(v) for k, v in form.items()})
        return JSONResponse({"id": "sms-1", "status": "waiting"})

    async def google_token(request: Request) -> JSONResponse:
        form = await request.form()
        claims = state.google_codes.pop(str(form.get("code")), None)
        if state.google_token_fail or claims is None or form.get("client_secret") != "google-secret":
            return JSONResponse({"error": "invalid_grant"}, status_code=400)
        return JSONResponse(
            {"access_token": "ya29.x", "id_token": state.id_token(claims), "token_type": "Bearer"}
        )

    async def google_certs(_: Request) -> JSONResponse:
        return JSONResponse(KeySet([state.google_key]).as_dict(private=False))

    return Starlette(
        routes=[
            Route("/bot{token}/sendMessage", send_message, methods=["POST"]),
            Route("/api/auth/login", eskiz_login, methods=["POST"]),
            Route("/api/message/sms/send", eskiz_send, methods=["POST"]),
            Route("/google/token", google_token, methods=["POST"]),
            Route("/google/certs", google_certs, methods=["GET"]),
        ]
    )


def start_stub() -> Iterator[Stub]:
    state = StubState()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(_app(state), log_level="warning", lifespan="off"))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.02)
    assert server.started, "stub server did not start"
    try:
        yield Stub(f"http://127.0.0.1:{port}", state)
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        sock.close()


def stub_settings(stub: Stub) -> dict[str, Any]:
    """Settings overrides that point the real adapters at the stub."""
    from pydantic import SecretStr

    return {
        "telegram_bot_token": SecretStr(BOT_TOKEN),
        "telegram_api_base_url": stub.base_url,
        "eskiz_base_url": stub.base_url,
        "eskiz_email": "eskiz@test.uz",
        "eskiz_password": SecretStr("eskiz-secret"),
        "eskiz_test_mode": False,
        "google_client_id": GOOGLE_CLIENT_ID,
        "google_client_secret": SecretStr("google-secret"),
        "google_android_client_ids": [GOOGLE_ANDROID_CLIENT_ID],
        "google_auth_url": f"{stub.base_url}/google/auth",
        "google_token_url": f"{stub.base_url}/google/token",
        "google_jwks_url": f"{stub.base_url}/google/certs",
        "otp_recovery_min_response_ms": 0,
    }


async def ensure_terms(migrator_engine: AsyncEngine) -> str:
    """The current ``terms`` version (12 platform.terms_versions) — seeded by deploy, here by the test."""
    async with migrator_engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO platform.terms_versions (version, kind, text_url, text_sha256, effective_from, "
                "is_current) SELECT :v, 'terms', 'https://erp.test/terms/v1', repeat('a', 64), now(), true "
                "WHERE NOT EXISTS (SELECT 1 FROM platform.terms_versions WHERE kind = 'terms' AND is_current)"
            ),
            {"v": TERMS_VERSION},
        )
        current = (
            await conn.execute(
                text("SELECT version FROM platform.terms_versions WHERE kind='terms' AND is_current")
            )
        ).scalar_one()
    return str(current)


SAME_ORIGIN = {"Origin": ISSUER}


async def request_otp(client: httpx.AsyncClient, phone: str, purpose: str = "signup") -> httpx.Response:
    return await client.post(
        "/auth/otp/request", json={"phone": phone, "purpose": purpose}, headers=SAME_ORIGIN
    )


async def verify_otp(client: httpx.AsyncClient, challenge_id: str, code: str) -> httpx.Response:
    return await client.post(
        "/auth/otp/verify", json={"challenge_id": challenge_id, "code": code}, headers=SAME_ORIGIN
    )


def signup_body(challenge_id: str, terms: str, **overrides: Any) -> dict[str, Any]:
    return {
        "otp_challenge_id": challenge_id,
        "password": STRONG_PASSWORD,
        "owner_name": "Aziz Karimov",
        "store_name": "Aziz do'koni",
        "business_type": "retail",
        "legal_form": "llc",
        "accepted_terms_version": terms,
        "ai_cross_border_consent": False,
        **overrides,
    }


async def verified_signup_challenge(client: httpx.AsyncClient, stub: Stub, phone: str) -> str:
    requested = await request_otp(client, phone)
    assert requested.status_code == 200, requested.text
    challenge = str(requested.json()["challenge_id"])
    verified = await verify_otp(client, challenge, stub.sms_code(phone))
    assert verified.status_code == 200, verified.text
    return challenge
