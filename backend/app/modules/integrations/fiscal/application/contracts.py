"""Cross-module fiscal contract (21 §1 FiscalPort, 18 §4.5/§4.10, 16 §6, qaror #43) — B3 coordination file.

Owner: sales slice (it builds the fiscal package with ``ERP_FISCAL_PROVIDER=fake``). Consumers: sales,
returns, cash (Z-report) — via ``app.modules.integrations.fiscal.wiring.fiscal_service(settings)``,
inside their posting transaction.

Usage (inside the posting ``tenant_transaction``)::

    fiscal = fiscal_service(settings)
    await fiscal.assert_can_issue(s, cash_register_id=cr, at=effective_created_at)   # sale/return
    ref = await fiscal.record(s, kind="sale", doc_id=sale.id, ..., created_at=effective_created_at)
    # after COMMIT (HandlerResult.after_commit / after the REST transaction):
    await fiscal.enqueue(tenant_id, [ref.id])

``record`` writes the ``fiscal_receipts`` row and — for the server-side providers (``fake`` in B3,
``partner_cloud`` later) — its ``outbox_jobs(kind='ofd_send')`` row in the caller's transaction; the
worker fiscalizes after commit (``enqueue`` is best effort, the per-minute cron sweeper is the backstop).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

FiscalKind = Literal["sale", "return", "z_report", "debt_settlement", "credit_sale"]
PaymentForm = Literal["cash", "card", "qr", "mixed"]


@dataclass(frozen=True, slots=True)
class FiscalReceiptRef:
    id: UUID
    status: str  # pending | sent | fiscalized | failed
    receipt_seq: int | None  # after a QT-M01-23 renumbering: the new value (≠ the requested one)
    fm_receipt_seq: int | None
    fiscal_sign: str | None
    qr_url: str | None
    ofd_acked_at: datetime | None
    renumbered_from: int | None = None  # device receipt_seq when the server renumbered (§4.6)


class FiscalService(Protocol):
    async def assert_can_issue(self, s: AsyncSession, *, cash_register_id: UUID, at: datetime) -> None:
        """``FISCAL_DEVICE_LOCKED`` when ``cash_registers.fm_state`` is not ok; ``FISCAL_OFFLINE_48H_BLOCKED``
        when the oldest receipt of the register with ``ofd_acked_at IS NULL`` is ≥ 48 h older than ``at``
        (``at`` = the server-clamped event time, 16 §8; QT-OFFLINE48-01…04). Called before posting
        sale/return/debt_settlement — never for the Z-report."""
        ...

    async def record(
        self,
        s: AsyncSession,
        *,
        kind: FiscalKind,
        doc_id: UUID,
        cash_register_id: UUID,
        shift_id: UUID,
        receipt_seq: int | None,
        payment_form: PaymentForm | None,
        payload: Mapping[str, Any],
        fiscal_result: Mapping[str, Any] | None,
        is_offline: bool,
        offline_since: datetime | None,
        delivery: Literal["printed", "electronic"] = "printed",
        delivery_reason: str | None = None,
        created_at: datetime | None = None,
    ) -> FiscalReceiptRef:
        """Insert the ``fiscal_receipts`` row (``doc_id`` goes to sale_id/return_id/debt_payment_id by kind;
        ignored for ``z_report``). ``created_at`` — when the receipt was made (event time; default now) —
        drives the 48 h timer.

        ``fiscal_result`` from the device (local bridge) → stored as ``fiscalized`` (``ofd_acked_at`` NULL);
        otherwise the configured provider (``fake`` in B3) fiscalizes after commit via ``ofd_send``.
        A second receipt with the same ``(cash_register_id, shift_id, receipt_seq)``: without
        ``fiscal_result`` → ``RECEIPT_SEQ_CONFLICT`` (QT-SEQ-01); with it → renumbered to the shift's
        ``max + 1`` (``renumbered_from`` set, ``payload.device_receipt_seq``; QT-M01-23). A second
        ``z_report`` for a shift → ``VALIDATION_ERROR`` (QT-SEQ-03)."""
        ...

    async def enqueue(self, tenant_id: UUID, receipt_ids: Sequence[UUID]) -> None:
        """After COMMIT: queue the ``ofd_send`` jobs of these receipts (best effort; failures are logged)."""
        ...
