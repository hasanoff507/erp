"""``GET /sales`` and ``GET /sales/{id}`` (18 §4.8) — read-only; there is no ``POST /sales`` (POS events)."""

from __future__ import annotations

import base64
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.db.session import tenant_transaction
from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from app.core.money import money_str, price_str, qty_str
from app.core.permissions import BranchScope
from app.modules.sales.application.ports import SaleFilter, SalesRepository


def encode_cursor(at: datetime, doc_id: UUID) -> str:
    return base64.urlsafe_b64encode(f"{at.isoformat()}|{doc_id}".encode()).decode()


def decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    try:
        at, doc_id = base64.urlsafe_b64decode(cursor.encode()).decode().split("|", 1)
        return datetime.fromisoformat(at), UUID(doc_id)
    except (ValueError, UnicodeDecodeError):
        raise AppError(ErrorCode.VALIDATION_ERROR, params={"field": "cursor"}) from None


def jsonable(value: Any, key: str = "") -> Any:
    """Money/qty/price as decimal strings (by column), dates ISO, UUIDs as strings."""
    if isinstance(value, dict):
        return {k: jsonable(v, k) for k, v in value.items()}
    if isinstance(value, list):
        return [jsonable(v, key) for v in value]
    if isinstance(value, Decimal):
        if key in ("qty", "returned_qty"):
            return qty_str(value)
        if key == "price":
            return price_str(value)
        if key in ("vat_rate", "discount_pct"):
            return format(value.quantize(Decimal("0.01")), "f")
        return money_str(value)
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    return value


def in_scope(scope: BranchScope, branch_id: UUID) -> bool:
    if scope.current is not None and branch_id != scope.current:
        return False
    return scope.unrestricted or branch_id in scope.allowed


def scope_branches(scope: BranchScope) -> tuple[UUID, ...] | None:
    if scope.current is not None:
        return (scope.current,)
    return None if scope.unrestricted else scope.allowed


class SaleQueries:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession], repo: SalesRepository) -> None:
        self._sf = session_factory
        self._repo = repo

    async def list_page(
        self, tenant_id: UUID, user_id: UUID, flt: SaleFilter, cursor: str | None, limit: int
    ) -> dict[str, Any]:
        after = decode_cursor(cursor) if cursor else None
        async with self._sf() as s, tenant_transaction(s, tenant_id, user_id=user_id):
            rows = await self._repo.page(s, flt, after, limit + 1)
        page = rows[:limit]
        items = []
        for r in page:
            payments = [
                {"method": p["method"], "amount": money_str(Decimal(str(p["amount"])))}
                for p in r["payments"] or []
            ]
            items.append(
                {
                    "id": str(r["id"]), "number": r["number"], "temp_number": r["temp_number"],
                    "doc_date": r["doc_date"].isoformat(), "status": r["status"],
                    "total_amount": money_str(r["total_amount"] or 0), "payments_summary": payments,
                    "counterparty_id": jsonable(r["counterparty_id"]), "is_offline": r["is_offline"],
                    "has_returns": r["has_returns"], "shift_id": str(r["shift_id"]),
                    "cash_register_id": str(r["cash_register_id"]), "branch_id": str(r["branch_id"]),
                    "created_at": jsonable(r["created_at"]),
                }
            )  # fmt: skip
        next_cursor = encode_cursor(page[-1]["created_at"], page[-1]["id"]) if len(rows) > limit else None
        return {"items": items, "next_cursor": next_cursor}

    async def get(self, tenant_id: UUID, user_id: UUID, scope: BranchScope, sale_id: UUID) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, tenant_id, user_id=user_id):
            found = await self._repo.get(s, sale_id)
        if found is None or not in_scope(scope, found["branch_id"]):
            raise AppError(ErrorCode.NOT_FOUND, params={"resource": "sale"})
        body: dict[str, Any] = jsonable(found)
        for line in body["lines"]:
            line["sale_line_id"] = line["id"]
        return body
