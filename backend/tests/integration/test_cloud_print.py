"""Cloud printers + print queue (B5-T04; 24 §6.1, qaror #21; 20 #40m–#40s; 12 ``cloud_printers``/``print_jobs``).

Star CloudPRNT and Epson Server Direct Print are driven through the real ``/print/*`` routes with HTTP Basic
(printer id + secret), no user session; the web ``CloudPrintAdapter`` side through ``POST /print-jobs``."""

from __future__ import annotations

import base64
import zlib
from uuid import UUID

import pytest
from sqlalchemy import text

from app.core.db.base import uuid7
from app.core.db.rls import SECURITY_DEFINER_FUNCTIONS_0028A_DEVICES, missing_security_definer_functions
from app.core.db.session import tenant_transaction, unscoped_transaction
from tests.support.card import API, audit_actions, card_env_fixture, card_shop, err
from tests.support.catalog import Env
from tests.support.devices import basic, create_printer, job_row, raster, sdp_post, star_poll, submit_job

__all__ = ["card_env_fixture"]

pytestmark = pytest.mark.asyncio


def _png_rows(png: bytes, width: int, height: int) -> list[bytes]:
    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    pos, idat = 8, b""
    while pos < len(png):
        length = int.from_bytes(png[pos : pos + 4], "big")
        tag = png[pos + 4 : pos + 8]
        if tag == b"IHDR":
            ihdr = png[pos + 8 : pos + 8 + length]
            assert int.from_bytes(ihdr[0:4], "big") == width and int.from_bytes(ihdr[4:8], "big") == height
            assert ihdr[8] == 1 and ihdr[9] == 0  # 1-bit grayscale
        elif tag == b"IDAT":
            idat += png[pos + 8 : pos + 8 + length]
        pos += 12 + length
    raw = zlib.decompress(idat)
    stride = (width + 7) // 8
    return [raw[y * (stride + 1) + 1 : (y + 1) * (stride + 1)] for y in range(height)]


async def test_b5_t04_cloud_printer_registry_secret_and_audit(env: Env) -> None:
    cs = await card_shop(env)
    printer = await create_printer(env.client, cs.shop)
    assert printer["protocol"] == "star_cloudprnt" and printer["poll_path"] == "/print/cloudprnt"
    assert printer["online"] is False and len(printer["secret"]) >= 40
    async with env.db.session_factory() as s, tenant_transaction(s, cs.tenant_id):
        stored = (
            await s.execute(
                text("SELECT secret_hash FROM app.cloud_printers WHERE id = :id"), {"id": printer["id"]}
            )
        ).scalar_one()
    assert stored != printer["secret"] and len(stored) == 64  # only the SHA-256 is kept
    # POS-16: the cashier sees the branch printers (no secret), but cannot register one
    r = await env.client.get(f"{API}/cloud-printers", headers=cs.h("cashier", key=None))
    assert r.status_code == 200 and r.json()["total"] == 1 and "secret" not in r.json()["items"][0]
    r = await env.client.post(
        f"{API}/cloud-printers",
        json={"branch_id": str(cs.branch_id), "name": "X", "protocol": "epson_sdp"},
        headers=cs.h("cashier"),
    )
    assert r.status_code == 403
    # rotate: the old secret stops working
    r = await env.client.post(f"{API}/cloud-printers/{printer['id']}/secret", headers=cs.h("owner"))
    assert r.status_code == 200
    rotated = r.json()
    assert (await star_poll(env.client, printer)).status_code == 401
    assert (await star_poll(env.client, rotated)).status_code == 200
    # disable → printer can no longer poll; archive is final
    r = await env.client.patch(
        f"{API}/cloud-printers/{printer['id']}", json={"status": "disabled", "version": rotated["version"]},
        headers=cs.h("owner"),
    )  # fmt: skip
    assert r.status_code == 200 and r.json()["status"] == "disabled"
    assert (await star_poll(env.client, rotated)).status_code == 401
    r = await env.client.patch(
        f"{API}/cloud-printers/{printer['id']}",
        json={"status": "archived", "version": 1},
        headers=cs.h("owner"),
    )
    assert r.status_code == 409 and err(r) == "VERSION_CONFLICT"
    r = await env.client.patch(
        f"{API}/cloud-printers/{printer['id']}", json={"status": "archived", "version": r.json()["error"]["params"]
                                                       ["current_version"]}, headers=cs.h("owner"),
    )  # fmt: skip
    assert r.status_code == 200
    assert await audit_actions(env, cs, UUID(printer["id"])) == [
        "cloud_printer.created", "cloud_printer.secret_rotated", "cloud_printer.updated", "cloud_printer.archived",
    ]  # fmt: skip
    async with env.db.session_factory() as s, unscoped_transaction(s):
        assert await missing_security_definer_functions(s, SECURITY_DEFINER_FUNCTIONS_0028A_DEVICES) == []


