"""Card terminal domain rules and the Fake adapter (21 §9.4; B3-T03)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.core.db.base import uuid7
from app.core.errors import AppError
from app.modules.integrations.card_terminal.application.ports import (
    CardPurchaseRequest,
    CardTerminalError,
    TerminalRef,
)
from app.modules.integrations.card_terminal.application.schemas import (
    card_result_from_port,
    parse_card_result,
)
from app.modules.integrations.card_terminal.domain.model import (
    can_transition,
    decline_code_of,
    derive_card_type,
    normalize_mask,
    private_ipv4,
    settlement_status,
    tx_status_of,
)
from app.modules.integrations.card_terminal.infrastructure.fake import FakeCardTerminalAdapter, outcome_for


def test_status_mapping_and_transitions() -> None:
    assert [tx_status_of(s) for s in ("approved", "declined", "cancelled", "error", "timeout", "unknown")] == [
        "approved", "declined", "declined", "declined", "unknown", "unknown",
    ]  # fmt: skip
    assert decline_code_of("cancelled", None) == "cancelled" and decline_code_of("declined", "51") == "51"
    assert can_transition("pending", "unknown") and can_transition("unknown", "approved")
    assert can_transition("approved", "voided") and can_transition("approved", "approved")
    assert not can_transition("approved", "declined") and not can_transition("declined", "approved")
    assert not can_transition("voided", "approved")
    with pytest.raises(ValueError, match="unknown"):
        tx_status_of("weird")


def test_mask_normalisation_keeps_bin_in_memory_only() -> None:
    norm = normalize_mask("860031******1234")
    assert norm is not None and norm.mask == "8600********1234" and norm.bin == "860031"
    same = normalize_mask("8600****1234")
    assert same is not None and same.mask == "8600****1234" and same.bin is None
    assert normalize_mask("8600 31** **** 1234") is not None
    assert normalize_mask("8600123412341234") is None  # a full PAN is never accepted as a mask
    assert normalize_mask(None) is None


def test_card_type_source_order() -> None:
    assert derive_card_type("social", "corporate") == ("social", "terminal")
    assert derive_card_type(None, "corporate") == ("corporate", "bin_table")
    assert derive_card_type(None, None) == ("unknown", "bin_table")


def test_settlement_status_and_private_hosts() -> None:
    assert settlement_status(Decimal("700000"), Decimal("0"), Decimal("700000"), failed=False) == "matched"
    assert settlement_status(Decimal("650000"), Decimal("0"), Decimal("700000"), failed=False) == "mismatch"
    assert settlement_status(Decimal("0"), Decimal("0"), Decimal("1"), failed=True) == "failed"
    assert private_ipv4("192.168.1.10") and private_ipv4("10.0.0.5") and private_ipv4("172.20.1.1")
    assert not private_ipv4("8.8.8.8") and not private_ipv4("172.32.0.1") and not private_ipv4("example.com")


def test_card_result_schema_rules() -> None:
    attempt, terminal = uuid7(), uuid7()
    base = {"attempt_id": str(attempt), "card_terminal_id": str(terminal), "kind": "purchase",
            "status": "approved", "amount": "12000.00", "resolved_by": "auto",
            "rrn": "612345678901", "card_mask": "8600****1234"}  # fmt: skip
    assert parse_card_result(base).rrn == "612345678901"
    for bad in (
        base | {"card_mask": None},  # approved without a mask
        base | {"resolved_by": "manager"},  # manager with card details
        base | {"card_mask": "8600123412341234"},  # PAN-like value
        base | {"pan": "8600123412341234"},  # unknown field
        base | {"kind": "void"},  # void without original
        base | {"card_type_source": "cashier", "card_type": "personal"},
    ):
        with pytest.raises(AppError):
            parse_card_result(bad)


async def test_fake_adapter_table_and_idempotency() -> None:
    fake = FakeCardTerminalAdapter()
    terminal = uuid7()
    assert outcome_for(1_200_000) == "approved" and outcome_for(1_200_100) == "declined_51"
    assert outcome_for(1_200_200) == "timeout_then_approved" and outcome_for(1_200_400) == "busy"

    def req(amount: int, attempt: object = None) -> CardPurchaseRequest:
        return CardPurchaseRequest(
            attempt_id=attempt or uuid7(), terminal=TerminalRef(card_terminal_id=terminal), amount_tiyin=amount,
            cash_register_id=uuid7(), client_event_id=uuid7(),
        )  # fmt: skip

    r = req(1_200_000)
    first = await fake.purchase(r)
    assert first.status == "approved" and first.card_mask == "860031******1234"
    assert (await fake.purchase(r)).rrn == first.rrn and fake.calls["purchase"] == 1
    with pytest.raises(CardTerminalError):
        await fake.purchase(req(1_200_400))
    timeout = await fake.purchase(req(1_200_300))
    assert timeout.status == "timeout"
    assert (await fake.get_status(timeout.attempt_id)).status == "unknown"
    mapped = card_result_from_port(first, card_terminal_id=terminal, requested_amount_tiyin=1_200_000,
                                   resolved_by="auto")  # fmt: skip
    assert mapped["card_mask"] == "8600********1234" and "860031" not in str(mapped)
    fake.script("amount_mismatch")
    assert (await fake.purchase(req(1_200_000))).amount_tiyin == 1_100_000
    assert (await fake.health(TerminalRef(card_terminal_id=terminal))).status == "online"
