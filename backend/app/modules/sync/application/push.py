"""``POST /sync/push`` (16 §3.1–§3.4, §8; 18 §2.1/§2.2/§2.6).

Request level (nothing is processed when it fails): the envelope (≤ ``max_events``, every
``events[i].device_id`` = ``device_id``, ``seq`` strictly increasing, no repeated ``client_event_id``), the
device of the token/session (``403 DEVICE_REVOKED``), backpressure (``429`` + ``Retry-After``).

Per event — ONE ``tenant_transaction`` each (``app.user_id`` = ``actor_user_id``):

1. advisory lock on ``(tenant, client_event_id)`` → a stored ``sync_receipts`` row answers ``duplicate``
   with the stored ``server``/``warnings`` (a different device reusing the id is refused);
2. the actor: membership active at ``created_at``, covering the device branch, holding the event's
   permission; a ``sync.drain`` token only drains events created before ``grace_ends_at`` (14 §16.4);
3. the module handler (``HandlerRegistry``) posts the document in the same transaction;
4. ``sync_receipts`` (the full ``PushResultEntry`` + raw/effective ``created_at``), the handler's
   ``sync_exceptions`` rows and their M18 telegram events, audit (clock clamp; actor ≠ session user);
5. COMMIT, then the handler's ``after_commit`` callbacks.

An ``AppError`` rolls the event back → ``rejected`` (``retryable`` per 16 §3.4); any other exception →
``rejected INTERNAL_ERROR`` (retryable, nothing written). Rejected events are not recorded — the device
keeps them (POS-12) and may resend. Afterwards ONE transaction reports ``devices.outbox_*`` /
``last_sync_at`` (16 §3.1).
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Final
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.audit import record_audit
from app.core.auth.principal import Principal
from app.core.db.base import uuid7
from app.core.db.session import tenant_transaction
from app.core.error_codes import ErrorCode
from app.core.errors import AppError, ErrorDetail
from app.modules.notifications.application.outbox import EventRecorder
from app.modules.sync.application.handlers import EventContext, HandlerResult, SyncExceptionRow
from app.modules.sync.application.ports import ActorVerifier, DeviceInfo, PushGate, SyncStore
from app.modules.sync.application.registry import HandlerRegistry
from app.modules.sync.domain.rules import (
    EVENT_PERMISSIONS,
    EVENT_TYPES,
    EXCEPTION_KINDS,
    NOTIFY_KINDS,
    actor_was_active,
    clamp_created_at,
    is_retryable,
    outbox_report,
)

log = structlog.get_logger(__name__)

SCOPE_SYNC: Final = "sync"
SCOPE_SYNC_DRAIN: Final = "sync.drain"
RECEIPT_ENTITY: Final = "sync_receipts"


@dataclass(frozen=True, slots=True)
class PushConfig:
    max_events: int = 100
    clamp_window_s: int = 7 * 86400
    clock_skew_s: int = 300
    binding_ttl_s: int = 12 * 3600  # ERP_ACTOR_BINDING_TTL_S — PIN binding lifetime (14 §4.3, SEC-02)


@dataclass(frozen=True, slots=True)
class EventIn:
    client_event_id: UUID
    device_id: UUID
    seq: int
    type: str
    created_at: datetime
    actor_user_id: UUID
    payload: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class OutboxStateIn:
    pending_count: int
    oldest_pending_created_at: datetime | None


def _invalid(field: str, key: str, **params: Any) -> AppError:
    return AppError(
        ErrorCode.VALIDATION_ERROR, params=params, details=[ErrorDetail(field=field, message_key=key)]
    )


def _jsonable(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, ensure_ascii=False))


def entry(
    client_event_id: UUID,
    status: str,
    *,
    server: Mapping[str, Any] | None = None,
    warnings: Sequence[str] = (),
    error: AppError | None = None,
) -> dict[str, Any]:
    """One ``PushResultEntry`` (18 §2.2) + ``params``/``details`` of the error for the client's i18n."""
    out: dict[str, Any] = {
        "client_event_id": str(client_event_id),
        "status": status,
        "server": _jsonable(dict(server)) if server is not None else None,
        "error_code": None,
        "message": None,
        "retryable": False,
        "warnings": list(warnings),
        "params": {},
        "details": [],
    }
    if error is not None:
        out.update(
            error_code=error.code.value,
            message=error.message_key,
            retryable=is_retryable(error.code.value),
            params=_jsonable(error.params),
            details=[d.model_dump() for d in error.details],
        )
    return out


