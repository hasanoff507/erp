"""Pure marking rules (B5-T07): GS1 DataMatrix parser, acceptance deadlines (qaror #63), MARKING_PRECHECK
decisions (18 §15) and the CRPT outbox retry policy (21 §4)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from app.modules.integrations.marking.domain import deadline, rules
from app.modules.integrations.marking.domain.gs1 import GS, Gs1Error, check_digit, gtin_valid, parse

TASHKENT = deadline.TASHKENT


# --- GS1 (GS1 General Specifications §5.4, §7.8.5, §7.9.1) ----------------------------------------------
def test_gs1_check_digit_known_values() -> None:
    assert check_digit("629104150021") == 3  # GenSpecs §7.9.1 example: GTIN-13 6291041500213
    assert gtin_valid("6291041500213") and gtin_valid("04780069000048")
    assert not gtin_valid("04600000000001")


def test_gs1_parses_asl_belgisi_code() -> None:
    raw = f"0104780069000048215a8pLsr>qeHnD{GS}93dGVz"
    code = parse(raw)
    assert code.gtin == "04780069000048" and code.serial == "5a8pLsr>qeHnD" and code.crypto_tail == "dGVz"
    assert code.is_marking_code and code.raw == raw


def test_gs1_symbology_id_leading_fnc1_and_91_92() -> None:
    raw = f"]d2{GS}0104780069000048217abc123{GS}91EE07{GS}92" + "A" * 44
    code = parse(raw)
    assert code.verification_key == "EE07" and code.verification_code == "A" * 44 and code.is_marking_code


def test_gs1_fixed_length_ais_need_no_separator() -> None:
    code = parse(f"010478006900004817261231310300150021SER{GS}93abcd")
    assert code.expiry == date(2026, 12, 31) and code.get("3103") == "001500" and code.serial == "SER"
    assert parse(f"0104780069000048172602002101{GS}93x").expiry == date(2026, 2, 28)  # DD=00 → month end


@pytest.mark.parametrize(
    ("raw", "reason"),
    [
        ("", "empty"),
        ("0104600000000001215abc", "gtin_check_digit"),
        ("01047800690000", "truncated"),
        ("2312345", "unknown_ai"),
        (f"0104780069000048215ab c{GS}93x", "bad_character"),
        (f"0104780069000048211{GS}211", "repeated_ai"),
        (f"010478006900004817261399211{GS}93x", "bad_date"),
        ("010478006900004821" + "x" * 21, "bad_length"),
    ],
)
def test_gs1_rejects_malformed(raw: str, reason: str) -> None:
    with pytest.raises(Gs1Error) as err:
        parse(raw)
    assert err.value.reason == reason


def test_gs1_code_without_crypto_is_not_a_marking_code() -> None:
    assert not parse("0104780069000048215abc").is_marking_code


# --- acceptance deadline (21 §4 SLA, qaror #63) -----------------------------------------------------------
def test_deadline_72_hours_from_dispatch_day_start() -> None:
    start = deadline.ownership_start(date(2026, 3, 4), shipped_on=date(2026, 3, 3))
    assert start == datetime(2026, 3, 3, tzinfo=TASHKENT)
    assert deadline.due_at("72_hours", start) == datetime(2026, 3, 6, tzinfo=TASHKENT)


def test_deadline_3_business_days_skips_weekend() -> None:
    friday = deadline.ownership_start(date(2026, 3, 6))  # Fri → Mon, Tue, Wed → due Thu 00:00
    assert deadline.due_at("3_business_days", friday) == datetime(2026, 3, 12, tzinfo=TASHKENT)
    monday = deadline.ownership_start(date(2026, 3, 2))
    assert deadline.due_at("3_business_days", monday) == datetime(2026, 3, 6, tzinfo=TASHKENT)
    assert deadline.add_business_days(date(2026, 3, 7), 1) == date(2026, 3, 9)  # Saturday → Monday


def test_deadline_strictest_group_wins() -> None:
    start = deadline.ownership_start(date(2026, 3, 6))
    kind, due = deadline.strictest({"3_business_days", "72_hours"}, start)
    assert kind == "72_hours" and due == start + timedelta(hours=72)
    assert deadline.strictest(set(), start)[0] == "3_business_days"


def test_deadline_stages() -> None:
    due = datetime(2026, 3, 6, tzinfo=TASHKENT)
    assert deadline.stage(due, due - timedelta(hours=25)) == "pending"
    assert deadline.stage(due, due - timedelta(hours=23)) == "due_soon"
    assert deadline.stage(due, due) == "overdue"


# --- MARKING_PRECHECK (18 §15) and retry (21 §4) -----------------------------------------------------------
def test_precheck_decision_table() -> None:
    assert rules.decide("warn", True) == rules.Decision("ok", False)
    assert rules.decide("warn", False) == rules.Decision("warn", True)
    assert rules.decide("warn", None) == rules.Decision("warn", True)
    assert rules.decide("block", False).outcome == "fail"
    assert rules.decide("block", None).outcome == "unavailable"
    assert rules.decide("off", False) == rules.Decision("ok", False)
    assert (
        rules.mode_of(None) == "warn" and rules.mode_of("block") == "block" and rules.mode_of("x") == "warn"
    )


def test_marking_retry_policy() -> None:
    assert [rules.backoff_seconds(n) for n in range(1, 8)] == [60, 120, 240, 480, 960, 1800, 1800]
    assert rules.retry_delay(1, 1.0) == timedelta(seconds=66)
    now = datetime(2026, 3, 6, tzinfo=UTC)
    assert not rules.exhausted(rules.ACCEPT, 300, now, now)  # inside the deadline window + grace
    assert rules.exhausted(rules.ACCEPT, 1, now + timedelta(hours=24), now)
    assert rules.exhausted(rules.VERIFY, 24, now, None) and not rules.exhausted(rules.VERIFY, 23, now, None)
    assert rules.exhausted(rules.WRITEOFF, 400, now, None)
