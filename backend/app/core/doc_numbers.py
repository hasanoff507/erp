"""Server-side document numbers (11 §11, 12 §2.9 ``doc_sequences``).

``{tur}-{filial kodi}-{yil}-{ketma-ket}``, e.g. ``C-01-2026-000001``. The
counter lives in ``app.doc_sequences`` and is advanced by ``app.next_doc_number``
(an ``INSERT … ON CONFLICT DO UPDATE``), so two concurrent posts of the same
type in the same branch never get the same number. Call it inside the posting
``tenant_transaction``: a rolled-back post does not consume a number.
"""

from __future__ import annotations

from typing import Final
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# 12 §2.9 (aniqlashtirish #12) — append-only list
DOC_TYPE_CODES: Final[dict[str, str]] = {
    "sales": "K",
    "returns": "V",
    "purchase_orders": "Z",
    "goods_receipts": "M",
    "supplier_returns": "MV",
    "transfers": "P",
    "stock_counts": "I",
    "write_offs": "L",
    "price_changes": "C",
    "stock_openings": "OO",
    "debt_openings": "OD",
    "debt_payments": "DP",
    "debt_writeoffs": "DW",
    "supplier_payments": "SP",
    "expenses": "E",
    "cash_movements": "CM",
    "ledger_adjustments": "BX",
    "bank_settlements": "BT",
    "tax_settlements": "ST",
}

_NEXT = text(
    "SELECT app.next_doc_number(:tenant_id, b.id, b.code, :doc_type, :year) "
    "FROM app.branches b WHERE b.id = :branch_id AND b.tenant_id = :tenant_id"
)


async def next_doc_number(
    session: AsyncSession, *, tenant_id: UUID, branch_id: UUID, table: str, year: int
) -> str:
    """Next number for ``table`` (a 12 §2.9 document table name) in ``branch_id``/``year``."""
    code = DOC_TYPE_CODES[table]
    number = (
        await session.execute(
            _NEXT, {"tenant_id": tenant_id, "branch_id": branch_id, "doc_type": code, "year": year}
        )
    ).scalar_one_or_none()
    if number is None:
        raise LookupError(f"branch {branch_id} not found in tenant {tenant_id}")
    return str(number)