def check_device(device: DeviceInfo | None) -> DeviceInfo:
    """The token's device (14 §7): known, not revoked (16 §9), a POS device with a branch."""
    if device is None:
        raise AppError(ErrorCode.DEVICE_REVOKED, params={"reason": "device_unknown"})
    if device.revoked_at is not None:
        raise AppError(ErrorCode.DEVICE_REVOKED)
    if device.kind not in ("web", "android"):
        raise AppError(ErrorCode.PERMISSION_DENIED, params={"reason": "device_kind"})
    if device.branch_id is None:
        raise AppError(ErrorCode.VALIDATION_ERROR, params={"reason": "device_branch_unknown"})
    return device


def require_device(principal: Principal, device_id: UUID | None = None) -> UUID:
    if principal.device_id is None:
        raise AppError(ErrorCode.PERMISSION_DENIED, params={"reason": "device_required"})
    if device_id is not None and device_id != principal.device_id:
        raise AppError(ErrorCode.PERMISSION_DENIED, params={"reason": "device_mismatch"})
    return principal.device_id


class PushService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        store: SyncStore,
        registry: HandlerRegistry,
        gate: PushGate,
        notifier: EventRecorder,
        config: PushConfig,
        actors: ActorVerifier | None = None,
    ) -> None:
        self._sf = session_factory
        self._store = store
        self.registry = registry
        self._gate = gate
        self._notifier = notifier
        self._cfg = config
        self._actors = actors

    # --- request ----------------------------------------------------------------------------------
    def _validate(self, device_id: UUID, events: Sequence[EventIn], state: OutboxStateIn) -> None:
        if len(events) > self._cfg.max_events:
            raise _invalid("events", "validation.max_items", max=self._cfg.max_events)
        if state.pending_count < 0:
            raise _invalid("outbox_state.pending_count", "validation.non_negative")
        if state.pending_count == 0 and state.oldest_pending_created_at is not None:
            raise _invalid("outbox_state.oldest_pending_created_at", "validation.must_be_null")
        seen: set[UUID] = set()
        last_seq: int | None = None
        for i, ev in enumerate(events):
            if ev.device_id != device_id:
                raise _invalid(f"events[{i}].device_id", "validation.device_mismatch")
            if ev.client_event_id in seen:
                raise _invalid(f"events[{i}].client_event_id", "validation.duplicate_event")
            seen.add(ev.client_event_id)
            if last_seq is not None and ev.seq <= last_seq:
                raise _invalid(f"events[{i}].seq", "validation.seq_not_increasing")
            last_seq = ev.seq

    async def push(
        self,
        principal: Principal,
        device_id: UUID,
        events: Sequence[EventIn],
        state: OutboxStateIn,
        *,
        ip: str | None = None,
    ) -> dict[str, Any]:
        require_device(principal, device_id)
        if not (principal.has_scope(SCOPE_SYNC) or principal.has_scope(SCOPE_SYNC_DRAIN)):
            raise AppError(ErrorCode.PERMISSION_DENIED, params={"reason": "sync_scope_missing"})
        self._validate(device_id, events, state)
        drain = principal.has_scope(SCOPE_SYNC_DRAIN)
        tenant_id = principal.tenant_id
        async with self._sf() as s, tenant_transaction(s, tenant_id, user_id=principal.user_id):
            device = check_device(await self._store.device(s, device_id))
            grace = await self._store.grace_ends_at(s) if drain else None
        token = await self._gate.enter(tenant_id, device_id)
        try:
            received_at = datetime.now(UTC)
            results: list[dict[str, Any]] = []
            rejected_at: list[datetime] = []
            for ev in events:
                result = await self._one(principal, device, ev, received_at, drain=drain, grace=grace, ip=ip)
                results.append(result)
                if result["status"] == "rejected":
                    rejected_at.append(ev.created_at)
            report = outbox_report(state.pending_count, state.oldest_pending_created_at, rejected_at)
            async with self._sf() as s, tenant_transaction(s, tenant_id, user_id=principal.user_id):
                await self._store.report_outbox(s, device_id, report.pending_count, report.oldest_pending_at)
                if drain:
                    await self._drain_audit(s, principal, device_id, grace, results, report.pending_count, ip)
        finally:
            await self._gate.leave(tenant_id, device_id, token)
        return {"results": results}

    async def _drain_audit(
        self,
        s: AsyncSession,
        principal: Principal,
        device_id: UUID,
        grace: datetime | None,
        results: Sequence[Mapping[str, Any]],
        pending: int,
        ip: str | None,
    ) -> None:
        """15 §6.1 / 14 §16.4: ``sync_drain_started`` once per lockout, ``sync_drain_completed`` when "
        "empty."""
        since = grace or datetime(2000, 1, 1, tzinfo=UTC)
        accepted = sum(1 for r in results if r["status"] in ("accepted", "duplicate"))
        common: dict[str, Any] = {
            "tenant_id": principal.tenant_id,
            "entity": "devices",
            "entity_id": device_id,
        }
        if not await self._store.audit_exists(s, "sync_drain_started", device_id, since):
            await record_audit(
                s,
                **common,
                action="sync_drain_started",
                user_id=principal.user_id,
                ip=ip,
                device_id=device_id,
                after={"events": len(results)},
            )
        if pending == 0:
            await record_audit(
                s,
                **common,
                action="sync_drain_completed",
                user_id=principal.user_id,
                ip=ip,
                device_id=device_id,
                after={"accepted": accepted, "events": len(results)},
            )

    # --- one event --------------------------------------------------------------------------------
    async def _one(
        self,
        principal: Principal,
        device: DeviceInfo,
        ev: EventIn,
        received_at: datetime,
        *,
        drain: bool,
        grace: datetime | None,
        ip: str | None,
    ) -> dict[str, Any]:
        handler = self.registry.get(ev.type)
        if handler is None:
            key = (
                "validation.event_type_not_supported"
                if ev.type in EVENT_TYPES
                else "validation.event_type_unknown"
            )
            return entry(ev.client_event_id, "rejected", error=_invalid("type", key, type=ev.type))
        clamp = clamp_created_at(
            ev.created_at, received_at, window_s=self._cfg.clamp_window_s, skew_s=self._cfg.clock_skew_s
        )
        assert device.branch_id is not None
        ctx = EventContext(
            tenant_id=principal.tenant_id,
            device_id=device.id,
            branch_id=device.branch_id,
            cash_register_id=device.cash_register_id,
            client_event_id=ev.client_event_id,
            seq=ev.seq,
            event_type=ev.type,
            created_at=clamp.effective,
            received_at=received_at,
            actor_user_id=ev.actor_user_id,
            session_user_id=principal.user_id,
            client_created_at=ev.created_at,
            actor_bound=self._binding_probe(principal),
        )
        result: HandlerResult | None = None
        try:
            async with self._sf() as s, tenant_transaction(s, principal.tenant_id, user_id=ev.actor_user_id):
                await self._store.lock_event(s, principal.tenant_id, ev.client_event_id)
                stored = await self._store.receipt(s, ev.client_event_id)
                if stored is not None:
                    if stored.device_id != device.id:
                        raise _invalid("client_event_id", "validation.client_event_id_reused")
                    return entry(
                        ev.client_event_id,
                        "duplicate",
                        server=stored.result.get("server"),
                        warnings=list(stored.result.get("warnings") or ()),
                    )
                await self._check_actor(s, ctx)
                if drain and (grace is None or clamp.effective > grace):
                    raise AppError(ErrorCode.SUBSCRIPTION_RESTRICTED, params={"reason": "after_lockout"})
                result = await handler(s, ctx, ev.payload)
                accepted = entry(
                    ev.client_event_id, "accepted", server=result.server, warnings=result.warnings
                )
                receipt_id = uuid7()
                await self._store.insert_receipt(
                    s,
                    receipt_id=receipt_id,
                    tenant_id=principal.tenant_id,
                    device_id=device.id,
                    client_event_id=ev.client_event_id,
                    result={
                        **accepted,
                        "type": ev.type,
                        "seq": ev.seq,
                        "actor_user_id": str(ev.actor_user_id),
                        "client_created_at": ev.created_at.astimezone(UTC).isoformat(),
                        "effective_created_at": clamp.effective.astimezone(UTC).isoformat(),
                    },
                )
                unverified = await self._unverified_actor(ctx, ev, result)
                await self._exceptions(s, ctx, result, extra=unverified)
                await self._audits(s, ctx, receipt_id, clamp.clamped, ip)
        except AppError as exc:
            return entry(ev.client_event_id, "rejected", error=exc)
        except Exception:
            log.exception("sync_event_failed", type=ev.type, client_event_id=str(ev.client_event_id))
            return entry(ev.client_event_id, "rejected", error=AppError(ErrorCode.INTERNAL_ERROR))
        for callback in result.after_commit:
            try:
                await callback()
            except Exception:  # committed already — never fail the event
                log.warning("sync_after_commit_failed", type=ev.type, exc_info=True)
        return accepted

    async def _check_actor(self, s: AsyncSession, ctx: EventContext) -> None:
        actor = await self._store.actor(s, ctx.actor_user_id)
        if actor is None or not actor_was_active(actor.status, actor.changed_at, ctx.created_at):
            raise AppError(ErrorCode.PERMISSION_DENIED, params={"reason": "actor_inactive"})
        if actor.branch_ids and ctx.branch_id not in actor.branch_ids:
            raise AppError(ErrorCode.PERMISSION_DENIED, params={"reason": "actor_branch"})
        code = EVENT_PERMISSIONS.get(ctx.event_type)
        if code is not None and not await self._store.actor_limits(s, ctx.actor_user_id, code):
            raise AppError(ErrorCode.PERMISSION_DENIED, params={"reason": "permission", "permission": code})

    def _binding_probe(self, principal: Principal) -> Callable[[UUID], Awaitable[bool]] | None:
        actors = self._actors
        if actors is None:
            return None

        async def bound(user_id: UUID) -> bool:
            return await actors.bound(principal, user_id)

        return bound

    async def _unverified_actor(
        self, ctx: EventContext, ev: EventIn, result: HandlerResult
    ) -> tuple[SyncExceptionRow, ...]:
        """SEC-02 / 15 §2.3a (detect, never reject): an ONLINE event (``is_offline=false``) made by someone
        other than the session user must name an actor PIN-bound to this device session; otherwise it is
        accepted with ``sync_exceptions(kind='actor_unverified')`` + M18. Offline events stay trusted (a
        binding cannot be proven offline) — the residual risk is documented in 15 §2.3a."""
        if ctx.actor_user_id == ctx.session_user_id or ev.payload.get("is_offline") is not False:
            return ()
        if (ctx.received_at - ctx.created_at).total_seconds() > self._cfg.binding_ttl_s:
            return ()  # older than any binding could be — nothing to prove against
        if ctx.actor_bound is not None and await ctx.actor_bound(ctx.actor_user_id):
            return ()
        server_id = (result.server or {}).get("id")
        return (
            SyncExceptionRow(
                "actor_unverified",
                {
                    "role": "actor",
                    "actor_user_id": str(ctx.actor_user_id),
                    "session_user_id": str(ctx.session_user_id),
                    "type": ctx.event_type,
                    "server_id": str(server_id) if server_id else None,
                },
            ),
        )

    async def _exceptions(
        self,
        s: AsyncSession,
        ctx: EventContext,
        result: HandlerResult,
        *,
        extra: Sequence[SyncExceptionRow] = (),
    ) -> None:
        for row in (*result.sync_exceptions, *extra):
            if row.kind not in EXCEPTION_KINDS:
                raise RuntimeError(f"unknown sync_exceptions.kind {row.kind!r} (16 §5)")
            exception_id = uuid7()
            details = _jsonable(dict(row.details))
            await self._store.insert_exception(
                s,
                {
                    "id": exception_id,
                    "tenant_id": ctx.tenant_id,
                    "device_id": ctx.device_id,
                    "client_event_id": ctx.client_event_id,
                    "kind": row.kind,
                    "doc_type": row.doc_type,
                    "doc_id": row.doc_id,
                    "details": json.dumps(details, ensure_ascii=False),
                },
            )
            notify = NOTIFY_KINDS.get(row.kind)
            if notify is not None:  # B3-T18: recorded only, the Telegram sender is Bosqich 4
                await self._notifier.record_event(
                    s,
                    ctx.tenant_id,
                    notify,
                    {
                        "sync_exception_id": str(exception_id),
                        "kind": row.kind,
                        "branch_id": str(ctx.branch_id),
                        "device_id": str(ctx.device_id),
                        "doc_type": row.doc_type,
                        "doc_id": str(row.doc_id) if row.doc_id else None,
                        "details": details,
                    },
                    f"sync_exception:{exception_id}",
                )

    async def _audits(
        self, s: AsyncSession, ctx: EventContext, receipt_id: UUID, clamped: bool, ip: str | None
    ) -> None:
        base: dict[str, Any] = {
            "tenant_id": ctx.tenant_id,
            "entity": RECEIPT_ENTITY,
            "entity_id": receipt_id,
            "device_id": ctx.device_id,
            "ip": ip,
        }
        event = {"type": ctx.event_type, "client_event_id": str(ctx.client_event_id), "seq": ctx.seq}
        if clamped:  # 16 §8: the clamp is marked for audit
            await record_audit(
                s,
                **base,
                action="sync.clock_skew_clamped",
                user_id=ctx.actor_user_id,
                after={
                    **event,
                    "client_created_at": ctx.client_created_at.isoformat() if ctx.client_created_at else None,
                    "effective_created_at": ctx.created_at.isoformat(),
                    "received_at": ctx.received_at.isoformat(),
                },
            )
        if ctx.actor_user_id != ctx.session_user_id:  # 16 §2: both users are audited
            await record_audit(
                s,
                **base,
                action="sync.event_by_other_actor",
                user_id=ctx.session_user_id,
                after={
                    **event,
                    "actor_user_id": str(ctx.actor_user_id),
                    "session_user_id": str(ctx.session_user_id),
                },
            )


__all__ = [
    "EventIn",
    "OutboxStateIn",
    "PushConfig",
    "PushService",
    "check_device",
    "entry",
    "require_device",
]
