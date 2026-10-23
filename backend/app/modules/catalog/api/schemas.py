"""Pydantic v2 request/response models of the catalog API (19 §1–§3, 17 §3/§4)."""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.core.money import PercentStr, QtyStr

Name = Annotated[str, StringConstraints(min_length=1, max_length=255)]
NameRu = Annotated[str, StringConstraints(max_length=255)]
ShortText = Annotated[str, StringConstraints(max_length=64)]
PackageCode = Annotated[str, StringConstraints(max_length=20)]
Reason = Annotated[str, StringConstraints(max_length=1000)]
BarcodeStr = Annotated[str, StringConstraints(min_length=1, max_length=64)]
PositiveQty = Annotated[str, StringConstraints(pattern=r"^\d{1,15}\.\d{3}$")]


class BarcodeOut(BaseModel):
    id: UUID
    barcode: str
    kind: Literal["ean", "internal", "weighed_prefix"]
    units_per_barcode: str


class ProductOut(BaseModel):
    id: UUID
    name: str
    name_ru: str | None
    category_id: UUID | None
    unit_code: str
    mxik_code: str | None
    package_code: str | None
    vat_rate: str | None
    vat_exemption_code: str | None
    is_marked: bool
    marking_group_code: str | None
    is_weighed: bool
    min_stock: str | None
    archived_at: str | None
    version: int
    barcodes: list[BarcodeOut]


class ProductListItem(ProductOut):
    current_price: str | None = Field(
        description=(
            "Effective retail price (4 dp) for X-Branch-Id / default branch: branch price, else global "
            "(19 §1, §4); null when the product has no price yet"
        )
    )
    current_cost: str | None = Field(
        description=(
            "Unit cost (4 dp) in the branch's warehouse: AVECO avg_cost / FIFO "
            "Σqty_left×unit_cost/Σqty_left, "
            "fallback last purchase cost (13 §2.11); null when unknown (BO-05 «Tannarx»)"
        )
    )
    markup_pct: str | None = Field(
        description=(
            "(net price − cost) / cost × 100, 2 dp; net price excludes VAT for a VAT payer "
            "(tenant_tax_regimes today); null without price or cost (BO-05 «Ustama %»)"
        )
    )


class ProductPage(BaseModel):
    items: list[ProductListItem]
    total: int
    page: int
    size: int


class ProductCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name
    name_ru: NameRu | None = None
    category_id: UUID | None = None
    unit_code: ShortText
    # format is checked by the service → 422 MXIK_CODE_INVALID (19 §1), not a generic VALIDATION_ERROR
    mxik_code: ShortText | None = None
    package_code: PackageCode | None = None
    vat_rate: PercentStr | None = None
    vat_exemption_code: ShortText | None = None
    is_marked: bool = False
    marking_group_code: ShortText | None = None
    is_weighed: bool = False
    min_stock: QtyStr | None = None
    barcode: BarcodeStr | None = None


class ProductUpdate(BaseModel):
    """19 §1 PATCH: any subset of the product fields + mandatory ``version`` (barcodes: sub-resource)."""

    model_config = ConfigDict(extra="forbid")

    version: int = Field(ge=1)
    name: Name | None = None
    name_ru: NameRu | None = None
    category_id: UUID | None = None
    unit_code: ShortText | None = None
    mxik_code: ShortText | None = None
    package_code: PackageCode | None = None
    vat_rate: PercentStr | None = None
    vat_exemption_code: ShortText | None = None
    is_marked: bool | None = None
    marking_group_code: ShortText | None = None
    is_weighed: bool | None = None
    min_stock: QtyStr | None = None


class ArchiveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Reason | None = None


class BarcodeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    barcode: BarcodeStr
    kind: Literal["ean", "internal", "weighed_prefix"]
    units_per_barcode: PositiveQty = "1.000"


class BarcodeList(BaseModel):
    items: list[BarcodeOut]


class InternalBarcodeOut(BaseModel):
    barcode: str
    kind: Literal["internal"]
    units_per_barcode: str


class EmptyBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MxikItem(BaseModel):
    code: str
    name: str
    vat_hint: str | None


class MxikSearchOut(BaseModel):
    items: list[MxikItem]


class MxikLookupOut(BaseModel):
    items: list[MxikItem]
    source: Literal["live", "cache", "stale_cache"]


class CategoryOut(BaseModel):
    id: UUID
    name: str
    parent_id: UUID | None
    archived_at: str | None
    version: int


class CategoryPage(BaseModel):
    items: list[CategoryOut]
    total: int
    page: int
    size: int


class CategoryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name
    parent_id: UUID | None = None


class CategoryUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(ge=1)
    name: Name | None = None
    parent_id: UUID | None = None


class UnitOut(BaseModel):
    code: str
    is_fractional: bool


class UnitList(BaseModel):
    items: list[UnitOut]
