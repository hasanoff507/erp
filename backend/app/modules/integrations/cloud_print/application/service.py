"""Cloud printers and the print-job queue (24 §6.1, qaror #21; 20 #40m–#40s).

* :class:`CloudPrinterService` — BO-14 / POS-16 registry: ``GET/POST /cloud-printers``,
  ``PATCH /cloud-printers/{id}``, ``POST /cloud-printers/{id}/secret`` (rotate),
  ``GET /cloud-printers/{id}/status``.
  The per-printer secret is generated here, returned once and stored only as SHA-256. Audit
  ``cloud_printer.created|updated|archived|secret_rotated`` (15 §6.1).
* :class:`PrintJobService` — ``POST /print-jobs`` (the web ``CloudPrintAdapter`` queue; idempotent by the
  client ``id``: the same id with the same printer and raster returns the stored job, a different body →
  ``VALIDATION_ERROR``) and ``GET /print-jobs/{id}``.
* :class:`PrinterPollService` — the printer side (``/print/cloudprnt``, ``/print/epson-sdp``): authenticated
  by printer id + secret (HTTP Basic), tenant resolved by ``app.cloud_printer_by_secret``; a job is handed out
  once (``queued → printing``) and closed by the printer's confirmation (``done``/``failed``; Star ``520`` →
  back to ``queued``). A job never re-prints by itself — a job left in ``printing`` stays there.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Final
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.audit import record_audit
from app.core.auth.principal import Principal
from app.core.db.base import uuid7
from app.core.db.session import tenant_transaction, unscoped_transaction
from app.core.error_codes import ErrorCode
from app.core.errors import AppError, ErrorDetail
from app.core.idempotency import stage_response
from app.core.permissions import BranchScope
from app.modules.integrations.cloud_print.application.ports import (
    CloudPrintRepository,
    JobRow,
    PrinterAuth,
    PrinterFilter,
    PrinterRow,
)
from app.modules.integrations.cloud_print.domain.model import (
    RasterError,
    SdpResponseError,
    decode_raster,
    epos_print_request,
    new_secret,
    parse_sdp_response,
    raster_sha256,
    raster_to_png,
    secret_hash,
    star_delete_outcome,
    star_poll_response,
)

ENTITY: Final = "cloud_printers"
POLL_PATHS: Final[Mapping[str, str]] = {"star_cloudprnt": "/print/cloudprnt", "epson_sdp": "/print/epson-sdp"}
EDITABLE: Final = ("name", "model", "status")
SDP_JOBS_PER_POLL: Final = 5


def invalid(field_name: str, key: str) -> AppError:
    return AppError(ErrorCode.VALIDATION_ERROR, details=[ErrorDetail(field=field_name, message_key=key)])


def _iso(value: datetime | None) -> str | None:
    return None if value is None else value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def printer_json(p: PrinterRow) -> dict[str, Any]:
    return {
        "id": str(p.id), "branch_id": str(p.branch_id), "name": p.name, "protocol": p.protocol,
        "model": p.model, "status": p.status, "poll_path": POLL_PATHS[p.protocol],
        "printer_mac": p.printer_mac,
        "last_poll_at": _iso(p.last_poll_at), "last_status": p.last_status, "online": p.online,
        "version": p.version,
    }  # fmt: skip


def job_json(j: JobRow) -> dict[str, Any]:
    return {
        "id": str(j.id), "cloud_printer_id": str(j.cloud_printer_id), "kind": j.kind, "status": j.status,
        "result_code": j.result_code,
    }  # fmt: skip


def _in_scope(scope: BranchScope, branch_id: UUID) -> bool:
    return scope.unrestricted or branch_id in scope.allowed


@dataclass(frozen=True, slots=True)
class PrinterPatch:
    version: int
    fields: Mapping[str, Any]


class CloudPrinterService:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession], repo: CloudPrintRepository) -> None:
        self._sf = session_factory
        self._repo = repo

    async def list_page(
        self, actor: Principal, scope: BranchScope, flt: PrinterFilter, page: int, size: int
    ) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            rows, total = await self._repo.list_printers(s, flt, page, size)
        return {"items": [printer_json(p) for p in rows], "total": total, "page": page, "size": size}

    async def get_status(self, actor: Principal, scope: BranchScope, printer_id: UUID) -> dict[str, Any]:
        """``CloudPrintApi.status(cloud_id)`` → ``{online, last_poll_at, pending}``."""
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            p = await self._repo.printer(s, printer_id)
            if p is None or not _in_scope(scope, p.branch_id):
                raise AppError(ErrorCode.NOT_FOUND, params={"resource": "cloud_printer"})
            pending = await self._repo.queued_count(s, printer_id)
        return {
            "id": str(p.id), "online": p.online and p.status == "active", "status": p.status,
            "last_poll_at": _iso(p.last_poll_at), "last_status": p.last_status, "pending": pending,
        }  # fmt: skip

    async def create(
        self, actor: Principal, scope: BranchScope, values: Mapping[str, Any], ip: str | None
    ) -> dict[str, Any]:
        printer_id = uuid7()
        secret = new_secret()
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            branch_id: UUID = values["branch_id"]
            if not _in_scope(scope, branch_id):
                raise AppError(ErrorCode.BRANCH_SCOPE_DENIED)
            await self._repo.insert_printer(
                s,
                {
                    "id": printer_id, "tenant_id": actor.tenant_id, "branch_id": branch_id,
                    "name": values["name"], "protocol": values["protocol"], "model": values.get("model"),
                    "secret_hash": secret_hash(secret), "created_by": actor.user_id,
                },
            )  # fmt: skip
            created = await self._repo.printer(s, printer_id)
            assert created is not None
            body = printer_json(created)
            await record_audit(
                s, tenant_id=actor.tenant_id, user_id=actor.user_id, action="cloud_printer.created",
                entity=ENTITY, entity_id=printer_id, ip=ip, after=body,
            )  # fmt: skip
            response = body | {"secret": secret}
            stage_response(response, 201)
        return response

    async def update(
        self, actor: Principal, scope: BranchScope, printer_id: UUID, patch: PrinterPatch, ip: str | None
    ) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            current = await self._load(s, scope, printer_id)
            if current.version != patch.version:
                raise AppError(ErrorCode.VERSION_CONFLICT, params={"current_version": current.version})
            if current.status == "archived":
                raise invalid("status", "validation.cloud_printer_archived")
            changes = {k: v for k, v in patch.fields.items() if k in EDITABLE}
            if changes:
                await self._repo.update_printer(s, printer_id, changes)
            updated = await self._repo.printer(s, printer_id)
            assert updated is not None
            body = printer_json(updated)
            action = "cloud_printer.archived" if updated.status == "archived" else "cloud_printer.updated"
            await record_audit(
                s, tenant_id=actor.tenant_id, user_id=actor.user_id, action=action, entity=ENTITY,
                entity_id=printer_id, ip=ip, before={k: printer_json(current)[k] for k in changes},
                after={k: body[k] for k in changes},
            )  # fmt: skip
            stage_response(body)
        return body

    async def rotate_secret(
        self, actor: Principal, scope: BranchScope, printer_id: UUID, ip: str | None
    ) -> dict[str, Any]:
        secret = new_secret()
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            current = await self._load(s, scope, printer_id)
            if current.status == "archived":
                raise invalid("status", "validation.cloud_printer_archived")
            await self._repo.update_printer(s, printer_id, {"secret_hash": secret_hash(secret)})
            updated = await self._repo.printer(s, printer_id)
            assert updated is not None
            await record_audit(
                s, tenant_id=actor.tenant_id, user_id=actor.user_id, action="cloud_printer.secret_rotated",
                entity=ENTITY, entity_id=printer_id, ip=ip,
            )  # fmt: skip
            response = printer_json(updated) | {"secret": secret}
            stage_response(response)
        return response

    async def _load(self, s: AsyncSession, scope: BranchScope, printer_id: UUID) -> PrinterRow:
        current = await self._repo.printer(s, printer_id, lock=True)
        if current is None or not _in_scope(scope, current.branch_id):
            raise AppError(ErrorCode.NOT_FOUND, params={"resource": "cloud_printer"})
        return current


@dataclass(frozen=True, slots=True)
class JobInput:
    id: UUID
    cloud_printer_id: UUID
    kind: str
    width_dots: int
    height_dots: int
    data_base64: str


class PrintJobService:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession], repo: CloudPrintRepository) -> None:
        self._sf = session_factory
        self._repo = repo

    async def submit(self, actor: Principal, scope: BranchScope, job: JobInput) -> tuple[dict[str, Any], int]:
        try:
            data = decode_raster(job.width_dots, job.height_dots, job.data_base64)
        except RasterError:
            raise invalid("raster", "validation.print_raster_invalid") from None
        digest = raster_sha256(data)
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            existing = await self._repo.job(s, job.id)
            if existing is not None:
                same = (
                    existing.cloud_printer_id == job.cloud_printer_id
                    and existing.kind == job.kind
                    and existing.data_sha256 == digest
                )
                if not same:
                    raise invalid("id", "validation.print_job_id_reused")
                body = job_json(existing)
                stage_response(body, 200)
                return body, 200
            printer = await self._repo.printer(s, job.cloud_printer_id)
            if printer is None or not _in_scope(scope, printer.branch_id):
                raise AppError(ErrorCode.NOT_FOUND, params={"resource": "cloud_printer"})
            if scope.current is not None and printer.branch_id != scope.current:
                raise invalid("cloud_printer_id", "validation.cloud_printer_other_branch")
            if printer.status != "active":
                raise invalid("cloud_printer_id", "validation.cloud_printer_inactive")
            await self._repo.insert_job(
                s,
                {
                    "id": job.id, "tenant_id": actor.tenant_id, "branch_id": printer.branch_id,
                    "cloud_printer_id": printer.id, "kind": job.kind, "width_dots": job.width_dots,
                    "height_dots": job.height_dots, "data": data, "data_sha256": digest,
                    "device_id": actor.device_id, "created_by": actor.user_id,
                },
            )  # fmt: skip
            created = await self._repo.job(s, job.id)
            assert created is not None
            body = job_json(created)
            stage_response(body, 201)
        return body, 201

    async def get(self, actor: Principal, scope: BranchScope, job_id: UUID) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            job = await self._repo.job(s, job_id)
            if job is None or not _in_scope(scope, job.branch_id):
                raise AppError(ErrorCode.NOT_FOUND, params={"resource": "print_job"})
        return job_json(job)


@dataclass(frozen=True, slots=True)
class StarJob:
    content_type: str
    body: bytes


class PrinterAuthError(Exception):
    """Unknown printer, wrong secret or inactive printer → 401 (no detail)."""


class PrinterPollService:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession], repo: CloudPrintRepository) -> None:
        self._sf = session_factory
        self._repo = repo

    async def authenticate(self, printer_id: UUID, secret: str, protocol: str) -> PrinterAuth:
        async with self._sf() as s, unscoped_transaction(s):
            found = await self._repo.printer_by_secret(s, printer_id, secret_hash(secret))
        if found is None or found.protocol != protocol:
            raise PrinterAuthError
        return found

    # --- Star CloudPRNT -----------------------------------------------------------------------------
    async def star_poll(self, auth: PrinterAuth, status: Mapping[str, Any]) -> dict[str, object]:
        mac = status.get("printerMAC")
        code = status.get("statusCode")
        async with self._sf() as s, tenant_transaction(s, auth.tenant_id):
            await self._repo.touch_poll(
                s, auth.printer_id, mac=None if not isinstance(mac, str) else mac[:64],
                status=None if not isinstance(code, str) else code[:200],
            )  # fmt: skip
            await self._repo.expire_jobs(s, auth.printer_id)
            printing = await self._repo.printing_jobs(s, auth.printer_id)
            if printing:  # one job at a time — wait for its DELETE
                return star_poll_response(None)
            queued = await self._repo.next_queued(s, auth.printer_id, 1)
        return star_poll_response(str(queued[0].id) if queued else None)

    async def star_job(self, auth: PrinterAuth, token: str | None, media_type: str | None) -> StarJob | None:
        if media_type not in (None, "", "image/png"):
            return None
        async with self._sf() as s, tenant_transaction(s, auth.tenant_id):
            job = await self._pick(s, auth, token)
            if job is None or job.data is None:
                return None
            await self._repo.mark_printing(s, job.id)
        return StarJob("image/png", raster_to_png(job.width_dots, job.height_dots, job.data))

    async def star_confirm(self, auth: PrinterAuth, token: str | None, code: str | None) -> bool:
        outcome = star_delete_outcome(code)
        async with self._sf() as s, tenant_transaction(s, auth.tenant_id):
            job = await self._pick(s, auth, token, printing_only=True)
            if job is None:
                return False
            if outcome.retry:
                await self._repo.requeue(s, job.id, outcome.code)
            else:
                await self._repo.finish_job(
                    s, job.id, status="done" if outcome.printed else "failed", code=outcome.code
                )
        return True

    async def _pick(
        self, s: AsyncSession, auth: PrinterAuth, token: str | None, *, printing_only: bool = False
    ) -> JobRow | None:
        if token:
            try:
                job_id = UUID(token)
            except ValueError:
                return None
            job = await self._repo.job(s, job_id, lock=True)
            if job is None or job.cloud_printer_id != auth.printer_id:
                return None
            allowed = ("printing",) if printing_only else ("queued", "printing")
            return job if job.status in allowed else None
        printing = await self._repo.printing_jobs(s, auth.printer_id)
        if printing:
            return printing[0]
        if printing_only:
            return None
        queued = await self._repo.next_queued(s, auth.printer_id, 1)
        return queued[0] if queued else None

    # --- Epson Server Direct Print ------------------------------------------------------------------
    async def sdp_get_request(self, auth: PrinterAuth) -> str | None:
        """``ConnectionType=GetRequest`` → ``PrintRequestInfo`` with queued jobs (``None`` — empty body)."""
        async with self._sf() as s, tenant_transaction(s, auth.tenant_id):
            await self._repo.touch_poll(s, auth.printer_id, mac=None, status=None)
            await self._repo.expire_jobs(s, auth.printer_id)
            if await self._repo.printing_jobs(s, auth.printer_id):
                return None  # previous batch not answered yet — never hand a job out twice
            jobs = [j for j in await self._repo.next_queued(s, auth.printer_id, SDP_JOBS_PER_POLL) if j.data]
            for job in jobs:
                await self._repo.mark_printing(s, job.id)
        if not jobs:
            return None
        return epos_print_request([(str(j.id), j.width_dots, j.height_dots, j.data or b"") for j in jobs])

    async def sdp_set_response(self, auth: PrinterAuth, response_file: str) -> int:
        """``ConnectionType=SetResponse``: close the jobs of the last batch; returns how many were closed."""
        try:
            results = parse_sdp_response(response_file)
        except SdpResponseError:
            results = []
        closed = 0
        async with self._sf() as s, tenant_transaction(s, auth.tenant_id):
            printing = await self._repo.printing_jobs(s, auth.printer_id)
            by_id = {str(j.id): j for j in printing}
            for index, result in enumerate(results):
                if result.printjobid is not None:
                    job = by_id.get(result.printjobid)
                else:  # Version 1.00: in request order
                    job = printing[index] if index < len(printing) else None
                if job is None:
                    continue
                await self._repo.finish_job(
                    s, job.id, status="done" if result.success else "failed", code=result.code or None
                )
                closed += 1
                by_id.pop(str(job.id), None)
            for job in by_id.values():  # handed out in the last batch but not reported — never re-sent
                await self._repo.finish_job(s, job.id, status="failed", code="no_result")
            last = results[-1].code if results else "response_unreadable"
            await self._repo.touch_poll(s, auth.printer_id, mac=None, status=last[:200] if last else None)
        return closed
