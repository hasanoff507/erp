"""Pricing SQL (12 ``product_prices``, ``price_changes``, ``price_change_lines``, ``label_print_queue``,
``approval_requests``). Runs inside the caller's ``tenant_transaction`` (RLS-bound)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import Row, bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.base import uuid7
from app.modules.pricing.domain.price_changes import PriceChange, PriceChangeLine
from app.modules.pricing.domain.resolution import PriceRecord

_PRICE_COLS = "id, product_id, branch_id, price, valid_from, set_by, price_change_doc_id"


def _record(row: Row[Any]) -> PriceRecord:
    m = row._mapping
    return PriceRecord(
        id=m["id"],
        product_id=m["product_id"],
        branch_id=m["branch_id"],
        price=m["price"],
        valid_from=m["valid_from"],
        set_by=m["set_by"],
        price_change_doc_id=m["price_change_doc_id"],
    )


def _expanding(sql: str, name: str) -> Any:
    return text(sql).bindparams(bindparam(name, expanding=True))


class SqlPricingRepository:
    async def price_records(self, s: AsyncSession, product_ids: Sequence[UUID]) -> list[PriceRecord]:
        if not product_ids:
            return []
        rows = await s.execute(
            _expanding(f"SELECT {_PRICE_COLS} FROM app.product_prices WHERE product_id IN :ids", "ids"),  # noqa: S608
            {"ids": list(dict.fromkeys(product_ids))},
        )
        return [_record(r) for r in rows]

    async def series(self, s: AsyncSession, product_id: UUID, branch_id: UUID | None) -> list[PriceRecord]:
        cond = "branch_id = :branch_id" if branch_id is not None else "branch_id IS NULL"
        rows = await s.execute(
            text(f"SELECT {_PRICE_COLS} FROM app.product_prices WHERE product_id = :pid AND {cond}"),  # noqa: S608
            {"pid": product_id, "branch_id": branch_id},
        )
        return [_record(r) for r in rows]

    async def current_prices(
        self, s: AsyncSession, product_ids: Sequence[UUID], branch_id: UUID | None, at: datetime
    ) -> dict[UUID, Decimal]:
        """One query for a page of products — the SQL twin of ``resolution.effective_record``.

        The branch row (``branch_id IS NULL`` sorts last) beats the global one; within a series the
        latest ``valid_from`` wins, ties broken by the later UUIDv7 ``id``; future rows are ignored.
        """
        if not product_ids:
            return {}
        series = "(branch_id IS NULL OR branch_id = :branch_id)" if branch_id else "branch_id IS NULL"
        rows = await s.execute(
            _expanding(
                "SELECT DISTINCT ON (product_id) product_id, price FROM app.product_prices "  # noqa: S608
                f"WHERE product_id IN :ids AND valid_from <= :at AND {series} "
                "ORDER BY product_id, (branch_id IS NULL), valid_from DESC, id DESC",
                "ids",
            ),
            {"ids": list(dict.fromkeys(product_ids)), "at": at, "branch_id": branch_id},
        )
        return {r[0]: r[1] for r in rows}

    async def user_names(self, s: AsyncSession, user_ids: Sequence[UUID]) -> dict[UUID, str]:
        """Display names; ``app.users`` RLS shows only members of the current tenant (12 §6.1)."""
        if not user_ids:
            return {}
        rows = await s.execute(
            _expanding("SELECT id, name FROM app.users WHERE id IN :ids", "ids"),
            {"ids": list(dict.fromkeys(user_ids))},
        )
        return {r[0]: r[1] for r in rows}

    async def default_branch_id(self, s: AsyncSession) -> UUID | None:
        row = (
            await s.execute(
                text(
                    "SELECT id FROM app.branches WHERE archived_at IS NULL "
                    "ORDER BY is_default DESC, code, id LIMIT 1"
                )
            )
        ).first()
        return row[0] if row else None

    async def existing_branch_ids(self, s: AsyncSession, branch_ids: Sequence[UUID]) -> set[UUID]:
        if not branch_ids:
            return set()
        rows = await s.execute(
            _expanding("SELECT id FROM app.branches WHERE archived_at IS NULL AND id IN :ids", "ids"),
            {"ids": list(branch_ids)},
        )
        return {r[0] for r in rows}

    async def product_archived_flags(self, s: AsyncSession, product_ids: Sequence[UUID]) -> dict[UUID, bool]:
        if not product_ids:
            return {}
        rows = await s.execute(
            _expanding("SELECT id, archived_at IS NOT NULL FROM app.products WHERE id IN :ids", "ids"),
            {"ids": list(dict.fromkeys(product_ids))},
        )
        return {r[0]: bool(r[1]) for r in rows}

    async def product_exists(self, s: AsyncSession, product_id: UUID) -> bool:
        found = await s.execute(text("SELECT 1 FROM app.products WHERE id = :id"), {"id": product_id})
        return found.first() is not None

    async def insert_price_change(self, s: AsyncSession, row: Mapping[str, Any]) -> None:
        await s.execute(
            text(
                "INSERT INTO app.price_changes (id, tenant_id, branch_id, doc_date, created_by, comment) "
                "VALUES (:id, :tenant_id, :branch_id, :doc_date, :created_by, :comment)"
            ),
            dict(row),
        )

    async def insert_lines(self, s: AsyncSession, rows: Sequence[Mapping[str, Any]]) -> None:
        await s.execute(
            text(
                "INSERT INTO app.price_change_lines (id, tenant_id, price_change_id, line_no, product_id, "
                "branch_id, old_price, new_price, valid_from) VALUES (:id, :tenant_id, :price_change_id, "
                ":line_no, :product_id, :branch_id, :old_price, :new_price, :valid_from)"
            ),
            [dict(r) for r in rows],
        )

    async def get_price_change(
        self, s: AsyncSession, doc_id: UUID, *, lock: bool = False
    ) -> PriceChange | None:
        head = (
            await s.execute(
                text(
                    "SELECT id, branch_id, number, doc_date, status, comment, created_by, posted_at "
                    "FROM app.price_changes WHERE id = :id" + (" FOR UPDATE" if lock else "")
                ),
                {"id": doc_id},
            )
        ).first()
        if head is None:
            return None
        lines = await s.execute(
            text(
                "SELECT id, line_no, product_id, branch_id, old_price, new_price, valid_from "
                "FROM app.price_change_lines WHERE price_change_id = :id ORDER BY line_no"
            ),
            {"id": doc_id},
        )
        m = head._mapping
        return PriceChange(
            id=m["id"],
            branch_id=m["branch_id"],
            number=m["number"],
            doc_date=m["doc_date"],
            status=m["status"],
            comment=m["comment"],
            created_by=m["created_by"],
            posted_at=m["posted_at"],
            lines=tuple(
                PriceChangeLine(
                    id=r[0],
                    line_no=r[1],
                    product_id=r[2],
                    branch_id=r[3],
                    old_price=r[4],
                    new_price=r[5],
                    valid_from=r[6],
                )
                for r in lines
            ),
        )

    async def set_old_prices(self, s: AsyncSession, values: Mapping[UUID, Any]) -> None:
        if not values:
            return
        await s.execute(
            text("UPDATE app.price_change_lines SET old_price = :old WHERE id = :id"),
            [{"id": lid, "old": old} for lid, old in values.items()],
        )

    async def mark_posted(self, s: AsyncSession, doc_id: UUID, number: str) -> None:
        await s.execute(
            text(
                "UPDATE app.price_changes SET status = 'posted', number = :n, posted_at = now() "
                "WHERE id = :id"
            ),
            {"id": doc_id, "n": number},
        )

    async def mark_pending(self, s: AsyncSession, doc_id: UUID) -> None:
        await s.execute(
            text("UPDATE app.price_changes SET status = 'pending_approval' WHERE id = :id"), {"id": doc_id}
        )

    async def insert_prices(self, s: AsyncSession, rows: Sequence[Mapping[str, Any]]) -> None:
        if not rows:
            return
        await s.execute(
            text(
                "INSERT INTO app.product_prices (id, tenant_id, product_id, branch_id, price, valid_from, "
                "set_by, price_change_doc_id) VALUES (:id, :tenant_id, :product_id, :branch_id, :price, "
                ":valid_from, :set_by, :price_change_doc_id)"
            ),
            [dict(r) for r in rows],
        )

    async def insert_approval_request(self, s: AsyncSession, row: Mapping[str, Any]) -> None:
        await s.execute(
            text(
                "INSERT INTO app.approval_requests (id, tenant_id, branch_id, kind, permission_code, "
                "requested_value, context, linked_doc_type, linked_doc_id, requested_by, expires_at) VALUES "
                "(:id, :tenant_id, :branch_id, :kind, :permission_code, :requested_value, "
                "CAST(:context AS jsonb), :linked_doc_type, :linked_doc_id, :requested_by, :expires_at)"
            ),
            dict(row),
        )

    async def queue_labels(
        self, s: AsyncSession, tenant_id: UUID, product_ids: Sequence[UUID], reason: str
    ) -> None:
        """US-M09-04: one pending (unprinted) row per product and reason."""
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
