"""The cost-line analytics contract (13 §1 analytics, §3.3 recost). Pure Python.

Every ledger line that books the *stock cost* of an issue — ``Dt 9120|2970|9430|4730|5910|6010… /
Kt inv_acct`` — is written **one per issued (document line, product, warehouse)** with::

    analytics = {
        "stock_cost": true,            # marker: this line mirrors stock_moves cost
        "product_id": "<uuid>",
        "warehouse_id": "<uuid>",
        "line_id": "<uuid of the document line>",
        "lot_ids": ["<uuid>", ...],    # 13 §1 "partiya" analytics (informational)
        ...caller extras (employee_id, expense_category_id, …)
    }

and ``ledger_entries.doc_type/doc_id`` = the issue document. The amount always equals
``−Σ stock_moves.cost_amount`` of that ``(doc_type, doc_id, line_id, warehouse, product)``.
Recost (13 §3.3) finds the lines by ``doc_type, doc_id`` + JSON containment of
:func:`cost_line_key` and, when the stock cost changed, writes storno + a new line with the same
accounts and analytics plus ``recost_job_id`` (and ``correction_of_period`` when the original
period is closed). Use :func:`cost_analytics` (or ``StockTxn.issue(cost=CostPosting(...))``, which
writes the line itself) — never hand-build these dicts.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, Final
from uuid import UUID

COST_MARKER: Final = "stock_cost"
RESERVED_KEYS: Final = frozenset(
    {COST_MARKER, "product_id", "warehouse_id", "line_id", "lot_ids", "recost_job_id", "correction_of_period"}
)


def cost_line_key(*, product_id: UUID, warehouse_id: UUID, line_id: UUID) -> dict[str, Any]:
    """The JSON-containment filter that identifies the cost line(s) of one issued line."""
    return {
        COST_MARKER: True,
        "product_id": str(product_id),
        "warehouse_id": str(warehouse_id),
        "line_id": str(line_id),
    }


def cost_analytics(
    *,
    product_id: UUID,
    warehouse_id: UUID,
    line_id: UUID,
    lot_ids: Iterable[UUID | None] = (),
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    clash = RESERVED_KEYS & set(extra or {})
    if clash:
        raise ValueError(f"analytics keys reserved by the cost-line contract: {sorted(clash)}")
    lots = sorted({str(lot) for lot in lot_ids if lot is not None})
    return {
        **cost_line_key(product_id=product_id, warehouse_id=warehouse_id, line_id=line_id),
        "lot_ids": lots,
        **(extra or {}),
    }
