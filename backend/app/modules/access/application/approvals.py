"""Approvals: the :class:`ApprovalGate` used by postings and the BO-16 queue (18 §2.4, §9; 15 §2.3, §6.1).

**Gate** (:class:`ApprovalGateService`, inside the caller's posting transaction):

1. the requester is an owner (QT-PERM-01) or ``not always_required`` and their own ``limit_value`` for
   ``permission`` (the requester's code, e.g. ``discount.give``) covers ``value`` → no approval;
2. otherwise an ``ApprovalRef`` is required (missing → the kind's ``*_LIMIT_EXCEEDED`` code, 18 §18):

   * ``local_pin`` — ``approved_by`` ≠ requester, active member of the tenant with access to the branch,
     holding the kind's approver code (``PERMISSION_BY_KIND``, e.g. ``discount.approve``); its limit
     must cover ``value`` — **offline** a too-small limit is accepted
     with ``offline_limit_exceeded`` (16 §5, the caller adds the ``sync_exceptions`` row), online it is
     ``APPROVAL_INVALID``;
   * ``remote_request`` — the row is locked; ``consumed``/``rejected``/``expired`` (or a ``pending`` one
     past ``expires_at``) → ``409 APPROVAL_REQUEST_ALREADY_RESOLVED`` (QT-PERM-07); ``pending`` (not
     approved yet), another kind/branch/requester, ``requested_value < value`` or a resolver who no
     longer covers ``value`` → ``APPROVAL_INVALID``; else ``status='consumed'``;

   then one ``doc_approvals`` row (``uq_doc_approvals_request`` — single use) and an ``audit_log``
   ``approval_applied`` row.

**Queue** (:class:`ApprovalRequestService`, REST 18 §9): create (online only, notification event
``over_limit_action``), list/get (kinds whose ``permission_code`` the caller holds with a limit covering
``requested_value``; the requester may always read their own request — POS polling), approve (PIN step-up
→ ``PIN_INVALID``; the requester never approves/rejects their own request — QT-PERM-06), reject (reason),
and the expiry sweep (``pending`` past ``expires_at`` → ``expired``).
"""

from __future__ import annotations

import base64
import json
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.audit import record_audit
from app.core.auth.principal import Principal
from app.core.db.base import uuid7
from app.core.db.session import tenant_transaction
from app.core.error_codes import ErrorCode
from app.core.errors import AppError, ErrorDetail
from app.core.idempotency import stage_response
from app.core.permissions import BranchScope
from app.modules.access.application.approval_gate import ApprovalKind, ApprovalOutcome, ApprovalRefIn
from app.modules.access.domain.approvals import (
    APPROVAL_TTL_MINUTES,
    KIND_MISSING_CODE,
    PERMISSION_BY_KIND,
    REQUESTER_PERMISSION,
    UNLIMITED_KINDS,
    UserGrant,
    value_key,
)

VALUE_EXP = Decimal("0.0001")  # approval_requests.requested_value NUMERIC(18,4)


# --- ports ----------------------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class ApprovalRequestRow:
    id: UUID
    branch_id: UUID
    kind: str
    permission_code: str
    requested_value: Decimal | None
    context: Mapping[str, Any]
    linked_doc_type: str | None
    linked_doc_id: UUID | None
    device_id: UUID | None
    status: str  # pending → 'expired' already applied when past expires_at
    requested_by: UUID
    requested_by_name: str | None
    requested_at: datetime
    expires_at: datetime
    resolved_by: UUID | None
    resolved_at: datetime | None
    reject_reason: str | None
    consumed_at: datetime | None


@dataclass(frozen=True, slots=True)
class QueueFilter:
    status: str | None
    branch_ids: tuple[UUID, ...] | None  # None = every branch
    permissions: Mapping[str, Decimal | None]  # code → most generous limit the caller holds
    viewer_id: UUID
    cursor: tuple[datetime, UUID] | None
    limit: int


