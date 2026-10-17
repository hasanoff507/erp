"""Composition of the sync module (23 §1 ``wiring.py``): ``/sync/push``, ``/sync/pull``, sync exceptions.

The handler registry collects ``<module>.wiring.sync_handlers(settings, db)`` of every document module
(contract — :mod:`app.modules.sync.application.handlers`). Modules written in parallel (cash, sales,
returns) are imported defensively: until a module exposes ``sync_handlers`` its event types answer
``rejected VALIDATION_ERROR validation.event_type_not_supported`` (non-retryable).
"""

from __future__ import annotations

import importlib
from collections.abc import Callable, Mapping
from typing import Any, Final
from uuid import UUID

import structlog
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.principal import Principal
from app.core.config import Settings
from app.core.db.session import Database
from app.modules.auth.application.actor import ActorBindings, ActorBindingUnavailableError, session_key
from app.modules.notifications.wiring import event_recorder
from app.modules.sync.application.exceptions import SyncExceptionService
from app.modules.sync.application.handlers import SyncEventHandler
from app.modules.sync.application.module import SyncModule
from app.modules.sync.application.ports import StaffPin, StaffPinSource
from app.modules.sync.application.pull import PullConfig, PullService
from app.modules.sync.application.push import PushConfig, PushService
from app.modules.sync.application.registry import HandlerRegistry
from app.modules.sync.infrastructure.gate_redis import GateConfig, RedisPushGate
from app.modules.sync.infrastructure.pull_sql import SqlPullReader
from app.modules.sync.infrastructure.store_sql import SqlExceptionStore, SqlSyncStore

log = structlog.get_logger(__name__)

# document modules exposing ``wiring.sync_handlers(settings, db)`` (PLAN contract 1)
HANDLER_MODULES: Final = (
    "app.modules.inventory.wiring",
    "app.modules.cash.wiring",
    "app.modules.sales.wiring",
    "app.modules.returns.wiring",
    "app.modules.debts.wiring",  # B4: debt_payment.created, counterparty.created
    "app.modules.expenses.wiring",  # B4: expense.created
)

__all__ = ["HANDLER_MODULES", "SyncModule", "build_sync_module", "collect_handlers"]


def collect_handlers(settings: Settings, db: Database) -> dict[str, SyncEventHandler]:
    handlers: dict[str, SyncEventHandler] = {}
    for name in HANDLER_MODULES:
        try:
            module = importlib.import_module(name)
        except ImportError:
            log.info("sync_handlers_module_missing", module=name)
            continue
        factory = getattr(module, "sync_handlers", None)
        if factory is None:
            log.info("sync_handlers_not_exposed", module=name)
            continue
        found: Mapping[str, SyncEventHandler] = factory(settings, db)
        for event_type, handler in found.items():
            if event_type in handlers:
                raise RuntimeError(f"two modules register a sync handler for {event_type!r}")
            handlers[event_type] = handler
    return handlers


class _AuthStaffPins:
    """Adapter of b3-device's ``auth.wiring.staff_pin_snapshot()`` (contract 6)."""

    def __init__(self, snapshot: Any) -> None:
        self._snapshot = snapshot

    async def for_branch(self, s: AsyncSession, tenant_id: UUID, branch_id: UUID) -> list[StaffPin]:
        rows = await self._snapshot.for_branch(s, tenant_id, branch_id)
        return [
            StaffPin(
                user_id=row.user_id,
                pin_local_hash=getattr(row, "pin_local_hash", None),
                must_change_pin=bool(getattr(row, "must_change_pin", False)),
                active=bool(getattr(row, "active", True)),
            )
            for row in rows
        ]


def staff_pins() -> StaffPinSource | None:
    try:
        module = importlib.import_module("app.modules.auth.wiring")
    except ImportError:  # pragma: no cover — the auth module always exists
        return None
    factory = getattr(module, "staff_pin_snapshot", None)
    return _AuthStaffPins(factory()) if factory is not None else None


class _AuthActorVerifier:
    """SEC-02 adapter over ``auth`` ``ActorBindings`` (the binding ``POST /auth/pin/verify`` records)."""

    def __init__(self, bindings: ActorBindings) -> None:
        self._bindings = bindings

    async def bound(self, principal: Principal, user_id: UUID) -> bool:
        key = session_key(principal.sid, principal.family_id)
        if principal.device_id is None or key is None:
            return False
        try:
            return await self._bindings.bound(principal.device_id, key, user_id)
        except ActorBindingUnavailableError:
            log.warning("sync_actor_binding_unavailable")
            return False


def build_sync_module(settings: Settings, db: Database, redis: Callable[[], Redis]) -> SyncModule:
    sf = db.session_factory
    store = SqlSyncStore()
    registry = HandlerRegistry(collect_handlers(settings, db))
    push = PushService(
        sf,
        store,
        registry,
        RedisPushGate(
            redis,
            GateConfig(
                rate_per_s=settings.sync_push_rate_per_s,
                tenant_concurrency=settings.sync_push_tenant_concurrency,
                lock_ttl_s=settings.sync_push_lock_ttl_s,
            ),
        ),
        event_recorder(),
        PushConfig(
            max_events=settings.sync_push_max_events,
            clamp_window_s=settings.sync_offline_clamp_window_s,
            clock_skew_s=settings.sync_clock_skew_warn_s,
            binding_ttl_s=settings.actor_binding_ttl_s,
        ),
        _AuthActorVerifier(ActorBindings(redis, ttl_s=settings.actor_binding_ttl_s)),
    )
    pull = PullService(
        sf,
        store,
        SqlPullReader(),
        staff_pins(),
        PullConfig(
            default_page_size=settings.sync_pull_page_size,
            max_page_size=settings.sync_pull_max_page_size,
            settle_s=settings.sync_pull_settle_s,
        ),
    )
    return SyncModule(push, pull, SyncExceptionService(sf, SqlExceptionStore()), registry)
