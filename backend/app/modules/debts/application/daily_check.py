"""Daily debt check (US-M08-03, US-M08-09, US-M08-10; QT-M08-05, QT-M08-12) — one run per tenant per day.

* ``debt_due_today`` — customers whose promise date (``counterparties.debt_due_date``, else the earliest
  ``due_date`` of their open documents) is today or already passed: «bugun to'lashi kerak: N kishi, S so'm»
  plus, per customer, a reminder **draft** for the Owner (``requires_confirmation: true`` — nothing is sent
  to the
  customer automatically). AI-06 writes the draft from Bosqich 6 (09); until then the deterministic template
  of
  :func:`app.modules.debts.domain.documents.reminder_text` (``source='template'``) is used.
* ``debt_aging_60`` — customers with an open document older than 60 days (``COALESCE(due_date, doc_date)``):
  a reminder list only — the system never sets a doubtful flag by itself (US-M08-10, 18 §12.6).

Both are recorded through the notifications outbox in the cron's tenant transaction with the dedupe key
``<kind>:<date>`` — a second run the same day records nothing (b4-telegram delivers them).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Final, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.money import money, money_str
from app.modules.debts.application.doc_ports import DebtDocsRepository
from app.modules.debts.application.open_docs import reconciled_targets
from app.modules.debts.domain.documents import reminder_text

ZERO: Final = Decimal("0.00")
AGING_DAYS: Final = 60
MAX_ITEMS: Final = 50


class EventRecorderPort(Protocol):
    async def record_event(
        self, s: AsyncSession, tenant_id: UUID, kind: str, payload: Mapping[str, Any], dedupe_key: str
    ) -> bool: ...


@dataclass(frozen=True, slots=True)
class DailyCheckResult:
    due_today: int
    aging_60: int
    recorded: tuple[str, ...]

    def as_json(self) -> dict[str, Any]:
        return {"due_today": self.due_today, "aging_60": self.aging_60, "recorded": list(self.recorded)}


class DebtDailyCheck:
    def __init__(self, repo: DebtDocsRepository, events: EventRecorderPort) -> None:
        self._repo = repo
        self._events = events

    async def run(self, s: AsyncSession, tenant_id: UUID, today: date) -> DailyCheckResult:
        debtors = await self._repo.debtors(s, "receivable")
        ids = [d["counterparty_id"] for d in debtors]
        docs = await reconciled_targets(
            self._repo, s, ids, balances={d["counterparty_id"]: money(d["balance"]) for d in debtors}
        )
        shop = await self._repo.tenant_name(s)
        due_items: list[dict[str, Any]] = []
        aging_items: list[dict[str, Any]] = []
        limit = today - timedelta(days=AGING_DAYS)
        for d in debtors:
            open_docs = [t for t in docs.get(d["counterparty_id"], []) if t.doc_type != "debt_writeoffs"]
            if not open_docs:
                continue
            balance = money(d["balance"])
            dues = [t.due_date for t in open_docs if t.due_date is not None]
            promise: date | None = d["debt_due_date"] or (min(dues) if dues else None)
            base = {
                "counterparty_id": str(d["counterparty_id"]),
                "name": d["name"],
                "phone": d["phone"],
                "amount": money_str(balance),
            }
            if promise is not None and promise <= today:
                due_items.append(
                    base
                    | {
                        "due_date": promise.isoformat(),
                        "overdue_days": (today - promise).days,
                        "reminder": {
                            "text": reminder_text(d["name"], money_str(balance), promise, shop),
                            "source": "template",
                            "requires_confirmation": True,
                        },
                    }
                )
            oldest = min((t.due_date or t.doc_date) for t in open_docs)
            if oldest < limit:
                aging_items.append(base | {"oldest_date": oldest.isoformat(), "days": (today - oldest).days})
        recorded: list[str] = []
        if due_items:
            total = sum((Decimal(i["amount"]) for i in due_items), ZERO)
            if await self._events.record_event(
                s,
                tenant_id,
                "debt_due_today",
                {
                    "date": today.isoformat(),
                    "count": len(due_items),
                    "total": money_str(total),
                    "items": due_items[:MAX_ITEMS],
                },
                f"debt_due_today:{today.isoformat()}",
            ):
                recorded.append("debt_due_today")
        if aging_items:
            aging_items.sort(key=lambda i: (-i["days"], i["counterparty_id"]))
            total = sum((Decimal(i["amount"]) for i in aging_items), ZERO)
            if await self._events.record_event(
                s,
                tenant_id,
                "debt_aging_60",
                {
                    "date": today.isoformat(),
                    "count": len(aging_items),
                    "total": money_str(total),
                    "items": aging_items[:MAX_ITEMS],
                    "auto_flagged": False,
                },
                f"debt_aging_60:{today.isoformat()}",
            ):
                recorded.append("debt_aging_60")
        return DailyCheckResult(len(due_items), len(aging_items), tuple(recorded))