class ApprovalRepository(Protocol):
    async def grant(self, s: AsyncSession, user_id: UUID, code: str) -> UserGrant: ...

    async def held_permissions(
        self, s: AsyncSession, user_id: UUID, codes: Sequence[str]
    ) -> dict[str, UserGrant]: ...

    async def get_request(
        self, s: AsyncSession, request_id: UUID, *, lock: bool = False
    ) -> ApprovalRequestRow | None: ...

    async def insert_request(self, s: AsyncSession, row: Mapping[str, Any]) -> None: ...

    async def resolve(
        self, s: AsyncSession, request_id: UUID, *, status: str, user_id: UUID, reason: str | None
    ) -> None: ...

    async def consume(self, s: AsyncSession, request_id: UUID) -> None: ...

    async def insert_doc_approval(self, s: AsyncSession, row: Mapping[str, Any]) -> None: ...

    async def list_requests(self, s: AsyncSession, flt: QueueFilter) -> list[ApprovalRequestRow]: ...

    async def expire_due(self, s: AsyncSession, now: datetime) -> list[UUID]: ...


class PinVerifier(Protocol):
    """``auth.wiring.pin_verifier`` (own transactions; ``False`` = wrong PIN; lockout raises)."""

    async def verify(
        self, *, tenant_id: UUID, user_id: UUID, pin: str, device_id: UUID | None, ip: str | None
    ) -> bool: ...


class NotificationRecorder(Protocol):
    async def record_event(
        self, s: AsyncSession, tenant_id: UUID, kind: str, payload: Mapping[str, Any], dedupe_key: str
    ) -> bool: ...


# a linked document reacting to a decision (e.g. price_changes → posted/rejected), inside the txn
LinkedDocHook = Callable[[AsyncSession, ApprovalRequestRow, str, UUID], Awaitable[None]]


# --- helpers --------------------------------------------------------------------------------------
def _ts(value: datetime | None) -> str | None:
    return None if value is None else value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _value_str(value: Decimal | None) -> str | None:
    return None if value is None else format(value.quantize(VALUE_EXP), "f")


def request_json(row: ApprovalRequestRow) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "branch_id": str(row.branch_id),
        "kind": row.kind,
        "permission_code": row.permission_code,
        "requested_value": _value_str(row.requested_value),
        "context": dict(row.context),
        "linked_doc_type": row.linked_doc_type,
        "linked_doc_id": None if row.linked_doc_id is None else str(row.linked_doc_id),
        "device_id": None if row.device_id is None else str(row.device_id),
        "status": row.status,
        "requested_by": str(row.requested_by),
        "requested_by_name": row.requested_by_name,
        "requested_at": _ts(row.requested_at),
        "expires_at": _ts(row.expires_at),
        "resolved_by": None if row.resolved_by is None else str(row.resolved_by),
        "resolved_at": _ts(row.resolved_at),
        "reject_reason": row.reject_reason,
        "consumed_at": _ts(row.consumed_at),
    }


def _missing_error(kind: str, override: str | None) -> AppError:
    code = ErrorCode(override or KIND_MISSING_CODE[kind])
    # APPROVAL_REQUIRED is a 202 "state" in REST; as a posting refusal it is a 403
    status = 403 if code is ErrorCode.APPROVAL_REQUIRED else None
    return AppError(code, params={"kind": kind}, status_code=status)


def _invalid(reason: str, **params: Any) -> AppError:
    return AppError(ErrorCode.APPROVAL_INVALID, params={"reason": reason, **params})


def encode_cursor(at: datetime, row_id: UUID) -> str:
    raw = json.dumps([at.isoformat(), str(row_id)]).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))
        at, row_id = json.loads(raw)
        return datetime.fromisoformat(at), UUID(row_id)
    except (ValueError, TypeError) as exc:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            details=[ErrorDetail(field="cursor", message_key="validation.cursor_invalid")],
        ) from exc


