"""``approval_requests`` / ``doc_approvals`` / grants SQL (12 §2.5a); caller's tenant transaction."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.access.application.approvals import ApprovalRequestRow, QueueFilter
from app.modules.access.domain.approvals import UserGrant

_GRANTS = text(
    "SELECT m.status, m.branch_ids, "
    "COALESCE(bool_or(r.system_code = 'owner'), false) AS owner, "
    "array_remove(array_agg(rp.permission_code), NULL) AS codes, "
    "array_agg(rp.limit_value) FILTER (WHERE rp.permission_code IS NOT NULL) AS limits, "
    "array_agg(rp.permission_code) FILTER (WHERE rp.permission_code IS NOT NULL) AS limit_codes "
    "FROM app.memberships m "
    "LEFT JOIN app.roles r ON r.tenant_id = m.tenant_id AND r.id = ANY(m.role_ids) AND r.archived_at IS NULL "
    "LEFT JOIN app.role_permissions rp ON rp.tenant_id = m.tenant_id AND rp.role_id = r.id "
    "AND rp.permission_code = ANY(CAST(:codes AS text[])) "
    "WHERE m.user_id = :u GROUP BY m.status, m.branch_ids"
)

_COLUMNS = (
    "ar.id, ar.branch_id, ar.kind, ar.permission_code, ar.requested_value, ar.context, ar.linked_doc_type, "
    "ar.linked_doc_id, ar.device_id, "
    "CASE WHEN ar.status = 'pending' AND ar.expires_at < now() THEN 'expired' ELSE ar.status END, "
    "ar.requested_by, u.name, ar.requested_at, ar.expires_at, ar.resolved_by, ar.resolved_at, "
    "ar.reject_reason, "
    "ar.consumed_at"
)


def _row(r: Any) -> ApprovalRequestRow:
    return ApprovalRequestRow(
        id=r[0],
        branch_id=r[1],
        kind=r[2],
        permission_code=r[3],
        requested_value=r[4],
        context=r[5] or {},
        linked_doc_type=r[6],
        linked_doc_id=r[7],
        device_id=r[8],
        status=r[9],
        requested_by=r[10],
        requested_by_name=r[11],
        requested_at=r[12],
        expires_at=r[13],
        resolved_by=r[14],
        resolved_at=r[15],
        reject_reason=r[16],
        consumed_at=r[17],
    )


class SqlApprovalRepository:
    async def held_permissions(
        self, s: AsyncSession, user_id: UUID, codes: Sequence[str]
    ) -> dict[str, UserGrant]:
        row = (await s.execute(_GRANTS, {"u": user_id, "codes": list(codes)})).first()
        if row is None:
            return {c: UserGrant(False, False, (), ()) for c in codes}
        active = row[0] == "active"
        branch_ids = tuple(str(b) for b in (row[1] or ()))
        owner = bool(row[2])
        pairs: list[tuple[str, Decimal | None]] = list(zip(row[5] or [], row[4] or [], strict=True))
        return {
            code: UserGrant(active, owner, branch_ids, tuple(v for c, v in pairs if c == code))
            for code in codes
        }

    async def grant(self, s: AsyncSession, user_id: UUID, code: str) -> UserGrant:
        return (await self.held_permissions(s, user_id, [code]))[code]

    async def get_request(
        self, s: AsyncSession, request_id: UUID, *, lock: bool = False
    ) -> ApprovalRequestRow | None:
        sql = (
            f"SELECT {_COLUMNS} FROM app.approval_requests ar LEFT JOIN app.users u ON u.id = "  # noqa: S608
            "ar.requested_by "
            "WHERE ar.id = :id" + (" FOR UPDATE OF ar" if lock else "")
        )
        r = (await s.execute(text(sql), {"id": request_id})).first()
        return None if r is None else _row(r)

    async def insert_request(self, s: AsyncSession, row: Mapping[str, Any]) -> None:
        await s.execute(
            text(
                "INSERT INTO app.approval_requests (id, tenant_id, branch_id, kind, permission_code, "
                "requested_value, "
                "context, linked_doc_type, linked_doc_id, device_id, requested_by, requested_at, expires_at) "
                "VALUES (:id, :tenant_id, :branch_id, :kind, :permission_code, :requested_value, "
                "CAST(:context AS jsonb), :linked_doc_type, :linked_doc_id, :device_id, :requested_by, "
                ":requested_at, :expires_at)"
            ),
            dict(row),
        )

    async def resolve(
        self, s: AsyncSession, request_id: UUID, *, status: str, user_id: UUID, reason: str | None
    ) -> None:
        await s.execute(
            text(
                "UPDATE app.approval_requests SET status = :st, resolved_by = :u, resolved_at = now(), "
                "reject_reason = :r, updated_at = now() WHERE id = :id AND status = 'pending'"
            ),
            {"st": status, "u": user_id, "r": reason, "id": request_id},
        )

    async def consume(self, s: AsyncSession, request_id: UUID) -> None:
        await s.execute(
            text(
                "UPDATE app.approval_requests SET status = 'consumed', consumed_at = now(), updated_at = "
                "now() "
                "WHERE id = :id AND status = 'approved'"
            ),
            {"id": request_id},
        )

    async def insert_doc_approval(self, s: AsyncSession, row: Mapping[str, Any]) -> None:
        await s.execute(
            text(
                "INSERT INTO app.doc_approvals (id, tenant_id, doc_type, doc_id, line_id, kind, mode, "
                "approved_by, "
                "approval_request_id, pin_verified_locally, requested_value, approved_at) VALUES (:id, "
                ":tenant_id, "
                ":doc_type, :doc_id, :line_id, :kind, :mode, :approved_by, :approval_request_id, "
                ":pin_verified_locally, :requested_value, :approved_at)"
            ),
            dict(row),
        )

    async def list_requests(self, s: AsyncSession, flt: QueueFilter) -> list[ApprovalRequestRow]:
        params: dict[str, Any] = {"viewer": flt.viewer_id, "lim": flt.limit}
        visible = ["ar.requested_by = :viewer"]
        for i, (code, limit) in enumerate(sorted(flt.permissions.items())):
            params[f"c{i}"] = code
            if limit is None:
                visible.append(f"ar.permission_code = :c{i}")
            else:
                params[f"l{i}"] = limit
                visible.append(
                    f"(ar.permission_code = :c{i} AND (ar.kind = 'card_manual_entry' OR ar.requested_value "
                    "IS NULL "
                    f"OR ar.requested_value <= :l{i}))"
                )
        where = ["(" + " OR ".join(visible) + ")"]
        status_expr = (
            "CASE WHEN ar.status = 'pending' AND ar.expires_at < now() THEN 'expired' ELSE ar.status END"
        )
        if flt.status is not None:
            where.append(f"{status_expr} = :st")
            params["st"] = flt.status
        if flt.branch_ids is not None:
            where.append("ar.branch_id = ANY(CAST(:branches AS uuid[]))")
            params["branches"] = [str(b) for b in flt.branch_ids]
        if flt.cursor is not None:
            where.append("(ar.requested_at, ar.id) < (:cat, :cid)")
            params["cat"], params["cid"] = flt.cursor
        sql = (
            f"SELECT {_COLUMNS} FROM app.approval_requests ar LEFT JOIN app.users u ON u.id = "  # noqa: S608
            "ar.requested_by "
            f"WHERE {' AND '.join(where)} ORDER BY ar.requested_at DESC, ar.id DESC LIMIT :lim"
        )
        return [_row(r) for r in (await s.execute(text(sql), params)).all()]

    async def expire_due(self, s: AsyncSession, now: datetime) -> list[UUID]:
        rows = await s.execute(
            text(
                "UPDATE app.approval_requests SET status = 'expired', updated_at = now() "
                "WHERE status = 'pending' AND expires_at < :now RETURNING id"
            ),
            {"now": now},
        )
        return [r[0] for r in rows.all()]

    async def expire_due_linked(
        self, s: AsyncSession, now: datetime
    ) -> list[tuple[UUID, str | None, UUID | None]]:
        rows = await s.execute(
            text(
                "UPDATE app.approval_requests SET status = 'expired', updated_at = now() "
                "WHERE status = 'pending' AND expires_at < :now RETURNING id, linked_doc_type, linked_doc_id"
            ),
            {"now": now},
        )
        return [(r[0], r[1], r[2]) for r in rows.all()]
