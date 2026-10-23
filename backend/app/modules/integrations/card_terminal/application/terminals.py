"""Card terminal registry — ``GET/POST /card-terminals``, ``PATCH /card-terminals/{id}``
(18 §16a.5; BO-12, POS-16).

Rules: ``agent_ecr`` → ``agent_id``, ``local_id``, ``host`` (RFC 1918 IPv4) required; ``cloud`` →
``vendor_terminal_ref``; ``fake`` → only where ``ERP_CARD_FAKE_TERMINALS`` is on and never in prod
(``VALIDATION_ERROR``); an active real terminal needs a tenant-unique ``tid``; ``is_default`` needs a cash
register and clears the previous default of that register. ``PATCH`` — optimistic ``version``; an archived
terminal is read-only; a terminal with a ``pending``/``unknown`` attempt cannot be disabled/archived
(``CARD_OUTCOME_UNKNOWN``). Audit ``card_terminal.created|updated|archived``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.audit import record_audit
from app.core.auth.principal import Principal
from app.core.db.base import uuid7
from app.core.db.session import tenant_transaction
from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from app.core.idempotency import stage_response
from app.core.permissions import BranchScope
from app.modules.integrations.card_terminal.application.ports import (
    CardRepository,
    TerminalFilter,
    TerminalRow,
)
from app.modules.integrations.card_terminal.application.transactions import invalid, iso
from app.modules.integrations.card_terminal.domain.model import (
    capability_devices,
    capability_enabled,
    private_ipv4,
)

ENTITY: Final = "card_terminals"
FAKE_CAPABILITIES: Final[Mapping[str, bool]] = {
    "refund": True, "void": True, "status_query": True, "last_transaction": True, "settlement": True,
    "contactless": True, "returns_card_type": False, "returns_bin": True,
}  # fmt: skip
EDITABLE: Final = (
    "name", "model", "cash_register_id", "agent_id", "local_id", "host", "port", "vendor_terminal_ref", "tid",
    "mid", "acquirer_counterparty_id", "status", "is_default",
)  # fmt: skip


def terminal_json(t: TerminalRow) -> dict[str, Any]:
    return {
        "id": str(t.id), "branch_id": str(t.branch_id),
        "cash_register_id": None if t.cash_register_id is None else str(t.cash_register_id),
        "name": t.name, "vendor": t.vendor, "model": t.model, "adapter": t.adapter, "driver": t.driver,
        "agent_id": None if t.agent_id is None else str(t.agent_id), "local_id": t.local_id, "host": t.host,
        "port": t.port, "vendor_terminal_ref": t.vendor_terminal_ref, "tid": t.tid, "mid": t.mid,
        "acquirer_counterparty_id": (
            None if t.acquirer_counterparty_id is None else str(t.acquirer_counterparty_id)
        ),
        "status": t.status, "is_default": t.is_default, "capabilities": dict(t.capabilities),
        "health_status": t.health_status, "health_checked_at": iso(t.health_checked_at), "version": t.version,
    }  # fmt: skip


@dataclass(frozen=True, slots=True)
class TerminalPatch:
    version: int
    fields: Mapping[str, Any]  # only the fields present in the request body


class CardTerminalService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        repo: CardRepository,
        *,
        fake_allowed: bool,
    ) -> None:
        self._sf = session_factory
        self._repo = repo
        self._fake_allowed = fake_allowed

    async def list_page(
        self,
        actor: Principal,
        scope: BranchScope,
        flt: TerminalFilter,
        page: int,
        size: int,
        *,
        can_manage: bool,
    ) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            if not can_manage:  # sales.create — only the terminals of the caller's own register (18 §16a.5)
                register = (
                    None if actor.device_id is None else await self._repo.device_register(s, actor.device_id)
                )
                if register is None:
                    raise AppError(ErrorCode.PERMISSION_DENIED, params={"permission": "cash_register.manage"})
                flt = TerminalFilter(flt.branch_ids, flt.branch_id, register, flt.status)
            rows, total = await self._repo.list_terminals(s, flt, page, size)
        return {"items": [terminal_json(t) for t in rows], "total": total, "page": page, "size": size}

    async def create(
        self, actor: Principal, scope: BranchScope, values: Mapping[str, Any], ip: str | None
    ) -> dict[str, Any]:
        terminal_id = uuid7()
        row = dict(values)
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            branch_id: UUID = row["branch_id"]
            if scope.allowed and branch_id not in scope.allowed:
                raise AppError(ErrorCode.BRANCH_SCOPE_DENIED)
            await self._validate(s, terminal_id, row)
            row.update({
                "id": terminal_id, "tenant_id": actor.tenant_id, "created_by": actor.user_id,
                "capabilities": dict(FAKE_CAPABILITIES) if row["adapter"] == "fake" else {},
            })  # fmt: skip
            if row.get("is_default") and row.get("cash_register_id") is not None:
                await self._repo.clear_default(s, row["cash_register_id"], terminal_id)
            await self._repo.insert_terminal(s, row)
            created = await self._repo.terminal(s, terminal_id)
            assert created is not None
            body = terminal_json(created)
            await record_audit(
                s, tenant_id=actor.tenant_id, user_id=actor.user_id, action="card_terminal.created",
                entity=ENTITY, entity_id=terminal_id, ip=ip, after=body,
            )  # fmt: skip
            stage_response(body, 201)
        return body

    async def update(
        self, actor: Principal, scope: BranchScope, terminal_id: UUID, patch: TerminalPatch, ip: str | None
    ) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            current = await self._repo.terminal(s, terminal_id, lock=True)
            if current is None or (scope.allowed and current.branch_id not in scope.allowed):
                raise AppError(ErrorCode.NOT_FOUND, params={"resource": "card_terminal"})
            if current.version != patch.version:
                raise AppError(ErrorCode.VERSION_CONFLICT, params={"current_version": current.version})
            if current.status == "archived":
                raise invalid("status", "validation.card_terminal_archived")
            changes = {k: v for k, v in patch.fields.items() if k in EDITABLE}
            new_status = changes.get("status", current.status)
            if (
                new_status != "active"
                and current.status == "active"
                and await self._repo.unresolved_on_terminal(s, terminal_id, uuid7())
            ):
                raise AppError(ErrorCode.CARD_OUTCOME_UNKNOWN, params={"card_terminal_id": str(terminal_id)})
            merged = {k: getattr(current, k) for k in EDITABLE} | changes
            merged.update(
                {"branch_id": current.branch_id, "adapter": current.adapter, "driver": current.driver}
            )
            if new_status != "active":
                merged["is_default"] = False
                changes["is_default"] = False
            await self._validate(s, terminal_id, merged)
            if merged.get("is_default") and merged.get("cash_register_id") is not None:
                await self._repo.clear_default(s, merged["cash_register_id"], terminal_id)
            if changes:
                await self._repo.update_terminal(s, terminal_id, changes)
            updated = await self._repo.terminal(s, terminal_id)
            assert updated is not None
            body = terminal_json(updated)
            action = "card_terminal.archived" if new_status == "archived" else "card_terminal.updated"
            await record_audit(
                s, tenant_id=actor.tenant_id, user_id=actor.user_id, action=action, entity=ENTITY,
                entity_id=terminal_id, ip=ip, before=terminal_json(current),
                after={k: body[k] for k in changes if k in body},
            )  # fmt: skip
            stage_response(body)
        return body

    async def _validate(self, s: AsyncSession, terminal_id: UUID, row: Mapping[str, Any]) -> None:
        adapter = row["adapter"]
        if adapter == "fake":
            if not self._fake_allowed:
                raise invalid("adapter", "validation.card_terminal_fake_forbidden")
            if row.get("driver") != "fake":
                raise invalid("driver", "validation.card_terminal_fake_driver")
        elif row.get("driver") == "fake":
            raise invalid("driver", "validation.card_terminal_fake_driver")
        if adapter == "agent_ecr":
            for name in ("agent_id", "local_id", "host"):
                if row.get(name) is None:
                    raise invalid(name, "validation.required")
        elif row.get("agent_id") is not None or row.get("local_id") is not None:
            raise invalid("agent_id", "validation.card_terminal_agent_only")
        if adapter == "cloud" and not row.get("vendor_terminal_ref"):
            raise invalid("vendor_terminal_ref", "validation.required")
        host = row.get("host")
        if host is not None and not private_ipv4(str(host)):
            raise invalid("host", "validation.private_ipv4_required")
        if adapter == "agent_ecr" and row.get("status", "active") == "active":
            await self._validate_agent_binding(s, row)
        status = row.get("status", "active")
        tid = row.get("tid")
        if adapter != "fake" and status == "active" and not tid:
            raise invalid("tid", "validation.required")
        if tid and status != "archived" and await self._repo.tid_taken(s, tid, terminal_id):
            raise invalid("tid", "validation.card_terminal_tid_taken")
        agent_id, local_id = row.get("agent_id"), row.get("local_id")
        if (
            agent_id is not None
            and local_id is not None
            and status != "archived"
            and await self._repo.agent_local_taken(s, agent_id, local_id, terminal_id)
        ):
            raise invalid("local_id", "validation.card_terminal_local_taken")
        register = row.get("cash_register_id")
        if register is not None and await self._repo.register_branch(s, register) != row["branch_id"]:
            raise invalid("cash_register_id", "validation.cash_register_not_in_branch")
        if row.get("is_default") and register is None:
            raise invalid("is_default", "validation.card_terminal_default_needs_register")

    async def _validate_agent_binding(self, s: AsyncSession, row: Mapping[str, Any]) -> None:
        """BO-12 terminal ↔ agent binding (18 §16a.5, 34 §14.2): an active agent of this tenant with
        ``capabilities.card_terminal.enabled``; ``local_id`` among its ``card_terminal.devices[]``; the
        device's reported ``host`` (when given) is the allow-list — the terminal ``host`` must equal it."""
        agent = await self._repo.agent(s, row["agent_id"])
        if agent is None:
            raise invalid("agent_id", "validation.card_terminal_agent_not_found")
        if agent.status != "active":
            raise invalid("agent_id", "validation.card_terminal_agent_revoked")
        if not capability_enabled(agent.capabilities, "card_terminal"):
            raise AppError(
                ErrorCode.AGENT_CAPABILITY_DISABLED,
                params={"agent_id": str(agent.id), "kind": "card", "family": "card_terminal"},
            )
        device = next(
            (
                d
                for d in capability_devices(agent.capabilities, "card_terminal")
                if d.get("local_id") == row["local_id"]
            ),
            None,
        )
        if device is None:
            raise invalid("local_id", "validation.card_terminal_local_unknown")
        reported_host = device.get("host")
        if reported_host and str(reported_host) != str(row.get("host")):
            raise invalid("host", "validation.card_terminal_host_mismatch")
