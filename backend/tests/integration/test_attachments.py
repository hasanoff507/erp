"""Attachments (17 §12): upload (kind/type/size/magic), read with a 15-minute signed URL, tenant isolation,
and the BO-17 receipt photo referenced by an expense (US-M15-01)."""

from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest

from app.modules.attachments.domain.rules import MAX_BYTES, PNG
from tests.support.cash import (
    cash_env_fixture,  # noqa: F401 - fixture "env"
    make_till,
    one,
)
from tests.support.catalog import Env
from tests.support.expenses import API, category_id, expense_body

pytestmark = pytest.mark.asyncio
ATT = f"{API}/attachments"
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"\x01" * 64


async def _upload(env: Env, headers: dict[str, str], kind: str, name: str, data: bytes, ctype: str) -> Any:
    return await env.client.post(
        ATT, data={"kind": kind}, files={"file": (name, data, ctype)}, headers=headers
    )


async def test_upload_receipt_photo_get_signed_url_and_download(env: Env) -> None:
    till = await make_till(env)
    r = await _upload(env, till.shop.h("manager"), "expense_receipt", "chek ijara.png", PNG_BYTES, PNG)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["content_type"] == PNG and body["size_bytes"] == len(PNG_BYTES)
    row = await one(
        env.db,
        till.shop.tenant_id,
        "SELECT kind || ':' || sha256 FROM app.attachments WHERE id = :i",
        i=body["id"],
    )
    assert str(row).startswith("expense_receipt:") and len(str(row)) == len("expense_receipt:") + 64
    meta = await env.client.get(f"{ATT}/{body['id']}", headers=till.shop.h("manager", key=None))
    assert meta.status_code == 200
    assert meta.json()["original_name"] == "chek ijara.png" and meta.json()["kind"] == "expense_receipt"
    # the signed URL works without a bearer token
    download = await env.client.get(meta.json()["url"])
    assert download.status_code == 200 and download.content == PNG_BYTES
    assert download.headers["content-type"] == PNG
    assert download.headers["x-content-type-options"] == "nosniff"
    # tampered signature / expired link → 403
    parts = urlsplit(meta.json()["url"])
    q = {k: v[0] for k, v in parse_qs(parts.query).items()}
    bad = await env.client.get(parts.path, params={**q, "sig": "0" * 64})
    assert bad.status_code == 403
    expired = await env.client.get(parts.path, params={**q, "exp": "1000"})
    assert expired.status_code == 403
    # the expense may reference it (BO-17 "Hujjat fotosi")
    rent = await category_id(env, till.shop.tenant_id, "rent_store")
    r = await env.client.post(
        f"{API}/expenses",
        json=expense_body(rent, attachment_id=body["id"]),
        headers=till.shop.h(branch=till.shop.branch_id),
    )
    assert r.status_code == 201, r.text
    assert r.json()["attachment_id"] == body["id"]


async def test_upload_rules_kind_type_magic_size_and_rights(env: Env) -> None:
    till = await make_till(env)
    h = till.shop.h
    # unknown / server-only kind
    assert (await _upload(env, h(), "export", "a.png", PNG_BYTES, PNG)).status_code == 422
    assert (await _upload(env, h(), "nope", "a.png", PNG_BYTES, PNG)).status_code == 422
    # type not allowed for the kind → 415
    r = await _upload(env, h(), "expense_receipt", "a.csv", b"a,b\n1,2\n", "text/csv")
    assert r.status_code == 415 and r.json()["error"]["code"] == "UNSUPPORTED_FILE_TYPE"
    # declared PNG but the bytes are not a PNG → 415
    assert (await _upload(env, h(), "expense_receipt", "x.png", b"<html>hi</html>", PNG)).status_code == 415
    assert (await _upload(env, h(), "expense_receipt", "x.jpg", JPEG_BYTES, "image/jpeg")).status_code == 201
    # image over 10 MB → 413
    big = b"\x89PNG\r\n\x1a\n" + b"\x00" * MAX_BYTES[PNG]
    r = await _upload(env, h(), "expense_receipt", "big.png", big, PNG)
    assert r.status_code == 413 and r.json()["error"]["code"] == "FILE_TOO_LARGE"
    # the cashier has no expenses.create → 403
    assert (await _upload(env, h("cashier"), "expense_receipt", "a.png", PNG_BYTES, PNG)).status_code == 403
    # Idempotency-Key is mandatory for the write
    assert (await _upload(env, h(key=None), "expense_receipt", "a.png", PNG_BYTES, PNG)).status_code in (
        400,
        422,
    )


async def test_other_tenant_cannot_read_and_expense_needs_receipt_kind(env: Env) -> None:
    till = await make_till(env)
    other = await make_till(env, "Boshqa do'kon")
    r = await _upload(env, till.shop.h(), "expense_receipt", "a.png", PNG_BYTES, PNG)
    attachment_id = r.json()["id"]
    assert (await env.client.get(f"{ATT}/{attachment_id}", headers=other.shop.h(key=None))).status_code == 404
    # a stranger's id cannot be attached to an expense
    rent = await category_id(env, other.shop.tenant_id, "rent_store")
    r = await env.client.post(
        f"{API}/expenses",
        json=expense_body(rent, attachment_id=attachment_id),
        headers=other.shop.h(branch=other.shop.branch_id),
    )
    assert r.status_code == 404 and r.json()["error"]["params"]["resource"] == "attachment"
    # an import file is not a receipt
    csv = await _upload(env, till.shop.h(), "import", "p.csv", b"name\nNon\n", "text/csv")
    assert csv.status_code == 201, csv.text
    own_rent = await category_id(env, till.shop.tenant_id, "rent_store")
    r = await env.client.post(
        f"{API}/expenses",
        json=expense_body(own_rent, attachment_id=csv.json()["id"]),
        headers=till.shop.h(branch=till.shop.branch_id),
    )
    assert r.status_code == 422 and r.json()["error"]["details"][0]["field"] == "attachment_id"
