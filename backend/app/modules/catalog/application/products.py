"""Product catalog use cases (19 §1, US-M09-05, BO-04/BO-05/BO-18).

Every write runs in one ``tenant_transaction`` together with its audit row and
the staged idempotency response (23 §3). Referenced ids (category, marking
group, unit) are re-read through RLS — a foreign key alone would accept another
tenant's row, because PostgreSQL checks FKs without RLS.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.audit import record_audit
from app.core.auth.principal import Principal
from app.core.db.base import uuid7
from app.core.db.session import tenant_transaction
from app.core.error_codes import ErrorCode
from app.core.errors import AppError, ErrorDetail
from app.core.idempotency import stage_response
from app.core.money import HUNDRED, price_str
from app.core.permissions import BranchScope
from app.modules.accounting.domain.calendar import business_today as tashkent_today
from app.modules.catalog.application.ports import (
    CatalogRepository,
    CurrentCostsPort,
    CurrentPricesPort,
    ProductFilter,
)
from app.modules.catalog.application.presenters import barcode_json, product_json
from app.modules.catalog.domain.barcodes import (
    INTERNAL_SEQ_MAX,
    BarcodeKind,
    barcode_format_ok,
    internal_barcode,
)
from app.modules.catalog.domain.products import (
    ALLOWED_VAT_RATES,
    Product,
    is_valid_mxik,
)

PRODUCT_FIELDS = (
    "name",
    "name_ru",
    "category_id",
    "unit_code",
    "mxik_code",
    "package_code",
    "vat_rate",
    "vat_exemption_code",
    "is_marked",
    "marking_group_code",
    "is_weighed",
    "min_stock",
)


@dataclass(frozen=True, slots=True)
class Page:
    items: list[dict[str, Any]]
    total: int
    page: int
    size: int

    def as_json(self) -> dict[str, Any]:
        return {"items": self.items, "total": self.total, "page": self.page, "size": self.size}


def _invalid(field: str, key: str) -> AppError:
    return AppError(ErrorCode.VALIDATION_ERROR, details=[ErrorDetail(field=field, message_key=key)])


def _not_found(resource: str) -> AppError:
    return AppError(ErrorCode.NOT_FOUND, params={"resource": resource})


def _price(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def markup_pct(
    price: Decimal | None, cost: Decimal | None, vat_rate: Decimal | None, vat_payer: bool
) -> str | None:
    """BO-05 «Ustama %» = (net selling price − cost) / cost × 100, 2 dp (ROUND_HALF_UP).

    For a VAT payer the net price excludes the VAT included in the retail price
    (``price × 100 / (100 + rate)``, 13 §2); for a turnover-tax payer it is the full price.
    ``None`` when the price or the cost is missing or zero.
    """
    if price is None or cost is None or price <= 0 or cost <= 0:
        return None
    rate = vat_rate if vat_payer and vat_rate is not None else Decimal(0)
    net = price * HUNDRED / (HUNDRED + rate)
    return _pct((net - cost) / cost * HUNDRED)


def _pct(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), "f")


def _audit_view(values: Mapping[str, Any]) -> dict[str, Any]:
    return {k: (str(v) if isinstance(v, Decimal | UUID) else v) for k, v in values.items()}


class ProductService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        repo: CatalogRepository,
        prices: CurrentPricesPort | None = None,
        costs: CurrentCostsPort | None = None,
    ) -> None:
        self._sf = session_factory
        self._repo = repo
        self._prices = prices
        self._costs = costs

    # --- reads ------------------------------------------------------------------------------------
    async def list_page(
        self, actor: Principal, flt: ProductFilter, page: int, size: int, scope: BranchScope
    ) -> Page:
        """19 §1: each item carries ``current_price`` (branch → global, 19 §4), ``current_cost`` (the
        branch warehouse's unit cost, inventory) and ``markup_pct`` (BO-05) — batched per page."""
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            items, total = await self._repo.list_products(s, flt, (page - 1) * size, size)
            ids = [p.id for p in items]
            prices: Mapping[UUID, Decimal] = (
                await self._prices(s, ids, scope) if self._prices and items else {}
            )
            costs: Mapping[UUID, Decimal] = await self._costs(s, ids, scope) if self._costs and items else {}
            vat_payer = await self._repo.vat_payer(s, tashkent_today()) if items else True
        out = []
        for p in items:
            cost = costs.get(p.id)
            out.append(
                product_json(p)
                | {
                    "current_price": _price(prices.get(p.id)),
                    "current_cost": None if cost is None else price_str(cost),
                    "markup_pct": markup_pct(prices.get(p.id), cost, p.vat_rate, vat_payer),
                }
            )
        return Page(out, total, page, size)

    async def get(self, actor: Principal, product_id: UUID) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            product = await self._repo.get_product(s, product_id)
        if product is None:
            raise _not_found("product")
        return product_json(product)

    async def list_barcodes(self, actor: Principal, product_id: UUID) -> list[dict[str, Any]]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            if await self._repo.get_product(s, product_id) is None:
                raise _not_found("product")
            return [barcode_json(b) for b in await self._repo.list_barcodes(s, product_id)]

    # --- writes -----------------------------------------------------------------------------------
    async def create(
        self, actor: Principal, values: Mapping[str, Any], barcode: str | None, ip: str | None
    ) -> dict[str, Any]:
        row = {k: values.get(k) for k in PRODUCT_FIELDS}
        row["is_marked"] = bool(row["is_marked"])
        row["is_weighed"] = bool(row["is_weighed"])
        product_id = uuid7()
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            await self._check(s, row)
            if barcode is not None and not barcode_format_ok(barcode, "ean"):
                raise _invalid("barcode", "validation.barcode_format")
            await self._repo.insert_products(s, actor.tenant_id, [{**row, "id": product_id}])
            if barcode is not None:
                added = await self._repo.insert_barcode(
                    s, actor.tenant_id, product_id, barcode, "ean", "1.000"
                )
                if added is None:
                    raise AppError(ErrorCode.BARCODE_DUPLICATE, params={"barcode": barcode})
            await self._repo.queue_labels(s, actor.tenant_id, [product_id], "new")
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="product_created",
                entity="products",
                entity_id=product_id,
                after={**_audit_view(row), "barcode": barcode},
                ip=ip,
            )
            body = product_json(await self._load(s, product_id))
            stage_response(body, 201)
        return body

    async def update(
        self, actor: Principal, product_id: UUID, version: int, changes: Mapping[str, Any], ip: str | None
    ) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            current = await self._repo.get_product(s, product_id, lock=True)
            if current is None:
                raise _not_found("product")
            if current.archived_at is not None:
                raise AppError(ErrorCode.RESOURCE_ARCHIVED, params={"resource": "product"})
            if current.version != version:
                raise AppError(ErrorCode.VERSION_CONFLICT, params={"current_version": current.version})
            merged = {k: getattr(current, k) for k in PRODUCT_FIELDS} | dict(changes)
            for flag in ("is_marked", "is_weighed"):
                if merged[flag] is None:
                    raise _invalid(flag, "validation.required")
            await self._check(s, merged, changed=set(changes))
            if changes and not await self._repo.update_product(s, product_id, version, changes):
                raise AppError(ErrorCode.VERSION_CONFLICT, params={"current_version": current.version})
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="product_updated",
                entity="products",
                entity_id=product_id,
                before=_audit_view({k: getattr(current, k) for k in changes}),
                after=_audit_view(changes),
                ip=ip,
            )
            body = product_json(await self._load(s, product_id))
            stage_response(body)
        return body

    async def set_archived(
        self, actor: Principal, product_id: UUID, archived: bool, reason: str | None, ip: str | None
    ) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            current = await self._repo.get_product(s, product_id, lock=True)
            if current is None:
                raise _not_found("product")
            if (current.archived_at is not None) != archived:
                await self._repo.set_product_archived(s, product_id, archived)
                await record_audit(
                    s,
                    tenant_id=actor.tenant_id,
                    user_id=actor.user_id,
                    action="product_archived" if archived else "product_unarchived",
                    entity="products",
                    entity_id=product_id,
                    after={"reason": reason},
                    ip=ip,
                )
            body = product_json(await self._load(s, product_id))
            stage_response(body)
        return body

    async def add_barcode(
        self,
        actor: Principal,
        product_id: UUID,
        barcode: str,
        kind: BarcodeKind,
        units_per_barcode: str,
        ip: str | None,
    ) -> dict[str, Any]:
        if not barcode_format_ok(barcode, kind):
            raise _invalid("barcode", "validation.barcode_format")
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            await self._writable(s, product_id)
            added = await self._repo.insert_barcode(
                s, actor.tenant_id, product_id, barcode, kind, units_per_barcode
            )
            if added is None:
                raise AppError(ErrorCode.BARCODE_DUPLICATE, params={"barcode": barcode})
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="product_barcode_added",
                entity="product_barcodes",
                entity_id=added.id,
                after={"product_id": str(product_id), "barcode": barcode, "kind": kind},
                ip=ip,
            )
            body = barcode_json(added)
            stage_response(body, 201)
        return body

    async def remove_barcode(
        self, actor: Principal, product_id: UUID, barcode_id: UUID, ip: str | None
    ) -> None:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            await self._writable(s, product_id)
            removed = await self._repo.delete_barcode(s, product_id, barcode_id)
            if removed is None:
                raise _not_found("product_barcode")
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="product_barcode_removed",
                entity="product_barcodes",
                entity_id=barcode_id,
                before={"product_id": str(product_id), "barcode": removed.barcode, "kind": removed.kind},
                ip=ip,
            )
            stage_response(None, 204)

    async def generate_internal_barcode(
        self, actor: Principal, product_id: UUID, ip: str | None
    ) -> dict[str, Any]:
        """US-M09-05: next free ``04…`` EAN-13 from ``internal_barcode_seq`` (row locked FOR UPDATE)."""
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            await self._writable(s, product_id)
            seq = await self._repo.lock_internal_seq(s, actor.tenant_id)
            while True:
                if seq > INTERNAL_SEQ_MAX:
                    raise _invalid("barcode", "validation.internal_barcode_range_exhausted")
                code = internal_barcode(seq)
                seq += 1
                # a manually entered code may already occupy this value: skip it, never collide
                added = await self._repo.insert_barcode(
                    s, actor.tenant_id, product_id, code, "internal", "1.000"
                )
                if added is not None:
                    break
            await self._repo.set_internal_seq(s, actor.tenant_id, min(seq, INTERNAL_SEQ_MAX))
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="internal_barcode_generated",
                entity="product_barcodes",
                entity_id=added.id,
                after={"product_id": str(product_id), "barcode": code},
                ip=ip,
            )
            body = {
                "barcode": added.barcode,
                "kind": "internal",
                "units_per_barcode": str(added.units_per_barcode),
            }
            stage_response(body, 201)
        return body

    # --- helpers ----------------------------------------------------------------------------------
    async def _load(self, s: AsyncSession, product_id: UUID) -> Product:
        product = await self._repo.get_product(s, product_id)
        assert product is not None
        return product

    async def _writable(self, s: AsyncSession, product_id: UUID) -> Product:
        product = await self._repo.get_product(s, product_id, lock=True)
        if product is None:
            raise _not_found("product")
        if product.archived_at is not None:
            raise AppError(ErrorCode.RESOURCE_ARCHIVED, params={"resource": "product"})
        return product

    async def _check(self, s: AsyncSession, row: Mapping[str, Any], changed: set[str] | None = None) -> None:
        """19 §1 validation of the full (merged) product; ``changed`` limits the reference re-checks."""

        def touched(field: str) -> bool:
            return changed is None or field in changed

        name = row.get("name")
        if not isinstance(name, str) or not name.strip():
            raise _invalid("name", "validation.required")
        mxik = row.get("mxik_code")
        if mxik is not None and not is_valid_mxik(mxik):
            raise AppError(
                ErrorCode.MXIK_CODE_INVALID,
                details=[ErrorDetail(field="mxik_code", message_key="validation.mxik_format")],
            )
        if touched("unit_code") and row.get("unit_code") not in await self._repo.unit_codes(s):
            raise _invalid("unit_code", "validation.unit_not_found")
        vat_rate = row.get("vat_rate")
        if vat_rate is not None and Decimal(vat_rate) not in ALLOWED_VAT_RATES:
            raise _invalid("vat_rate", "validation.vat_rate_not_allowed")
        if vat_rate is None and not row.get("vat_exemption_code"):
            raise _invalid("vat_rate", "validation.vat_rate_or_exemption_required")
        if row.get("is_marked"):
            group = row.get("marking_group_code")
            if not group:
                raise _invalid("marking_group_code", "validation.required")
            if touched("marking_group_code") and not await self._repo.marking_group_exists(s, group):
                raise _invalid("marking_group_code", "validation.marking_group_not_found")
        category_id = row.get("category_id")
        if category_id is not None and touched("category_id"):
            category = await self._repo.get_category(s, category_id)
            if category is None or category.archived_at is not None:
                raise _invalid("category_id", "validation.category_not_found")
        min_stock = row.get("min_stock")
        if min_stock is not None and Decimal(min_stock) < 0:
            raise _invalid("min_stock", "validation.min_value")
