"""Handler registry of ``/sync/push`` (contract: :mod:`app.modules.sync.application.handlers`).

``sync.wiring`` fills it from every document module's ``wiring.sync_handlers(settings, db)``; tests may
:meth:`register` their own handlers (the real push pipeline then runs them — no DB mocks).
"""

from __future__ import annotations

from collections.abc import Mapping

from app.modules.sync.application.handlers import SyncEventHandler


class HandlerRegistry:
    def __init__(self, handlers: Mapping[str, SyncEventHandler] | None = None) -> None:
        self._handlers: dict[str, SyncEventHandler] = dict(handlers or {})

    def register(self, event_type: str, handler: SyncEventHandler, *, replace: bool = False) -> None:
        if event_type in self._handlers and not replace:
            raise ValueError(f"sync handler for {event_type!r} is already registered")
        self._handlers[event_type] = handler

    def unregister(self, event_type: str) -> None:
        self._handlers.pop(event_type, None)

    def get(self, event_type: str) -> SyncEventHandler | None:
        return self._handlers.get(event_type)

    def types(self) -> frozenset[str]:
        return frozenset(self._handlers)
