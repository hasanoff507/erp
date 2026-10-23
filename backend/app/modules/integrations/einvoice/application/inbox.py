"""Operator poll (21 §2 "faqat poll", §2.1; 19 §19, §8a): incoming e-invoices and answers to sent documents.

Every 10 minutes per tenant (cron ``einvoice_poll_fanout``), outside any business transaction:

1. ``fetch_incoming(updated_from)`` — ``updated_from`` = the newest ``payload.operator_updated_at`` already
   stored − 5 min (first run: 30 days back). Each document is stored in its own transaction: the supplier
   is found by STIR (or created as a ``company`` supplier, audit ``counterparty.created_from_einvoice``),
   ``einvoices(direction='in', status='received', risk_flag=<operator>|'unknown')`` upserted on
   ``(operator, operator_doc_id)`` (a document already signed/answered locally is not overwritten), an
   ``additional``/``corrected`` EHF is linked to its original (``related_einvoice_id``) and an additional
   EHF to
   the matching posted supplier return (``related_doc_type='supplier_returns'``, 13 §2.20); a combined EHF+TTN
   creates the incoming ``ettn_documents(direction='in', transport_type='seller_to_buyer',
   status='received')``.
2. Sent outgoing e-invoices → ``get_status`` → ``accepted``/``rejected``; sent powers of attorney →
   ``get_power_of_attorney_status`` → ``accepted``/``rejected`` (``responded_at``, ``reject_reason``).

An operator error stops the run (logged); the next tick retries — nothing is half-written.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, Final
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.audit import record_audit
from app.core.db.base import uuid7
from app.core.db.session import tenant_transaction
from app.modules.integrations.einvoice.application.ports import (
    EInvoicePortProvider,
    EInvoiceProviderError,
    IncomingInvoice,
)
from app.modules.integrations.einvoice.application.records import EDocsRepository
from app.modules.integrations.einvoice.application.vat_credit import VatCreditRepository

log = structlog.get_logger(__name__)

OVERLAP: Final = timedelta(minutes=5)
FIRST_LOOKBACK: Final = timedelta(days=30)
STATUS_BATCH: Final = 200
KEEP_STATUSES: Final = frozenset({"accepted", "rejected", "cancelled"})


@dataclass(frozen=True, slots=True)
class PollResult:
    fetched: int
    created: int
    updated_out: int
    updated_poa: int

    def as_json(self) -> dict[str, Any]:
        return {
            "fetched": self.fetched,
            "created": self.created,
            "updated_out": self.updated_out,
            "updated_poa": self.updated_poa,
        }


def _dec(value: Any) -> Decimal | None:
    return None if value is None else Decimal(str(value))


class InboxPoller:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        repo: EDocsRepository,
        vat_repo: VatCreditRepository,
        ports: EInvoicePortProvider,
        *,
        operator: str = "faktura",
    ) -> None:
        self._sf = session_factory
        self._repo = repo
        self._vat_repo = vat_repo
        self._ports = ports
        self._operator = operator

    async def run(self, tenant_id: UUID, *, now: datetime | None = None) -> PollResult:
        now = now or datetime.now(UTC)
        async with self._sf() as s, tenant_transaction(s, tenant_id):
            last = await self._repo.last_incoming_update(s)
            out_ids = await self._repo.sent_out_operator_ids(s, STATUS_BATCH)
            poa_ids = await self._repo.sent_poas(s, STATUS_BATCH)
        updated_from = (last - OVERLAP) if last is not None else now - FIRST_LOOKBACK
        try:
            port = await self._ports.for_tenant(tenant_id)
            docs = await port.fetch_incoming(updated_from)
        except EInvoiceProviderError:
            log.warning("einvoice_poll_failed", tenant_id=str(tenant_id), exc_info=True)
            return PollResult(0, 0, 0, 0)
        created = 0
        for doc in sorted(docs, key=lambda d: (d.updated_at, d.operator_doc_id)):
            if await self._store(tenant_id, doc):
                created += 1
        updated_out = await self._refresh_out(tenant_id, port, out_ids)
        updated_poa = await self._refresh_poa(tenant_id, port, poa_ids)
        return PollResult(len(docs), created, updated_out, updated_poa)

    async def _store(self, tenant_id: UUID, doc: IncomingInvoice) -> bool:
        async with self._sf() as s, tenant_transaction(s, tenant_id):
            supplier_id = await self._supplier(s, tenant_id, doc)
            related = (
                await self._repo.einvoice_by_operator_doc(s, doc.related_operator_doc_id)
                if doc.related_operator_doc_id
                else None
            )
            factura_type = (
                doc.factura_type
                if doc.factura_type in ("standard", "additional", "corrected")
                else "standard"
            )
            if factura_type != "standard" and related is None:
                factura_type = "standard"  # the original is unknown here: keep the row valid (12 CHECK)
            payload = {**dict(doc.payload), "operator_updated_at": doc.updated_at.astimezone(UTC).isoformat()}
            status = doc.status if doc.status in KEEP_STATUSES else "received"
            einvoice_id, inserted = await self._repo.upsert_incoming(
                s,
                {
                    "id": uuid7(),
                    "tenant_id": tenant_id,
                    "operator": self._operator,
                    "operator_doc_id": doc.operator_doc_id,
                    "counterparty_id": supplier_id,
                    "status": status,
                    "number": payload.get("number"),
                    "doc_date": doc.doc_date,
                    "total_amount": _dec(payload.get("total_amount")),
                    "vat_amount": _dec(payload.get("vat_amount")),
                    "risk_flag": doc.risk_flag,
                    "factura_type": factura_type,
                    "related_einvoice_id": related,
                    "payload": payload,
                },
            )
            if not inserted:
                return False
            if factura_type == "additional" and related is not None:
                vat = _dec(payload.get("vat_amount"))
                sr = await self._vat_repo.match_supplier_return(s, related, vat)
                if sr is not None:
                    await self._repo.update_einvoice(
                        s, einvoice_id, {"related_doc_type": "supplier_returns", "related_doc_id": sr}
                    )
            ettn = payload.get("ettn")
            if isinstance(ettn, dict):
                await self._repo.insert_ettn(
                    s,
                    {
                        "id": uuid7(),
                        "tenant_id": tenant_id,
                        "einvoice_id": einvoice_id,
                        "transfer_id": None,
                        "transport_type": "seller_to_buyer",
                        "direction": "in",
                        "status": "received",
                        "counterparty_id": supplier_id,
                        "doc_date": doc.doc_date,
                        "payload": ettn,
                        "operator_doc_id": ettn.get("operator_doc_id"),
                    },
                )
            return True

    async def _supplier(self, s: AsyncSession, tenant_id: UUID, doc: IncomingInvoice) -> UUID:
        found = await self._repo.supplier_by_stir(s, doc.seller_stir)
        if found is not None:
            return found
        seller = doc.payload.get("seller") if isinstance(doc.payload.get("seller"), dict) else {}
        name = str((seller or {}).get("name") or doc.seller_stir)
        new_id = uuid7()
        await self._repo.insert_supplier(
            s, {"id": new_id, "tenant_id": tenant_id, "name": name, "stir": doc.seller_stir}
        )
        await record_audit(
            s,
            tenant_id=tenant_id,
            action="counterparty.created_from_einvoice",
            entity="counterparties",
            entity_id=new_id,
            after={"stir": doc.seller_stir, "name": name, "operator_doc_id": doc.operator_doc_id},
        )
        return new_id

    async def _refresh_out(self, tenant_id: UUID, port: Any, ids: list[tuple[UUID, str]]) -> int:
        changed = 0
        for einvoice_id, op_id in ids:
            try:
                status = await port.get_status(op_id)
            except EInvoiceProviderError:
                log.warning("einvoice_status_failed", einvoice_id=str(einvoice_id), exc_info=True)
                return changed
            if status not in ("accepted", "rejected"):
                continue
            async with self._sf() as s, tenant_transaction(s, tenant_id):
                e = await self._repo.einvoice(s, einvoice_id, lock=True)
                if e is None or e.status != "sent":
                    continue
                await self._repo.update_einvoice(s, einvoice_id, {"status": status})
                await record_audit(
                    s,
                    tenant_id=tenant_id,
                    action=f"einvoice.{status}",
                    entity="einvoices",
                    entity_id=einvoice_id,
                    before={"status": "sent"},
                    after={"status": status, "source": "operator_poll"},
                )
            changed += 1
        return changed

    async def _refresh_poa(self, tenant_id: UUID, port: Any, ids: list[tuple[UUID, str]]) -> int:
        changed = 0
        for poa_id, op_id in ids:
            try:
                state = await port.get_power_of_attorney_status(op_id)
            except EInvoiceProviderError:
                log.warning("poa_status_failed", poa_id=str(poa_id), exc_info=True)
                return changed
            if state.status not in ("accepted", "rejected"):
                continue
            async with self._sf() as s, tenant_transaction(s, tenant_id):
                p = await self._repo.poa(s, poa_id, lock=True)
                if p is None or p.status != "sent":
                    continue
                await self._repo.update_poa(
                    s,
                    poa_id,
                    {
                        "status": state.status,
                        "responded_at": datetime.now(UTC),
                        "reject_reason": state.reason,
                    },
                )
                await record_audit(
                    s,
                    tenant_id=tenant_id,
                    action=f"power_of_attorney.{state.status}",
                    entity="powers_of_attorney",
                    entity_id=poa_id,
                    before={"status": "sent"},
                    after={"status": state.status, "reason": state.reason},
                )
            changed += 1
        return changed
