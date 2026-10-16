"""Cash registers (20 #38–#40, #40i; US-M14-03, US-M17-02 edge case; BO-12)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.audit import record_audit
from app.core.auth.principal import Principal
from app.core.db.base import uuid7
from app.core.db.session import tenant_transaction
from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from app.core.idempotency import stage_response
from app.modules.branches.application.common import (
    archived,
    check_branch_scope,
    check_version,
    invalid,
    iso,
    not_found,
    scoped_branch_ids,
)
from app.modules.branches.application.ports import BranchRepository, CashRegisterRepository, CashRegisterRow
from app.modules.branches.domain.model import (
    EXTRA_REGISTER_ADDON,
    fiscal_pair_ok,
    register_allowance,
    tashkent_today,
)


@dataclass(frozen=True, slots=True)
class CashRegisterView:
    id: UUID
    branch_id: UUID
    name: str
    kind: str
    fiscal_module_id: str | None
    txkm_contract_ref: str | None
    fiscal_agent_id: UUID | None
    fiscal_local_device_id: str | None
    ofd_status: str
    fm_state: str
    last_unacked_receipt_at: str | None
    fm_receipts_pending: int | None
    tax_registered_at: str | None
    archived_at: str | None
    version: int


@dataclass(frozen=True, slots=True)
class CashRegisterCreated:
    id: UUID
    branch_id: UUID
    name: str
    kind: str
    ofd_status: str
    version: int


@dataclass(frozen=True, slots=True)
class CashRegisterUpdated:
    id: UUID
    name: str
    fiscal_agent_id: UUID | None
    fiscal_local_device_id: str | None
    version: int


@dataclass(frozen=True, slots=True)
class CashRegisterArchived:
    id: UUID
    archived_at: str | None


@dataclass(frozen=True, slots=True)
class CashRegisterPatch:
    version: int
    name: str | None = None
    fiscal_fields_set: bool = False  # fiscal_agent_id / fiscal_local_device_id present in the body
    fiscal_agent_id: UUID | None = None
    fiscal_local_device_id: str | None = None


def _view(row: CashRegisterRow) -> CashRegisterView:
    return CashRegisterView(
        id=row.id,
        branch_id=row.branch_id,
        name=row.name,
        kind=row.kind,
        fiscal_module_id=row.fiscal_module_id,
        txkm_contract_ref=row.txkm_contract_ref,
        fiscal_agent_id=row.fiscal_agent_id,
        fiscal_local_device_id=row.fiscal_local_device_id,
        ofd_status=row.ofd_status,
        fm_state=row.fm_state,
        last_unacked_receipt_at=iso(row.last_unacked_receipt_at),
        fm_receipts_pending=row.fm_receipts_pending,
        tax_registered_at=iso(row.tax_registered_at),
        archived_at=iso(row.archived_at),
        version=row.version,
    )


class CashRegistersService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        registers: CashRegisterRepository,
        branches: BranchRepository,
    ) -> None:
        self._sf = session_factory
        self._registers = registers
        self._branches = branches

    async def list_registers(
        self, actor: Principal, allowed: tuple[UUID, ...], branch_id: UUID | None, include_archived: bool
    ) -> list[CashRegisterView]:
        branch_ids = scoped_branch_ids(allowed, branch_id)
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            rows = await self._registers.list_cash_registers(
                s, actor.tenant_id, branch_ids, include_archived=include_archived
            )
        return [_view(r) for r in rows]

    async def create(
        self,
        actor: Principal,
        allowed: tuple[UUID, ...],
        branch_id: UUID,
        name: str,
        kind: str,
        ip: str | None,
    ) -> CashRegisterCreated:
        check_branch_scope(allowed, branch_id)
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            branch = await self._branches.get_branch(s, actor.tenant_id, branch_id, tashkent_today())
            if branch is None or branch.archived_at is not None:
                raise invalid("branch_id", "validation.not_found")
            # serialize concurrent creations: the active count must not overshoot the allowance
            await self._branches.lock_tenant(s, actor.tenant_id)
            active = await self._registers.active_count(s, actor.tenant_id)
            included, extra = await self._registers.allowance(s, actor.tenant_id)
            limit = register_allowance(included, extra)
            if active + 1 > limit:
                raise AppError(
                    ErrorCode.ADDON_REQUIRED,
                    params={"addon_code": EXTRA_REGISTER_ADDON, "limit": limit, "active": active},
                )
            register_id = uuid7()
            await self._registers.insert_cash_register(s, actor.tenant_id, register_id, branch_id, name, kind)
            result = CashRegisterCreated(register_id, branch_id, name, kind, "pending", 1)
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="cash_register.created",
                entity="cash_registers",
                entity_id=register_id,
                after=asdict(result),
                ip=ip,
            )
            stage_response(asdict(result), 201)
        return result

    async def update(
        self,
        actor: Principal,
        allowed: tuple[UUID, ...],
        register_id: UUID,
        patch: CashRegisterPatch,
        *,
        may_bind_fiscal_agent: bool,
        ip: str | None,
    ) -> CashRegisterUpdated:
        if patch.fiscal_fields_set:
            if not may_bind_fiscal_agent:
                # 20 #40: fiscal_agent_id / fiscal_local_device_id need settings.branches as well
                raise AppError(ErrorCode.PERMISSION_DENIED, params={"permission": "settings.branches"})
            if not fiscal_pair_ok(patch.fiscal_agent_id, patch.fiscal_local_device_id):
                raise invalid("fiscal_local_device_id", "validation.fiscal_agent_pair")
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            row = await self._live_register(s, actor.tenant_id, allowed, register_id)
            check_version(row.version, patch.version)
            fields: dict[str, Any] = {}
            if patch.name is not None and patch.name != row.name:
                fields["name"] = patch.name
            if patch.fiscal_fields_set and (patch.fiscal_agent_id, patch.fiscal_local_device_id) != (
                row.fiscal_agent_id,
                row.fiscal_local_device_id,
            ):
                if patch.fiscal_agent_id is not None and not await self._registers.fiscal_agent_exists(
                    s, patch.fiscal_agent_id
                ):
                    raise invalid("fiscal_agent_id", "validation.not_found")
                fields["fiscal_agent_id"] = patch.fiscal_agent_id
                fields["fiscal_local_device_id"] = patch.fiscal_local_device_id
            version = row.version
            if fields:
                version = await self._registers.update_cash_register(s, register_id, fields)
                await record_audit(
                    s,
                    tenant_id=actor.tenant_id,
                    user_id=actor.user_id,
                    action="cash_register.updated",
                    entity="cash_registers",
                    entity_id=register_id,
                    before={k: getattr(row, k) for k in fields},
                    after=fields,
                    ip=ip,
                )
            result = CashRegisterUpdated(
                id=register_id,
                name=fields.get("name", row.name),
                fiscal_agent_id=fields.get("fiscal_agent_id", row.fiscal_agent_id),
                fiscal_local_device_id=fields.get("fiscal_local_device_id", row.fiscal_local_device_id),
                version=version,
            )
            stage_response(asdict(result))
        return result

    async def archive(
        self, actor: Principal, allowed: tuple[UUID, ...], register_id: UUID, ip: str | None
    ) -> CashRegisterArchived:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            await self._live_register(s, actor.tenant_id, allowed, register_id)
            archived_at = await self._registers.archive_cash_register(s, register_id)
            result = CashRegisterArchived(register_id, iso(archived_at))
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="cash_register.archived",
                entity="cash_registers",
                entity_id=register_id,
                after={"archived_at": result.archived_at},
                ip=ip,
            )
            stage_response(asdict(result))
        return result

    async def _live_register(
        self, s: AsyncSession, tenant_id: UUID, allowed: tuple[UUID, ...], register_id: UUID
    ) -> CashRegisterRow:
        row = await self._registers.get_cash_register(s, tenant_id, register_id, for_update=True)
        if row is None:
            raise not_found("cash_registers")
        check_branch_scope(allowed, row.branch_id)
        if row.archived_at is not None:
            raise archived("cash_registers")
        return row
