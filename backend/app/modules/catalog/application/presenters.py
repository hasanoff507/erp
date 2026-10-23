"""JSON shapes of catalog resources (19 §1–§3).

The same dict is returned by the route and staged for the idempotency journal
(23 §3), so a replay is byte-for-byte the original answer. Decimals leave as
strings with their DB scale (17 §3).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from app.modules.catalog.domain.products import Barcode, Category, Product, Unit


def _dec(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def _ts(value: datetime | None) -> str | None:
    return None if value is None else value.isoformat().replace("+00:00", "Z")


def barcode_json(b: Barcode) -> dict[str, Any]:
    return {
        "id": str(b.id),
        "barcode": b.barcode,
        "kind": b.kind,
        "units_per_barcode": str(b.units_per_barcode),
    }


def product_json(p: Product) -> dict[str, Any]:
    return {
        "id": str(p.id),
        "name": p.name,
        "name_ru": p.name_ru,
        "category_id": str(p.category_id) if p.category_id else None,
        "unit_code": p.unit_code,
        "mxik_code": p.mxik_code,
        "package_code": p.package_code,
        "vat_rate": _dec(p.vat_rate),
        "vat_exemption_code": p.vat_exemption_code,
        "is_marked": p.is_marked,
        "marking_group_code": p.marking_group_code,
        "is_weighed": p.is_weighed,
        "min_stock": _dec(p.min_stock),
        "archived_at": _ts(p.archived_at),
        "version": p.version,
        "barcodes": [barcode_json(b) for b in p.barcodes],
    }


def category_json(c: Category) -> dict[str, Any]:
    return {
        "id": str(c.id),
        "name": c.name,
        "parent_id": str(c.parent_id) if c.parent_id else None,
        "archived_at": _ts(c.archived_at),
        "version": c.version,
    }


def unit_json(u: Unit) -> dict[str, Any]:
    return {"code": u.code, "is_fractional": u.is_fractional}