async def test_b5_t04_print_job_idempotent_and_validated(env: Env) -> None:
    cs = await card_shop(env)
    printer = await create_printer(env.client, cs.shop)
    job_id = uuid7()
    r = await submit_job(env.client, cs.shop, printer, job_id=job_id)
    assert r.status_code == 201, r.text
    assert r.json() == {"id": str(job_id), "cloud_printer_id": printer["id"], "kind": "receipt",
                        "status": "queued", "result_code": None}  # fmt: skip
    # the same id and content (a retry with a new Idempotency-Key) → the stored job, no second row
    r = await submit_job(env.client, cs.shop, printer, job_id=job_id)
    assert r.status_code == 200 and r.json()["status"] == "queued"
    # the same id with another raster → VALIDATION_ERROR
    r = await submit_job(env.client, cs.shop, printer, job_id=job_id, body_raster=raster(fill=0x0F))
    assert (
        r.status_code == 422
        and r.json()["error"]["details"][0]["message_key"] == "validation.print_job_id_reused"
    )
    # raster length ≠ ceil(w/8)·h
    bad = raster() | {"height_dots": 4}
    r = await submit_job(env.client, cs.shop, printer, body_raster=bad)
    assert r.status_code == 422 and r.json()["error"]["details"][0]["field"] == "raster"
    # label needs labels.print (the cashier has none)
    r = await submit_job(env.client, cs.shop, printer, kind="label")
    assert r.status_code == 403
    # GET /print-jobs/{id} and the status probe of the adapter
    r = await env.client.get(f"{API}/print-jobs/{job_id}", headers=cs.h("cashier", key=None))
    assert r.status_code == 200 and r.json()["status"] == "queued"
    r = await env.client.get(
        f"{API}/cloud-printers/{printer['id']}/status", headers=cs.h("cashier", key=None)
    )
    assert r.status_code == 200 and r.json()["online"] is False and r.json()["pending"] == 1
    # an inactive printer takes no new job
    await env.client.patch(
        f"{API}/cloud-printers/{printer['id']}",
        json={"status": "disabled", "version": 1},
        headers=cs.h("owner"),
    )
    r = await submit_job(env.client, cs.shop, printer)
    assert (
        r.status_code == 422
        and r.json()["error"]["details"][0]["message_key"] == "validation.cloud_printer_inactive"
    )


