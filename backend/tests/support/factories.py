"""Minimal tenant worlds created through the real erp_app role and RLS."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from sqlalchemy import text

from app.core.db.base import uuid7
from app.core.db.session import Database, tenant_transaction


@dataclass(frozen=True)
class TenantWorld:
    tenant_id: UUID
    user_id: UUID
    branch_id: UUID
    cash_register_id: UUID
    device_id: UUID
    shift_id: UUID


async def create_tenant_world(db: Database, name: str) -> TenantWorld:
    tid, uid, bid, crid, did, sid = (uuid7() for _ in range(6))
    phone = f"+998{int(tid.int % 10**9):09d}"
    async with db.session_factory() as s, tenant_transaction(s, tid, user_id=uid):
        await s.execute(
            text("INSERT INTO app.tenants (id, name, phone) VALUES (:id, :name, :phone)"),
            {"id": tid, "name": name, "phone": phone},
        )
        await s.execute(
            text("INSERT INTO app.users (id, phone, name) VALUES (:id, :phone, :name)"),
            {"id": uid, "phone": phone, "name": f"{name} egasi"},
        )
        await s.execute(
            text("INSERT INTO app.memberships (tenant_id, user_id) VALUES (:t, :u)"), {"t": tid, "u": uid}
        )
        await s.execute(
            text(
                "INSERT INTO app.branches (id, tenant_id, code, name, is_default, settlement_category, activity_type) "
                "VALUES (:id, :t, '01', 'Asosiy', true, 'city_100k_plus', 'retail')"
            ),
            {"id": bid, "t": tid},
        )
        await s.execute(
            text(
                "INSERT INTO app.cash_registers (id, tenant_id, branch_id, name, kind) VALUES (:id, :t, :b, 'K1', 'web')"
            ),
            {"id": crid, "t": tid, "b": bid},
        )
        await s.execute(
            text(
                "INSERT INTO app.devices (id, tenant_id, cash_register_id, kind) VALUES (:id, :t, :c, 'web')"
            ),
            {"id": did, "t": tid, "c": crid},
        )
        await s.execute(
            text(
                "INSERT INTO app.shifts (id, tenant_id, branch_id, cash_register_id, device_id, shift_no, opened_by) "
                "VALUES (:id, :t, :b, :c, :d, 1, :u)"
            ),
            {"id": sid, "t": tid, "b": bid, "c": crid, "d": did, "u": uid},
        )
    return TenantWorld(tid, uid, bid, crid, did, sid)


async def create_sale(db: Database, w: TenantWorld, total: str = "120000.00") -> UUID:
    sale_id = uuid7()
    async with db.session_factory() as s, tenant_transaction(s, w.tenant_id, user_id=w.user_id):
        await s.execute(
            text(
                "INSERT INTO app.sales (id, tenant_id, branch_id, doc_date, shift_id, cash_register_id, "
                "total_amount, created_by, device_id) VALUES (:id, :t, :b, :d, :s, :c, :total, :u, :dev)"
            ),
            {
                "id": sale_id,
                "t": w.tenant_id,
                "b": w.branch_id,
                "d": date(2026, 10, 16),
                "s": w.shift_id,
                "c": w.cash_register_id,
                "total": total,
                "u": w.user_id,
                "dev": w.device_id,
            },
        )
    return sale_id
