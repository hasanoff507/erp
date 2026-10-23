"""SQL of the fiscal package (caller's transaction; RLS — one tenant)."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import date, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.base import uuid7
from app.modules.integrations.fiscal.application.ports import (
    ClaimedJob,
    FiscalResult,
    ReceiptFilter,
    ReceiptRow,
    RegisterBinding,
    RegisterState,
)

STALE_RUNNING_S = 600
KIND = "ofd_send"

_COLS = (
    "f.id, f.kind, f.sale_id, f.return_id, f.debt_payment_id, f.cash_register_id, f.shift_id, f.receipt_seq, "
    "f.fm_terminal_id, f.fm_receipt_seq, f.fiscal_at, f.payload, f.fiscal_sign, f.qr_url, f.payment_form, "
    "f.delivery, f.delivery_reason, f.sent_at, f.ofd_acked_at, f.offline_since, f.status, f.attempts, "
    "f.created_at, cr.branch_id"
)
_FROM = "FROM app.fiscal_receipts f LEFT JOIN app.cash_registers cr ON cr.id = f.cash_register_id"
_BINDING = (
    "SELECT id, branch_id, name, fiscal_agent_id, fiscal_local_device_id, fm_state, fm_receipts_pending, "
    "archived_at FROM app.cash_registers"
)


def _binding(r: Any) -> RegisterBinding:
    m = r._mapping
    return RegisterBinding(
        id=m["id"], branch_id=m["branch_id"], name=m["name"], agent_id=m["fiscal_agent_id"],
        local_id=m["fiscal_local_device_id"], fm_state=m["fm_state"],
        fm_receipts_pending=m["fm_receipts_pending"],
        archived=m["archived_at"] is not None,
    )  # fmt: skip


def _json(raw: Any) -> Any:
    return json.loads(raw) if isinstance(raw, str) else raw


def _row(r: Any) -> ReceiptRow:
    m = r._mapping
    return ReceiptRow(
        id=m["id"], kind=m["kind"], sale_id=m["sale_id"], return_id=m["return_id"],
        debt_payment_id=m["debt_payment_id"], cash_register_id=m["cash_register_id"], shift_id=m["shift_id"],
        receipt_seq=m["receipt_seq"], fm_terminal_id=m["fm_terminal_id"], fm_receipt_seq=m["fm_receipt_seq"],
        fiscal_at=m["fiscal_at"], payload=_json(m["payload"]) or {}, fiscal_sign=m["fiscal_sign"],
        qr_url=m["qr_url"], payment_form=m["payment_form"], delivery=m["delivery"],
        delivery_reason=m["delivery_reason"], sent_at=m["sent_at"], ofd_acked_at=m["ofd_acked_at"],
        offline_since=m["offline_since"], status=m["status"], attempts=m["attempts"],
        created_at=m["created_at"],
        branch_id=m["branch_id"],
    )  # fmt: skip


class SqlFiscalRepository:
    def __init__(self, stale_running_s: int = STALE_RUNNING_S) -> None:
        self._stale = stale_running_s

    # --- registers ----------------------------------------------------------------------------------
    async def register(
        self, s: AsyncSession, register_id: UUID, *, lock: bool = False
    ) -> RegisterState | None:
        row = (
            await s.execute(
                text(
                    "SELECT id, tenant_id, branch_id, fm_state, fiscal_module_id, last_unacked_receipt_at "
                    "FROM app.cash_registers WHERE id = :id" + (" FOR UPDATE" if lock else "")
                ),
                {"id": register_id},
            )
        ).first()
        return RegisterState(row[0], row[1], row[2], row[3], row[4], row[5]) if row else None

    async def set_fm_state(self, s: AsyncSession, register_id: UUID, fm_state: str) -> None:
        await s.execute(
            text("UPDATE app.cash_registers SET fm_state = :st, updated_at = now() WHERE id = :id"),
            {"st": fm_state, "id": register_id},
        )

    async def set_last_unacked(self, s: AsyncSession, register_id: UUID, at: datetime | None) -> None:
        await s.execute(
            text(
                "UPDATE app.cash_registers SET last_unacked_receipt_at = :at, updated_at = now() WHERE id "
                "= :id"
            ),
            {"at": at, "id": register_id},
        )

    async def oldest_unacked(self, s: AsyncSession, register_id: UUID) -> tuple[UUID, datetime] | None:
        row = (
            await s.execute(
                text(
                    "SELECT id, created_at FROM app.fiscal_receipts WHERE cash_register_id = :cr "
                    "AND ofd_acked_at IS NULL AND kind <> 'z_report' ORDER BY created_at, id LIMIT 1"
                ),
                {"cr": register_id},
            )
        ).first()
        return (row[0], row[1]) if row else None

    async def unacked_registers(self, s: AsyncSession) -> list[tuple[UUID, UUID, datetime]]:
        rows = await s.execute(
            text(
                "SELECT DISTINCT ON (cash_register_id) cash_register_id, id, created_at FROM "
                "app.fiscal_receipts "
                "WHERE ofd_acked_at IS NULL AND kind <> 'z_report' AND cash_register_id IS NOT NULL "
                "ORDER BY cash_register_id, created_at, id"
            )
        )
        return [(r[0], r[1], r[2]) for r in rows]

    async def blocked_registers(self, s: AsyncSession) -> list[tuple[UUID, datetime]]:
        rows = await s.execute(
            text(
                "SELECT id, last_unacked_receipt_at FROM app.cash_registers "
                "WHERE last_unacked_receipt_at IS NOT NULL"
            )
        )
        return [(r[0], r[1]) for r in rows]

    # --- receipts -----------------------------------------------------------------------------------
    async def seq_taken(self, s: AsyncSession, register_id: UUID, shift_id: UUID, receipt_seq: int) -> bool:
        row = (
            await s.execute(
                text(
                    "SELECT 1 FROM app.fiscal_receipts WHERE cash_register_id = :cr AND shift_id = :sh "
                    "AND receipt_seq = :seq"
                ),
                {"cr": register_id, "sh": shift_id, "seq": receipt_seq},
            )
        ).first()
        return row is not None

    async def max_seq(self, s: AsyncSession, register_id: UUID, shift_id: UUID) -> int:
        value = (
            await s.execute(
                text(
                    "SELECT COALESCE(max(receipt_seq), 0) FROM app.fiscal_receipts "
                    "WHERE cash_register_id = :cr AND shift_id = :sh"
                ),
                {"cr": register_id, "sh": shift_id},
            )
        ).scalar_one()
        return int(value)

    async def z_exists(self, s: AsyncSession, shift_id: UUID) -> bool:
        row = (
            await s.execute(
                text("SELECT 1 FROM app.fiscal_receipts WHERE shift_id = :sh AND kind = 'z_report'"),
                {"sh": shift_id},
            )
        ).first()
        return row is not None

    async def insert_receipt(self, s: AsyncSession, row: Mapping[str, Any]) -> None:
        await s.execute(
            text(
                "INSERT INTO app.fiscal_receipts (id, tenant_id, kind, sale_id, return_id, debt_payment_id, "
                "cash_register_id, shift_id, receipt_seq, fm_terminal_id, fm_receipt_seq, fiscal_at, "
                "payload, "
                "fiscal_sign, qr_url, payment_form, delivery, delivery_reason, sent_at, offline_since, "
                "status, "
                "created_at, updated_at) VALUES (:id, :tenant_id, :kind, :sale_id, :return_id, "
                ":debt_payment_id, "
                ":cash_register_id, :shift_id, :receipt_seq, :fm_terminal_id, :fm_receipt_seq, :fiscal_at, "
                "CAST(:payload AS jsonb), :fiscal_sign, :qr_url, :payment_form, :delivery, :delivery_reason, "
                ":sent_at, :offline_since, :status, :created_at, now())"
            ),
            dict(row),
        )

    async def insert_job(self, s: AsyncSession, tenant_id: UUID, receipt_id: UUID) -> UUID:
        job_id = uuid7()
        found = (
            await s.execute(
                text(
                    "INSERT INTO app.outbox_jobs (id, tenant_id, kind, payload, idempotency_key) "
                    "VALUES (:id, :t, 'ofd_send', CAST(:p AS jsonb), :k) "
                    "ON CONFLICT (tenant_id, idempotency_key) DO UPDATE SET status = 'queued', "
                    "next_run_at = now(), updated_at = now() RETURNING id"
                ),
                {
                    "id": job_id,
                    "t": tenant_id,
                    "p": json.dumps({"fiscal_receipt_id": str(receipt_id)}),
                    "k": f"ofd_send:{receipt_id}",
                },
            )
        ).scalar_one()
        return UUID(str(found))

    async def job_of(self, s: AsyncSession, receipt_id: UUID) -> UUID | None:
        value = (
            await s.execute(
                text("SELECT id FROM app.outbox_jobs WHERE kind = 'ofd_send' AND idempotency_key = :k"),
                {"k": f"ofd_send:{receipt_id}"},
            )
        ).scalar_one_or_none()
        return value

    async def get(self, s: AsyncSession, receipt_id: UUID, *, lock: bool = False) -> ReceiptRow | None:
        sql = f"SELECT {_COLS} {_FROM} WHERE f.id = :id"
        if lock:
            sql += " FOR UPDATE OF f"
        row = (await s.execute(text(sql), {"id": receipt_id})).first()
        return _row(row) if row else None

    async def page(
        self, s: AsyncSession, flt: ReceiptFilter, after: tuple[datetime, UUID] | None, limit: int
    ) -> list[ReceiptRow]:
        where: list[str] = []
        params: dict[str, Any] = {"limit": limit}
        if flt.branch_ids is not None:
            where.append("cr.branch_id = ANY(:branches)")
            params["branches"] = list(flt.branch_ids)
        for col in ("sale_id", "return_id", "debt_payment_id", "shift_id", "kind", "status"):
            value = getattr(flt, col)
            if value is not None:
                where.append(f"f.{col} = :{col}")
                params[col] = value
        if after is not None:
            where.append("(f.created_at, f.id) < (:after_at, :after_id)")
            params["after_at"], params["after_id"] = after
        sql = f"SELECT {_COLS} {_FROM}"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY f.created_at DESC, f.id DESC LIMIT :limit"
        return [_row(r) for r in await s.execute(text(sql), params)]

    async def set_fiscalized(self, s: AsyncSession, receipt_id: UUID, result: FiscalResult) -> None:
        await s.execute(
            text(
                "UPDATE app.fiscal_receipts SET status = 'fiscalized', fm_terminal_id = :t, fm_receipt_seq "
                "= :seq, "
                "fiscal_at = :at, fiscal_sign = :sign, qr_url = :qr, sent_at = now(), attempts = attempts "
                "+ 1, "
                "updated_at = now() WHERE id = :id"
            ),
            {
                "t": result.terminal_id, "seq": result.fm_receipt_seq, "at": result.fiscal_at,
                "sign": result.fiscal_sign, "qr": result.qr_url, "id": receipt_id,
            },
        )  # fmt: skip

    async def set_status(
        self, s: AsyncSession, receipt_id: UUID, status: str, *, attempt: bool = False
    ) -> None:
        await s.execute(
            text(
                "UPDATE app.fiscal_receipts SET status = :st, attempts = attempts + :inc, updated_at = now() "
                "WHERE id = :id"
            ),
            {"st": status, "inc": 1 if attempt else 0, "id": receipt_id},
        )

    async def ack(self, s: AsyncSession, receipt_id: UUID, at: datetime) -> None:
        await s.execute(
            text(
                "UPDATE app.fiscal_receipts SET ofd_acked_at = :at, updated_at = now() "
                "WHERE id = :id AND ofd_acked_at IS NULL"
            ),
            {"at": at, "id": receipt_id},
        )

    async def ack_fm(
        self, s: AsyncSession, fm_terminal_id: str, fm_receipt_seq: int, at: datetime
    ) -> UUID | None:
        value = (
            await s.execute(
                text(
                    "UPDATE app.fiscal_receipts SET ofd_acked_at = :at, updated_at = now() "
                    "WHERE fm_terminal_id = :t AND fm_receipt_seq = :seq AND ofd_acked_at IS NULL "
                    "RETURNING id"
                ),
                {"at": at, "t": fm_terminal_id, "seq": fm_receipt_seq},
            )
        ).scalar_one_or_none()
        return value

    async def mark_codes_sold(self, s: AsyncSession, doc_id: UUID) -> None:
        await s.execute(
            text(
                "UPDATE app.marking_codes SET status = 'sold', verified_at = COALESCE(verified_at, now()), "
                "updated_at = now() WHERE last_doc_id = :d AND status = 'pending_verification'"
            ),
            {"d": doc_id},
        )

    async def original_sale_receipt(self, s: AsyncSession, return_id: UUID) -> ReceiptRow | None:
        """RefundInfo source (21 §1): the sale's own ``kind='sale'`` receipt; a pure debt sale has none — then
        the latest fiscalized ``debt_settlement`` receipt whose lines came from that sale (13 §2.14)."""
        row = (
            await s.execute(
                text(
                    f"SELECT {_COLS} {_FROM} JOIN app.returns r ON r.sale_id = f.sale_id "
                    "WHERE r.id = :rid AND f.kind = 'sale' ORDER BY f.created_at, f.id LIMIT 1"
                ),
                {"rid": return_id},
            )
        ).first()
        if row is None:
            row = (
                await s.execute(
                    text(
                        f"SELECT {_COLS} {_FROM} JOIN app.returns r ON r.id = :rid "  # noqa: S608
                        "WHERE f.kind = 'debt_settlement' AND f.status = 'fiscalized' "
                        "AND r.sale_id IS NOT NULL "
                        "AND EXISTS (SELECT 1 FROM jsonb_array_elements(f.payload->'items') it "
                        "WHERE it->>'sale_id' = r.sale_id::text) "
                        "ORDER BY f.fiscal_at DESC NULLS LAST, f.id DESC LIMIT 1"
                    ),
                    {"rid": return_id},
                )
            ).first()
        return _row(row) if row else None

    # --- B5: agent binding, FM status, acks, Z-report, readiness ------------------------------------
    async def binding(self, s: AsyncSession, register_id: UUID) -> RegisterBinding | None:
        row = (await s.execute(text(_BINDING + " WHERE id = :id"), {"id": register_id})).first()
        return _binding(row) if row else None

    async def bound_registers(self, s: AsyncSession) -> list[RegisterBinding]:
        rows = await s.execute(
            text(_BINDING + " WHERE fiscal_agent_id IS NOT NULL AND archived_at IS NULL ORDER BY id")
        )
        return [_binding(r) for r in rows]

    async def set_fm_status(
        self, s: AsyncSession, register_id: UUID, fm_state: str, pending: int | None
    ) -> None:
        await s.execute(
            text(
                "UPDATE app.cash_registers SET fm_state = :st, fm_receipts_pending = :p, updated_at = now() "
                "WHERE id = :id"
            ),
            {"st": fm_state, "p": pending, "id": register_id},
        )

    async def z_of_shift(self, s: AsyncSession, shift_id: UUID) -> ReceiptRow | None:
        row = (
            await s.execute(
                text(
                    f"SELECT {_COLS} {_FROM} WHERE f.shift_id = :sh AND f.kind = 'z_report' FOR UPDATE OF f"
                ),
                {"sh": shift_id},
            )
        ).first()
        return _row(row) if row else None

    async def set_z_fiscalized(
        self,
        s: AsyncSession,
        receipt_id: UUID,
        terminal_id: str,
        fiscal_at: datetime,
        fm_z: Mapping[str, Any],
    ) -> None:
        """The Z-report's FM requisites: terminal, time and ``payload.fm_z`` (Z number, totals). The Z number
        is not an ``fm_receipt_seq`` (``uq_fiscal_fm_seq`` is the receipts' numbering)."""
        await s.execute(
            text(
                "UPDATE app.fiscal_receipts SET status = 'fiscalized', fm_terminal_id = :t, fiscal_at = :at, "
                "sent_at = COALESCE(sent_at, now()), attempts = attempts + 1, "
                "payload = payload || jsonb_build_object('fm_z', CAST(:z AS jsonb)), updated_at = now() "
                "WHERE id = :id"
            ),
            {"t": terminal_id, "at": fiscal_at, "z": json.dumps(dict(fm_z), default=str), "id": receipt_id},
        )

    async def unacked_by_register(self, s: AsyncSession, provider_side: bool) -> list[tuple[UUID, int]]:
        """Registers with fiscalized receipts the OFD has not acknowledged: ``(register_id, count)``;
        ``provider_side`` — only registers without a fiscal agent (server-side providers poll the partner)."""
        sql = (
            "SELECT f.cash_register_id, count(*) FROM app.fiscal_receipts f "
            "JOIN app.cash_registers cr ON cr.id = f.cash_register_id "
            "WHERE f.ofd_acked_at IS NULL AND f.status = 'fiscalized' AND f.kind <> 'z_report' "
        )
        if provider_side:
            sql += "AND cr.fiscal_agent_id IS NULL "
        sql += "GROUP BY f.cash_register_id ORDER BY f.cash_register_id"
        return [(r[0], int(r[1])) for r in await s.execute(text(sql))]

    async def readiness(
        self, s: AsyncSession, date_from: date, date_to: date
    ) -> tuple[int, int, datetime | None]:
        row = (
            await s.execute(
                text(
                    "SELECT count(*) FILTER (WHERE status IN ('pending','sent','failed')), "
                    "count(*) FILTER (WHERE status = 'fiscalized' AND ofd_acked_at IS NULL "
                    "AND kind <> 'z_report'), "
                    "min(created_at) FILTER (WHERE status = 'fiscalized' AND ofd_acked_at IS NULL "
                    "AND kind <> 'z_report') "
                    "FROM app.fiscal_receipts WHERE (created_at AT TIME ZONE 'Asia/Tashkent')::date "
                    "BETWEEN :a AND :b"
                ),
                {"a": date_from, "b": date_to},
            )
        ).one()
        return int(row[0]), int(row[1]), row[2]

    async def alert_counts(
        self, s: AsyncSession, at: datetime, branch_ids: tuple[UUID, ...] | None
    ) -> tuple[int, int, int, int]:
        params: dict[str, Any] = {"at": at}
        scope = ""
        if branch_ids is not None:
            scope = " AND cr.branch_id = ANY(:b)"
            params["b"] = list(branch_ids)
        row = (
            await s.execute(
                text(
                    "WITH oldest AS (SELECT f.cash_register_id, min(f.created_at) AS at "  # noqa: S608
                    "FROM app.fiscal_receipts f WHERE f.ofd_acked_at IS NULL AND f.kind <> 'z_report' "
                    "GROUP BY f.cash_register_id) "
                    "SELECT "
                    "(SELECT count(*) FROM oldest o JOIN app.cash_registers cr ON cr.id = o.cash_register_id "
                    f"WHERE o.at <= CAST(:at AS timestamptz) - interval '24 hours'{scope}), "
                    "(SELECT count(*) FROM oldest o JOIN app.cash_registers cr ON cr.id = o.cash_register_id "
                    f"WHERE o.at <= CAST(:at AS timestamptz) - interval '48 hours'{scope}), "
                    "(SELECT count(*) FROM app.cash_registers cr WHERE cr.archived_at IS NULL "
                    f"AND cr.fm_state IN ('locked','ack_overdue','memory_full'){scope}), "
                    "(SELECT count(*) FROM app.fiscal_receipts f JOIN app.cash_registers cr "
                    f"ON cr.id = f.cash_register_id WHERE f.status = 'failed'{scope})"
                ),
                params,
            )
        ).one()
        return int(row[0]), int(row[1]), int(row[2]), int(row[3])

    async def registers_overview(
        self, s: AsyncSession, branch_ids: tuple[UUID, ...] | None
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        scope = ""
        if branch_ids is not None:
            scope = " AND cr.branch_id = ANY(:b)"
            params["b"] = list(branch_ids)
        rows = await s.execute(
            text(
                "SELECT cr.id, cr.name, cr.branch_id, cr.fiscal_agent_id, cr.fiscal_local_device_id, "  # noqa: S608
                "cr.fm_state, cr.fm_receipts_pending, cr.last_unacked_receipt_at, "
                "(SELECT count(*) FROM app.fiscal_receipts f WHERE f.cash_register_id = cr.id "
                "AND f.ofd_acked_at IS NULL AND f.kind <> 'z_report') AS unacked_count, "
                "(SELECT min(f.created_at) FROM app.fiscal_receipts f WHERE f.cash_register_id = cr.id "
                "AND f.ofd_acked_at IS NULL AND f.kind <> 'z_report') AS oldest_unacked_at, "
                "(SELECT count(*) FROM app.fiscal_receipts f WHERE f.cash_register_id = cr.id "
                "AND f.status = 'failed') AS failed_count "
                f"FROM app.cash_registers cr WHERE cr.archived_at IS NULL{scope} ORDER BY cr.name, cr.id"
            ),
            params,
        )
        return [dict(r._mapping) for r in rows]

    # --- outbox jobs --------------------------------------------------------------------------------
    async def claim(self, s: AsyncSession, job_id: UUID | None) -> ClaimedJob | None:
        row = (
            await s.execute(
                text(
                    "UPDATE app.outbox_jobs j SET status = 'running', attempts = j.attempts + 1, "
                    "updated_at = now() "
                    "WHERE j.id = (SELECT o.id FROM app.outbox_jobs o WHERE o.kind = 'ofd_send' "
                    "AND (CAST(:jid AS uuid) IS NULL OR o.id = CAST(:jid AS uuid)) "
                    "AND ((o.status IN ('queued', 'retry') AND o.next_run_at <= now()) "
                    "OR (o.status = 'running' AND o.updated_at < now() - make_interval(secs => :stale))) "
                    "ORDER BY o.next_run_at, o.id LIMIT 1 FOR UPDATE SKIP LOCKED) "
                    "RETURNING j.id, j.payload, j.attempts"
                ),
                {"jid": str(job_id) if job_id else None, "stale": self._stale},
            )
        ).first()
        return ClaimedJob(row[0], _json(row[1]) or {}, row[2]) if row else None

    async def finish_job(
        self,
        s: AsyncSession,
        job_id: UUID,
        status: str,
        last_error: str | None,
        run_after: timedelta | None = None,
    ) -> None:
        await s.execute(
            text(
                "UPDATE app.outbox_jobs SET status = :st, last_error = :err, next_run_at = CASE WHEN "
                "CAST(:after AS double precision) IS NULL THEN next_run_at "
                "ELSE now() + make_interval(secs => CAST(:after AS double precision)) END, "
                "updated_at = now() WHERE id = :id AND kind = 'ofd_send'"
            ),
            {
                "st": status,
                "err": last_error,
                "id": job_id,
                "after": run_after.total_seconds() if run_after is not None else None,
            },
        )

    async def requeue(self, s: AsyncSession, receipt_id: UUID) -> UUID | None:
        value = (
            await s.execute(
                text(
                    "UPDATE app.outbox_jobs SET status = 'queued', next_run_at = now(), last_error = NULL, "
                    "updated_at = now() WHERE kind = 'ofd_send' AND idempotency_key = :k "
                    "AND status IN ('failed', 'retry', 'queued', 'done') RETURNING id"
                ),
                {"k": f"ofd_send:{receipt_id}"},
            )
        ).scalar_one_or_none()
        return value
