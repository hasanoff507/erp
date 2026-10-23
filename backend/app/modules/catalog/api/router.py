"""Catalog endpoints (19 §1–§3): products, barcodes, MXIK, categories, units.

OpenAPI tag ``pricing`` — 17 §11 maps M09 to the ``pricing`` tag.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response

from app.core.error_codes import ErrorCode
from app.core.errors import AppError, ErrorDetail
from app.core.permissions import BranchScope, current_branch_scope
from app.modules.catalog.api.deps import Actor, CanManage, CanView, catalog_module, client_ip
from app.modules.catalog.api.schemas import (
    ArchiveRequest,
    BarcodeCreate,
    BarcodeList,
    BarcodeOut,
    CategoryCreate,
    CategoryOut,
    CategoryPage,
    CategoryUpdate,
    EmptyBody,
    InternalBarcodeOut,
    MxikLookupOut,
    MxikSearchOut,
    ProductCreate,
    ProductOut,
    ProductPage,
    ProductUpdate,
    UnitList,
)
from app.modules.catalog.application.ports import ProductFilter

router = APIRouter(tags=["pricing"])

PageNo = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=200)]
_NOT_NULL_PRODUCT = frozenset({"name", "unit_code", "is_marked", "is_weighed"})
_DECIMAL_FIELDS = frozenset({"vat_rate", "min_stock"})


def _decimals(values: dict[str, Any]) -> dict[str, Any]:
    return {k: (Decimal(v) if k in _DECIMAL_FIELDS and v is not None else v) for k, v in values.items()}


# --- products -------------------------------------------------------------------------------------
@router.get("/products", operation_id="pricing_list_products", response_model=ProductPage)
async def list_products(
    request: Request,
    actor: Actor,
    _: CanView,
    scope: Annotated[BranchScope, Depends(current_branch_scope)],
    search: Annotated[str | None, Query(max_length=255)] = None,
    category_id: UUID | None = None,
    archived: bool = False,
    is_weighed: bool | None = None,
    low_stock: bool = False,
    page: PageNo = 1,
    size: PageSize = 50,
) -> dict[str, Any]:
    branches: tuple[UUID, ...] | None
    if scope.current is not None:
        branches = (scope.current,)
    else:
        branches = None if scope.unrestricted else scope.allowed
    flt = ProductFilter(
        search=(search or "").strip() or None,
        category_id=category_id,
        archived=archived,
        is_weighed=is_weighed,
        low_stock=low_stock,
        branch_ids=branches,
    )
    result = await catalog_module(request).products.list_page(actor, flt, page, size, scope)
    return result.as_json()


@router.post("/products", operation_id="pricing_create_product", response_model=ProductOut, status_code=201)
async def create_product(
    request: Request, response: Response, body: ProductCreate, actor: Actor, _: CanManage
) -> dict[str, Any]:
    values = _decimals(body.model_dump(exclude={"barcode"}))
    product = await catalog_module(request).products.create(actor, values, body.barcode, client_ip(request))
    response.headers["Location"] = f"{request.url.path}/{product['id']}"
    return product


@router.get("/products/{product_id}", operation_id="pricing_get_product", response_model=ProductOut)
async def get_product(request: Request, product_id: UUID, actor: Actor, _: CanView) -> dict[str, Any]:
    return await catalog_module(request).products.get(actor, product_id)


@router.patch("/products/{product_id}", operation_id="pricing_update_product", response_model=ProductOut)
async def update_product(
    request: Request, product_id: UUID, body: ProductUpdate, actor: Actor, _: CanManage
) -> dict[str, Any]:
    changes = {k: getattr(body, k) for k in body.model_fields_set if k != "version"}
    for field in _NOT_NULL_PRODUCT & changes.keys():
        if changes[field] is None:
            raise AppError(
                ErrorCode.VALIDATION_ERROR,
                details=[ErrorDetail(field=field, message_key="validation.required")],
            )
    return await catalog_module(request).products.update(
        actor, product_id, body.version, _decimals(changes), client_ip(request)
    )


@router.post(
    "/products/{product_id}/archive", operation_id="pricing_archive_product", response_model=ProductOut
)
async def archive_product(
    request: Request, product_id: UUID, actor: Actor, _: CanManage, body: ArchiveRequest | None = None
) -> dict[str, Any]:
    reason = body.reason if body else None
    return await catalog_module(request).products.set_archived(
        actor, product_id, True, reason, client_ip(request)
    )


@router.post(
    "/products/{product_id}/unarchive", operation_id="pricing_unarchive_product", response_model=ProductOut
)
async def unarchive_product(
    request: Request, product_id: UUID, actor: Actor, _: CanManage, body: ArchiveRequest | None = None
) -> dict[str, Any]:
    reason = body.reason if body else None
    return await catalog_module(request).products.set_archived(
        actor, product_id, False, reason, client_ip(request)
    )


# --- barcodes -------------------------------------------------------------------------------------
@router.get(
    "/products/{product_id}/barcodes",
    operation_id="pricing_list_product_barcodes",
    response_model=BarcodeList,
)
async def list_barcodes(request: Request, product_id: UUID, actor: Actor, _: CanManage) -> dict[str, Any]:
    return {"items": await catalog_module(request).products.list_barcodes(actor, product_id)}


@router.post(
    "/products/{product_id}/barcodes",
    operation_id="pricing_create_product_barcode",
    response_model=BarcodeOut,
    status_code=201,
)
async def create_barcode(
    request: Request, product_id: UUID, body: BarcodeCreate, actor: Actor, _: CanManage
) -> dict[str, Any]:
    return await catalog_module(request).products.add_barcode(
        actor, product_id, body.barcode, body.kind, body.units_per_barcode, client_ip(request)
    )


@router.delete(
    "/products/{product_id}/barcodes/{barcode_id}",
    operation_id="pricing_delete_product_barcode",
    status_code=204,
    response_class=Response,
)
async def delete_barcode(
    request: Request, product_id: UUID, barcode_id: UUID, actor: Actor, _: CanManage
) -> Response:
    await catalog_module(request).products.remove_barcode(actor, product_id, barcode_id, client_ip(request))
    return Response(status_code=204)


@router.post(
    "/products/{product_id}/barcodes/internal-generate",
    operation_id="pricing_generate_internal_barcode",
    response_model=InternalBarcodeOut,
    status_code=201,
)
async def generate_internal_barcode(
    request: Request, product_id: UUID, actor: Actor, _: CanManage, body: EmptyBody | None = None
) -> dict[str, Any]:
    return await catalog_module(request).products.generate_internal_barcode(
        actor, product_id, client_ip(request)
    )


# --- MXIK -----------------------------------------------------------------------------------------
@router.get("/mxik-codes", operation_id="pricing_search_mxik_codes", response_model=MxikSearchOut)
async def search_mxik(
    request: Request,
    actor: Actor,
    _: CanManage,
    query: Annotated[str, Query(min_length=1, max_length=200)],
    limit: Annotated[int, Query(ge=1, le=20)] = 20,
) -> dict[str, Any]:
    result = await catalog_module(request).mxik.search(query, limit)
    return {"items": [_mxik(c) for c in result.items]}


@router.get("/mxik-codes/{code}", operation_id="pricing_get_mxik_code", response_model=MxikLookupOut)
async def get_mxik(request: Request, code: str, actor: Actor, _: CanManage) -> dict[str, Any]:
    result = await catalog_module(request).mxik.get(code)
    return {"items": [_mxik(c) for c in result.items], "source": result.source}


def _mxik(candidate: Any) -> dict[str, Any]:
    return {"code": candidate.code, "name": candidate.name, "vat_hint": candidate.vat_hint}


# --- categories -----------------------------------------------------------------------------------
@router.get(
    "/product-categories", operation_id="pricing_list_product_categories", response_model=CategoryPage
)
async def list_categories(
    request: Request,
    actor: Actor,
    _: CanView,
    parent_id: UUID | None = None,
    page: PageNo = 1,
    size: PageSize = 50,
) -> dict[str, Any]:
    result = await catalog_module(request).categories.list_page(actor, parent_id, page, size)
    return result.as_json()


@router.post(
    "/product-categories",
    operation_id="pricing_create_product_category",
    response_model=CategoryOut,
    status_code=201,
)
async def create_category(
    request: Request, response: Response, body: CategoryCreate, actor: Actor, _: CanManage
) -> dict[str, Any]:
    category = await catalog_module(request).categories.create(
        actor, body.name, body.parent_id, client_ip(request)
    )
    response.headers["Location"] = f"{request.url.path}/{category['id']}"
    return category


@router.patch(
    "/product-categories/{category_id}",
    operation_id="pricing_update_product_category",
    response_model=CategoryOut,
)
async def update_category(
    request: Request, category_id: UUID, body: CategoryUpdate, actor: Actor, _: CanManage
) -> dict[str, Any]:
    changes = {k: getattr(body, k) for k in body.model_fields_set if k != "version"}
    if "name" in changes and changes["name"] is None:
        raise AppError(
            ErrorCode.VALIDATION_ERROR, details=[ErrorDetail(field="name", message_key="validation.required")]
        )
    return await catalog_module(request).categories.update(
        actor, category_id, body.version, changes, client_ip(request)
    )


@router.post(
    "/product-categories/{category_id}/archive",
    operation_id="pricing_archive_product_category",
    response_model=CategoryOut,
)
async def archive_category(
    request: Request, category_id: UUID, actor: Actor, _: CanManage, body: EmptyBody | None = None
) -> dict[str, Any]:
    return await catalog_module(request).categories.archive(actor, category_id, client_ip(request))


# --- units ----------------------------------------------------------------------------------------
@router.get("/units", operation_id="pricing_list_units", response_model=UnitList)
async def list_units(request: Request, actor: Actor, _: CanView) -> dict[str, Any]:
    return {"items": await catalog_module(request).categories.list_units(actor)}
