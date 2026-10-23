"""Cloud print REST (20 #40m–#40q). Tag ``cloud_print``.

* ``GET /cloud-printers`` — ``cash_register.manage`` or ``sales.create`` (POS-16 ``printer.cloud_id`` choice);
  ``POST`` / ``PATCH /cloud-printers/{id}`` / ``POST /cloud-printers/{id}/secret`` — ``cash_register.manage``
  (BO-14 «Bulut printerlar»).
* ``GET /cloud-printers/{id}/status`` — the ``CloudPrintApi.status`` call of the web adapter.
* ``POST /print-jobs`` — ``{id, cloud_printer_id, kind, raster:{width_dots, height_dots, data_base64}}``
  (``CloudPrintJob`` of ``shared/lib/src/printer/cloud-system.ts``); ``receipt``/``test`` — ``sales.create``,
  ``label`` — ``labels.print``. ``GET /print-jobs/{id}`` — the same rights.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.core.auth.dependencies import auth_gateway, require_subscription_ok
from app.core.auth.principal import Principal
from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from app.core.permissions import BranchScope, PermissionGrant, current_branch_scope, require_permission
from app.modules.integrations.cloud_print.application.module import CloudPrintModule
from app.modules.integrations.cloud_print.application.ports import PrinterFilter
from app.modules.integrations.cloud_print.application.service import JobInput, PrinterPatch

router = APIRouter(tags=["cloud_print"])

Actor = Annotated[Principal, Depends(require_subscription_ok)]
Scope = Annotated[BranchScope, Depends(current_branch_scope)]
CanManage = Annotated[PermissionGrant, Depends(require_permission("cash_register.manage"))]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Model = Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)]
PrinterProtocol = Literal["star_cloudprnt", "epson_sdp"]
PrinterStatus = Literal["active", "disabled", "archived"]
JOB_PERMISSIONS: dict[str, tuple[str, ...]] = {
    "receipt": ("sales.create",),
    "test": ("sales.create", "cash_register.manage"),
    "label": ("labels.print",),
}


def cloud_print_module(request: Request) -> CloudPrintModule:
    module: CloudPrintModule | None = getattr(request.app.state, "cloud_print", None)
    if module is None:
        raise RuntimeError("cloud print module is not wired (app.state.cloud_print)")
    return module


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


async def _holds(request: Request, principal: Principal, code: str) -> bool:
    if not principal.has_scope(code.split(".", 1)[0]):
        return False
    return bool(await auth_gateway(request).permission_limits(principal, code))


async def _require_any(request: Request, principal: Principal, codes: tuple[str, ...]) -> None:
    for code in codes:
        if await _holds(request, principal, code):
            return
    raise AppError(ErrorCode.PERMISSION_DENIED, params={"permission": codes[0], "any_of": list(codes)})


# --- schemas ---------------------------------------------------------------------------------------


class CloudPrinterCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    branch_id: UUID
    name: Name
    protocol: PrinterProtocol
    model: Model | None = None


class CloudPrinterUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name | None = None
    model: Model | None = None
    status: PrinterStatus | None = None
    version: int


class CloudPrinterOut(BaseModel):
    id: UUID
    branch_id: UUID
    name: str
    protocol: PrinterProtocol
    model: str | None
    status: PrinterStatus
    poll_path: str = Field(description="Path the printer polls (CloudPRNT / Server Direct Print URL)")
    printer_mac: str | None
    last_poll_at: str | None
    last_status: str | None
    online: bool
    version: int


class CloudPrinterWithSecret(CloudPrinterOut):
    secret: str = Field(
        description="Printer password for HTTP Basic (username = printer id) — shown only in this response"
    )


class CloudPrinterPage(BaseModel):
    items: list[CloudPrinterOut]
    total: int
    page: int
    size: int


class CloudPrinterStatus(BaseModel):
    id: UUID
    online: bool
    status: PrinterStatus
    last_poll_at: str | None
    last_status: str | None
    pending: int


class Raster(BaseModel):
    model_config = ConfigDict(extra="forbid")

    width_dots: Annotated[int, Field(ge=8, le=1024)]
    height_dots: Annotated[int, Field(ge=1, le=20000)]
    data_base64: Annotated[str, StringConstraints(min_length=4, max_length=800_000)]


class PrintJobIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(description="UUIDv7 chosen by the client — idempotency key of the queue")
    cloud_printer_id: UUID
    kind: Literal["receipt", "test", "label"]
    raster: Raster


class PrintJobOut(BaseModel):
    id: UUID
    cloud_printer_id: UUID
    kind: Literal["receipt", "test", "label"]
    status: Literal["queued", "printing", "done", "failed"]
    result_code: str | None


# --- printers --------------------------------------------------------------------------------------


@router.get("/cloud-printers", operation_id="cloud_print_list_printers", response_model=CloudPrinterPage)
async def list_cloud_printers(
    request: Request,
    actor: Actor,
    scope: Scope,
    branch_id: UUID | None = None,
    status: PrinterStatus | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    await _require_any(request, actor, ("cash_register.manage", "sales.create"))
    flt = PrinterFilter(scope.allowed, branch_id or scope.current, status)
    return await cloud_print_module(request).printers.list_page(actor, scope, flt, page, size)


@router.post(
    "/cloud-printers",
    operation_id="cloud_print_create_printer",
    response_model=CloudPrinterWithSecret,
    status_code=201,
)
async def create_cloud_printer(
    request: Request, response: Response, body: CloudPrinterCreate, actor: Actor, scope: Scope, _: CanManage
) -> dict[str, Any]:
    created = await cloud_print_module(request).printers.create(actor, scope, body.model_dump(), _ip(request))
    response.headers["Location"] = f"{request.url.path.rstrip('/')}/{created['id']}"
    return created


@router.patch(
    "/cloud-printers/{printer_id}", operation_id="cloud_print_update_printer", response_model=CloudPrinterOut
)
async def update_cloud_printer(
    request: Request, printer_id: UUID, body: CloudPrinterUpdate, actor: Actor, scope: Scope, _: CanManage
) -> dict[str, Any]:
    fields = {k: getattr(body, k) for k in body.model_fields_set if k != "version"}
    for key in ("name", "status"):
        if key in fields and fields[key] is None:
            fields.pop(key)
    patch = PrinterPatch(version=body.version, fields=fields)
    return await cloud_print_module(request).printers.update(actor, scope, printer_id, patch, _ip(request))


@router.post(
    "/cloud-printers/{printer_id}/secret",
    operation_id="cloud_print_rotate_secret",
    response_model=CloudPrinterWithSecret,
)
async def rotate_cloud_printer_secret(
    request: Request, printer_id: UUID, actor: Actor, scope: Scope, _: CanManage
) -> dict[str, Any]:
    return await cloud_print_module(request).printers.rotate_secret(actor, scope, printer_id, _ip(request))


@router.get(
    "/cloud-printers/{printer_id}/status",
    operation_id="cloud_print_printer_status",
    response_model=CloudPrinterStatus,
)
async def cloud_printer_status(
    request: Request, printer_id: UUID, actor: Actor, scope: Scope
) -> dict[str, Any]:
    await _require_any(request, actor, ("cash_register.manage", "sales.create"))
    return await cloud_print_module(request).printers.get_status(actor, scope, printer_id)


# --- jobs ------------------------------------------------------------------------------------------


@router.post(
    "/print-jobs",
    operation_id="cloud_print_submit_job",
    response_model=PrintJobOut,
    status_code=201,
    responses={200: {"model": PrintJobOut, "description": "Already queued (same id and content)"}},
)
async def submit_print_job(
    request: Request, response: Response, body: PrintJobIn, actor: Actor, scope: Scope
) -> dict[str, Any]:
    await _require_any(request, actor, JOB_PERMISSIONS[body.kind])
    job = JobInput(
        id=body.id, cloud_printer_id=body.cloud_printer_id, kind=body.kind, width_dots=body.raster.width_dots,
        height_dots=body.raster.height_dots, data_base64=body.raster.data_base64,
    )  # fmt: skip
    result, status = await cloud_print_module(request).jobs.submit(actor, scope, job)
    response.status_code = status
    return result


@router.get("/print-jobs/{job_id}", operation_id="cloud_print_get_job", response_model=PrintJobOut)
async def get_print_job(request: Request, job_id: UUID, actor: Actor, scope: Scope) -> dict[str, Any]:
    await _require_any(request, actor, ("sales.create", "labels.print", "cash_register.manage"))
    return await cloud_print_module(request).jobs.get(actor, scope, job_id)