# --- the gate -------------------------------------------------------------------------------------
class ApprovalGateService:
    """Implementation of :class:`app.modules.access.application.approval_gate.ApprovalGate`."""

    def __init__(self, repo: ApprovalRepository, notifications: NotificationRecorder | None = None) -> None:
        self._repo = repo
        self._notify = notifications

    async def require(
        self,
        s: AsyncSession,
        *,
        tenant_id: UUID,
        branch_id: UUID,
        kind: ApprovalKind,
        permission: str,
        requested_by: UUID,
        value: Decimal | None,
        approval: ApprovalRefIn | None,
        doc_type: str,
        doc_id: UUID,
        offline: bool,
        always_required: bool = False,
        line_id: UUID | None = None,
        missing_code: str | None = None,
        approver_bound: Callable[[UUID], Awaitable[bool]] | None = None,
    ) -> ApprovalOutcome:
        if kind not in PERMISSION_BY_KIND:
            raise ValueError(f"unknown approval kind {kind!r}")
        if kind in UNLIMITED_KINDS:
            value_for_limit: Decimal | None = None
        else:
            value_for_limit = value
        own = await self._repo.grant(s, requested_by, permission)
        if own.active and own.owner:
            return ApprovalOutcome(required=False)  # QT-PERM-01
        if not always_required and own.holds and own.covers(value_for_limit):
            return ApprovalOutcome(required=False)
        if approval is None:
            raise _missing_error(kind, missing_code)
        permission = PERMISSION_BY_KIND[kind]  # the approver's code (15 §2.3), e.g. discount.approve
        if approval.mode == "local_pin":
            outcome = await self._local_pin(
                s,
                tenant_id,
                branch_id,
                kind,
                permission,
                requested_by,
                value,
                value_for_limit,
                approval,
                doc_type,
                doc_id,
                offline,
                line_id,
            )
            approver = approval.approved_by
            # SEC-02: an online PIN approver must be bound to the session — detect, never reject (F-6)
            if (
                not offline
                and approver_bound is not None
                and approver is not None
                and not await approver_bound(approver)
            ):
                outcome = replace(
                    outcome,
                    approver_unverified=True,
                    unverified_details={
                        "role": "approver",
                        "approved_by": str(approver),
                        "requested_by": str(requested_by),
                        "kind": kind,
                    },
                )
            return outcome
        if approval.mode == "remote_request":
            return await self._remote(
                s,
                tenant_id,
                branch_id,
                kind,
                permission,
                requested_by,
                value,
                value_for_limit,
                approval,
                doc_type,
                doc_id,
                line_id,
            )
        raise _invalid("mode")

    async def _local_pin(
        self,
        s: AsyncSession,
        tenant_id: UUID,
        branch_id: UUID,
        kind: str,
        permission: str,
        requested_by: UUID,
        value: Decimal | None,
        value_for_limit: Decimal | None,
        approval: ApprovalRefIn,
        doc_type: str,
        doc_id: UUID,
        offline: bool,
        line_id: UUID | None,
    ) -> ApprovalOutcome:
        approver = approval.approved_by
        if approver is None or approval.pin_verified_locally is not True:
            raise _invalid("approved_by_required")
        if approver == requested_by:
            raise _invalid("self_approval")
        grant = await self._repo.grant(s, approver, permission)
        if not grant.holds or not grant.in_branch(str(branch_id)):
            raise _invalid("approver_lacks_permission", permission=permission)
        exceeded = not grant.covers(value_for_limit)
        if exceeded and not offline:
            raise _invalid("approver_limit", permission=permission, limit=_value_str(grant.limit))
        row_id = await self._write(
            s,
            tenant_id,
            kind,
            "local_pin",
            approver,
            None,
            True,
            value,
            doc_type,
            doc_id,
            line_id,
            requested_by,
        )
        details: dict[str, Any] = {}
        if exceeded:
            details = {
                "kind": kind,
                "permission": permission,
                "approved_by": str(approver),
                "limit": _value_str(grant.limit),
                "requested": _value_str(value),
            }
            if self._notify is not None:  # M18 to the owner/manager (15 §2.3 step 4; sending — Bosqich 4)
                await self._notify.record_event(
                    s,
                    tenant_id,
                    "over_limit_action",
                    {**details, "offline": True, "doc_type": doc_type, "doc_id": str(doc_id)},
                    f"approval_limit_exceeded_offline:{row_id}",
                )
        return ApprovalOutcome(
            required=True, doc_approval_id=row_id, offline_limit_exceeded=exceeded, details=details
        )

    async def _remote(
        self,
        s: AsyncSession,
        tenant_id: UUID,
        branch_id: UUID,
        kind: str,
        permission: str,
        requested_by: UUID,
        value: Decimal | None,
        value_for_limit: Decimal | None,
        approval: ApprovalRefIn,
        doc_type: str,
        doc_id: UUID,
        line_id: UUID | None,
    ) -> ApprovalOutcome:
        if approval.approval_request_id is None:
            raise _invalid("approval_request_id_required")
        req = await self._repo.get_request(s, approval.approval_request_id, lock=True)
        if req is None:
            raise _invalid("approval_request_not_found")
        if req.status in ("consumed", "rejected", "expired"):
            raise AppError(
                ErrorCode.APPROVAL_REQUEST_ALREADY_RESOLVED, params={"id": str(req.id), "status": req.status}
            )
        if req.status != "approved":
            raise _invalid("approval_request_not_approved", status=req.status)
        if req.kind != kind or req.branch_id != branch_id or req.requested_by != requested_by:
            raise _invalid("approval_request_mismatch")
        if value is not None and (req.requested_value is None or req.requested_value < value):
            raise _invalid("approval_request_value", requested=_value_str(req.requested_value))
        if req.resolved_by is None:
            raise _invalid("approval_request_not_approved")
        resolver = await self._repo.grant(s, req.resolved_by, permission)
        if not resolver.covers(value_for_limit):
            raise _invalid("approver_limit", permission=permission, limit=_value_str(resolver.limit))
        await self._repo.consume(s, req.id)
        row_id = await self._write(
            s,
            tenant_id,
            kind,
            "remote_request",
            req.resolved_by,
            req.id,
            False,
            value,
            doc_type,
            doc_id,
            line_id,
            requested_by,
        )
        return ApprovalOutcome(required=True, doc_approval_id=row_id)

    async def _write(
        self,
        s: AsyncSession,
        tenant_id: UUID,
        kind: str,
        mode: str,
        approved_by: UUID,
        request_id: UUID | None,
        pin_local: bool,
        value: Decimal | None,
        doc_type: str,
        doc_id: UUID,
        line_id: UUID | None,
        requested_by: UUID,
    ) -> UUID:
        row_id = uuid7()
        await self._repo.insert_doc_approval(
            s,
            {
                "id": row_id,
                "tenant_id": tenant_id,
                "doc_type": doc_type,
                "doc_id": doc_id,
                "line_id": line_id,
                "kind": kind,
                "mode": mode,
                "approved_by": approved_by,
                "approval_request_id": request_id,
                "pin_verified_locally": pin_local,
                "requested_value": None if value is None else value.quantize(VALUE_EXP),
                "approved_at": datetime.now(UTC),
            },
        )
        await record_audit(
            s,
            tenant_id=tenant_id,
            user_id=requested_by,
            action="approval_applied",
            entity=doc_type,
            entity_id=doc_id,
            after={
                "kind": kind,
                "mode": mode,
                "approved_by": str(approved_by),
                "approval_request_id": None if request_id is None else str(request_id),
                "requested_value": _value_str(value),
            },
        )
        return row_id


