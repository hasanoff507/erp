"""Attachments — file upload and download (17 §12). Tag ``attachments``.

``POST /attachments`` (multipart ``file`` + ``kind``, ``Idempotency-Key``) → ``201 {id, url, content_type,
size_bytes}``; ``GET /attachments/{id}`` → ``{id, url, content_type, original_name, size_bytes, kind}`` —
``url`` is a 15-minute signed link to ``GET /attachments/{id}/content`` (no bearer needed, the signature
carries tenant/id/expiry). Rights: the ``kind``'s module permission (``expense_receipt`` →
``expenses.create`` …), for reading as well; a bank statement only ``bank_settlements.manage`` (SEC-02).
"""

from __future__ import annotations

from typing import Annotated, Any
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, Request, Response, UploadFile
from pydantic import BaseModel

from app.core.auth.dependencies import auth_gateway, require_subscription_ok
from app.core.auth.principal import Principal
from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from app.modules.attachments.application.service import AttachmentService
from app.modules.attachments.domain.rules import UPLOAD_LIMIT

router = APIRouter(tags=["attachments"])
Actor = Annotated[Principal, Depends(require_subscription_ok)]
_CHUNK = 64 * 1024


class AttachmentCreated(BaseModel):
    id: UUID
    url: str
    content_type: str
    size_bytes: int


class AttachmentOut(AttachmentCreated):
    original_name: str | None
    kind: str


def _service(request: Request) -> AttachmentService:
    service: AttachmentService | None = getattr(request.app.state, "attachments", None)
    if service is None:
        raise RuntimeError("attachments are not configured (app.state.attachments)")
    return service


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


async def _require_any(request: Request, actor: Principal, codes: tuple[str, ...]) -> None:
    for code in codes:
        if actor.has_scope(code.split(".", 1)[0]) and await auth_gateway(request).permission_limits(
            actor, code
        ):
            return
    raise AppError(ErrorCode.PERMISSION_DENIED, params={"permission": " | ".join(codes)})


async def _read_limited(upload: UploadFile, limit: int) -> bytes:
    chunks: list[bytes] = []
    size = 0
    while chunk := await upload.read(_CHUNK):
        size += len(chunk)
        if size > limit:
            raise AppError(ErrorCode.FILE_TOO_LARGE, params={"max_bytes": limit})
        chunks.append(chunk)
    return b"".join(chunks)


@router.post(
    "/attachments", operation_id="attachments_upload", response_model=AttachmentCreated, status_code=201
)
async def upload_attachment(
    request: Request,
    response: Response,
    actor: Actor,
    kind: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
) -> dict[str, Any]:
    service = _service(request)
    await _require_any(request, actor, service.check_kind(kind))
    content = await _read_limited(file, UPLOAD_LIMIT)
    body = await service.upload(actor, kind, file.filename, file.content_type, content, _ip(request))
    response.headers["Location"] = f"{request.url.path}/{body['id']}"
    return body


@router.get("/attachments/{attachment_id}", operation_id="attachments_get", response_model=AttachmentOut)
async def get_attachment(request: Request, attachment_id: UUID, actor: Actor) -> dict[str, Any]:
    service = _service(request)
    row = await service.load(actor, attachment_id)
    codes = await service.read_permissions(actor, row)
    if codes:
        await _require_any(request, actor, codes)
    elif row.uploaded_by != actor.user_id:
        raise AppError(ErrorCode.NOT_FOUND, params={"resource": "attachment"})
    return service.describe(actor.tenant_id, row)


@router.get(
    "/attachments/{attachment_id}/content",
    operation_id="attachments_download",
    response_class=Response,
    responses={200: {"content": {"application/octet-stream": {}}}},
)
async def download_attachment(
    request: Request,
    attachment_id: UUID,
    t: UUID,
    exp: Annotated[int, Query(ge=0)],
    sig: Annotated[str, Query(min_length=64, max_length=64)],
) -> Response:
    content, row = await _service(request).content(t, attachment_id, exp, sig)
    name = quote(row.original_name or f"{row.id}", safe="")
    return Response(
        content=content,
        media_type=row.content_type,
        headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{name}",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; sandbox",
            "Cache-Control": "private, max-age=900",
        },
    )
