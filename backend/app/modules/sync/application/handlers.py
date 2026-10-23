"""Contract between ``/sync/push`` and the modules that own POS documents (16 §3.1, 18 §2.1).

The sync module validates the envelope (device, seq order, clock skew, actor membership), dedupes by
``client_event_id`` and then calls the handler registered for ``type`` **inside the one tenant
transaction of that event** (the ``sync_receipts`` row is written in the same transaction, so an
event is either fully posted and recorded, or neither). A handler:

* validates its own payload (Pydantic, ``extra="forbid"``) — failures raise
  ``AppError(ErrorCode.VALIDATION_ERROR, details=[...])``;
* posts the document through its posting service (document + registers + ledger in ``s``);
* rejects with ``AppError(<catalog code>)`` — the sync module turns it into a ``rejected`` result and
  decides ``retryable`` (16 §3.4); nothing the handler wrote survives (the transaction rolls back);
* returns :class:`HandlerResult` — ``server`` is the ``PushResultEntry.server`` object of 18 for that
  event type, ``warnings`` are catalog codes (``STOCK_NEGATIVE`` …), ``sync_exceptions`` are rows the
  sync module inserts into ``app.sync_exceptions`` in the same transaction (16 §5), ``after_commit``
  callbacks run once the transaction committed (queue jobs, recost …; failures are logged only).

Handlers are registered per module: ``<module>.wiring.sync_handlers(settings, db)`` returns
``Mapping[str, SyncEventHandler]`` keyed by event type; ``sync.wiring`` collects them.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True, slots=True)
class EventContext:
    tenant_id: UUID
    device_id: UUID
    branch_id: UUID  # devices.branch_id of the pushing device
    cash_register_id: UUID | None  # devices.cash_register_id (None for a warehouse-only device)
    client_event_id: UUID
    seq: int
    event_type: str
    created_at: datetime  # effective created_at: device clock clamped by the sync module (16 §8)
    received_at: datetime  # server time the push was received
    actor_user_id: UUID  # 18 §2.1 — active membership at created_at already verified
    session_user_id: UUID  # user of the pushing session/token (audited when it differs from actor)
    # raw device ``created_at`` before the 16 §8 clamp (``created_at`` above is the effective value);
    # None when the event was not clamped-checked (direct service tests)
    client_created_at: datetime | None = None
    # SEC-02 (15 §2.3a): ``await ctx.actor_bound(user_id)`` — is ``user_id`` PIN-bound to this device session
    # right now (``POST /auth/pin/verify`` binding)? None when the session has no binding key; never raises
    # (binding store down → False). Only meaningful for ONLINE events (``is_offline=false``).
    actor_bound: Callable[[UUID], Awaitable[bool]] | None = None


@dataclass(frozen=True, slots=True)
class SyncExceptionRow:
    """One ``app.sync_exceptions`` row (16 §5 kinds) raised while the event was still accepted."""

    kind: str
    details: Mapping[str, Any] = field(default_factory=dict)
    doc_type: str | None = None
    doc_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class HandlerResult:
    server: Mapping[str, Any] | None
    warnings: tuple[str, ...] = ()
    sync_exceptions: tuple[SyncExceptionRow, ...] = ()
    after_commit: tuple[Callable[[], Awaitable[None]], ...] = ()


class SyncEventHandler(Protocol):
    async def __call__(
        self, s: AsyncSession, ctx: EventContext, payload: Mapping[str, Any]
    ) -> HandlerResult: ...
