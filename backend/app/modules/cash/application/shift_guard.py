"""The :class:`~app.modules.cash.application.contracts.ShiftGuard` implementation (18 §3.1, 16 §3.3).

The shift row is locked ``FOR SHARE`` — a concurrent ``shift.closed`` (``FOR UPDATE``) waits for the
document's transaction, so a closing Z-report always sees every document accepted before it.

Late document (ACC-01, 13 X-01): created before ``closed_at`` but accepted after the close. It is accepted
(the cash really moved); :meth:`ShiftGuardService.settle_late` moves ``expected_cash`` by the document's
cash delta and posts the change of the variance line (shortage 4730 / overage 9390 against 5010) so 5010
is not moved twice. The fiscalized Z-report stays as issued.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from app.modules.accounting.wiring import LedgerLine, LedgerPoster, business_date
from app.modules.cash.application.contracts import OpenShift
from app.modules.cash.application.ports import CashRepository
from app.modules.cash.domain.shifts import m2, variance_correction
from app.modules.sync.application.handlers import SyncExceptionRow

LATE_NOTE = "Smena yopilgandan keyin qabul qilingan hujjat bo'yicha tuzatish"


class ShiftGuardService:
    def __init__(self, repo: CashRepository, poster: LedgerPoster | None = None) -> None:
        self._repo = repo
        self._poster = poster

    async def require_open(
        self, s: AsyncSession, *, shift_id: UUID, device_id: UUID, at: datetime
    ) -> OpenShift:
        row = await self._repo.get_shift(s, shift_id, lock="share")
        if row is None:
            # its shift.opened is not accepted yet — retry later (16 §3.3, SYNC-06)
            raise AppError(
                ErrorCode.DEPENDENCY_NOT_SYNCED, params={"entity": "shifts", "shift_id": str(shift_id)}
            )
        if row.device_id != device_id:
            raise AppError(ErrorCode.SHIFT_DEVICE_MISMATCH, params={"shift_id": str(shift_id)})  # QT-SEQ-02
        if row.status != "open" and (row.closed_at is None or at > row.closed_at):
            raise AppError(ErrorCode.SHIFT_NOT_OPEN, params={"shift_id": str(shift_id), "status": row.status})
        return OpenShift(
            id=row.id,
            branch_id=row.branch_id,
            cash_register_id=row.cash_register_id,
            device_id=row.device_id,
            shift_no=row.shift_no,
            opened_at=row.opened_at,
            closed_at=row.closed_at if row.status != "open" else None,
        )

    async def settle_late(
        self, s: AsyncSession, *, tenant_id: UUID, shift: OpenShift, doc_type: str, doc_id: UUID
    ) -> SyncExceptionRow | None:
        if not shift.late:
            return None
        if self._poster is None:
            raise RuntimeError(
                "ShiftGuardService.settle_late needs a LedgerPoster (cash.wiring.shift_guard())"
            )
        delta = await self._repo.doc_cash_delta(s, shift.id, doc_type, doc_id)
        if delta == 0:
            return None
        row = await self._repo.get_shift(s, shift.id, lock="update")
        if row is None or row.expected_cash is None or row.counted_cash is None:
            return None
        before = row.counted_cash - row.expected_cash
        after = before - delta
        await self._repo.adjust_expected(s, shift.id, delta, LATE_NOTE)
        lines = variance_correction(
            before, after, cashier_id=row.opened_by, cash_register_id=row.cash_register_id, shift_id=row.id
        )
        if lines:
            entry_date = await self._poster.first_open_date(s, business_date(datetime.now(UTC)))
            await self._poster.post(
                s,
                tenant_id,
                "shifts",
                row.id,
                [
                    LedgerLine(
                        entry_date,
                        row.branch_id,
                        ln.account_dt,
                        ln.account_kt,
                        ln.amount,
                        {**ln.analytics, "late_doc_type": doc_type, "late_doc_id": str(doc_id)},
                    )
                    for ln in lines
                ],
            )
        return SyncExceptionRow(
            kind="late_in_closed_shift",
            details={
                "shift_id": str(row.id),
                "cash_delta": m2(delta),
                "expected_cash_before": m2(row.expected_cash),
                "expected_cash_after": m2(row.expected_cash + delta),
                "variance_before": m2(before),
                "variance_after": m2(after),
            },
            doc_type=doc_type,
            doc_id=doc_id,
        )
