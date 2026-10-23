"""Pure rules of the stock documents: transfer receive pieces (13 §2.10), overdue flag (QT-M06-05), offline
payload validators (19 §13–§14, Bosqich 3), write-off accounts/VAT/estimate (13 §2.12), count surplus cost
(13 §2.11) and the e-TTN outbox backoff (21 §0, §3)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from app.modules.integrations.einvoice.domain.retry import (
    MAX_ATTEMPTS,
    backoff_seconds,
    exhausted,
    next_run_at,
)
from app.modules.inventory.domain.costing import LotView
from app.modules.inventory.domain.stock_counts import parse_line_recorded, shortage_account, surplus_unit_cost
from app.modules.inventory.domain.transfers import (
    EventPayloadError,
    IssuedPiece,
    is_overdue,
    overdue_hours,
    parse_transfer_received,
    parse_transfer_sent,
    receive_pieces,
    weighted_unit_cost,
)
from app.modules.inventory.domain.write_offs import (
    EstimateLine,
    KeyState,
    cost_account,
    estimate_cost,
    gift_needs_vat,
    gift_vat,
)

D = Decimal
A, B = uuid4(), uuid4()


def test_receive_pieces_fill_in_order_and_shortage_from_the_tail() -> None:
    issued = [
        IssuedPiece(A, D("6.000"), D("30000.00"), False),
        IssuedPiece(B, D("4.000"), D("22000.00"), False),
    ]
    plan = receive_pieces(issued, D("8.000"))
    assert [(p.piece.lot_id, p.qty, p.amount) for p in plan.pieces] == [
        (A, D("6.000"), D("30000.00")),
        (B, D("2.000"), D("11000.00")),
    ]
    assert (plan.send_cost, plan.received_cost, plan.shortage_cost) == (
        D("52000.00"),
        D("41000.00"),
        D("11000.00"),
    )
    full = receive_pieces(issued, D("10.000"))
    assert full.shortage_cost == D("0.00") and full.received_cost == full.send_cost
    nothing = receive_pieces(issued, D("0.000"))
    assert nothing.pieces == [] and nothing.shortage_cost == D("52000.00")
    with pytest.raises(ValueError, match="outside"):
        receive_pieces(issued, D("10.001"))


def test_receive_pieces_rounding_keeps_2970_exact() -> None:
    issued = [IssuedPiece(A, D("3.000"), D("10000.00"), False)]  # 3333.333… per unit
    plan = receive_pieces(issued, D("1.000"))
    assert plan.received_cost == D("3333.33") and plan.shortage_cost == D("6666.67")
    assert plan.received_cost + plan.shortage_cost == plan.send_cost
    assert weighted_unit_cost(D("10000.00"), D("3.000")) == D("3333.3333")


def test_overdue_flag_and_setting() -> None:
    sent = datetime(2026, 10, 1, 8, tzinfo=UTC)
    assert is_overdue("sent", sent, sent + timedelta(hours=48, seconds=1), 48)
    assert not is_overdue("sent", sent, sent + timedelta(hours=48), 48)
    assert not is_overdue("received", sent, sent + timedelta(days=9), 48)
    assert not is_overdue("posted", None, sent, 1)
    assert [overdue_hours(x) for x in (None, "12", 0, 721, "x", 720)] == [48, 12, 48, 48, 48, 720]


def test_transfer_sent_payload() -> None:
    tid, w1, w2, line, prod = uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
    existing = parse_transfer_sent({"transfer_id": str(tid)})
    assert existing.transfer_id == tid and existing.lines == ()
    new = parse_transfer_sent(
        {"id": str(tid), "temp_number": "T-1", "doc_date": "2026-10-17", "from_warehouse_id": str(w1),
         "to_warehouse_id": str(w2), "transport_mode": "on_foot_or_public",
         "lines": [{"line_id": str(line), "product_id": str(prod), "qty_sent": "2.500"}]}
    )  # fmt: skip
    assert new.transfer_id is None and new.id == tid and new.lines[0].qty_sent == D("2.500")
    assert new.transport_mode == "on_foot_or_public"
    bad = [
        ({"transfer_id": str(tid), "lines": []}, "lines"),
        ({"id": str(tid), "doc_date": "x", "from_warehouse_id": str(w1), "to_warehouse_id": str(w2),
          "lines": [{"line_id": str(line), "product_id": str(prod), "qty_sent": "1.000"}]}, "doc_date"),
        ({"id": str(tid), "doc_date": "2026-10-17", "from_warehouse_id": str(w1), "to_warehouse_id": str(w1),
          "lines": [{"line_id": str(line), "product_id": str(prod), "qty_sent": "1.000"}]}, "to_warehouse_id"),
        ({"id": str(tid), "doc_date": "2026-10-17", "from_warehouse_id": str(w1), "to_warehouse_id": str(w2),
          "lines": [{"line_id": str(line), "product_id": str(prod), "qty_sent": "0.000"}]}, "lines[0].qty_sent"),
        ({"id": str(tid), "doc_date": "2026-10-17", "from_warehouse_id": str(w1), "to_warehouse_id": str(w2),
          "transport_mode": "plane", "lines": []}, "transport_mode"),
    ]  # fmt: skip
    for payload, field in bad:
        with pytest.raises(EventPayloadError) as exc:
            parse_transfer_sent(payload)
        assert exc.value.field == field


def test_transfer_received_payload() -> None:
    tid, line = uuid4(), uuid4()
    ev = parse_transfer_received(
        {"transfer_id": str(tid), "lines": [{"transfer_line_id": str(line), "qty_received": "0.000"}]}
    )
    assert ev.transfer_id == tid and ev.lines[0].qty_received == D("0.000")
    with pytest.raises(EventPayloadError) as exc:
        parse_transfer_received(
            {"transfer_id": str(tid), "lines": [{"transfer_line_id": str(line), "qty_received": "1.000"}] * 2}
        )
    assert exc.value.field == "lines"
    with pytest.raises(EventPayloadError) as exc:
        parse_transfer_received(
            {"transfer_id": str(tid), "lines": [{"transfer_line_id": str(line), "qty_received": 1}]}
        )
    assert exc.value.field == "lines[0].qty_received"


def test_line_recorded_payload() -> None:
    cid, pid = uuid4(), uuid4()
    ev = parse_line_recorded(
        {
            "count_id": str(cid),
            "product_id": str(pid),
            "counted": "7.000",
            "recorded_at": "2026-10-17T10:00:00+05:00",
        }
    )
    assert ev.counted == D("7.000") and ev.recorded_at == datetime(2026, 10, 17, 5, tzinfo=UTC)
    unknown = parse_line_recorded(
        {"count_id": str(cid), "barcode": "478000", "counted": "1.000", "recorded_at": "2026-10-17T05:00:00Z"}
    )
    assert unknown.product_id is None and unknown.barcode == "478000"
    for payload, field in (
        (
            {
                "count_id": "x",
                "product_id": str(pid),
                "counted": "1.000",
                "recorded_at": "2026-10-17T05:00:00Z",
            },
            "count_id",
        ),
        ({"count_id": str(cid), "counted": "1.000", "recorded_at": "2026-10-17T05:00:00Z"}, "product_id"),
        (
            {
                "count_id": str(cid),
                "product_id": str(pid),
                "counted": "-1.000",
                "recorded_at": "2026-10-17T05:00:00Z",
            },
            "counted",
        ),
        (
            {
                "count_id": str(cid),
                "product_id": str(pid),
                "counted": "1.000",
                "recorded_at": "2026-10-17T05:00:00",
            },
            "recorded_at",
        ),
    ):
        with pytest.raises(EventPayloadError) as exc:
            parse_line_recorded(payload)
        assert exc.value.field == field


def test_count_accounts_and_surplus_cost() -> None:
    assert shortage_account(uuid4()) == "4730" and shortage_account(None) == "5910"
    assert surplus_unit_cost(D("8000"), D("10"), D("50000")) == D("8000.0000")
    assert surplus_unit_cost(None, D("3.000"), D("10000.00")) == D("3333.3333")
    assert surplus_unit_cost(None, D("-2.000"), D("0.00")) == D("0.0000")


def test_write_off_accounts_and_gift_vat() -> None:
    who = uuid4()
    assert [cost_account(r, None, None) for r in ("expired", "damaged", "expired_return", "other")] == [
        "9430"
    ] * 4
    assert [cost_account(r, None, who) for r in ("expired", "damaged", "expired_return", "other")] == [
        "4730"
    ] * 4
    assert cost_account("gift", "promo_justified", who) == "9410"
    assert cost_account("gift", "other", who) == "9430"
    assert gift_needs_vat("gift", "other") and not gift_needs_vat("gift", "promo_justified")
    vat = gift_vat(D("11200.0000"), D("12.00"), D("2.000"))
    assert (vat.market_value, vat.vat) == (D("20000.00"), D("2400.00"))
    odd = gift_vat(D("9999.9900"), D("12.00"), D("1.000"))  # 8928.5625 → 8928.56; × 12% = 1071.4272
    assert (odd.market_value, odd.vat) == (D("8928.56"), D("1071.43"))


def test_write_off_estimate_follows_the_toolkit_rules() -> None:
    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    lot1 = LotView(A, t0, D("3.000"), D("0.000"), D("1000.0000"))
    lot2 = LotView(B, t0 + timedelta(days=1), D("10.000"), D("2.000"), D("1500.0000"))
    key = (uuid4(), uuid4())
    states = {key: KeyState([lot1, lot2], D("1384.6154"), D("1500.0000"))}
    lines = [EstimateLine(key, D("4.000"), None, False), EstimateLine(key, D("10.000"), None, False)]
    fifo = estimate_cost("fifo", lines, states)
    # line 1: 3 × 1000 + 1 × 1500; line 2: 7 free units of lot2 × 1500 + 3 pending × 1500
    assert (fifo.total, fifo.covered, fifo.uncovered) == (
        D("19500.00"), [D("4.000"), D("7.000")], [D("0.000"), D("3.000")],
    )  # fmt: skip
    aveco = estimate_cost("aveco", lines[:1], states)
    assert aveco.total == D("5538.46")  # ROUND(4 × 1384.6154)
    blocked = estimate_cost("fifo", [EstimateLine(key, D("2.000"), B, True)], states)
    assert (blocked.total, blocked.uncovered) == (D("3000.00"), [D("0.000")])


def test_ettn_backoff_policy() -> None:
    assert [backoff_seconds(n) for n in (1, 2, 3, 6, 7, 8, 23)] == [60, 120, 240, 1920, 3600, 3600, 3600]
    assert not exhausted(MAX_ATTEMPTS - 1) and exhausted(MAX_ATTEMPTS) and MAX_ATTEMPTS == 24
    now = datetime(2026, 10, 17, tzinfo=UTC)
    assert next_run_at(now, 1, 0.0) == now + timedelta(seconds=60)
    assert next_run_at(now, 1, 0.999) < now + timedelta(seconds=66.01)
    with pytest.raises(ValueError, match="attempts"):
        backoff_seconds(0)