async def test_b5_t04_star_cloudprnt_poll_get_delete(env: Env) -> None:
    cs = await card_shop(env)
    printer = await create_printer(env.client, cs.shop)
    # no job yet: jobReady false; the printer is now online
    r = await star_poll(env.client, printer)
    assert r.status_code == 200 and r.json() == {"jobReady": False}
    r = await env.client.get(
        f"{API}/cloud-printers/{printer['id']}/status", headers=cs.h("cashier", key=None)
    )
    assert r.json()["online"] is True and r.json()["last_status"] == "200%20OK"
    # wrong secret / no auth → 401 with a Basic challenge
    r = await env.client.post("/print/cloudprnt", json={}, headers=basic(printer, "wrong"))
    assert r.status_code == 401 and r.headers["www-authenticate"].startswith("Basic")
    assert (await env.client.post("/print/cloudprnt", json={})).status_code == 401
    # a 16×3 raster: first byte 0xF0 → 4 black + 4 white dots, second byte the same
    job_id = uuid7()
    assert (await submit_job(env.client, cs.shop, printer, job_id=job_id)).status_code == 201
    r = await star_poll(env.client, printer)
    assert r.json() == {"jobReady": True, "mediaTypes": ["image/png"], "jobToken": str(job_id)}
    r = await env.client.get(
        "/print/cloudprnt", params={"mac": "00:11:62:aa:bb:cc", "type": "image/png", "token": str(job_id)},
        headers=basic(printer),
    )  # fmt: skip
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    assert _png_rows(r.content, 16, 3) == [bytes([0x0F, 0x0F])] * 3  # PNG: 0 = black
    assert (await job_row(env, cs.tenant_id, job_id))["status"] == "printing"
    # while printing, the next poll offers nothing (one job at a time, never twice)
    assert (await star_poll(env.client, printer)).json() == {"jobReady": False}
    r = await env.client.delete(
        "/print/cloudprnt", params={"mac": "00:11:62:aa:bb:cc", "code": "200 OK", "token": str(job_id)},
        headers=basic(printer),
    )  # fmt: skip
    assert r.status_code == 200
    row = await job_row(env, cs.tenant_id, job_id)
    assert row["status"] == "done" and row["result_code"] == "200 OK" and row["purged"] is True
    r = await env.client.get(f"{API}/print-jobs/{job_id}", headers=cs.h("cashier", key=None))
    assert r.json()["status"] == "done"


async def test_b5_t04_star_download_timeout_requeues_and_error_fails(env: Env) -> None:
    cs = await card_shop(env)
    printer = await create_printer(env.client, cs.shop)
    first, second = uuid7(), uuid7()
    await submit_job(env.client, cs.shop, printer, job_id=first)
    await submit_job(env.client, cs.shop, printer, job_id=second)
    assert (await star_poll(env.client, printer)).json()["jobToken"] == str(first)  # oldest first
    await env.client.get(
        "/print/cloudprnt", params={"type": "image/png", "token": str(first)}, headers=basic(printer)
    )
    # 520 = download timeout → back to the queue
    await env.client.delete("/print/cloudprnt", params={"code": "520 Timeout", "token": str(first)},
                            headers=basic(printer))  # fmt: skip
    assert (await job_row(env, cs.tenant_id, first))["status"] == "queued"
    assert (await star_poll(env.client, printer)).json()["jobToken"] == str(first)
    await env.client.get("/print/cloudprnt", params={"type": "image/png"}, headers=basic(printer))
    # the GET-variant confirmation ("deleteMethod":"GET") with a printer error → failed
    await env.client.get(
        "/print/cloudprnt", params={"code": "410 Paper empty", "delete": ""}, headers=basic(printer)
    )
    row = await job_row(env, cs.tenant_id, first)
    assert row["status"] == "failed" and row["result_code"] == "410 Paper empty" and row["attempts"] == 2
    # unsupported media type → 404, job untouched
    r = await env.client.get("/print/cloudprnt", params={"type": "application/vnd.star.starprnt"},
                             headers=basic(printer))  # fmt: skip
    assert r.status_code == 404 and (await job_row(env, cs.tenant_id, second))["status"] == "queued"
    # a queued job past its expiry is not printed any more
    async with env.db.session_factory() as s, tenant_transaction(s, cs.tenant_id):
        await s.execute(text("UPDATE app.print_jobs SET expires_at = now() - interval '1 minute' WHERE id = :id"),
                        {"id": second})  # fmt: skip
    assert (await star_poll(env.client, printer)).json() == {"jobReady": False}
    assert (await job_row(env, cs.tenant_id, second))["result_code"] == "expired"


