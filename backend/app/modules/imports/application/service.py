"""Import jobs (19 §6, US-M04-04): ``upload → validate → commit``; validate/commit are SAQ jobs (202 + poll).

``kind=products``: new ``products`` + ``product_barcodes`` (+ missing categories,
``label_print_queue(reason='new')``) and the first prices as one posted ``price_changes``
document — all in ONE transaction. ``kind=opening_stock`` (Bosqich 2): one ``stock_openings``
document created and posted in the commit transaction (lots, balances, ``Dt inv_acct / Kt 0000``,
13 §2.21) in the default branch's warehouse. ``opening_debts`` (Bosqich 4) is refused.

The API flips the status (``validating``/``committing``) and enqueues the job in
the same transaction; the job locks the row ``FOR UPDATE`` first, so it waits
for that commit and simply exits if the request was rolled back.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC
from decimal import Decimal
from typing import Any, Final
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.audit import record_audit
from app.core.auth.principal import Principal
from app.core.db.base import uuid7
from app.core.db.session import tenant_transaction
from app.core.error_codes import ErrorCode
from app.core.errors import AppError, ErrorDetail
from app.core.idempotency import stage_response
from app.core.permissions import BranchScope
from app.modules.imports.application.parsing import (
    FileFormat,
    FileInvalidError,
    FileTooLargeError,
    Table,
    read_table,
)
from app.modules.imports.application.ports import (
    CatalogImportPort,
    FileStoragePort,
    ImportJob,
    ImportJobRepository,
    InitialPricesPort,
    JobEnqueuer,
    OpeningStockPort,
)
from app.modules.imports.domain.opening_stock import REQUIRED_COLUMNS as OPENING_REQUIRED
from app.modules.imports.domain.opening_stock import (
    OpeningStockRow,
    opening_template_csv,
    parse_opening_row,
)
from app.modules.imports.domain.products import (
    ALL_KINDS,
    DEFAULT_MARKING_GROUP,
    REQUIRED_COLUMNS,
    SUPPORTED_KINDS,
    ProductRow,
    RowError,
    parse_product_row,
    template_csv,
)

log = structlog.get_logger(__name__)

VALIDATE_JOB: Final = "import_jobs_validate"
COMMIT_JOB: Final = "import_jobs_commit"
JOB_TIMEOUT_S: Final = 900
XLSX_TYPE: Final = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
CSV_TYPES: Final = frozenset({"text/csv", "application/csv", "text/plain", "application/vnd.ms-excel"})


@dataclass(frozen=True, slots=True)
class ImportLimits:
    max_bytes: int
    max_rows: int


def _invalid(field: str, key: str) -> AppError:
    return AppError(ErrorCode.VALIDATION_ERROR, details=[ErrorDetail(field=field, message_key=key)])


def check_kind(kind: str) -> None:
    if kind not in ALL_KINDS:
        raise _invalid("kind", "validation.enum")
    if kind not in SUPPORTED_KINDS:
        # opening_debts — Bosqich 4 (debts)
        raise _invalid("kind", "validation.import_kind_not_supported")


def kind_permission(kind: str) -> str:
    """19 §6: ``products`` → ``catalog.manage``; opening balances → ``stock.opening.manage``."""
    return "catalog.manage" if kind == "products" else "stock.opening.manage"


def _required(kind: str) -> frozenset[str]:
    return OPENING_REQUIRED if kind == "opening_stock" else REQUIRED_COLUMNS


def detect_format(filename: str | None, content_type: str | None) -> tuple[FileFormat, str]:
    name = (filename or "").lower()
    ctype = (content_type or "").split(";", 1)[0].strip().lower()
    if name.endswith(".xlsx") or (not name and ctype == XLSX_TYPE):
        return "xlsx", XLSX_TYPE
    if name.endswith(".csv") or (not name and ctype in CSV_TYPES):
        return "csv", "text/csv"
    raise AppError(ErrorCode.UNSUPPORTED_FILE_TYPE, params={"allowed": ["csv", "xlsx"]})


def _ts(job: ImportJob) -> str:
    return job.created_at.astimezone(UTC).isoformat().replace("+00:00", "Z")


def job_json(job: ImportJob) -> dict[str, Any]:
    return {
        "id": str(job.id),
        "kind": job.kind,
        "status": job.status,
        "total_rows": job.total_rows,
        "ok_rows": job.ok_rows,
        "error_rows": job.total_rows - job.ok_rows,
        "result": job.result,
        "created_at": _ts(job),
    }


class ImportService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        repo: ImportJobRepository,
        storage: FileStoragePort,
        queue: JobEnqueuer,
        catalog: CatalogImportPort,
        prices: InitialPricesPort,
        limits: ImportLimits,
        openings: OpeningStockPort | None = None,
    ) -> None:
        self._sf = session_factory
        self._repo = repo
        self._storage = storage
        self._queue = queue
        self._catalog = catalog
        self._prices = prices
        self._limits = limits
        self._openings = openings

    @property
    def max_bytes(self) -> int:
        return self._limits.max_bytes

    # --- API side ---------------------------------------------------------------------------------
    @staticmethod
    def template(kind: str) -> str:
        check_kind(kind)
        return opening_template_csv() if kind == "opening_stock" else template_csv(kind)

    async def upload(
        self,
        actor: Principal,
        scope: BranchScope,
        kind: str,
        filename: str | None,
        content_type: str | None,
        content: bytes,
        ip: str | None,
    ) -> dict[str, Any]:
        check_kind(kind)
        fmt, stored_type = detect_format(filename, content_type)
        if len(content) > self._limits.max_bytes:
            raise AppError(ErrorCode.FILE_TOO_LARGE, params={"max_bytes": self._limits.max_bytes})
        await self._parse(content, fmt, kind)  # structure/encoding/row limit (19 §6 errors at upload)
        if kind == "opening_stock":
            async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
                await self._opening_port().check_scope(s, scope)
        attachment_id, job_id = uuid7(), uuid7()
        key = f"tenants/{actor.tenant_id}/imports/{attachment_id}.{fmt}"
        await self._storage.put(key, content, stored_type)
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            await self._repo.insert_attachment(
                s,
                {
                    "id": attachment_id,
                    "tenant_id": actor.tenant_id,
                    "s3_key": key,
                    "content_type": stored_type,
                    "original_name": (filename or "")[:255] or None,
                    "sha256": hashlib.sha256(content).hexdigest(),
                    "kind": "import",
                    "size_bytes": len(content),
                    "uploaded_by": actor.user_id,
                },
            )
            await self._repo.insert_job(
                s,
                {
                    "id": job_id,
                    "tenant_id": actor.tenant_id,
                    "kind": kind,
                    "attachment_id": attachment_id,
                    "created_by": actor.user_id,
                },
            )
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="import_job_uploaded",
                entity="import_jobs",
                entity_id=job_id,
                after={"kind": kind, "file": filename, "size_bytes": len(content)},
                ip=ip,
            )
            body = {"id": str(job_id), "kind": kind, "status": "uploaded", "total_rows": 0}
            stage_response(body, 201)
        return body

    async def kind_of(self, actor: Principal, job_id: UUID) -> str:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            return (await self._job(s, job_id)).kind

    async def get(self, actor: Principal, job_id: UUID) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            job = await self._job(s, job_id)
        return job_json(job)

    async def errors(self, actor: Principal, job_id: UUID, cursor: str | None, limit: int) -> dict[str, Any]:
        start = 0
        if cursor:
            try:
                start = int(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode())
            except ValueError as exc:
                raise _invalid("cursor", "validation.cursor_invalid") from exc
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            job = await self._job(s, job_id)
        page = job.errors[start : start + limit]
        end = start + len(page)
        nxt = (
            base64.urlsafe_b64encode(str(end).encode()).decode().rstrip("=")
            if end < len(job.errors)
            else None
        )
        return {"items": page, "next_cursor": nxt}

    async def request_validate(
        self, actor: Principal, scope: BranchScope, job_id: UUID, ip: str | None
    ) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            job = await self._job(s, job_id, lock=True)
            if job.kind == "opening_stock":
                await self._opening_port().check_scope(s, scope)
            if job.status in ("committed", "committing"):
                raise AppError(ErrorCode.IMPORT_JOB_ALREADY_COMMITTED)
            if job.status == "validating":
                raise AppError(
                    ErrorCode.DOC_INVALID_STATE,
                    params={"expected_status": "uploaded", "actual_status": job.status},
                )
            await self._repo.set_status(s, job_id, "validating")
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="import_job_validation_requested",
                entity="import_jobs",
                entity_id=job_id,
                ip=ip,
            )
            body = {"job_id": str(job_id), "status": "validating"}
            stage_response(body, 202)
            # the job locks the row FOR UPDATE, so it starts after this COMMIT (or exits on rollback)
            await self._queue.enqueue(
                VALIDATE_JOB, actor.tenant_id, job_id=str(job_id), timeout=JOB_TIMEOUT_S
            )
        return body

    async def request_commit(
        self, actor: Principal, scope: BranchScope, job_id: UUID, skip_error_rows: bool, ip: str | None
    ) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            job = await self._job(s, job_id, lock=True)
            if job.kind == "opening_stock":
                await self._opening_port().check_scope(s, scope)
            if job.status in ("committed", "committing"):
                raise AppError(ErrorCode.IMPORT_JOB_ALREADY_COMMITTED)
            if job.status != "validated":
                raise AppError(ErrorCode.IMPORT_JOB_NOT_VALIDATED, params={"status": job.status})
            if not skip_error_rows and job.ok_rows < job.total_rows:
                raise _invalid("skip_error_rows", "validation.import_has_error_rows")
            await self._repo.set_status(s, job_id, "committing")
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="import_job_commit_requested",
                entity="import_jobs",
                entity_id=job_id,
                after={"skip_error_rows": skip_error_rows},
                ip=ip,
            )
            body = {"job_id": str(job_id), "status": "committing"}
            stage_response(body, 202)
            await self._queue.enqueue(
                COMMIT_JOB,
                actor.tenant_id,
                job_id=str(job_id),
                user_id=str(actor.user_id),
                skip_error_rows=skip_error_rows,
                branch_ids=[str(b) for b in scope.allowed],  # [] = unrestricted (BranchScope)
                timeout=JOB_TIMEOUT_S,
            )
        return body

    # --- worker side ------------------------------------------------------------------------------
    async def run_validate(self, tenant_id: UUID, job_id: UUID) -> dict[str, Any]:
        try:
            async with self._sf() as s, tenant_transaction(s, tenant_id):
                job = await self._repo.get_job(s, job_id, lock=True)
                if job is None or job.status != "validating":
                    return {"skipped": True}
                rows, errors, total = await self._check_any(s, job)
                status = "validated" if rows else "failed"
                await self._repo.save_validation(
                    s,
                    job_id,
                    status=status,
                    total_rows=total,
                    ok_rows=len(rows),
                    errors=[e.as_json() for e in errors],
                )
                return {"status": status, "total_rows": total, "ok_rows": len(rows)}
        except Exception:
            log.exception("import_validate_failed", job_id=str(job_id))
            await self._fail(tenant_id, job_id, "INTERNAL_ERROR")
            raise

    async def run_commit(
        self, tenant_id: UUID, job_id: UUID, user_id: UUID, skip_error_rows: bool, scope: BranchScope
    ) -> dict[str, Any]:
        """``scope`` — the committing actor's branch scope (an ``opening_stock`` import posts into the
        default branch's warehouse only when the scope covers it)."""
        try:
            async with self._sf() as s, tenant_transaction(s, tenant_id, user_id=user_id):
                job = await self._repo.get_job(s, job_id, lock=True)
                if job is None or job.status != "committing":
                    return {"skipped": True}
                # re-checked against the catalog as it is now (barcodes may have been added since validate)
                rows, errors, total = await self._check_any(s, job)
                if errors and not skip_error_rows:
                    await self._repo.save_commit(
                        s,
                        job_id,
                        status="failed",
                        ok_rows=len(rows),
                        errors=[e.as_json() for e in errors],
                        result={},
                    )
                    return {"status": "failed"}
                if job.kind == "opening_stock":
                    result = await self._create_opening(s, tenant_id, user_id, job, rows, scope)
                else:
                    result = await self._create_products(s, tenant_id, user_id, job, rows)
                await self._repo.save_commit(
                    s,
                    job_id,
                    status="committed",
                    ok_rows=len(rows),
                    errors=[e.as_json() for e in errors],
                    result=result,
                )
                await record_audit(
                    s,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    action="import_job_committed",
                    entity="import_jobs",
                    entity_id=job_id,
                    after={"kind": job.kind, "total_rows": total, "ok_rows": len(rows), **result},
                )
                return {"status": "committed", **result}
        except AppError as exc:  # a business refusal (e.g. go_live_date missing, PERIOD_CLOSED)
            log.info("import_commit_refused", job_id=str(job_id), code=exc.code.value)
            message = exc.details[0].message_key if exc.details else exc.message_key
            await self._fail(tenant_id, job_id, exc.code.value, message)
            return {"status": "failed", "code": exc.code.value}
        except Exception:
            log.exception("import_commit_failed", job_id=str(job_id))
            await self._fail(tenant_id, job_id, "INTERNAL_ERROR")
            raise

    # --- helpers ----------------------------------------------------------------------------------
    def _opening_port(self) -> OpeningStockPort:
        assert self._openings is not None, "opening_stock import needs the inventory port"
        return self._openings

    async def _job(self, s: AsyncSession, job_id: UUID, *, lock: bool = False) -> ImportJob:
        job = await self._repo.get_job(s, job_id, lock=lock)
        if job is None:
            raise AppError(ErrorCode.NOT_FOUND, params={"resource": "import_job"})
        return job

    async def _parse(self, content: bytes, fmt: FileFormat, kind: str = "products") -> Table:
        try:
            return await asyncio.to_thread(
                read_table, content, fmt, required=_required(kind), max_rows=self._limits.max_rows
            )
        except FileTooLargeError as exc:  # rows (params.max_rows), unpacked size or zip ratio
            raise AppError(ErrorCode.FILE_TOO_LARGE, params=exc.params) from exc
        except FileInvalidError as exc:
            raise AppError(ErrorCode.IMPORT_FILE_INVALID, params={"reason": str(exc)}) from exc

    async def _check_any(self, s: AsyncSession, job: ImportJob) -> tuple[list[Any], list[RowError], int]:
        if job.kind == "opening_stock":
            opening = await self._check_opening_rows(s, job)
            return list(opening[0]), opening[1], opening[2]
        products = await self._check_rows(s, job)
        return list(products[0]), products[1], products[2]

    async def _table(self, job: ImportJob) -> Table | RowError:
        content = await self._storage.get(job.s3_key)
        fmt: FileFormat = "xlsx" if job.content_type == XLSX_TYPE else "csv"
        try:
            return await self._parse(content, fmt, job.kind)
        except AppError as exc:
            return RowError(0, "file", exc.code.value, exc.message_key)

    async def _check_opening_rows(
        self, s: AsyncSession, job: ImportJob
    ) -> tuple[list[OpeningStockRow], list[RowError], int]:
        table = await self._table(job)
        if isinstance(table, RowError):
            return [], [table], 0
        assert self._openings is not None, "opening_stock import needs the inventory port"
        parsed: list[OpeningStockRow] = []
        errors: list[RowError] = []
        for line_no, raw in table.rows:
            row, row_errors = parse_opening_row(line_no, raw)
            errors.extend(row_errors)
            if row is not None:
                parsed.append(row)
        known = await self._openings.barcode_products(s, [r.barcode for r in parsed])
        ok: list[OpeningStockRow] = []
        for row in parsed:
            if row.barcode not in known:
                errors.append(
                    RowError(
                        row.row, "barcode", "BARCODE_NOT_IN_CATALOG", "validation.barcode_not_in_catalog"
                    )
                )
                continue
            ok.append(row)
        errors.sort(key=lambda e: e.row)
        return ok, errors, len(table.rows)

    async def _create_opening(
        self,
        s: AsyncSession,
        tenant_id: UUID,
        user_id: UUID,
        job: ImportJob,
        rows: Sequence[OpeningStockRow],
        scope: BranchScope,
    ) -> dict[str, Any]:
        openings = self._opening_port()
        products = await openings.barcode_products(s, [r.barcode for r in rows])
        doc_id = await openings.post_opening(
            s,
            tenant_id,
            user_id,
            [(products[r.barcode], r.qty, r.unit_cost, r.expiry_date) for r in rows],
            comment=f"Import {job.id}",
            scope=scope,
        )
        return {"created_doc_ids": [str(doc_id)], "line_count": len(rows)}

    async def _check_rows(
        self, s: AsyncSession, job: ImportJob
    ) -> tuple[list[ProductRow], list[RowError], int]:
        table = await self._table(job)
        if isinstance(table, RowError):
            return [], [table], 0
        units = await self._catalog.unit_codes(s)
        parsed: list[ProductRow] = []
        errors: list[RowError] = []
        for line_no, raw in table.rows:
            row, row_errors = parse_product_row(line_no, raw, units)
            errors.extend(row_errors)
            if row is not None:
                parsed.append(row)
        taken = await self._catalog.taken_barcodes(s, [r.barcode for r in parsed if r.barcode])
        seen: set[str] = set()
        ok: list[ProductRow] = []
        for row in parsed:
            if row.barcode is not None and (row.barcode in taken or row.barcode in seen):
                errors.append(
                    RowError(row.row, "barcode", "BARCODE_DUPLICATE", "validation.barcode_duplicate")
                )
                continue
            if row.barcode is not None:
                seen.add(row.barcode)
            ok.append(row)
        errors.sort(key=lambda e: e.row)
        return ok, errors, len(table.rows)

    async def _create_products(
        self, s: AsyncSession, tenant_id: UUID, user_id: UUID, job: ImportJob, rows: Sequence[ProductRow]
    ) -> dict[str, Any]:
        categories = await self._catalog.active_categories_by_name(s)
        for row in rows:
            key = row.category.lower() if row.category else None
            if key is not None and key not in categories:
                categories[key] = uuid7()
                await self._catalog.insert_category(s, tenant_id, categories[key], row.category or "", None)
        if any(r.is_marked for r in rows) and not await self._catalog.marking_group_exists(
            s, DEFAULT_MARKING_GROUP
        ):
            raise RuntimeError("platform.marking_product_groups 'general' is not seeded")
        ids = [uuid7() for _ in rows]
        await self._catalog.insert_products(
            s,
            tenant_id,
            [
                {
                    "id": pid,
                    "name": r.name,
                    "name_ru": r.name_ru,
                    "category_id": categories[r.category.lower()] if r.category else None,
                    "unit_code": r.unit_code,
                    "mxik_code": r.mxik_code,
                    "package_code": None,
                    "vat_rate": r.vat_rate,
                    "vat_exemption_code": None,
                    "is_marked": r.is_marked,
                    "marking_group_code": DEFAULT_MARKING_GROUP if r.is_marked else None,
                    "is_weighed": False,
                    "min_stock": None,
                }
                for pid, r in zip(ids, rows, strict=True)
            ],
        )
        await self._catalog.insert_barcodes(
            s,
            tenant_id,
            [
                {"product_id": pid, "barcode": r.barcode}
                for pid, r in zip(ids, rows, strict=True)
                if r.barcode
            ],
        )
        await self._catalog.queue_labels(s, tenant_id, ids, "new")
        prices: list[tuple[UUID, Decimal]] = [
            (pid, r.price) for pid, r in zip(ids, rows, strict=True) if r.price is not None
        ]
        doc_id = await self._prices.post_initial_prices(
            s, tenant_id, user_id, prices, comment=f"Import {job.id}"
        )
        return {
            "created_doc_ids": [str(doc_id)] if doc_id else [],
            "created_product_count": len(ids),
        }

    async def _fail(
        self, tenant_id: UUID, job_id: UUID, code: str, message: str = "errors.internal_error"
    ) -> None:
        try:
            async with self._sf() as s, tenant_transaction(s, tenant_id):
                job = await self._repo.get_job(s, job_id, lock=True)
                if job is not None and job.status in ("validating", "committing"):
                    await self._repo.save_validation(
                        s,
                        job_id,
                        status="failed",
                        total_rows=job.total_rows,
                        ok_rows=job.ok_rows,
                        errors=[RowError(0, "file", code, message).as_json()],
                    )
        except Exception:  # pragma: no cover - best effort
            log.exception("import_fail_mark_failed", job_id=str(job_id))
