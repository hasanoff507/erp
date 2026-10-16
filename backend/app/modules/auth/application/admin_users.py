"""Owner blocks / unblocks a staff member (14 §18.2, US-M13-05, QT-OAUTH-07).

Blocking revokes every session and refresh-token family of the user in this
tenant **in the same transaction** as the status change, then updates the
Redis sid-revoke cache — the effect is immediate, not "on the next refresh".
Role/branch assignment and the rest of BO-11 come with Bosqich 1.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass
from typing import Literal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.audit import record_audit
from app.core.auth.principal import Principal
from app.core.db.session import tenant_transaction
from app.core.error_codes import ErrorCode
from app.core.errors import AppError, ErrorDetail
from app.core.idempotency import stage_response
from app.modules.auth.application.revocation import RevocationCache
from app.modules.auth.infrastructure.repositories import MembershipAdminRepository

MembershipStatus = Literal["active", "blocked"]


@dataclass(frozen=True, slots=True)
class MembershipStatusResult:
    user_id: UUID
    status: MembershipStatus
    sessions_revoked: int


class AdminUsersService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        revocation: RevocationCache,
        drop_bff_session: Callable[[UUID], Awaitable[None]],
        forget_profile: Callable[[UUID, UUID], Awaitable[None]],
    ) -> None:
        self._sf = session_factory
        self._repo = MembershipAdminRepository()
        self._revocation = revocation
        self._drop = drop_bff_session
        self._forget_profile = forget_profile

    async def set_status(
        self, actor: Principal, user_id: UUID, status: MembershipStatus, ip: str | None
    ) -> MembershipStatusResult:
        if user_id == actor.user_id and status == "blocked":
            raise AppError(
                ErrorCode.VALIDATION_ERROR,
                details=[ErrorDetail(field="status", message_key="validation.cannot_block_self")],
            )
        sids: list[UUID] = []
        revoked = 0
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            row = await self._repo.lock(s, actor.tenant_id, user_id)
            if row is None:
                raise AppError(ErrorCode.NOT_FOUND, params={"resource": "users"})
            if row.status != status:
                await self._repo.set_status(s, row.id, status)
                await record_audit(
                    s, tenant_id=actor.tenant_id, user_id=actor.user_id, action="membership_status_changed",
                    entity="memberships", entity_id=row.id, before={"status": row.status},
                    after={"status": status, "user_id": str(user_id)}, ip=ip,
                )  # fmt: skip
            if status == "blocked":
                sids = await self._repo.session_ids(s, user_id, actor.tenant_id)
                revoked = await self._repo.revoke_user(s, user_id, actor.tenant_id, "membership_blocked")
                await record_audit(
                    s, tenant_id=actor.tenant_id, user_id=actor.user_id, action="all_sessions_revoked",
                    entity="users", entity_id=user_id, ip=ip,
                    after={"sessions": revoked, "reason": "membership_blocked"},
                )  # fmt: skip
            result = MembershipStatusResult(user_id, status, revoked)
            # Idempotency-Key journal row commits with the membership change (23 §3)
            stage_response(asdict(result))
        await self._forget_profile(actor.tenant_id, user_id)  # /auth/session cache (14 §20)
        if status == "blocked":
            # after commit: the RS sees the revocation on the very next request
            await self._revocation.mark_sessions_revoked(sids)
            await self._revocation.mark_user_revoked(user_id, actor.tenant_id)
            for sid in sids:
                await self._drop(sid)
        return result
