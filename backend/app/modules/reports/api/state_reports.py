"""BO-10 state-report upload and report history (20 #3, #5–#6)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, Request, Response, UploadFile
from pydantic import BaseModel, StringConstraints

from app.core.auth.dependencies import require_subscription_ok
from app.core.auth.principal import Principal
from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from app.core.permissions import PermissionGrant, require_permission
from app.modules.reports.application.state_reports import StateReportsService

router = APIRouter(tags=["tax"])

UPLOAD_LIMIT = 5 * 1024 * 1024
_CHUNK = 64 * 1024
Actor = Annotated[Principal, Depends(require_subscription_ok)]
CanView = Annotated[PermissionGrant, Depends(require_permission("tax.vat.view"))]
CanReview = Annotated[PermissionGrant, Depends(require_permission("tax.compare.review"))]
TaxType = Literal["vat", "turnover"]
ReportStatus = Literal[
    "uploaded",
    "compared",
    "match",
    "diff_found",
    "correction_sent",
    "confirmed",
    "auto_accepted",
]
Period = Annotated[str, StringConstraints(pattern=r"^\d{4}-\d{2}$")]


class StateReportCreated(BaseModel):
    id: UUID
    tax_type: TaxType
    period: str
    status: Literal["uploaded"]
    deadline_at: str


class StateReportRowOut(BaseModel):
    id: UUID
    tax_type: TaxType
    period: str
    status: ReportStatus
    deadline_at: str
    diff_amount: str | None


class StateReportHistoryEvent(BaseModel):
    action: str
    changed_by: UUID | None
    changed_at: str
    status: ReportStatus | None


class StateReportOut(StateReportRowOut):
    published_at: str | None
    state_amount: str | None
    our_amount: str | None
    file_url: str | None
    correction_sent_at: str | None
    correction_comment: str | None
    correction_portal_ref: str | None
    confirmed_at: str | None
    confirmed_by: UUID | None
    history: list[StateReportHistoryEvent]


class StateReportPage(BaseModel):
    items: list[StateReportRowOut]
    next_cursor: str | None


def _service(request: Request) -> StateReportsService:
    service: StateReportsService | None = getattr(request.app.state, "state_reports", None)
    if service is None:
        raise RuntimeError("state reports are not configured (app.state.state_reports)")
    return service


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


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
    "/state-reports",
    operation_id="tax_upload_state_report",
    response_model=StateReportCreated,
    status_code=201,
)
async def upload_state_report(
    request: Request,
    response: Response,
    actor: Actor,
    _: CanReview,
    tax_type: Annotated[TaxType, Form()],
    period: Annotated[Period, Form()],
    published_at: Annotated[datetime, Form()],
    file: Annotated[UploadFile, File()],
) -> dict[str, object]:
    content = await _read_limited(file, UPLOAD_LIMIT)
    created = await _service(request).upload(
        actor,
        tax_type=tax_type,
        period_label=period,
        published_at=published_at,
        filename=file.filename,
        content_type=file.content_type,
        content=content,
        ip=_ip(request),
    )
    response.headers["Location"] = f"{request.url.path}/{created['id']}"
    return created


@router.get("/state-reports", operation_id="tax_list_state_reports", response_model=StateReportPage)
async def list_state_reports(
    request: Request,
    actor: Actor,
    _: CanView,
    tax_type: TaxType | None = None,
    period: Period | None = None,
    status: ReportStatus | None = None,
    cursor: Annotated[str | None, Query(max_length=64)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, object]:
    return await _service(request).list_page(
        actor,
        tax_type=tax_type,
        period_label=period,
        status=status,
        cursor=cursor,
        limit=limit,
    )


@router.get(
    "/state-reports/{report_id}",
    operation_id="tax_get_state_report",
    response_model=StateReportOut,
)
async def get_state_report(
    request: Request, report_id: UUID, actor: Actor, _: CanView
) -> dict[str, object]:
    return await _service(request).get(actor, report_id, include_file_url=True)
