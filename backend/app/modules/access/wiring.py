"""Composition and public entry points of the access module (23 §1 ``wiring.py``).

Other modules (signup provisioning, seed) import **only** from here — never
from ``access.infrastructure``. Signatures are a cross-module contract.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.session import Database, tenant_transaction
from app.modules.access.application import provisioning
from app.modules.access.application.approval_gate import ApprovalGate, ApprovalOutcome, ApprovalRefIn
from app.modules.access.application.approvals import (
    ApprovalGateService,
    ApprovalRequestService,
    LinkedDocHook,
    PinVerifier,
)
from app.modules.access.application.roles import RolesService
from app.modules.access.domain.approvals import APPROVAL_TTL_MINUTES
from app.modules.access.domain.permissions import SystemRole
from app.modules.access.infrastructure.approvals_sql import SqlApprovalRepository
from app.modules.access.infrastructure.repositories import SqlRoleRepository
from app.modules.notifications.wiring import event_recorder

__all__ = [
    "AccessModule",
    "ApprovalGate",
    "ApprovalOutcome",
    "ApprovalRefIn",
    "ApprovalRequestService",
    "PinVerifier",
    "approval_gate",
    "approval_request_service",
    "build_access_module",
    "expire_approval_requests",
    "permission_grants",
    "provision_system_roles",
]


@dataclass(frozen=True, slots=True)
class AccessModule:
    roles: RolesService


def build_access_module(db: Database) -> AccessModule:
    return AccessModule(roles=RolesService(db.session_factory, SqlRoleRepository()))


async def provision_system_roles(session: AsyncSession, tenant_id: UUID) -> dict[SystemRole, UUID]:
    """Create the 5 system roles and their ``role_permissions`` in the caller's transaction; idempotent."""
    return await provisioning.provision_system_roles(SqlRoleRepository(), session, tenant_id)


# --- Bosqich 3: approvals (18 §2.4, §9) -----------------------------------------------------------
def approval_gate() -> ApprovalGateService:
    """The :class:`~app.modules.access.application.approval_gate.ApprovalGate` used inside postings."""
    return ApprovalGateService(SqlApprovalRepository(), event_recorder())


def permission_grants() -> SqlApprovalRepository:
    """``grant(s, user_id, code) -> UserGrant`` — what any user holds for a code (inside a tenant txn)."""
    return SqlApprovalRepository()


ExpiredHook = Callable[[AsyncSession, str, UUID], Awaitable[None]]


async def expire_approval_requests(
    db: Database, tenant_id: UUID, hooks: Mapping[str, ExpiredHook] | None = None
) -> int:
    """Cron sweep of one tenant: ``pending`` past ``expires_at`` → ``expired`` (18 §9.1); ``hooks`` by
    ``linked_doc_type`` release the linked document in the same transaction (``price_changes`` — 18 §10)."""
    async with db.session_factory() as s, tenant_transaction(s, tenant_id):
        rows = await SqlApprovalRepository().expire_due_linked(s, datetime.now(UTC))
        for _, doc_type, doc_id in rows:
            hook = (hooks or {}).get(doc_type or "")
            if hook is not None and doc_id is not None:
                await hook(s, doc_type or "", doc_id)
        return len(rows)


def approval_request_service(
    db: Database,
    pins: PinVerifier,
    *,
    ttl_minutes: int = APPROVAL_TTL_MINUTES,
    hooks: dict[str, LinkedDocHook] | None = None,
) -> ApprovalRequestService:
    """BO-16 queue (``/approval-requests``); ``pins`` = ``auth.wiring.pin_verifier(...)``."""
    return ApprovalRequestService(
        db.session_factory, SqlApprovalRepository(), pins, event_recorder(), ttl_minutes, dict(hooks or {})
    )
