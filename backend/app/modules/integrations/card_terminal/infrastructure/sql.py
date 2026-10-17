# ruff: noqa: S608 -- column lists / WHERE fragments are module constants; every value is a bound parameter
"""Raw-SQL repository of the card slice (``app.card_terminals``, ``app.card_terminal_transactions``,
``app.card_terminal_settlements``, ``platform.card_bin_rules``; 12 §2.5/§2.6). Runs under RLS in the
caller's ``tenant_transaction``."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import RowMapping, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.integrations.card_terminal.application.ports import (
    OrphanRow,
    SettlementRow,
    TerminalFilter,
    TerminalRow,
    TxRow,
)

_TERMINAL_COLS = (
    "id, tenant_id, branch_id, cash_register_id, name, vendor, model, adapter, driver, agent_id, local_id, "
    "host(host) AS host, port, vendor_terminal_ref, tid, mid, acquirer_counterparty_id, status, is_default, "
    "capabilities, health_status, health_checked_at, version, created_at, updated_at"
)
_TX_COLS = (
    "id, tenant_id, branch_id, card_terminal_id, cash_register_id, shift_id, device_id, kind, "
    "original_transaction_id, amount, approved_amount, status, approval_code, rrn, stan, card_mask, "
    "card_scheme, "
    "card_type, card_type_source, entry_mode, tid, mid, acquirer, decline_code, decline_message, "
    "resolved_by, "
    "resolved_by_user_id, client_event_id, doc_type, doc_id, settlement_id, requested_at, tx_at, "
    "resolved_at, "
    "created_by, created_at, updated_at"
)
_JSONB = frozenset({"capabilities", "terminal_response"})


_TERMINAL_FIELDS = tuple(TerminalRow.__dataclass_fields__)
_TX_FIELDS = tuple(TxRow.__dataclass_fields__)


def _terminal(row: RowMapping) -> TerminalRow:
    return TerminalRow(**{k: row[k] for k in _TERMINAL_FIELDS})


def _tx(row: RowMapping) -> TxRow:
    return TxRow(**{k: row[k] for k in _TX_FIELDS})


def _params(values: Mapping[str, Any]) -> dict[str, Any]:
    return {k: json.dumps(v, default=str) if k in _JSONB else v for k, v in values.items()}


def _placeholder(column: str) -> str:
    if column in _JSONB:
        return f"CAST(:{column} AS jsonb)"
    if column == "host":
        return "CAST(:host AS inet)"
    return f":{column}"


class SqlCardRepository:
    # --- terminals ----------------------------------------------------------------------------------
    async def terminal(self, s: AsyncSession, terminal_id: UUID, *, lock: bool = False) -> TerminalRow | None:
        sql = f"SELECT {_TERMINAL_COLS} FROM app.card_terminals WHERE id = :id" + (
            " FOR UPDATE" if lock else ""
        )
        row = (await s.execute(text(sql), {"id": terminal_id})).mappings().first()
        return None if row is None else _terminal(row)

    async def list_terminals(
        self, s: AsyncSession, flt: TerminalFilter, page: int, size: int
    ) -> tuple[list[TerminalRow], int]:
        where = ["true"]
        params: dict[str, Any] = {"limit": size, "offset": (page - 1) * size}
        if flt.branch_ids:
            where.append("branch_id = ANY(:branch_ids)")
            params["branch_ids"] = list(flt.branch_ids)
        if flt.branch_id is not None:
            where.append("branch_id = :branch_id")
            params["branch_id"] = flt.branch_id
        if flt.cash_register_id is not None:
            where.append("cash_register_id = :cash_register_id")
            params["cash_register_id"] = flt.cash_register_id
        if flt.status is not None:
            where.append("status = :status")
            params["status"] = flt.status
        else:
            where.append("status <> 'archived'")
        cond = " AND ".join(where)
        total = int(
            (
                await s.execute(text(f"SELECT count(*) FROM app.card_terminals WHERE {cond}"), params)
            ).scalar_one()
        )
        rows = (
            await s.execute(
                text(
                    f"SELECT {_TERMINAL_COLS} FROM app.card_terminals WHERE {cond} "
                    "ORDER BY name, id LIMIT :limit OFFSET :offset"
                ),
                params,
            )
        ).mappings()
        return [_terminal(r) for r in rows], total

    async def insert_terminal(self, s: AsyncSession, values: Mapping[str, Any]) -> None:
        cols = list(values)
        sql = (
            f"INSERT INTO app.card_terminals ({', '.join(cols)}) "
            f"VALUES ({', '.join(_placeholder(c) for c in cols)})"
        )
        await s.execute(text(sql), _params(values))

    async def update_terminal(self, s: AsyncSession, terminal_id: UUID, values: Mapping[str, Any]) -> None:
        sets = ", ".join(f"{c} = {_placeholder(c)}" for c in values)
        await s.execute(
            text(f"UPDATE app.card_terminals SET {sets}, version = version + 1 WHERE id = :_id"),
            {**_params(values), "_id": terminal_id},
        )

    async def clear_default(self, s: AsyncSession, cash_register_id: UUID, except_id: UUID) -> None:
        await s.execute(
            text(
                "UPDATE app.card_terminals SET is_default = false, version = version + 1 "
                "WHERE cash_register_id = :c AND is_default AND id <> :id"
            ),
            {"c": cash_register_id, "id": except_id},
        )

    async def active_terminal_count(self, s: AsyncSession, cash_register_id: UUID) -> int:
        return int(
            (
                await s.execute(
                    text(
                        "SELECT count(*) FROM app.card_terminals WHERE cash_register_id = :c AND status = "
                        "'active'"
                    ),
                    {"c": cash_register_id},
                )
            ).scalar_one()
        )

    async def register_branch(self, s: AsyncSession, cash_register_id: UUID) -> UUID | None:
        value: UUID | None = (
            await s.execute(
                text("SELECT branch_id FROM app.cash_registers WHERE id = :c AND archived_at IS NULL"),
                {"c": cash_register_id},
            )
        ).scalar_one_or_none()
        return value

    async def manual_fallback_setting(self, s: AsyncSession) -> str | None:
        value: str | None = (
            await s.execute(
                text(
                    "SELECT settings ->> 'card_manual_fallback' FROM app.tenants WHERE id = "
                    "app.current_tenant_id()"
                )
            )
        ).scalar_one_or_none()
        return value

    async def device_register(self, s: AsyncSession, device_id: UUID) -> UUID | None:
        value: UUID | None = (
            await s.execute(
                text("SELECT cash_register_id FROM app.devices WHERE id = :d AND revoked_at IS NULL"),
                {"d": device_id},
            )
        ).scalar_one_or_none()
        return value

    async def approval_request_resolver(self, s: AsyncSession, request_id: UUID) -> UUID | None:
        value: UUID | None = (
            await s.execute(
                text("SELECT resolved_by FROM app.approval_requests WHERE id = :id"), {"id": request_id}
            )
        ).scalar_one_or_none()
        return value

    async def shift_exists(self, s: AsyncSession, shift_id: UUID) -> bool:
        return bool(
            (
                await s.execute(
                    text("SELECT EXISTS (SELECT 1 FROM app.shifts WHERE id = :id)"), {"id": shift_id}
                )
            ).scalar_one()
        )

    async def tid_taken(self, s: AsyncSession, tid: str, exclude: UUID) -> bool:
        return bool(
            (
                await s.execute(
                    text(
                        "SELECT EXISTS (SELECT 1 FROM app.card_terminals WHERE tid = :tid AND status <> "
                        "'archived' "
                        "AND id <> :x)"
                    ),
                    {"tid": tid, "x": exclude},
                )
            ).scalar_one()
        )

    async def agent_local_taken(self, s: AsyncSession, agent_id: UUID, local_id: str, exclude: UUID) -> bool:
        return bool(
            (
                await s.execute(
                    text(
                        "SELECT EXISTS (SELECT 1 FROM app.card_terminals WHERE agent_id = :a AND local_id = "
                        ":l "
                        "AND status <> 'archived' AND id <> :x)"
                    ),
                    {"a": agent_id, "l": local_id, "x": exclude},
                )
            ).scalar_one()
        )

    # --- transactions -------------------------------------------------------------------------------
    async def tx(self, s: AsyncSession, tx_id: UUID, *, lock: bool = False) -> TxRow | None:
        sql = f"SELECT {_TX_COLS} FROM app.card_terminal_transactions WHERE id = :id" + (
            " FOR UPDATE" if lock else ""
        )
        row = (await s.execute(text(sql), {"id": tx_id})).mappings().first()
        return None if row is None else _tx(row)

    async def insert_tx(self, s: AsyncSession, values: Mapping[str, Any]) -> None:
        cols = list(values)
        sql = (
            f"INSERT INTO app.card_terminal_transactions ({', '.join(cols)}) "
            f"VALUES ({', '.join(_placeholder(c) for c in cols)})"
        )
        await s.execute(text(sql), _params(values))

    async def update_tx(self, s: AsyncSession, tx_id: UUID, values: Mapping[str, Any]) -> None:
        if not values:
            return
        sets = ", ".join(f"{c} = {_placeholder(c)}" for c in values)
        await s.execute(
            text(f"UPDATE app.card_terminal_transactions SET {sets} WHERE id = :_id"),
            {**_params(values), "_id": tx_id},
        )

    async def clone_tx(
        self,
        s: AsyncSession,
        source_id: UUID,
        new_id: UUID,
        *,
        doc: tuple[str, UUID],
        client_event_id: UUID | None,
    ) -> None:
        """Duplicate of an approved attempt for a second document (event mode, see ``TxWriter._link``)."""
        await s.execute(
            text(
                "INSERT INTO app.card_terminal_transactions (id, tenant_id, branch_id, card_terminal_id, "
                "cash_register_id, shift_id, device_id, kind, original_transaction_id, amount, "
                "approved_amount, "
                "status, approval_code, rrn, stan, card_mask, card_scheme, card_type, card_type_source, "
                "entry_mode, "
                "tid, mid, acquirer, resolved_by, resolved_by_user_id, terminal_response, slip_text, "
                "client_event_id, doc_type, doc_id, requested_at, tx_at, resolved_at, created_by) "
                "SELECT :new_id, tenant_id, branch_id, card_terminal_id, cash_register_id, shift_id, "
                "device_id, "
                "kind, original_transaction_id, amount, COALESCE(approved_amount, amount), 'approved', "
                "approval_code, rrn, stan, card_mask, card_scheme, card_type, card_type_source, entry_mode, "
                "NULL, "
                "mid, acquirer, COALESCE(resolved_by, 'auto'), resolved_by_user_id, terminal_response || "
                "jsonb_build_object('duplicate_of', id::text, 'tid', tid), slip_text, :event, :doc_type, "
                ":doc_id, "
                "requested_at, tx_at, COALESCE(resolved_at, now()), created_by "
                "FROM app.card_terminal_transactions WHERE id = :source_id"
            ),
            {
                "new_id": new_id,
                "source_id": source_id,
                "event": client_event_id,
                "doc_type": doc[0],
                "doc_id": doc[1],
            },
        )

    async def unresolved_on_terminal(self, s: AsyncSession, terminal_id: UUID, exclude: UUID) -> list[str]:
        rows = await s.execute(
            text(
                "SELECT status FROM app.card_terminal_transactions WHERE card_terminal_id = :t "
                "AND status IN ('pending','unknown') AND id <> :x"
            ),
            {"t": terminal_id, "x": exclude},
        )
        return [r[0] for r in rows]

    async def unresolved_in_shift(self, s: AsyncSession, shift_id: UUID) -> int:
        return int(
            (
                await s.execute(
                    text(
                        "SELECT count(*) FROM app.card_terminal_transactions WHERE shift_id = :s "
                        "AND status IN ('pending','unknown')"
                    ),
                    {"s": shift_id},
                )
            ).scalar_one()
        )

    async def rrn_taken(self, s: AsyncSession, tid: str, rrn: str, exclude: UUID) -> UUID | None:
        value: UUID | None = (
            await s.execute(
                text(
                    "SELECT id FROM app.card_terminal_transactions WHERE kind = 'purchase' AND tid = :tid "
                    "AND rrn = :rrn AND id <> :x LIMIT 1"
                ),
                {"tid": tid, "rrn": rrn, "x": exclude},
            )
        ).scalar_one_or_none()
        return value

    async def bin_rule_type(self, s: AsyncSession, bin_value: str, on: date) -> str | None:
        """Longest matching prefix valid on ``on`` (12 ``platform.card_bin_rules``)."""
        value: str | None = (
            await s.execute(
                text(
                    "SELECT card_type FROM platform.card_bin_rules WHERE :bin LIKE bin_prefix || '%' "
                    "AND valid_from <= :on AND (valid_to IS NULL OR valid_to >= :on) "
                    "ORDER BY length(bin_prefix) DESC, valid_from DESC LIMIT 1"
                ),
                {"bin": bin_value, "on": on},
            )
        ).scalar_one_or_none()
        return value

    async def doc_by_client_event(self, s: AsyncSession, client_event_id: UUID) -> tuple[str, UUID] | None:
        row = (
            await s.execute(
                text(
                    "SELECT 'sales', id FROM app.sales WHERE client_event_id = :e "
                    "UNION ALL SELECT 'returns', id FROM app.returns WHERE client_event_id = :e "
                    "UNION ALL SELECT 'debt_payments', id FROM app.debt_payments WHERE client_event_id = :e "
                    "LIMIT 1"
                ),
                {"e": client_event_id},
            )
        ).first()
        return None if row is None else (str(row[0]), row[1])

    async def manager_resolved_by_event(self, s: AsyncSession, client_event_id: UUID) -> list[TxRow]:
        rows = (
            await s.execute(
                text(
                    f"SELECT {_TX_COLS} FROM app.card_terminal_transactions WHERE client_event_id = :e "
                    "AND resolved_by = 'manager' AND status = 'approved' ORDER BY created_at FOR UPDATE"
                ),
                {"e": client_event_id},
            )
        ).mappings()
        return [_tx(r) for r in rows]

    # --- settlements --------------------------------------------------------------------------------
    async def settlement(self, s: AsyncSession, settlement_id: UUID) -> SettlementRow | None:
        row = (
            (
                await s.execute(
                    text(
                        "SELECT id, card_terminal_id, status, net_total, expected_total, variance "
                        "FROM app.card_terminal_settlements WHERE id = :id"
                    ),
                    {"id": settlement_id},
                )
            )
            .mappings()
            .first()
        )
        return None if row is None else SettlementRow(**row)

    async def unbatched_totals(self, s: AsyncSession, terminal_id: UUID) -> tuple[int, Decimal, Decimal]:
        """Approved purchases (incl. later voided ones are excluded) and refunds not yet in a batch."""
        row = (
            await s.execute(
                text(
                    "SELECT count(*) FILTER (WHERE kind = 'purchase'), "
                    "COALESCE(sum(approved_amount) FILTER (WHERE kind = 'purchase'), 0), "
                    "COALESCE(sum(approved_amount) FILTER (WHERE kind = 'refund'), 0) "
                    "FROM app.card_terminal_transactions WHERE card_terminal_id = :t AND settlement_id IS "
                    "NULL "
                    "AND status = 'approved' AND kind IN ('purchase','refund') "
                    "AND NOT (terminal_response ? 'duplicate_of')"
                ),
                {"t": terminal_id},
            )
        ).one()
        return int(row[0]), Decimal(row[1]), Decimal(row[2])

    async def insert_settlement(self, s: AsyncSession, values: Mapping[str, Any]) -> SettlementRow:
        cols = list(values)
        row = (
            (
                await s.execute(
                    text(
                        f"INSERT INTO app.card_terminal_settlements ({', '.join(cols)}) "
                        f"VALUES ({', '.join(_placeholder(c) for c in cols)}) "
                        "RETURNING id, card_terminal_id, status, net_total, expected_total, variance"
                    ),
                    _params(values),
                )
            )
            .mappings()
            .one()
        )
        return SettlementRow(**row)

    async def stamp_settlement(self, s: AsyncSession, terminal_id: UUID, settlement_id: UUID) -> None:
        await s.execute(
            text(
                "UPDATE app.card_terminal_transactions SET settlement_id = :sid WHERE card_terminal_id = :t "
                "AND settlement_id IS NULL AND status IN ('approved','voided') AND kind IN "
                "('purchase','refund')"
            ),
            {"sid": settlement_id, "t": terminal_id},
        )

    # --- orphan sweep -------------------------------------------------------------------------------
    async def orphans(self, s: AsyncSession, older_than: datetime, limit: int) -> list[OrphanRow]:
        rows = (
            await s.execute(
                text(
                    "SELECT id, card_terminal_id, branch_id, device_id, client_event_id, approved_amount AS "
                    "amount, "
                    "rrn, created_at FROM app.card_terminal_transactions WHERE status = 'approved' "
                    "AND kind = 'purchase' AND doc_id IS NULL AND created_at < :before AND NOT EXISTS "
                    "(SELECT 1 FROM "
                    "app.sync_exceptions x WHERE x.kind = 'card_orphan_transaction' AND x.doc_type = "
                    "'card_terminal_transactions' AND x.doc_id = card_terminal_transactions.id) "
                    "ORDER BY created_at LIMIT :limit"
                ),
                {"before": older_than, "limit": limit},
            )
        ).mappings()
        return [OrphanRow(**r) for r in rows]

    async def orphan_reported(self, s: AsyncSession, tx_id: UUID) -> bool:
        return bool(
            (
                await s.execute(
                    text(
                        "SELECT EXISTS (SELECT 1 FROM app.sync_exceptions WHERE kind = "
                        "'card_orphan_transaction' "
                        "AND doc_type = 'card_terminal_transactions' AND doc_id = :id)"
                    ),
                    {"id": tx_id},
                )
            ).scalar_one()
        )

    async def insert_sync_exception(
        self,
        s: AsyncSession,
        *,
        kind: str,
        device_id: UUID | None,
        client_event_id: UUID | None,
        doc_type: str | None,
        doc_id: UUID | None,
        details: Mapping[str, Any],
    ) -> None:
        await s.execute(
            text(
                "INSERT INTO app.sync_exceptions (tenant_id, device_id, client_event_id, kind, doc_type, "
                "doc_id, "
                "details) VALUES (app.current_tenant_id(), :d, :e, :k, :dt, :di, CAST(:details AS jsonb))"
            ),
            {
                "d": device_id, "e": client_event_id, "k": kind, "dt": doc_type, "di": doc_id,
                "details": json.dumps(dict(details), default=str),
            },
        )  # fmt: skip