async def test_b5_t04_epson_server_direct_print(env: Env) -> None:
    cs = await card_shop(env)
    printer = await create_printer(env.client, cs.shop, protocol="epson_sdp", name="Epson-1")
    assert printer["poll_path"] == "/print/epson-sdp"
    # the Star route refuses an Epson printer (protocol bound to the credentials)
    assert (await star_poll(env.client, printer)).status_code == 401
    r = await sdp_post(env.client, printer, ConnectionType="GetRequest", ID="shop-1", Name="TM-m30III")
    assert r.status_code == 200 and r.text == ""
    a, b = uuid7(), uuid7()
    await submit_job(env.client, cs.shop, printer, job_id=a)
    await submit_job(env.client, cs.shop, printer, job_id=b, body_raster=raster(width=8, height=2, fill=0xFF))
    r = await sdp_post(env.client, printer, ConnectionType="GetRequest", ID="shop-1")
    assert r.headers["content-type"].startswith("text/xml")
    xml = r.text
    assert xml.startswith('<?xml version="1.0" encoding="utf-8"?><PrintRequestInfo Version="2.00">')
    assert f"<printjobid>{a}</printjobid>" in xml and f"<printjobid>{b}</printjobid>" in xml
    assert 'xmlns="http://www.epson-pos.com/schemas/2011/03/epos-print"' in xml
    assert (
        f'<image width="8" height="2" color="color_1" mode="mono">{base64.b64encode(b"\xff\xff").decode()}'
        in xml
    )
    # nothing is handed out twice while the batch is unanswered
    assert (await sdp_post(env.client, printer, ConnectionType="GetRequest")).text == ""
    response_file = (
        '<?xml version="1.0" encoding="utf-8"?><PrintResponseInfo Version="2.00">'
        f"<ePOSPrint><Parameter><devid>local_printer</devid><printjobid>{a}</printjobid></Parameter>"
        '<PrintResponse><response success="true" code="" status="251658262" battery="0"/></PrintResponse>'
        "</ePOSPrint></PrintResponseInfo>"
    )
    r = await sdp_post(env.client, printer, ConnectionType="SetResponse", ResponseFile=response_file)
    assert r.status_code == 200
    assert (await job_row(env, cs.tenant_id, a))["status"] == "done"
    row = await job_row(env, cs.tenant_id, b)  # handed out but not reported → failed, never re-sent
    assert row["status"] == "failed" and row["result_code"] == "no_result"
    # Version 1.00 (results in request order) and a printer error
    c = uuid7()
    await submit_job(env.client, cs.shop, printer, job_id=c)
    await sdp_post(env.client, printer, ConnectionType="GetRequest")
    v1 = '<PrintResponseInfo Version="1.00"><response success="false" code="EPTR_REC_EMPTY" status="0"/>' \
         "</PrintResponseInfo>"  # fmt: skip
    await sdp_post(env.client, printer, ConnectionType="SetResponse", ResponseFile=v1)
    row = await job_row(env, cs.tenant_id, c)
    assert row["status"] == "failed" and row["result_code"] == "EPTR_REC_EMPTY"


async def test_b5_t04_printer_cannot_reach_other_tenant(env: Env) -> None:
    a = await card_shop(env, "Printer A")
    b = await card_shop(env, "Printer B")
    pa = await create_printer(env.client, a.shop)
    pb = await create_printer(env.client, b.shop)
    job_b = uuid7()
    await submit_job(env.client, b.shop, pb, job_id=job_b)
    # printer A asks for B's job by token → nothing (RLS + printer check)
    r = await env.client.get(
        "/print/cloudprnt", params={"type": "image/png", "token": str(job_b)}, headers=basic(pa)
    )
    assert r.status_code == 404
    # B's printer id with A's secret is refused
    assert (
        await env.client.post("/print/cloudprnt", json={}, headers=basic(pb, pa["secret"]))
    ).status_code == 401
    # A's user cannot queue on B's printer
    r = await submit_job(env.client, a.shop, pb)
    assert r.status_code == 404
