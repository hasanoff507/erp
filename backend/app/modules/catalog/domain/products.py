"""Product rules (19 §1, 11 §4, 12 ``products``) — pure, no I/O."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Final
from uuid import UUID

from app.modules.catalog.domain.barcodes import BarcodeKind

MXIK_RE: Final = re.compile(r"^[0-9]{17}$")
NAME_MAX: Final = 255
PACKAGE_CODE_MAX: Final = 20
# 19 §1: `vat_rate` is "12.00" or "0.00" (12 products.vat_rate NUMERIC(5,2))
ALLOWED_VAT_RATES: Final = frozenset({Decimal("12.00"), Decimal("0.00")})
DEFAULT_MARKING_GROUP: Final = "general"


def is_valid_mxik(code: str) -> bool:
    return bool(MXIK_RE.match(code))


@dataclass(frozen=True, slots=True)
class Barcode:
    id: UUID
    barcode: str
    kind: BarcodeKind
    units_per_barcode: Decimal


@dataclass(frozen=True, slots=True)
class Product:
    id: UUID
    name: str
    name_ru: str | None
    category_id: UUID | None
    unit_code: str
    mxik_code: str | None
    package_code: str | None
    vat_rate: Decimal | None
    vat_exemption_code: str | None
    is_marked: bool
    marking_group_code: str | None
    is_weighed: bool
    min_stock: Decimal | None
    archived_at: datetime | None
    version: int
    barcodes: tuple[Barcode, ...] = field(default=())


@dataclass(frozen=True, slots=True)
class Category:
    id: UUID
    name: str
    parent_id: UUID | None
    archived_at: datetime | None
    version: int


@dataclass(frozen=True, slots=True)
class Unit:
    code: str
    is_fractional: bool
