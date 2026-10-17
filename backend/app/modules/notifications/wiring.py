"""Composition of the notifications module (23 §1 ``wiring.py``).

Other modules record events through :func:`event_recorder` (``record_event(session, tenant_id, kind,
payload, dedupe_key)`` inside their own transaction).
"""

from __future__ import annotations

from app.modules.notifications.application.outbox import EventRecorder
from app.modules.notifications.domain.events import EVENT_KINDS, OUTBOX_KIND, EventKind
from app.modules.notifications.infrastructure.repositories import SqlOutboxRepository

__all__ = ["EVENT_KINDS", "OUTBOX_KIND", "EventKind", "EventRecorder", "event_recorder"]


def event_recorder() -> EventRecorder:
    return EventRecorder(SqlOutboxRepository())
