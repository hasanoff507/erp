"""Authorization Server endpoints (14 §1, §20): ``/oauth/*`` and ``/.well-known/*`` (root, no ``/api/v1``)."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit
from uuid import UUID

from authlib.oauth2 import OAuth2Error
from authlib.oauth2.rfc6749.util import extract_basic_authorization
from authlib.oauth2.rfc8414 import AuthorizationServerMetadata
from fastapi import APIRouter, Request
from redis.exceptions import RedisError
from starlette.datastructures import FormData
from starlette.responses import JSONResponse, Response

from app.core.ratelimit import hit
from app.modules.auth.api.deps import auth_module
from app.modules.auth.api.login_page import OAUTH_PARAMS, UI_LOCALES_PARAM, render_login
from app.modules.auth.application.agent_grants import AGENT_SCOPE, DEVICE_CODE_GRANT
from app.modules.auth.application.gateway import request_meta
from app.modules.auth.application.login import LoginError
from app.modules.auth.application.oauth_server import ErpOAuth2Request, OAuthResponse
from app.modules.auth.domain.constants import IMPLICIT_SCOPES

router = APIRouter(tags=["auth"])

_LOGIN_STATUS = {
    "INVALID_CREDENTIALS": 401,
    "ACCOUNT_LOCKED": 423,
    "RATE_LIMITED": 429,
    "SUBSCRIPTION_RESTRICTED": 403,
    "PERMISSION_DENIED": 403,
    "VALIDATION_ERROR": 422,
}


def to_response(result: OAuthResponse) -> Response:
    status, body, headers = result
    header_map = {k: v for k, v in headers if k.lower() != "content-type"}
    if isinstance(body, dict):
        return JSONResponse(body, status_code=status, headers=header_map)
    return Response(body or b"", status_code=status, headers=header_map)


def _oauth_request(
    request: Request, form: FormData | None = None, *, only: tuple[str, ...] | None = None
) -> ErpOAuth2Request:
    issuer = auth_module(request).settings.issuer
    uri = f"{issuer}{request.url.path}" + (f"?{request.url.query}" if request.url.query else "")
    form_items = [
        (k, v)
        for k, v in (form.multi_items() if form is not None else [])
        if isinstance(v, str) and (only is None or k in only)
    ]
    return ErpOAuth2Request(
        request.method,
        uri,
        request.headers,
        query=list(request.query_params.multi_items()),
        form=form_items,
        meta=request_meta(request),
    )


def _issuer_origin(issuer: str) -> str:
    parts = urlsplit(issuer)
    return f"{parts.scheme}://{parts.netloc}"


def same_origin(request: Request) -> bool:
    """Login-CSRF guard for the password POST (14 §2.1 "Qo'shimcha himoya" 1)."""
    origin = request.headers.get("origin")
    if origin and origin != "null":
        module = auth_module(request)
        if origin.rstrip("/") == _issuer_origin(module.settings.issuer):
            return True
        # Vite serves the first-party app from :5173 and proxies this POST to the AS. Keep
        # the browser's origin intact; trust that exact origin only in local development.
        return module.settings.environment == "local" and origin == "http://localhost:5173"
    # Sandboxed/document contexts can serialize Origin as "null". That value is not
    # trusted by itself; use the same Fetch Metadata fallback as requests without Origin.
    return request.headers.get("sec-fetch-site") == "same-origin"


def _oauth_error(error: str, description: str, status: int = 400) -> JSONResponse:
    return JSONResponse(
        {"error": error, "error_description": description},
        status_code=status,
        headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
    )


# --- metadata --------------------------------------------------------------------------------------
@router.get("/.well-known/oauth-authorization-server", operation_id="oauth_metadata", include_in_schema=False)
async def metadata(request: Request) -> JSONResponse:
    issuer = auth_module(request).settings.issuer
    data: dict[str, Any] = {
        "issuer": issuer,
        "authorization_endpoint": f"{issuer}/oauth/authorize",
        "token_endpoint": f"{issuer}/oauth/token",
        "jwks_uri": f"{issuer}/.well-known/jwks.json",
        "revocation_endpoint": f"{issuer}/oauth/revoke",
        "introspection_endpoint": f"{issuer}/oauth/introspect",
        "response_types_supported": ["code"],
        "response_modes_supported": ["query"],
        # client_credentials (+ private_key_jwt) and device_code: the store agent only (14 §2.3)
        "grant_types_supported": [
            "authorization_code",
            "refresh_token",
            "client_credentials",
            DEVICE_CODE_GRANT,
        ],
        "device_authorization_endpoint": f"{issuer}/oauth/device_authorization",
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": [
            "client_secret_basic",
            "client_secret_post",
            "none",
            "private_key_jwt",
        ],
        "token_endpoint_auth_signing_alg_values_supported": ["EdDSA"],
        "revocation_endpoint_auth_methods_supported": ["client_secret_basic", "client_secret_post", "none"],
        "introspection_endpoint_auth_methods_supported": ["client_secret_basic", "client_secret_post"],
        "scopes_supported": sorted({*IMPLICIT_SCOPES, AGENT_SCOPE}),
    }
    AuthorizationServerMetadata(data).validate()
    return JSONResponse(data, headers={"Cache-Control": "public, max-age=300"})


@router.get("/.well-known/jwks.json", operation_id="oauth_jwks", include_in_schema=False)
async def jwks(request: Request) -> JSONResponse:
    return JSONResponse(
        await auth_module(request).ring.jwks(), headers={"Cache-Control": "public, max-age=300"}
    )


# --- authorization endpoint ------------------------------------------------------------------------
@router.get("/oauth/authorize", operation_id="oauth_authorize_page", include_in_schema=False)
async def authorize_page(request: Request) -> Response:
    module = auth_module(request)
    oreq = _oauth_request(request)
    try:
        await module.server.consent_grant(oreq)
    except OAuth2Error as error:
        return to_response(module.server.error_response(oreq, error))
    params = dict(oreq.args)
    return render_login(params, accept_language=request.headers.get("accept-language"))


@router.post("/oauth/authorize", operation_id="oauth_authorize_login", include_in_schema=False)
async def authorize_login(request: Request) -> Response:
    module = auth_module(request)
    if not same_origin(request):
        return _oauth_error("invalid_request", "cross_origin_login_rejected", 403)
    form = await request.form()
    oreq = _oauth_request(request, form, only=OAUTH_PARAMS)
    try:
        grant = await module.server.consent_grant(oreq)
    except OAuth2Error as error:
        return to_response(module.server.error_response(oreq, error))

    params = dict(oreq.form)
    phone = str(form.get("phone") or "")
    password = str(form.get("password") or "")
    raw_tenant = str(form.get("tenant_id") or "")
    if raw_tenant:
        params["tenant_id"] = raw_tenant
    ui_locales = str(form.get(UI_LOCALES_PARAM) or "")[:64]
    if ui_locales:
        params[UI_LOCALES_PARAM] = ui_locales
    try:
        tenant_id = UUID(raw_tenant) if raw_tenant else None
    except ValueError:
        tenant_id = None
    try:
        user = await module.login.authenticate(phone, password, request_meta(request).ip, tenant_id)
    except LoginError as exc:
        headers = {"Retry-After": str(exc.retry_after_s)} if exc.retry_after_s else None
        return render_login(
            params,
            error_code=exc.code.value,
            tenants=exc.tenants,
            phone=phone,
            status_code=_LOGIN_STATUS.get(exc.code.value, 400),
            headers=headers,
            accept_language=request.headers.get("accept-language"),
        )
    return to_response(await module.server.authorize(oreq, grant, user))


# --- token / revoke / introspect -------------------------------------------------------------------
async def _token_rate_limited(request: Request, form: FormData) -> int | None:
    module = auth_module(request)
    client_id = str(form.get("client_id") or "")[:64]  # bounded Redis key, like the Basic path
    if not client_id:
        basic_id, _ = extract_basic_authorization(request.headers)
        client_id = str(basic_id or "-")[:64]
    ip = request_meta(request).ip or "-"
    try:
        state = await hit(request.app.state.redis, f"auth:rl:token:{client_id}:{ip}", 60)
    except RedisError:
        return None
    if state.count > module.settings.token_requests_per_minute:
        return state.retry_after_s
    return None


@router.post("/oauth/token", operation_id="oauth_token", include_in_schema=False)
async def token(request: Request) -> Response:
    module = auth_module(request)
    form = await request.form()
    retry_after = await _token_rate_limited(request, form)
    if retry_after is not None:
        response = _oauth_error("slow_down", "rate_limited", 429)
        response.headers["Retry-After"] = str(retry_after)
        return response
    agent_form = {k: v for k, v in form.items() if isinstance(v, str)}
    if module.agent_grants.handles(agent_form):  # store agent: device code / private_key_jwt (14 §2.3)
        status, body, headers = await module.agent_grants.token(agent_form)
        return to_response((status, body, list(headers.items())))
    return to_response(await module.server.token(_oauth_request(request, form)))


@router.post(
    "/oauth/device_authorization", operation_id="oauth_device_authorization", include_in_schema=False
)
async def device_authorization(request: Request) -> Response:
    """RFC 8628 §3.1 — only ``client_id=onec-agent`` (14 §2.3, 33 §9.2); 10 requests / IP / hour."""
    module = auth_module(request)
    form = await request.form()
    fields = {k: v for k, v in form.items() if isinstance(v, str)}
    status, body, headers = await module.agent_grants.device_authorization(fields, request_meta(request).ip)
    return to_response((status, body, list(headers.items())))


@router.post("/oauth/revoke", operation_id="oauth_revoke", include_in_schema=False)
async def revoke(request: Request) -> Response:
    module = auth_module(request)
    form = await request.form()
    return to_response(await module.server.endpoint("revocation", _oauth_request(request, form)))


@router.post("/oauth/introspect", operation_id="oauth_introspect", include_in_schema=False)
async def introspect(request: Request) -> Response:
    module = auth_module(request)
    form = await request.form()
    return to_response(await module.server.endpoint("introspection", _oauth_request(request, form)))
