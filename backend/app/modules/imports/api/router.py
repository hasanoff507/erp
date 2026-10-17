"""``/import-jobs`` (19 §6, US-M04-04). OpenAPI tag ``inventory`` (17 §11: M04).

``kind=products`` needs ``catalog.manage``; ``opening_stock`` needs ``stock.opening.manage``
(19 §6) — checked per kind (job endpoints: the job's kind). ``opening_debts`` (Bosqich 4) is refused
with ``VALIDATION_ERROR``.
"""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, Request, Response, UploadFile
from pydantic import BaseModel, ConfigDict

from app.core.auth.dependencies import auth_gateway, require_subscription_ok
from app.core.auth.principal import Principal
from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from app.core.permissions import BranchScope, current_branch_scope
from app.modules.imports.application.service import ImportService, check_kind, kind_permission

router = APIRouter(prefix="/import-jobs", tags=["inventory"])

Actor = Annotated[Principal, Depends(require_subscription_ok)]
Scope = Annotated[BranchScope, Depends(current_branch_scope)]


async def require_kind_permission(request: Request, actor: Principal, kind: str) -> None:
    """The import permission of ``kind`` (19 §6), same rules as ``require_permission``."""
    code = kind_permission(kind)
    if not actor.has_scope(code.split(".", 1)[0]):
        raise AppError(ErrorCode.PERMISSION_DENIED, params={"permission": code})
    if not await auth_gateway(request).permission_limits(actor, code):
        raise AppError(ErrorCode.PERMISSION_DENIED, params={"permission": code})


async def _job_permission(request: Request, actor: Principal, job_id: UUID) -> None:
    await require_kind_permission(request, actor, await import_service(request).kind_of(actor, job_id))


_CHUNK = 1024 * 1024


class ImportJobCreated(BaseModel):
    id: UUID
    kind: str
    status: str
    total_rows: int


class ImportJobAccepted(BaseModel):
    job_id: UUID
    status: str


class ImportJobOut(BaseModel):
    id: UUID
    kind: str
    status: str
    total_rows: int
    ok_rows: int
    error_rows: int
    result: dict[str, Any]
    created_at: str


class ImportErrorItem(BaseModel):
    row: int
    field: str
    code: str
    message: str


class ImportErrorPage(BaseModel):
    items: list[ImportErrorItem]
    next_cursor: str | None


class CommitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    skip_error_rows: bool = True


class EmptyBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


def import_service(request: Request) -> ImportService:
    service: ImportService | None = getattr(request.app.state, "imports", None)
    if service is None:
        raise RuntimeError("imports module is not configured (app.state.imports)")
    return service


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get(
    "/templates/{kind}",
    operation_id="inventory_get_import_template",
    response_class=Response,
    responses={200: {"content": {"text/csv": {}}}},
)
async def get_template(request: Request, kind: str, actor: Actor) -> Response:
    check_kind(kind)
    await require_kind_permission(request, actor, kind)
    body = ImportService.template(kind)
    return Response(
        content=body.encode("utf-8-sig"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{kind}.csv"'},
    )


async def _read_limited(upload: UploadFile, limit: int) -> bytes:
    chunks: list[bytes] = []
    size = 0
    while chunk := await upload.read(_CHUNK):
        size += len(chunk)
        if size > limit:
            raise AppError(ErrorCode.FILE_TOO_LARGE, params={"max_bytes": limit})
        chunks.append(chunk)
    return b"".join(chunks)


@router.post("", operation_id="inventory_create_import_job", response_model=ImportJobCreated, status_code=201)
async def create_import_job(
    request: Request,
    response: Response,
    actor: Actor,
    scope: Scope,
    kind: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
) -> dict[str, Any]:
    check_kind(kind)
    await require_kind_permission(request, actor, kind)
    service = import_service(request)
    content = await _read_limited(file, service.max_bytes)
    job = await service.upload(actor, scope, kind, file.filename, file.content_type, content, _ip(request))
    response.headers["Location"] = f"{request.url.path}/{job['id']}"
    return job


@router.post(
    "/{job_id}/validate",
    operation_id="inventory_validate_import_job",
    response_model=ImportJobAccepted,
    status_code=202,
)
async def validate_import_job(
    request: Request, job_id: UUID, actor: Actor, scope: Scope, body: EmptyBody | None = None
) -> dict[str, Any]:
    await _job_permission(request, actor, job_id)
    return await import_service(request).request_validate(actor, scope, job_id, _ip(request))


@router.get("/{job_id}", operation_id="inventory_get_import_job", response_model=ImportJobOut)
async def get_import_job(request: Request, job_id: UUID, actor: Actor) -> dict[str, Any]:
    await _job_permission(request, actor, job_id)
    return await import_service(request).get(actor, job_id)


@router.get(
    "/{job_id}/errors", operation_id="inventory_list_import_job_errors", response_model=ImportErrorPage
)
async def list_import_job_errors(
    request: Request,
    job_id: UUID,
    actor: Actor,
    cursor: Annotated[str | None, Query(max_length=64)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    await _job_permission(request, actor, job_id)
    return await import_service(request).errors(actor, job_id, cursor, limit)


@router.post(
    "/{job_id}/commit",
    operation_id="inventory_commit_import_job",
    response_model=ImportJobAccepted,
    status_code=202,
)
async def commit_import_job(
    request: Request, job_id: UUID, actor: Actor, scope: Scope, body: CommitRequest | None = None
) -> dict[str, Any]:
    await _job_permission(request, actor, job_id)
    skip = body.skip_error_rows if body else True
    return await import_service(request).request_commit(actor, scope, job_id, skip, _ip(request))
