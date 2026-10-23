"""BO-14 «Fiskal» tab: per-register fiscal state and the manual «Qayta yuborish» (21 §0 BO-14, §1 Monitoring,
§16 ``fiscal.resend_unsent``; 18 §14.3–§14.4)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.audit import record_audit
from app.core.db.session import tenant_transaction
from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from app.core.idempotency import stage_response
from app.core.permissions import BranchScope
from app.modules.integrations.fiscal.application.agent_tasks import FiscalAgentDispatcher
from app.modules.integrations.fiscal.application.ports import FiscalRepository


def _ts(value: datetime | None) -> str | None:
    return None if value is None else value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _s(value: UUID | None) -> str | None:
    return None if value is None else str(value)


def _branches(scope: BranchScope) -> tuple[UUID, ...] | None:
    if scope.current is not None:
        return (scope.current,)
    return None if scope.unrestricted else scope.allowed


def _in_scope(scope: BranchScope, branch_id: UUID) -> bool:
    allowed = _branches(scope)
    return allowed is None or branch_id in allowed


class FiscalRegisterQueries:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        repo: FiscalRepository,
        dispatcher: FiscalAgentDispatcher,
    ) -> None:
        self._sf = session_factory
        self._repo = repo
        self._dispatch = dispatcher

    async def list_registers(self, tenant_id: UUID, user_id: UUID, scope: BranchScope) -> dict[str, Any]:
        now = datetime.now(UTC)
        async with self._sf() as s, tenant_transaction(s, tenant_id, user_id=user_id):
            rows = await self._repo.registers_overview(s, _branches(scope))
        items = []
        for r in rows:
            oldest = r["oldest_unacked_at"]
            items.append(
                {
                    "cash_register_id": str(r["id"]),
                    "name": r["name"],
                    "branch_id": str(r["branch_id"]),
                    "fiscal_agent_id": _s(r["fiscal_agent_id"]),
                    "fiscal_local_device_id": r["fiscal_local_device_id"],
                    "fm_state": r["fm_state"],
                    "fm_receipts_pending": r["fm_receipts_pending"],
                    "last_unacked_receipt_at": _ts(r["last_unacked_receipt_at"]),
                    "unacked_count": int(r["unacked_count"]),
                    "failed_count": int(r["failed_count"]),
                    "oldest_unacked_at": _ts(oldest),
                    "oldest_unacked_age_s": None
                    if oldest is None
                    else max(int((now - oldest).total_seconds()), 0),
                }
            )
        return {"items": items}

    async def resend(
        self, tenant_id: UUID, user_id: UUID, scope: BranchScope, register_id: UUID, ip: str | None
    ) -> dict[str, Any]:
        """BO-14 «Qayta yuborish»: ``fiscal.resend_unsent`` for the register's store agent (21 §16)."""
        async with self._sf() as s, tenant_transaction(s, tenant_id, user_id=user_id):
            reg = await self._repo.binding(s, register_id)
            if reg is None or reg.archived or not _in_scope(scope, reg.branch_id):
                raise AppError(ErrorCode.NOT_FOUND, params={"resource": "cash_register"})
            key = f"manual:{datetime.now(UTC):%Y%m%dT%H%M%S}"
            task_id = await self._dispatch.resend(s, tenant_id, reg, key, strict=True, created_by=user_id)
            body = {"task_id": str(task_id), "status": "queued"}
            await record_audit(
                s,
                tenant_id=tenant_id,
                user_id=user_id,
                action="fiscal.resend_requested",
                entity="cash_registers",
                entity_id=register_id,
                after={"task_id": str(task_id)},
                ip=ip,
            )
            stage_response(body, 202)
        return body
