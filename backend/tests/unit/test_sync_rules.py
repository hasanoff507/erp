"""Pure sync rules (16 §3.1, §3.4, §8): clamp, outbox report, retryable, actor activity, pull cursor."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.modules.sync.domain.cursor import (
    ALL_SCOPES,
    CursorError,
    Position,
    PullCursor,
    ScopeError,
    digest,
    parse_scopes,
)
from app.modules.sync.domain.rules import (
    EVENT_PERMISSIONS,
    EVENT_TYPES,
    actor_was_active,
    clamp_created_at,
    is_retryable,
    outbox_report,
)

NOW = datetime(2026, 10, 17, 9, 0, tzinfo=UTC)


def test_clock_skew_clamp_both_directions() -> None:
    fwd = clamp_created_at(NOW + timedelta(days=3), NOW, window_s=7 * 86400, skew_s=300)
    assert (fwd.effective, fwd.clamped) == (NOW + timedelta(seconds=300), True)
    back = clamp_created_at(NOW - timedelta(days=30), NOW, window_s=7 * 86400, skew_s=300)
    assert (back.effective, back.clamped) == (NOW - timedelta(days=7), True)
    fine = clamp_created_at(NOW - timedelta(hours=47), NOW, window_s=7 * 86400, skew_s=300)
    assert (fine.effective, fine.clamped) == (NOW - timedelta(hours=47), False)


def test_outbox_report_adds_rejected_events() -> None:
    assert outbox_report(0, None, []) == outbox_report(0, None, ())
    report = outbox_report(3, NOW, [NOW - timedelta(hours=1), NOW + timedelta(hours=1)])
    assert (report.pending_count, report.oldest_pending_at) == (5, NOW - timedelta(hours=1))
    assert outbox_report(0, None, []).oldest_pending_at is None


def test_retryable_only_for_dependencies_and_faults() -> None:
    assert is_retryable("SALE_NOT_FOUND") and is_retryable("DEPENDENCY_NOT_SYNCED")
    assert is_retryable("INTERNAL_ERROR")
    assert not is_retryable("VALIDATION_ERROR") and not is_retryable("RECEIPT_SEQ_CONFLICT")
    assert not is_retryable("FISCAL_OFFLINE_48H_BLOCKED")


def test_event_catalog_matches_16_section_2() -> None:
    assert set(EVENT_PERMISSIONS) == EVENT_TYPES
    assert len(EVENT_TYPES) == 13


def test_actor_blocked_after_the_event_still_counts() -> None:
    assert actor_was_active("active", NOW, NOW)
    assert actor_was_active("blocked", NOW, NOW - timedelta(minutes=1))
    assert not actor_was_active("blocked", NOW - timedelta(minutes=1), NOW)
    assert not actor_was_active("invited", NOW, NOW - timedelta(days=1))


def test_cursor_round_trip_and_errors() -> None:
    cur = PullCursor({"catalog.products": Position(NOW, "abc")}, {"settings": "d1"})
    back = PullCursor.decode(cur.encode())
    assert back.positions == cur.positions and back.digests == cur.digests
    assert PullCursor.decode(None).positions == {} and PullCursor.decode("").digests == {}
    for bad in ("x", "e30", PullCursor({"s": Position(datetime(2200, 1, 1, tzinfo=UTC), "k")}).encode()):
        with pytest.raises(CursorError):
            PullCursor.decode(bad)


def test_scopes() -> None:
    assert parse_scopes(None) == ALL_SCOPES and parse_scopes("all") == ALL_SCOPES
    assert parse_scopes("prices, catalog") == ("catalog", "prices")
    with pytest.raises(ScopeError):
        parse_scopes("catalog,secrets")
    assert digest({"a": 1, "b": [1]}) == digest({"b": [1], "a": 1})