# --- the queue (REST) -----------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class NewRequest:
    kind: str
    context: Mapping[str, Any]
    linked_doc_type: str | None
    linked_doc_id: UUID | None


@dataclass(slots=True)
class ApprovalRequestService:
    session_factory: async_sessionmaker[AsyncSession]
    repo: ApprovalRepository
    pins: PinVerifier
    notifications: NotificationRecorder
    ttl_minutes: int = APPROVAL_TTL_MINUTES
    hooks: dict[str, LinkedDocHook] = field(default_factory=dict)  # linked_doc_type → hook

    async def create(
        self, actor: Principal, scope: BranchScope, body: NewRequest, ip: str | None
    ) -> dict[str, Any]:
        requester_code = REQUESTER_PERMISSION.get(body.kind)
        if requester_code is None:
            raise AppError(
                ErrorCode.VALIDATION_ERROR,
                details=[ErrorDetail(field="kind", message_key="validation.approval_kind_not_requestable")],
            )
        branch_id = _request_branch(scope)
        value = _requested_value(body.kind, body.context)
        if (body.linked_doc_type is None) != (body.linked_doc_id is None):
            raise AppError(
                ErrorCode.VALIDATION_ERROR,
                details=[ErrorDetail(field="linked_doc_id", message_key="validation.required")],
            )
        async with self.session_factory() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            own = await self.repo.grant(s, actor.user_id, requester_code)
            if not own.holds:
                raise AppError(ErrorCode.PERMISSION_DENIED, params={"permission": requester_code})
            now = datetime.now(UTC)
            row_id = uuid7()
            permission = PERMISSION_BY_KIND[body.kind]
            await self.repo.insert_request(
                s,
                {
                    "id": row_id,
                    "tenant_id": actor.tenant_id,
                    "branch_id": branch_id,
                    "kind": body.kind,
                    "permission_code": permission,
                    "requested_value": value,
                    "context": json.dumps(dict(body.context), default=str, ensure_ascii=False),
                    "linked_doc_type": body.linked_doc_type,
                    "linked_doc_id": body.linked_doc_id,
                    "device_id": actor.device_id,
                    "requested_by": actor.user_id,
                    "requested_at": now,
                    "expires_at": now + timedelta(minutes=self.ttl_minutes),
                },
            )
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="approval_requested",
                entity="approval_requests",
                entity_id=row_id,
                ip=ip,
                device_id=actor.device_id,
                after={"kind": body.kind, "requested_value": _value_str(value), "branch_id": str(branch_id)},
            )
            # M18: the manager/owner is notified (sending — Bosqich 4; B3 records the event)
            await self.notifications.record_event(
                s,
                actor.tenant_id,
                "over_limit_action",
                {
                    "approval_request_id": str(row_id),
                    "kind": body.kind,
                    "branch_id": str(branch_id),
                    "requested_value": _value_str(value),
                    "requested_by": str(actor.user_id),
                },
                f"approval_requested:{row_id}",
            )
            row = await self.repo.get_request(s, row_id)
            assert row is not None
            body_out = {
                "id": str(row.id),
                "kind": row.kind,
                "status": row.status,
                "expires_at": _ts(row.expires_at),
            }
            stage_response(body_out, 201)
        return body_out

    async def list_page(
        self, actor: Principal, scope: BranchScope, status: str | None, cursor: str | None, limit: int
    ) -> dict[str, Any]:
        async with self.session_factory() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            held = await self.repo.held_permissions(
                s, actor.user_id, sorted(set(PERMISSION_BY_KIND.values()))
            )
            permissions = {code: g.limit for code, g in held.items() if g.holds}
            if scope.current is not None:
                branches: tuple[UUID, ...] | None = (scope.current,)
            else:
                branches = None if scope.unrestricted else scope.allowed
            rows = await self.repo.list_requests(
                s,
                QueueFilter(
                    status=status,
                    branch_ids=branches,
                    permissions=permissions,
                    viewer_id=actor.user_id,
                    cursor=decode_cursor(cursor) if cursor else None,
                    limit=limit + 1,
                ),
            )
        more = len(rows) > limit
        rows = rows[:limit]
        return {
            "items": [request_json(r) for r in rows],
            "next_cursor": encode_cursor(rows[-1].requested_at, rows[-1].id) if more and rows else None,
        }

    async def get(self, actor: Principal, scope: BranchScope, request_id: UUID) -> dict[str, Any]:
        async with self.session_factory() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            row = await self._visible(s, actor, scope, request_id)
        return request_json(row)

    async def approve(
        self, actor: Principal, scope: BranchScope, request_id: UUID, pin: str, ip: str | None
    ) -> dict[str, Any]:
        ok = await self.pins.verify(
            tenant_id=actor.tenant_id, user_id=actor.user_id, pin=pin, device_id=actor.device_id, ip=ip
        )
        if not ok:
            raise AppError(ErrorCode.PIN_INVALID)
        async with self.session_factory() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            row = await self._for_decision(s, actor, scope, request_id)
            grant = await self.repo.grant(s, actor.user_id, row.permission_code)
            limited = None if row.kind in UNLIMITED_KINDS else row.requested_value
            if not grant.covers(limited) or not grant.in_branch(str(row.branch_id)):
                raise _invalid("approver_lacks_permission", permission=row.permission_code)
            await self.repo.resolve(s, row.id, status="approved", user_id=actor.user_id, reason=None)
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="approval_request_approved",
                entity="approval_requests",
                entity_id=row.id,
                ip=ip,
                device_id=actor.device_id,
                before={"status": "pending"},
                after={
                    "status": "approved",
                    "kind": row.kind,
                    "requested_value": _value_str(row.requested_value),
                    "limit": _value_str(grant.limit),
                    "requested_by": str(row.requested_by),
                },
            )
            hook = self.hooks.get(row.linked_doc_type or "")
            if hook is not None:
                await hook(s, row, "approved", actor.user_id)
            done = await self.repo.get_request(s, row.id)
            assert done is not None
            body = {
                "id": str(done.id),
                "status": "approved",
                "resolved_by": str(done.resolved_by),
                "resolved_at": _ts(done.resolved_at),
            }
            stage_response(body, 200)
        return body

    async def reject(
        self, actor: Principal, scope: BranchScope, request_id: UUID, reason: str, ip: str | None
    ) -> dict[str, Any]:
        async with self.session_factory() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            row = await self._for_decision(s, actor, scope, request_id)
            grant = await self.repo.grant(s, actor.user_id, row.permission_code)
            if not grant.holds or not grant.in_branch(str(row.branch_id)):
                raise _invalid("approver_lacks_permission", permission=row.permission_code)
            await self.repo.resolve(s, row.id, status="rejected", user_id=actor.user_id, reason=reason)
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="approval_request_rejected",
                entity="approval_requests",
                entity_id=row.id,
                ip=ip,
                device_id=actor.device_id,
                before={"status": "pending"},
                after={
                    "status": "rejected",
                    "kind": row.kind,
                    "reason": reason,
                    "requested_value": _value_str(row.requested_value),
                },
            )
            hook = self.hooks.get(row.linked_doc_type or "")
            if hook is not None:
                await hook(s, row, "rejected", actor.user_id)
            body = {"id": str(row.id), "status": "rejected"}
            stage_response(body, 200)
        return body

    async def expire_due(self, tenant_id: UUID, now: datetime | None = None) -> int:
        """Cron sweep: ``pending`` past ``expires_at`` → ``expired`` (one tenant transaction)."""
        async with self.session_factory() as s, tenant_transaction(s, tenant_id):
            expired = await self.repo.expire_due(s, now or datetime.now(UTC))
        return len(expired)

    # --- helpers ----------------------------------------------------------------------------------
    async def _visible(
        self, s: AsyncSession, actor: Principal, scope: BranchScope, request_id: UUID, *, lock: bool = False
    ) -> ApprovalRequestRow:
        row = await self.repo.get_request(s, request_id, lock=lock)
        if row is None or (not scope.unrestricted and row.branch_id not in scope.allowed):
            raise AppError(ErrorCode.NOT_FOUND, params={"resource": "approval_request"})
        if row.requested_by == actor.user_id:
            return row
        grant = await self.repo.grant(s, actor.user_id, row.permission_code)
        limited = None if row.kind in UNLIMITED_KINDS else row.requested_value
        if not grant.covers(limited):
            raise AppError(ErrorCode.NOT_FOUND, params={"resource": "approval_request"})
        return row

    async def _for_decision(
        self, s: AsyncSession, actor: Principal, scope: BranchScope, request_id: UUID
    ) -> ApprovalRequestRow:
        row = await self._visible(s, actor, scope, request_id, lock=True)
        if row.requested_by == actor.user_id:
            raise _invalid("self_approval")  # QT-PERM-06 (CHECK resolved_by <> requested_by)
        if row.status == "expired":
            raise AppError(ErrorCode.APPROVAL_REQUEST_EXPIRED, params={"id": str(row.id)})
        if row.status != "pending":
            raise AppError(
                ErrorCode.APPROVAL_REQUEST_ALREADY_RESOLVED, params={"id": str(row.id), "status": row.status}
            )
        return row


def _request_branch(scope: BranchScope) -> UUID:
    if scope.current is not None:
        return scope.current
    if len(scope.allowed) == 1:
        return scope.allowed[0]
    raise AppError(
        ErrorCode.VALIDATION_ERROR,
        details=[ErrorDetail(field="X-Branch-Id", message_key="validation.required")],
    )


def _requested_value(kind: str, context: Mapping[str, Any]) -> Decimal | None:
    key = value_key(kind)
    raw = context.get(key)
    if raw is None:
        if kind == "card_manual_entry":
            return None
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            details=[ErrorDetail(field=f"context.{key}", message_key="validation.required")],
        )
    if not isinstance(raw, str):
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            details=[ErrorDetail(field=f"context.{key}", message_key="validation.decimal_string")],
        )
    try:
        value = Decimal(raw)
    except InvalidOperation:
        value = Decimal("NaN")
    if not value.is_finite() or value < 0 or value >= Decimal("1e14"):
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            details=[ErrorDetail(field=f"context.{key}", message_key="validation.decimal_string")],
        )
    return value.quantize(VALUE_EXP)
