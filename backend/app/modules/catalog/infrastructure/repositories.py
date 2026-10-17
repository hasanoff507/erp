"""Catalog SQL (12 ``products``, ``product_categories``, ``product_barcodes``, ``internal_barcode_seq``).

Every statement runs inside the caller's ``tenant_transaction``; RLS limits
reads/writes to the current tenant, ``tenant_id`` is still written explicitly.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import Row, bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.base import uuid7
from app.modules.catalog.application.ports import ProductFilter
from app.modules.catalog.domain.barcodes import BarcodeKind
from app.modules.catalog.domain.products import Barcode, Category, Product, Unit

_PRODUCT_COLUMNS = (
    "id, name, name_ru, category_id, unit_code, mxik_code, package_code, vat_rate, vat_exemption_code, "
    "is_marked, marking_group_code, is_weighed, min_stock, archived_at, version"
)
_UPDATABLE_PRODUCT = frozenset(
    {
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
    }
)
_UPDATABLE_CATEGORY = frozenset({"name", "parent_id"})

_BARCODES_OF = text(
    "SELECT id, product_id, barcode, kind, units_per_barcode FROM app.product_barcodes "
    "WHERE product_id IN :ids ORDER BY created_at, id"
).bindparams(bindparam("ids", expanding=True))


def _product(row: Row[Any], barcodes: tuple[Barcode, ...] = ()) -> Product:
    m = row._mapping
    return Product(
        id=m["id"],
        name=m["name"],
        name_ru=m["name_ru"],
        category_id=m["category_id"],
        unit_code=m["unit_code"],
        mxik_code=m["mxik_code"],
        package_code=m["package_code"],
        vat_rate=m["vat_rate"],
        vat_exemption_code=m["vat_exemption_code"],
        is_marked=m["is_marked"],
        marking_group_code=m["marking_group_code"],
        is_weighed=m["is_weighed"],
        min_stock=m["min_stock"],
        archived_at=m["archived_at"],
        version=m["version"],
        barcodes=barcodes,
    )


def _barcode(row: Row[Any]) -> Barcode:
    m = row._mapping
    return Barcode(id=m["id"], barcode=m["barcode"], kind=m["kind"], units_per_barcode=m["units_per_barcode"])


def _category(row: Row[Any]) -> Category:
    m = row._mapping
    return Category(
        id=m["id"],
        name=m["name"],
        parent_id=m["parent_id"],
        archived_at=m["archived_at"],
        version=m["version"],
    )


class SqlCatalogRepository:
    # --- reference data ---------------------------------------------------------------------------
    async def list_units(self, s: AsyncSession) -> list[Unit]:
        rows = await s.execute(text("SELECT code, is_fractional FROM platform.units ORDER BY code"))
        return [Unit(code=r[0], is_fractional=r[1]) for r in rows]

    async def unit_codes(self, s: AsyncSession) -> set[str]:
        return {r[0] for r in await s.execute(text("SELECT code FROM platform.units"))}

    async def marking_group_exists(self, s: AsyncSession, code: str) -> bool:
        found = await s.execute(
            text("SELECT 1 FROM platform.marking_product_groups WHERE code = :c"), {"c": code}
        )
        return found.first() is not None

    # --- categories -------------------------------------------------------------------------------
    async def get_category(
        self, s: AsyncSession, category_id: UUID, *, lock: bool = False
    ) -> Category | None:
        sql = "SELECT id, name, parent_id, archived_at, version FROM app.product_categories WHERE id = :id"
        row = (await s.execute(text(sql + (" FOR UPDATE" if lock else "")), {"id": category_id})).first()
        return _category(row) if row else None

    async def list_categories(
        self, s: AsyncSession, parent_id: UUID | None, offset: int, limit: int
    ) -> tuple[list[Category], int]:
        where = "archived_at IS NULL" + (" AND parent_id = :parent" if parent_id is not None else "")
        params: dict[str, Any] = {"parent": parent_id, "offset": offset, "limit": limit}
        count_sql = f"SELECT count(*) FROM app.product_categories WHERE {where}"  # noqa: S608
        total = (await s.execute(text(count_sql), params)).scalar_one()
        rows = await s.execute(
            text(
                "SELECT id, name, parent_id, archived_at, version FROM app.product_categories "  # noqa: S608
                f"WHERE {where} ORDER BY name, id OFFSET :offset LIMIT :limit"
            ),
            params,
        )
        return [_category(r) for r in rows], int(total)

    async def insert_category(
        self, s: AsyncSession, tenant_id: UUID, category_id: UUID, name: str, parent_id: UUID | None
    ) -> None:
        await s.execute(
            text(
                "INSERT INTO app.product_categories (id, tenant_id, parent_id, name) "
                "VALUES (:id, :tenant_id, :parent_id, :name)"
            ),
            {"id": category_id, "tenant_id": tenant_id, "parent_id": parent_id, "name": name},
        )

    async def update_category(
        self, s: AsyncSession, category_id: UUID, version: int, values: Mapping[str, Any]
    ) -> bool:
        cols = [k for k in values if k in _UPDATABLE_CATEGORY]
        assignments = ", ".join(f"{c} = :{c}" for c in cols)
        result = await s.execute(
            text(
                f"UPDATE app.product_categories SET {assignments}, version = version + 1 "  # noqa: S608
                "WHERE id = :id AND version = :version RETURNING 1"
            ),
            {**{c: values[c] for c in cols}, "id": category_id, "version": version},
        )
        return result.first() is not None

    async def category_ancestors(self, s: AsyncSession, category_id: UUID) -> list[UUID]:
        rows = await s.execute(
            text(
                "WITH RECURSIVE up(id, parent_id, depth) AS ("
                " SELECT id, parent_id, 0 FROM app.product_categories WHERE id = :id"
                " UNION ALL SELECT c.id, c.parent_id, up.depth + 1 FROM app.product_categories c"
                " JOIN up ON c.id = up.parent_id WHERE up.depth < 64)"
                " SELECT id FROM up"
            ),
            {"id": category_id},
        )
        return [r[0] for r in rows]

    async def set_category_archived(self, s: AsyncSession, category_id: UUID) -> None:
        await s.execute(
            text(
                "UPDATE app.product_categories SET archived_at = now(), version = version + 1 WHERE id = :id"
            ),
            {"id": category_id},
        )

    async def category_has_active_products(self, s: AsyncSession, category_id: UUID) -> bool:
        found = await s.execute(
            text("SELECT 1 FROM app.products WHERE category_id = :id AND archived_at IS NULL LIMIT 1"),
            {"id": category_id},
        )
        return found.first() is not None

    async def category_has_active_children(self, s: AsyncSession, category_id: UUID) -> bool:
        found = await s.execute(
            text(
                "SELECT 1 FROM app.product_categories WHERE parent_id = :id AND archived_at IS NULL LIMIT 1"
            ),
            {"id": category_id},
        )
        return found.first() is not None

    async def active_categories_by_name(self, s: AsyncSession) -> dict[str, UUID]:
        rows = await s.execute(
            text(
                "SELECT lower(name), id FROM app.product_categories WHERE archived_at IS NULL "
                "ORDER BY created_at DESC, id DESC"
            )
        )
        return {str(row[0]): row[1] for row in rows}

    async def vat_payer(self, s: AsyncSession, on: date) -> bool:
        """``tenant_tax_regimes`` in force on ``on``; no row → VAT payer (the general regime)."""
        regime = (
            await s.execute(
                text(
                    "SELECT regime FROM app.tenant_tax_regimes WHERE valid_from <= :d "
                    "ORDER BY valid_from DESC LIMIT 1"
                ),
                {"d": on},
            )
        ).scalar()
        return regime != "turnover"

    # --- products ---------------------------------------------------------------------------------
    async def get_product(self, s: AsyncSession, product_id: UUID, *, lock: bool = False) -> Product | None:
        sql = f"SELECT {_PRODUCT_COLUMNS} FROM app.products WHERE id = :id"  # noqa: S608
        row = (await s.execute(text(sql + (" FOR UPDATE" if lock else "")), {"id": product_id})).first()
        if row is None:
            return None
        return _product(row, tuple(await self.list_barcodes(s, product_id)))

    async def list_products(
        self, s: AsyncSession, flt: ProductFilter, offset: int, limit: int
    ) -> tuple[list[Product], int]:
        where = ["p.archived_at IS NOT NULL" if flt.archived else "p.archived_at IS NULL"]
        params: dict[str, Any] = {"offset": offset, "limit": limit}
        if flt.search:
            params["search"] = flt.search
            params["like"] = (
                "%" + flt.search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            )
            where.append(
                "(p.name ILIKE :like OR p.name_ru ILIKE :like OR EXISTS ("
                "SELECT 1 FROM app.product_barcodes b WHERE b.product_id = p.id AND b.barcode = :search))"
            )
        if flt.category_id is not None:
            where.append("p.category_id = :category_id")
            params["category_id"] = flt.category_id
        if flt.is_weighed is not None:
            where.append("p.is_weighed = :is_weighed")
            params["is_weighed"] = flt.is_weighed
        if flt.low_stock:
            scope = ""
            if flt.branch_ids is not None:
                scope = " AND w.branch_id = ANY(CAST(:branch_ids AS uuid[]))"
                params["branch_ids"] = [str(b) for b in flt.branch_ids]
            low = (
                "p.min_stock IS NOT NULL AND COALESCE((SELECT sum(sb.qty) FROM app.stock_balances sb "  # noqa: S608
                f"JOIN app.warehouses w ON w.id = sb.warehouse_id WHERE sb.product_id = p.id{scope}), 0) "
                "<= p.min_stock"
            )
            where.append(low)
        clause = " AND ".join(where)
        count_sql = f"SELECT count(*) FROM app.products p WHERE {clause}"  # noqa: S608
        total = (await s.execute(text(count_sql), params)).scalar_one()
        rows = list(
            await s.execute(
                text(
                    f"SELECT {_PRODUCT_COLUMNS} FROM app.products p WHERE {clause} "  # noqa: S608
                    "ORDER BY p.name, p.id OFFSET :offset LIMIT :limit"
                ),
                params,
            )
        )
        by_product: dict[UUID, list[Barcode]] = {}
        if rows:
            for b in await s.execute(_BARCODES_OF, {"ids": [r._mapping["id"] for r in rows]}):
                by_product.setdefault(b._mapping["product_id"], []).append(_barcode(b))
        items = [_product(r, tuple(by_product.get(r._mapping["id"], ()))) for r in rows]
        return items, int(total)

    async def insert_products(
        self, s: AsyncSession, tenant_id: UUID, rows: Sequence[Mapping[str, Any]]
    ) -> None:
        if not rows:
            return
        await s.execute(
            text(
                "INSERT INTO app.products (id, tenant_id, name, name_ru, category_id, unit_code, "
                "mxik_code, package_code, vat_rate, vat_exemption_code, is_marked, marking_group_code, "
                "is_weighed, min_stock) VALUES (:id, :tenant_id, :name, :name_ru, :category_id, :unit_code, "
                ":mxik_code, :package_code, :vat_rate, :vat_exemption_code, :is_marked, :marking_group_code, "
                ":is_weighed, :min_stock)"
            ),
            [{**row, "tenant_id": tenant_id} for row in rows],
        )

    async def update_product(
        self, s: AsyncSession, product_id: UUID, version: int, values: Mapping[str, Any]
    ) -> bool:
        cols = [k for k in values if k in _UPDATABLE_PRODUCT]
        assignments = ", ".join(f"{c} = :{c}" for c in cols)
        result = await s.execute(
            text(
                f"UPDATE app.products SET {assignments}, version = version + 1 "  # noqa: S608
                "WHERE id = :id AND version = :version RETURNING 1"
            ),
            {**{c: values[c] for c in cols}, "id": product_id, "version": version},
        )
        return result.first() is not None

    async def set_product_archived(self, s: AsyncSession, product_id: UUID, archived: bool) -> None:
        value = "now()" if archived else "NULL"
        await s.execute(
            text(f"UPDATE app.products SET archived_at = {value}, version = version + 1 WHERE id = :id"),  # noqa: S608
            {"id": product_id},
        )

    async def existing_product_ids(self, s: AsyncSession, product_ids: Sequence[UUID]) -> set[UUID]:
        if not product_ids:
            return set()
        rows = await s.execute(
            text("SELECT id FROM app.products WHERE id IN :ids").bindparams(bindparam("ids", expanding=True)),
            {"ids": list(product_ids)},
        )
        return {r[0] for r in rows}

    # --- barcodes ---------------------------------------------------------------------------------
    async def list_barcodes(self, s: AsyncSession, product_id: UUID) -> list[Barcode]:
        rows = await s.execute(_BARCODES_OF, {"ids": [product_id]})
        return [_barcode(r) for r in rows]

    async def insert_barcode(
        self,
        s: AsyncSession,
        tenant_id: UUID,
        product_id: UUID,
        barcode: str,
        kind: BarcodeKind,
        units_per_barcode: str,
    ) -> Barcode | None:
        row = (
            await s.execute(
                text(
                    "INSERT INTO app.product_barcodes (id, tenant_id, product_id, barcode, kind, "
                    "units_per_barcode) VALUES (:id, :tenant_id, :product_id, :barcode, :kind, "
                    "CAST(:units AS numeric)) "
                    "ON CONFLICT (tenant_id, barcode) DO NOTHING "
                    "RETURNING id, product_id, barcode, kind, units_per_barcode"
                ),
                {
                    "id": uuid7(),
                    "tenant_id": tenant_id,
                    "product_id": product_id,
                    "barcode": barcode,
                    "kind": kind,
                    "units": units_per_barcode,
                },
            )
        ).first()
        return _barcode(row) if row else None

    async def insert_barcodes(
        self, s: AsyncSession, tenant_id: UUID, rows: Sequence[Mapping[str, Any]]
    ) -> int:
        if not rows:
            return 0
        await s.execute(
            text(
                "INSERT INTO app.product_barcodes (id, tenant_id, product_id, barcode, kind, "
                "units_per_barcode) VALUES (:id, :tenant_id, :product_id, :barcode, :kind, 1)"
            ),
            [{"id": uuid7(), "tenant_id": tenant_id, "kind": "ean", **row} for row in rows],
        )
        return len(rows)

    async def taken_barcodes(self, s: AsyncSession, barcodes: Sequence[str]) -> set[str]:
        if not barcodes:
            return set()
        rows = await s.execute(
            text("SELECT barcode FROM app.product_barcodes WHERE barcode IN :codes").bindparams(
                bindparam("codes", expanding=True)
            ),
            {"codes": list(barcodes)},
        )
        return {r[0] for r in rows}

    async def delete_barcode(self, s: AsyncSession, product_id: UUID, barcode_id: UUID) -> Barcode | None:
        row = (
            await s.execute(
                text(
                    "DELETE FROM app.product_barcodes WHERE id = :id AND product_id = :product_id "
                    "RETURNING id, product_id, barcode, kind, units_per_barcode"
                ),
                {"id": barcode_id, "product_id": product_id},
            )
        ).first()
        return _barcode(row) if row else None

    async def lock_internal_seq(self, s: AsyncSession, tenant_id: UUID) -> int:
        await s.execute(
            text(
                "INSERT INTO app.internal_barcode_seq (tenant_id) VALUES (:t) "
                "ON CONFLICT (tenant_id) DO NOTHING"
            ),
            {"t": tenant_id},
        )
        value = (
            await s.execute(
                text("SELECT next_value FROM app.internal_barcode_seq WHERE tenant_id = :t FOR UPDATE"),
                {"t": tenant_id},
            )
        ).scalar_one()
        return int(value)

    async def set_internal_seq(self, s: AsyncSession, tenant_id: UUID, next_value: int) -> None:
        await s.execute(
            text("UPDATE app.internal_barcode_seq SET next_value = :v WHERE tenant_id = :t"),
            {"v": next_value, "t": tenant_id},
        )

    # --- label queue ------------------------------------------------------------------------------
    async def queue_labels(
        self, s: AsyncSession, tenant_id: UUID, product_ids: Sequence[UUID], reason: str
    ) -> None:
        """One pending row per (product, reason): a still-unprinted entry is not duplicated."""
        if not product_ids:
            return
        await s.execute(
            text(
                "INSERT INTO app.label_print_queue (id, tenant_id, product_id, reason) "
                "SELECT :id, :tenant_id, :product_id, :reason WHERE NOT EXISTS ("
                " SELECT 1 FROM app.label_print_queue q WHERE q.product_id = :product_id"
                " AND q.reason = :reason AND q.printed_at IS NULL)"
            ),
            [
                {"id": uuid7(), "tenant_id": tenant_id, "product_id": pid, "reason": reason}
                for pid in dict.fromkeys(product_ids)
            ],
        )
