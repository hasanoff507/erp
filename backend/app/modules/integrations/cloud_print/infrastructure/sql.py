# ruff: noqa: S608 -- column lists / WHERE fragments are module constants; every value is a bound parameter
"""Raw-SQL repository of the cloud print slice (``app.cloud_printers``, ``app.print_jobs``; 12 §2.5a).

Everything runs under RLS in the caller's ``tenant_transaction`` except :meth:`printer_by_secret`, which calls
the SECURITY DEFINER ``app.cloud_printer_by_secret`` from an unscoped transaction (printer polls carry no
user session)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import UUID

from sqlalchemy import RowMapping, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.integrations.cloud_print.application.ports import (
    JobRow,
    PrinterAuth,
    PrinterFilter,
    PrinterRow,
)
from app.modules.integrations.cloud_print.domain.model import (
    JOB_TTL_MINUTES,
    ONLINE_WITHIN_S,
    UNCONFIRMED_MINUTES,
)

_PRINTER_COLS = (
    "id, tenant_id, branch_id, name, protocol, model, status, printer_mac, last_poll_at, last_status, "
    "version, "
    f"COALESCE(last_poll_at > now() - interval '{ONLINE_WITHIN_S} seconds', false) AS online"
)
_JOB_COLS = (
    "id, tenant_id, branch_id, cloud_printer_id, kind, width_dots, height_dots, data, data_sha256, status, "
    "result_code, attempts"
)


def _printer(row: RowMapping) -> PrinterRow:
    return PrinterRow(**{k: row[k] for k in PrinterRow.__dataclass_fields__})


def _job(row: RowMapping) -> JobRow:
    values = {k: row[k] for k in JobRow.__dataclass_fields__}
    if values["data"] is not None:
        values["data"] = bytes(values["data"])
    return JobRow(**values)


class SqlCloudPrintRepository:
    async def printer_by_secret(
        self, s: AsyncSession, printer_id: UUID, secret_hash: str
    ) -> PrinterAuth | None:
        row = (
            await s.execute(
                text("SELECT tenant_id, branch_id, protocol FROM app.cloud_printer_by_secret(:id, :h)"),
                {"id": printer_id, "h": secret_hash},
            )
        ).first()
        return None if row is None else PrinterAuth(printer_id, row[0], row[1], str(row[2]))

    async def printer(self, s: AsyncSession, printer_id: UUID, *, lock: bool = False) -> PrinterRow | None:
        sql = f"SELECT {_PRINTER_COLS} FROM app.cloud_printers WHERE id = :id" + (
            " FOR UPDATE" if lock else ""
        )
        row = (await s.execute(text(sql), {"id": printer_id})).mappings().first()
        return None if row is None else _printer(row)

    async def list_printers(
        self, s: AsyncSession, flt: PrinterFilter, page: int, size: int
    ) -> tuple[list[PrinterRow], int]:
        where = ["true"]
        params: dict[str, Any] = {"limit": size, "offset": (page - 1) * size}
        if flt.branch_ids:
            where.append("branch_id = ANY(:branch_ids)")
            params["branch_ids"] = list(flt.branch_ids)
        if flt.branch_id is not None:
            where.append("branch_id = :branch_id")
            params["branch_id"] = flt.branch_id
        if flt.status is not None:
            where.append("status = :status")
            params["status"] = flt.status
        else:
            where.append("status <> 'archived'")
        cond = " AND ".join(where)
        total = int(
            (
                await s.execute(text(f"SELECT count(*) FROM app.cloud_printers WHERE {cond}"), params)
            ).scalar_one()
        )
        rows = (
            await s.execute(
                text(
                    f"SELECT {_PRINTER_COLS} FROM app.cloud_printers WHERE {cond} "
                    "ORDER BY name, id LIMIT :limit OFFSET :offset"
                ),
                params,
            )
        ).mappings()
        return [_printer(r) for r in rows], total

    async def insert_printer(self, s: AsyncSession, values: Mapping[str, Any]) -> None:
        cols = list(values)
        await s.execute(
            text(
                f"INSERT INTO app.cloud_printers ({', '.join(cols)}) "
                f"VALUES ({', '.join(':' + c for c in cols)})"
            ),
            dict(values),
        )

    async def update_printer(self, s: AsyncSession, printer_id: UUID, values: Mapping[str, Any]) -> None:
        sets = ", ".join(f"{c} = :{c}" for c in values)
        await s.execute(
            text(f"UPDATE app.cloud_printers SET {sets}, version = version + 1 WHERE id = :_id"),
            {**values, "_id": printer_id},
        )

    async def touch_poll(
        self, s: AsyncSession, printer_id: UUID, *, mac: str | None, status: str | None
    ) -> None:
        await s.execute(
            text(
                "UPDATE app.cloud_printers SET last_poll_at = now(), "
                "printer_mac = COALESCE(:mac, printer_mac), last_status = COALESCE(:st, last_status) "
                "WHERE id = :id"
            ),
            {"id": printer_id, "mac": mac, "st": status},
        )

    async def queued_count(self, s: AsyncSession, printer_id: UUID) -> int:
        return int(
            (
                await s.execute(
                    text(
                        "SELECT count(*) FROM app.print_jobs WHERE cloud_printer_id = :p "
                        "AND status IN ('queued','printing')"
                    ),
                    {"p": printer_id},
                )
            ).scalar_one()
        )

    # --- jobs -----------------------------------------------------------------------------------------
    async def job(self, s: AsyncSession, job_id: UUID, *, lock: bool = False) -> JobRow | None:
        sql = f"SELECT {_JOB_COLS} FROM app.print_jobs WHERE id = :id" + (" FOR UPDATE" if lock else "")
        row = (await s.execute(text(sql), {"id": job_id})).mappings().first()
        return None if row is None else _job(row)

    async def insert_job(self, s: AsyncSession, values: Mapping[str, Any]) -> None:
        cols = list(values)
        await s.execute(
            text(
                f"INSERT INTO app.print_jobs ({', '.join(cols)}, expires_at) VALUES "
                f"({', '.join(':' + c for c in cols)}, now() + interval '{JOB_TTL_MINUTES} minutes')"
            ),
            dict(values),
        )

    async def expire_jobs(self, s: AsyncSession, printer_id: UUID) -> int:
        """Queued past ``expires_at`` → ``expired``; handed out but never confirmed for
        ``UNCONFIRMED_MINUTES`` → ``unconfirmed`` (failed, never re-sent: it may have printed)."""
        result = await s.execute(
            text(
                "UPDATE app.print_jobs SET status = 'failed', data = NULL, finished_at = now(), "
                "result_code = CASE WHEN status = 'queued' THEN 'expired' ELSE 'unconfirmed' END "
                "WHERE cloud_printer_id = :p AND ((status = 'queued' AND expires_at < now()) OR "
                f"(status = 'printing' AND printing_at < now() - interval '{UNCONFIRMED_MINUTES} minutes'))"
            ),
            {"p": printer_id},
        )
        return int(getattr(result, "rowcount", 0) or 0)

    async def next_queued(self, s: AsyncSession, printer_id: UUID, limit: int) -> list[JobRow]:
        rows = (
            await s.execute(
                text(
                    f"SELECT {_JOB_COLS} FROM app.print_jobs WHERE cloud_printer_id = :p "
                    "AND status = 'queued' "
                    "ORDER BY id LIMIT :limit FOR UPDATE SKIP LOCKED"
                ),
                {"p": printer_id, "limit": limit},
            )
        ).mappings()
        return [_job(r) for r in rows]

    async def printing_jobs(self, s: AsyncSession, printer_id: UUID) -> list[JobRow]:
        rows = (
            await s.execute(
                text(
                    f"SELECT {_JOB_COLS} FROM app.print_jobs WHERE cloud_printer_id = :p "
                    "AND status = 'printing' "
                    "ORDER BY id FOR UPDATE"
                ),
                {"p": printer_id},
            )
        ).mappings()
        return [_job(r) for r in rows]

    async def mark_printing(self, s: AsyncSession, job_id: UUID) -> None:
        await s.execute(
            text(
                "UPDATE app.print_jobs SET status = 'printing', attempts = attempts + 1, printing_at = now() "
                "WHERE id = :id AND status IN ('queued','printing')"
            ),
            {"id": job_id},
        )

    async def finish_job(self, s: AsyncSession, job_id: UUID, *, status: str, code: str | None) -> None:
        await s.execute(
            text(
                "UPDATE app.print_jobs SET status = :st, result_code = :code, data = NULL, "
                "finished_at = now() "
                "WHERE id = :id AND status IN ('queued','printing')"
            ),
            {"id": job_id, "st": status, "code": code},
        )

    async def requeue(self, s: AsyncSession, job_id: UUID, code: str | None) -> None:
        await s.execute(
            text(
                "UPDATE app.print_jobs SET status = 'queued', result_code = :code "
                "WHERE id = :id AND status = 'printing'"
            ),
            {"id": job_id, "code": code},
        )
