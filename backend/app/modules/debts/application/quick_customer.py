"""``counterparty.created`` — the POS quick customer (18 §11.1, US-M08-05, QT-M08-08), offline too.

Name + phone only (``debts.create``, checked by ``/sync/push``); the row is the same ``counterparties`` row
the
back-office creates (18 §11.2 quick customer). Dedupe is ``client_event_id`` (``sync_receipts``); the same
``id``
arriving again with the same name and phone (e.g. re-sent after a lost answer under a new event id) is
answered
with the existing row, a different body under a taken ``id`` is ``VALIDATION_ERROR``
(``validation.duplicate_id``).
Phones are not unique: two devices may create the same person offline — nothing is merged automatically.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit
from app.modules.debts.application.counterparties import COUNTERPARTY_FIELDS, invalid_field, validate_row
from app.modules.debts.application.payloads import CounterpartyCreatedPayload, parse
from app.modules.debts.application.ports import CounterpartyRepository
from app.modules.sync.application.handlers import EventContext, HandlerResult


class CounterpartyCreatedHandler:
    def __init__(self, repo: CounterpartyRepository) -> None:
        self._repo = repo

    async def __call__(self, s: AsyncSession, ctx: EventContext, payload: Mapping[str, Any]) -> HandlerResult:
        p = parse(CounterpartyCreatedPayload, payload)
        row: dict[str, Any] = dict.fromkeys(COUNTERPARTY_FIELDS)
        row.update(
            kind=p.kind,
            name=p.name,
            phone=p.phone,
            is_customer=True,
            is_supplier=False,
            notify_consent=p.notify_consent,
        )
        validate_row(row)
        existing = await self._repo.get(s, p.id)
        if existing is not None:
            if existing.name == row["name"] and existing.phone == row["phone"] and existing.is_customer:
                return HandlerResult(server={"id": str(p.id)})
            raise invalid_field("id", "validation.duplicate_id")
        await self._repo.insert(
            s,
            {
                **row,
                "id": p.id,
                "tenant_id": ctx.tenant_id,
                "notify_consent_at": datetime.now(UTC) if p.notify_consent else None,
            },
        )
        await record_audit(
            s,
            tenant_id=ctx.tenant_id,
            user_id=ctx.actor_user_id,
            action="counterparty.created",
            entity="counterparties",
            entity_id=p.id,
            device_id=ctx.device_id,
            after={
                "kind": row["kind"],
                "name": row["name"],
                "phone": row["phone"],
                "source": "pos",
                "client_event_id": str(ctx.client_event_id),
            },
        )
        return HandlerResult(server={"id": str(p.id)})
