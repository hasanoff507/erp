"""Cross-module contract of the cash module (Bosqich 3 coordination file).

Owner: cash slice. Consumers (sales/returns posting) obtain an instance via
``app.modules.cash.wiring.shift_guard()`` and call it inside their own tenant transaction.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.sync.application.handlers import SyncExceptionRow


@dataclass(frozen=True, slots=True)
class OpenShift:
    id: UUID
    branch_id: UUID
    cash_register_id: UUID
    device_id: UUID
    shift_no: int
    opened_at: datetime
    closed_at: datetime | None = None  # set → the document is late into a closed shift (ACC-01)

    @property
    def late(self) -> bool:
        return self.closed_at is not None


class ShiftGuard(Protocol):
    async def require_open(
        self, s: AsyncSession, *, shift_id: UUID, device_id: UUID, at: datetime
    ) -> OpenShift:
        """Lock (``FOR SHARE``) and return the shift a POS document belongs to.

        ``DEPENDENCY_NOT_SYNCED`` (``params.entity='shifts'``, retryable) — unknown shift (its
        ``shift.opened`` is not accepted yet, 16 §3.3); ``SHIFT_DEVICE_MISMATCH`` — the shift was opened on
        another device (QT-SEQ-02); ``SHIFT_NOT_OPEN`` — the shift was closed before ``at``. A document
        created while the shift was open but accepted after the close is accepted
        (``OpenShift.late``); the caller
        then calls :meth:`settle_late` after posting its ``cash_moves`` (18 §3.2, 13 X-01).
        """
        ...

    async def settle_late(
        self, s: AsyncSession, *, tenant_id: UUID, shift: OpenShift, doc_type: str, doc_id: UUID
    ) -> SyncExceptionRow | None:
        """Late document in a closed shift (ACC-01): add the document's cash delta (``Σ cash_moves`` of
        ``doc_type``/``doc_id`` with ``method='cash'`` in the shift) to ``shifts.expected_cash``, post the
        variance correction (4730/9390 ↔ 5010, ``doc_type='shifts'``) and return the
        ``sync_exceptions(kind='late_in_closed_shift')`` row for the caller's ``HandlerResult``. The
        fiscalized Z-report is not re-issued. ``None`` when the shift is open or the delta is zero."""
        ...
