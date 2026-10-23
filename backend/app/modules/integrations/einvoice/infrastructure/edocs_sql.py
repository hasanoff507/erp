"""SQL of the e-documents slice (12 ``einvoices``, ``ettn_documents``, ``powers_of_attorney``,
``edoc_signatures``, ``outbox_jobs``; reads ``counterparties``, ``sales``/``sale_lines``/``returns``,
``transfers``, ``purchase_orders``, ``memberships``). Runs inside the caller's ``tenant_transaction``
(RLS)."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.base import uuid7
from app.modules.integrations.einvoice.application.records import (
    CounterpartyRef,
    EInvoice,
    EttnDoc,
    Page,
    PowerOfAttorney,
    SaleForInvoice,
    StoredSignature,
)

_EI_UPDATABLE = frozenset(
    {
        "status",
        "signed_at",
        "signed_by",
        "operator_doc_id",
        "risk_flag",
        "related_doc_type",
        "related_doc_id",
        "payload",
        "total_amount",
        "vat_amount",
        "number",
        "doc_date",
        "updated_at",
    }
)
_ETTN_UPDATABLE = frozenset(
    {"status", "signed_at", "operator_doc_id", "last_error", "doc_date", "receipt_id", "updated_at"}
)
_POA_UPDATABLE = frozenset(
    {
        "status",
        "signed_at",
        "sent_at",
        "responded_at",
        "reject_reason",
        "number",
        "operator_doc_id",
        "last_error",
        "updated_at",
    }
)

_EI = (
    "SELECT e.id, e.direction, e.operator, e.operator_doc_id, e.counterparty_id, c.name AS "
    "counterparty_name, "
    "c.stir AS counterparty_stir, c.kind AS counterparty_kind, e.related_doc_type, e.related_doc_id, "
    "e.status, "
    "e.number, e.doc_date, e.total_amount, e.vat_amount, e.signed_by, e.risk_flag, e.factura_type, "
    "e.related_einvoice_id, e.signed_at, e.payload, e.created_at, e.updated_at, j.last_error, j.status AS "
    "job_status "
    "FROM app.einvoices e "
    "LEFT JOIN app.counterparties c ON c.id = e.counterparty_id "
    "LEFT JOIN LATERAL (SELECT o.last_error, o.status FROM app.outbox_jobs o "
    "  WHERE o.kind IN ('einvoice_send', 'einvoice_accept') AND o.payload->>'einvoice_id' = e.id::text "
    "  ORDER BY o.id DESC LIMIT 1) j ON true "
)
_ETTN = (
    "SELECT x.id, x.direction, x.transport_type, x.status, x.operator_doc_id, x.transfer_id, x.einvoice_id, "
    "x.counterparty_id, x.receipt_id, x.doc_date, x.signed_at, x.last_error, x.payload, x.created_at, "
    "t.from_branch_id AS transfer_from_branch_id, t.to_branch_id AS transfer_to_branch_id, "
    "t.status AS transfer_status "
    "FROM app.ettn_documents x LEFT JOIN app.transfers t ON t.id = x.transfer_id "
)
_POA = (
    "SELECT p.id, p.branch_id, p.purchase_order_id, p.supplier_id, c.name AS supplier_name, c.stir AS "
    "supplier_stir, "
    "p.employee_user_id, u.name AS employee_name, p.doc_date, p.valid_from, p.valid_to, p.number, "
    "p.operator_doc_id, p.status, p.last_error, p.signed_at, p.sent_at, p.responded_at, p.reject_reason, "
    "p.created_by, p.created_at, p.version "
    "FROM app.powers_of_attorney p "
    "LEFT JOIN app.counterparties c ON c.id = p.supplier_id "
    "LEFT JOIN app.users u ON u.id = p.employee_user_id "
)


def _json(raw: Any) -> Any:
    return json.loads(raw) if isinstance(raw, str) else raw


def _dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _einvoice(m: Any) -> EInvoice:
    data = dict(m)
    data["payload"] = _json(data["payload"]) or {}
    return EInvoice(**data)


def _ettn(m: Any) -> EttnDoc:
    data = dict(m)
    data["payload"] = _json(data["payload"]) or {}
    return EttnDoc(**data)


def _where(filters: Mapping[str, Any], alias: str, page: Page) -> tuple[str, dict[str, Any]]:
    where: list[str] = []
    params: dict[str, Any] = {}
    for key, value in filters.items():
        if value is None:
            continue
        where.append(f"{alias}.{key} = :{key}")
        params[key] = value
    if page.after is not None:
        where.append(f"{alias}.id < :after_id")
        params["after_id"] = page.after[1]
    params["limit"] = page.limit
    return ("WHERE " + " AND ".join(where) + " " if where else ""), params


class SqlEDocsRepository:
    # --- einvoices --------------------------------------------------------------------------------------
    async def einvoice(self, s: AsyncSession, einvoice_id: UUID, *, lock: bool = False) -> EInvoice | None:
        if lock:
            got = await s.execute(
                text("SELECT id FROM app.einvoices WHERE id = :id FOR UPDATE"), {"id": einvoice_id}
            )
            if got.first() is None:
                return None
        row = (await s.execute(text(_EI + "WHERE e.id = :id"), {"id": einvoice_id})).first()
        return _einvoice(row._mapping) if row else None

    async def einvoices(self, s: AsyncSession, filters: Mapping[str, Any], page: Page) -> list[EInvoice]:
        clause, params = _where(filters, "e", page)
        rows = await s.execute(text(_EI + clause + "ORDER BY e.id DESC LIMIT :limit"), params)
        return [_einvoice(r._mapping) for r in rows]

    async def insert_einvoice(self, s: AsyncSession, row: Mapping[str, Any]) -> None:
        await s.execute(
            text(
                "INSERT INTO app.einvoices (id, tenant_id, direction, operator, operator_doc_id, "
                "counterparty_id, "
                "related_doc_type, related_doc_id, status, number, doc_date, total_amount, vat_amount, "
                "risk_flag, "
                "factura_type, related_einvoice_id, payload) VALUES (:id, :tenant_id, :direction, :operator, "
                ":operator_doc_id, :counterparty_id, :related_doc_type, :related_doc_id, :status, :number, "
                ":doc_date, :total_amount, :vat_amount, :risk_flag, :factura_type, :related_einvoice_id, "
                "CAST(:payload AS jsonb))"
            ),
            _ei_row(row),
        )

    async def insert_out_once(self, s: AsyncSession, row: Mapping[str, Any]) -> UUID | None:
        got = (
            await s.execute(
                text(
                    "INSERT INTO app.einvoices (id, tenant_id, direction, operator, operator_doc_id, "
                    "counterparty_id, related_doc_type, related_doc_id, status, number, doc_date, "
                    "total_amount, "
                    "vat_amount, risk_flag, factura_type, related_einvoice_id, payload) VALUES (:id, "
                    ":tenant_id, "
                    ":direction, :operator, :operator_doc_id, :counterparty_id, :related_doc_type, "
                    ":related_doc_id, :status, :number, :doc_date, :total_amount, :vat_amount, :risk_flag, "
                    ":factura_type, :related_einvoice_id, CAST(:payload AS jsonb)) "
                    "ON CONFLICT (tenant_id, related_doc_type, related_doc_id) "
                    "WHERE direction = 'out' AND related_doc_id IS NOT NULL AND status <> 'cancelled' DO "
                    "NOTHING "
                    "RETURNING id"
                ),
                _ei_row(row),
            )
        ).first()
        return got[0] if got else None

    async def active_out_for(self, s: AsyncSession, doc_type: str, doc_id: UUID) -> UUID | None:
        got = await s.execute(
            text(
                "SELECT id FROM app.einvoices WHERE direction = 'out' AND related_doc_type = :t "
                "AND related_doc_id = :d AND status <> 'cancelled'"
            ),
            {"t": doc_type, "d": doc_id},
        )
        value: UUID | None = got.scalar_one_or_none()
        return value

    async def update_einvoice(self, s: AsyncSession, einvoice_id: UUID, values: Mapping[str, Any]) -> None:
        cols = [k for k in values if k in _EI_UPDATABLE]
        if not cols:
            return
        sets = ", ".join(f"{c} = CAST(:{c} AS jsonb)" if c == "payload" else f"{c} = :{c}" for c in cols)
        params = {c: (_dumps(values[c]) if c == "payload" else values[c]) for c in cols}
        await s.execute(
            text(f"UPDATE app.einvoices SET {sets}, updated_at = now() WHERE id = :id"),  # noqa: S608
            {**params, "id": einvoice_id},
        )

    async def upsert_incoming(self, s: AsyncSession, row: Mapping[str, Any]) -> tuple[UUID, bool]:
        got = (
            await s.execute(
                text(
                    "INSERT INTO app.einvoices (id, tenant_id, direction, operator, operator_doc_id, "
                    "counterparty_id, status, number, doc_date, total_amount, vat_amount, risk_flag, "
                    "factura_type, "
                    "related_einvoice_id, payload) VALUES (:id, :tenant_id, 'in', :operator, "
                    ":operator_doc_id, "
                    ":counterparty_id, :status, :number, :doc_date, :total_amount, :vat_amount, :risk_flag, "
                    ":factura_type, :related_einvoice_id, CAST(:payload AS jsonb)) "
                    "ON CONFLICT (tenant_id, operator, operator_doc_id) WHERE operator_doc_id IS NOT NULL "
                    "DO UPDATE SET payload = EXCLUDED.payload, number = EXCLUDED.number, "
                    "doc_date = EXCLUDED.doc_date, total_amount = EXCLUDED.total_amount, "
                    "vat_amount = EXCLUDED.vat_amount, updated_at = now() "
                    "WHERE app.einvoices.status = 'received' AND app.einvoices.direction = 'in' "
                    "RETURNING id, (xmax = 0) AS inserted"
                ),
                _ei_row(row),
            )
        ).first()
        if got is not None:
            return got[0], bool(got[1])
        existing = await self.einvoice_by_operator_doc(s, str(row["operator_doc_id"]))
        assert existing is not None
        return existing, False

    async def einvoice_by_operator_doc(self, s: AsyncSession, operator_doc_id: str) -> UUID | None:
        got = await s.execute(
            text("SELECT id FROM app.einvoices WHERE operator_doc_id = :o ORDER BY id LIMIT 1"),
            {"o": operator_doc_id},
        )
        value: UUID | None = got.scalar_one_or_none()
        return value

    async def last_incoming_update(self, s: AsyncSession) -> datetime | None:
        got = await s.execute(
            text(
                "SELECT max((payload->>'operator_updated_at')::timestamptz) FROM app.einvoices "
                "WHERE direction = 'in' AND payload ? 'operator_updated_at'"
            )
        )
        value: datetime | None = got.scalar_one_or_none()
        return value

    async def sent_out_operator_ids(self, s: AsyncSession, limit: int) -> list[tuple[UUID, str]]:
        rows = await s.execute(
            text(
                "SELECT id, operator_doc_id FROM app.einvoices WHERE direction = 'out' AND status = 'sent' "
                "AND operator_doc_id IS NOT NULL ORDER BY id LIMIT :l"
            ),
            {"l": limit},
        )
        return [(r[0], r[1]) for r in rows]

    # --- counterparties / sales ---------------------------------------------------------------------------
    async def counterparty(self, s: AsyncSession, counterparty_id: UUID) -> CounterpartyRef | None:
        row = (
            await s.execute(
                text(
                    "SELECT id, kind, name, stir, archived_at IS NOT NULL FROM app.counterparties WHERE id "
                    "= :id"
                ),
                {"id": counterparty_id},
            )
        ).first()
        return CounterpartyRef(row[0], row[1], row[2], row[3], bool(row[4])) if row else None

    async def supplier_by_stir(self, s: AsyncSession, stir: str) -> UUID | None:
        got = await s.execute(
            text(
                "SELECT id FROM app.counterparties WHERE stir = :s AND archived_at IS NULL "
                "ORDER BY is_supplier DESC, id LIMIT 1"
            ),
            {"s": stir},
        )
        value: UUID | None = got.scalar_one_or_none()
        return value

    async def insert_supplier(self, s: AsyncSession, row: Mapping[str, Any]) -> None:
        await s.execute(
            text(
                "INSERT INTO app.counterparties (id, tenant_id, kind, name, stir, is_supplier) "
                "VALUES (:id, :tenant_id, 'company', :name, :stir, true)"
            ),
            dict(row),
        )

    async def sale(self, s: AsyncSession, sale_id: UUID) -> SaleForInvoice | None:
        head = (
            await s.execute(
                text(
                    "SELECT sa.id, sa.branch_id, sa.status, sa.number, sa.doc_date, sa.counterparty_id, "
                    "EXISTS (SELECT 1 FROM app.sale_payments p WHERE p.sale_id = sa.id AND p.method = "
                    "'debt') "
                    "FROM app.sales sa WHERE sa.id = :id"
                ),
                {"id": sale_id},
            )
        ).first()
        if head is None:
            return None
        lines = await s.execute(
            text(
                "SELECT l.id, l.product_id, p.name, p.mxik_code AS mxik, p.unit_code, l.qty, l.line_total, "
                "l.vat_rate, l.vat_amount, l.marking_code, COALESCE(r.qty, 0) AS returned_qty, "
                "COALESCE(r.total, 0) AS returned_total, COALESCE(r.vat, 0) AS returned_vat "
                "FROM app.sale_lines l LEFT JOIN app.products p ON p.id = l.product_id "
                "LEFT JOIN LATERAL (SELECT sum(rl.qty) AS qty, sum(rl.line_total) AS total, "
                "  sum(rl.vat_amount) AS vat FROM app.return_lines rl JOIN app.returns r ON r.id = "
                "rl.return_id "
                "  WHERE rl.sale_line_id = l.id AND r.status = 'posted') r ON true "
                "WHERE l.sale_id = :id ORDER BY l.line_no"
            ),
            {"id": sale_id},
        )
        return SaleForInvoice(
            id=head[0],
            branch_id=head[1],
            status=head[2],
            number=head[3],
            doc_date=head[4],
            counterparty_id=head[5],
            has_debt_payment=bool(head[6]),
            lines=tuple(dict(r._mapping) for r in lines),
        )

    async def tenant_stir(self, s: AsyncSession) -> tuple[str | None, str | None]:
        row = (
            await s.execute(
                text("SELECT t.stir, t.name FROM app.tenants t WHERE t.id = app.current_tenant_id()")
            )
        ).first()
        return (row[0], row[1]) if row else (None, None)

    # --- e-TTN ---------------------------------------------------------------------------------------------
    async def ettn(self, s: AsyncSession, ettn_id: UUID, *, lock: bool = False) -> EttnDoc | None:
        if lock:
            got = await s.execute(
                text("SELECT id FROM app.ettn_documents WHERE id = :id FOR UPDATE"), {"id": ettn_id}
            )
            if got.first() is None:
                return None
        row = (await s.execute(text(_ETTN + "WHERE x.id = :id"), {"id": ettn_id})).first()
        return _ettn(row._mapping) if row else None

    async def ettns(self, s: AsyncSession, filters: Mapping[str, Any], page: Page) -> list[EttnDoc]:
        clause, params = _where(filters, "x", page)
        rows = await s.execute(text(_ETTN + clause + "ORDER BY x.id DESC LIMIT :limit"), params)
        return [_ettn(r._mapping) for r in rows]

    async def update_ettn(self, s: AsyncSession, ettn_id: UUID, values: Mapping[str, Any]) -> None:
        cols = [k for k in values if k in _ETTN_UPDATABLE]
        if not cols:
            return
        sets = ", ".join(f"{c} = :{c}" for c in cols)
        await s.execute(
            text(f"UPDATE app.ettn_documents SET {sets}, updated_at = now() WHERE id = :id"),  # noqa: S608
            {**{c: values[c] for c in cols}, "id": ettn_id},
        )

    async def insert_ettn(self, s: AsyncSession, row: Mapping[str, Any]) -> None:
        await s.execute(
            text(
                "INSERT INTO app.ettn_documents (id, tenant_id, einvoice_id, transfer_id, transport_type, "
                "direction, "
                "status, counterparty_id, doc_date, payload, operator_doc_id) VALUES (:id, :tenant_id, "
                ":einvoice_id, "
                ":transfer_id, :transport_type, :direction, :status, :counterparty_id, :doc_date, "
                "CAST(:payload AS jsonb), :operator_doc_id)"
            ),
            {**dict(row), "payload": _dumps(row.get("payload") or {})},
        )

    async def ettns_of_einvoice(self, s: AsyncSession, einvoice_id: UUID) -> list[UUID]:
        rows = await s.execute(
            text("SELECT id FROM app.ettn_documents WHERE einvoice_id = :e ORDER BY id FOR UPDATE"),
            {"e": einvoice_id},
        )
        return [r[0] for r in rows]

    async def lock_transfer(self, s: AsyncSession, transfer_id: UUID) -> None:
        await s.execute(text("SELECT id FROM app.transfers WHERE id = :id FOR UPDATE"), {"id": transfer_id})

    async def set_transfer_ettn_ref(self, s: AsyncSession, transfer_id: UUID, ref: str) -> None:
        await s.execute(
            text("UPDATE app.transfers SET ettn_ref = :r, updated_at = now() WHERE id = :id"),
            {"r": ref, "id": transfer_id},
        )

    # --- powers of attorney ------------------------------------------------------------------------------
    async def poa(self, s: AsyncSession, poa_id: UUID, *, lock: bool = False) -> PowerOfAttorney | None:
        if lock:
            got = await s.execute(
                text("SELECT id FROM app.powers_of_attorney WHERE id = :id FOR UPDATE"), {"id": poa_id}
            )
            if got.first() is None:
                return None
        row = (await s.execute(text(_POA + "WHERE p.id = :id"), {"id": poa_id})).first()
        return PowerOfAttorney(**dict(row._mapping)) if row else None

    async def poas(self, s: AsyncSession, filters: Mapping[str, Any], page: Page) -> list[PowerOfAttorney]:
        clause, params = _where({k: v for k, v in filters.items() if k != "branch_ids"}, "p", page)
        branch_ids = filters.get("branch_ids")
        if branch_ids is not None:
            clause = (clause or "WHERE true ") + "AND p.branch_id = ANY(:branch_ids) "
            params["branch_ids"] = list(branch_ids)
        rows = await s.execute(text(_POA + clause + "ORDER BY p.id DESC LIMIT :limit"), params)
        return [PowerOfAttorney(**dict(r._mapping)) for r in rows]

    async def insert_poa(self, s: AsyncSession, row: Mapping[str, Any]) -> None:
        await s.execute(
            text(
                "INSERT INTO app.powers_of_attorney (id, tenant_id, branch_id, purchase_order_id, "
                "supplier_id, "
                "employee_user_id, doc_date, valid_from, valid_to, status, created_by) VALUES (:id, "
                ":tenant_id, "
                ":branch_id, :purchase_order_id, :supplier_id, :employee_user_id, :doc_date, :valid_from, "
                ":valid_to, :status, :created_by)"
            ),
            dict(row),
        )

    async def update_poa(self, s: AsyncSession, poa_id: UUID, values: Mapping[str, Any]) -> None:
        cols = [k for k in values if k in _POA_UPDATABLE]
        if not cols:
            return
        sets = ", ".join(f"{c} = :{c}" for c in cols)
        await s.execute(
            text(
                f"UPDATE app.powers_of_attorney SET {sets}, version = version + 1, "  # noqa: S608
                "updated_at = now() WHERE id = :id"
            ),
            {**{c: values[c] for c in cols}, "id": poa_id},
        )

    async def sent_poas(self, s: AsyncSession, limit: int) -> list[tuple[UUID, str]]:
        rows = await s.execute(
            text(
                "SELECT id, operator_doc_id FROM app.powers_of_attorney WHERE status = 'sent' "
                "AND operator_doc_id IS NOT NULL ORDER BY id LIMIT :l"
            ),
            {"l": limit},
        )
        return [(r[0], r[1]) for r in rows]

    async def purchase_order_supplier(self, s: AsyncSession, po_id: UUID) -> tuple[UUID, UUID] | None:
        row = (
            await s.execute(
                text("SELECT supplier_id, branch_id FROM app.purchase_orders WHERE id = :id"), {"id": po_id}
            )
        ).first()
        return (row[0], row[1]) if row else None

    async def tenant_user_exists(self, s: AsyncSession, user_id: UUID) -> bool:
        got = await s.execute(
            text("SELECT 1 FROM app.memberships WHERE user_id = :u AND tenant_id = app.current_tenant_id()"),
            {"u": user_id},
        )
        return got.first() is not None

    # --- signatures / outbox -----------------------------------------------------------------------------
    async def insert_signature(self, s: AsyncSession, row: Mapping[str, Any]) -> None:
        await s.execute(
            text(
                "INSERT INTO app.edoc_signatures (id, tenant_id, entity, entity_id, action, document_hash, "
                "signature_pkcs7, certificate_serial, signer_tin, signed_by) VALUES (:id, :tenant_id, "
                ":entity, "
                ":entity_id, :action, :document_hash, :signature_pkcs7, :certificate_serial, :signer_tin, "
                ":signed_by)"
            ),
            {"id": uuid7(), **dict(row)},
        )

    async def latest_signature(
        self, s: AsyncSession, entity: str, entity_id: UUID, action: str
    ) -> StoredSignature | None:
        row = (
            await s.execute(
                text(
                    "SELECT signature_pkcs7, certificate_serial, document_hash FROM app.edoc_signatures "
                    "WHERE entity = :e AND entity_id = :id AND action = :a ORDER BY id DESC LIMIT 1"
                ),
                {"e": entity, "id": entity_id, "a": action},
            )
        ).first()
        return StoredSignature(row[0], row[1], row[2]) if row else None

    async def queue_job(
        self,
        s: AsyncSession,
        tenant_id: UUID,
        kind: str,
        payload: Mapping[str, Any],
        key: str,
        created_by: UUID | None,
    ) -> UUID:
        """Insert a ``queued`` job, or put an existing ``failed``/``done`` job with the same key back to
        ``queued`` with the new payload (re-sign / re-send, 21 §0 manual retry)."""
        got = (
            await s.execute(
                text(
                    "INSERT INTO app.outbox_jobs (id, tenant_id, kind, payload, idempotency_key, created_by) "
                    "VALUES (:id, :t, :k, CAST(:p AS jsonb), :key, :u) "
                    "ON CONFLICT (tenant_id, idempotency_key) DO UPDATE SET status = 'queued', attempts = 0, "
                    "payload = EXCLUDED.payload, next_run_at = now(), last_error = NULL, updated_at = now() "
                    "WHERE app.outbox_jobs.status IN ('failed', 'done') RETURNING id"
                ),
                {
                    "id": uuid7(),
                    "t": tenant_id,
                    "k": kind,
                    "p": _dumps(dict(payload)),
                    "key": key,
                    "u": created_by,
                },
            )
        ).first()
        if got is not None:
            job_id: UUID = got[0]
            return job_id
        existing: UUID = (
            await s.execute(text("SELECT id FROM app.outbox_jobs WHERE idempotency_key = :key"), {"key": key})
        ).scalar_one()
        return existing

    async def alerts(self, s: AsyncSession) -> dict[str, int]:
        row = (
            await s.execute(
                text(
                    "SELECT "
                    "(SELECT count(*) FROM app.einvoices WHERE direction = 'in' AND status = 'received'), "
                    "(SELECT count(*) FROM app.einvoices WHERE direction = 'out' AND status = 'draft'), "
                    "(SELECT count(*) FROM app.outbox_jobs WHERE kind IN ('einvoice_send', "
                    "'einvoice_accept', "
                    "  'poa_send', 'ettn_send', 'ettn_accept') AND status = 'failed'), "
                    "(SELECT count(*) FROM app.ettn_documents WHERE direction = 'out' "
                    "  AND status IN ('pending_signature', 'failed'))"
                )
            )
        ).one()
        return {
            "incoming_awaiting_signature": int(row[0]),
            "outgoing_drafts": int(row[1]),
            "send_failed": int(row[2]),
            "ettn_pending_signature": int(row[3]),
        }


def _ei_row(row: Mapping[str, Any]) -> dict[str, Any]:
    defaults: dict[str, Any] = {
        "operator_doc_id": None,
        "related_doc_type": None,
        "related_doc_id": None,
        "number": None,
        "doc_date": None,
        "total_amount": None,
        "vat_amount": None,
        "risk_flag": "unknown",
        "factura_type": "standard",
        "related_einvoice_id": None,
        "operator": "faktura",
    }
    out = {**defaults, **dict(row)}
    out["payload"] = _dumps(out.get("payload") or {})
    for key in ("total_amount", "vat_amount"):
        if out[key] is not None:
            out[key] = Decimal(out[key])
    return out
