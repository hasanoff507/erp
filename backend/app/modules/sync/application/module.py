"""The sync module facade published on ``app.state.sync`` (built by ``wiring.py``)."""

from __future__ import annotations

from dataclasses import dataclass

from app.modules.sync.application.exceptions import SyncExceptionService
from app.modules.sync.application.pull import PullService
from app.modules.sync.application.push import PushService
from app.modules.sync.application.registry import HandlerRegistry


@dataclass(slots=True)
class SyncModule:
    push: PushService
    pull: PullService
    exceptions: SyncExceptionService
    registry: HandlerRegistry
