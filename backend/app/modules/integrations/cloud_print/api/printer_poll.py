"""Printer-side polling routes — no user session, no ``/api/v1`` prefix (24 §6.1; 20 #40r/#40s).

The printer authenticates with HTTP Basic: username = ``cloud_printers.id``, password = the printer secret
(shown once on create/rotate). Unknown printer, wrong secret, a disabled printer or the other protocol's
route → ``401`` with ``WWW-Authenticate`` (no body detail).

* ``/print/cloudprnt`` — Star CloudPRNT (HTTP): ``POST`` poll (JSON status → ``{jobReady, mediaTypes,
  jobToken}``), ``GET ?mac=&type=&token=`` job body (``image/png``), ``DELETE ?mac=&code=&token=`` (or ``GET``
  with ``&delete``) confirmation. Source: Star Micronics CloudPRNT Protocol Guide; reference server
  github.com/star-micronics/cloudprnt-sdk ``ExampleServers/php_queue/cloudprnt.php``.
* ``/print/epson-sdp`` — Epson Server Direct Print: ``POST`` form ``ConnectionType=GetRequest`` →
  ``PrintRequestInfo`` (ePOS-Print XML) or an empty body; ``ConnectionType=SetResponse`` + ``ResponseFile``
  → results. Source: Seiko Epson Server Direct Print User's Manual / sample program.
"""

from __future__ import annotations

import base64
import binascii
import json
from typing import Any
from urllib.parse import parse_qs
from uuid import UUID

from fastapi import APIRouter, Request, Response

from app.modules.integrations.cloud_print.api.router import cloud_print_module
from app.modules.integrations.cloud_print.application.ports import PrinterAuth
from app.modules.integrations.cloud_print.application.service import PrinterAuthError

router = APIRouter(include_in_schema=False)

MAX_POLL_BODY = 64 * 1024


def _unauthorized() -> Response:
    return Response(status_code=401, headers={"WWW-Authenticate": 'Basic realm="erp-print"'})


def _basic(request: Request) -> tuple[UUID, str] | None:
    header = request.headers.get("authorization", "")
    scheme, _, value = header.partition(" ")
    if scheme.lower() != "basic" or not value:
        return None
    try:
        decoded = base64.b64decode(value.strip(), validate=True).decode("utf-8")
        user, sep, secret = decoded.partition(":")
        return (UUID(user), secret) if sep and secret else None
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return None


async def _auth(request: Request, protocol: str) -> PrinterAuth | None:
    creds = _basic(request)
    if creds is None:
        return None
    try:
        return await cloud_print_module(request).poll.authenticate(creds[0], creds[1], protocol)
    except PrinterAuthError:
        return None


async def _body(request: Request) -> bytes | None:
    data = await request.body()
    return None if len(data) > MAX_POLL_BODY else data


# --- Star CloudPRNT --------------------------------------------------------------------------------


@router.post("/print/cloudprnt")
async def cloudprnt_poll(request: Request) -> Response:
    auth = await _auth(request, "star_cloudprnt")
    if auth is None:
        return _unauthorized()
    raw = await _body(request)
    try:
        status: Any = json.loads(raw or b"{}")
    except ValueError:
        status = {}
    reply = await cloud_print_module(request).poll.star_poll(auth, status if isinstance(status, dict) else {})
    return Response(content=json.dumps(reply), media_type="application/json")


@router.get("/print/cloudprnt")
async def cloudprnt_get(request: Request) -> Response:
    auth = await _auth(request, "star_cloudprnt")
    if auth is None:
        return _unauthorized()
    params = request.query_params
    module = cloud_print_module(request)
    if "delete" in params or "code" in params:  # "deleteMethod": "GET" variant
        await module.poll.star_confirm(auth, params.get("token"), params.get("code"))
        return Response(status_code=200)
    job = await module.poll.star_job(auth, params.get("token"), params.get("type"))
    if job is None:
        return Response(status_code=404)
    return Response(content=job.body, media_type=job.content_type)


@router.delete("/print/cloudprnt")
async def cloudprnt_delete(request: Request) -> Response:
    auth = await _auth(request, "star_cloudprnt")
    if auth is None:
        return _unauthorized()
    params = request.query_params
    await cloud_print_module(request).poll.star_confirm(auth, params.get("token"), params.get("code"))
    return Response(status_code=200)


# --- Epson Server Direct Print ---------------------------------------------------------------------


@router.post("/print/epson-sdp")
async def epson_sdp(request: Request) -> Response:
    auth = await _auth(request, "epson_sdp")
    if auth is None:
        return _unauthorized()
    raw = await _body(request)
    if raw is None:
        return Response(status_code=413)
    form = {k: v[0] for k, v in parse_qs(raw.decode("utf-8", "replace"), keep_blank_values=True).items()}
    poll = cloud_print_module(request).poll
    kind = form.get("ConnectionType")
    if kind == "GetRequest":
        xml = await poll.sdp_get_request(auth)
        return Response(content=xml or "", media_type="text/xml; charset=utf-8")
    if kind == "SetResponse":
        await poll.sdp_set_response(auth, form.get("ResponseFile", ""))
    return Response(content="", media_type="text/xml; charset=utf-8")
