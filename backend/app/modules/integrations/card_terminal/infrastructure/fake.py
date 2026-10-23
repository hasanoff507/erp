"""``FakeCardTerminalAdapter`` (21 §9.4; dev/test/staging and the agent emulator — never real money).

Deterministic by the last three digits of the amount in so'm (``amount_tiyin // 100 % 1000``) — the table of
24 §6.5, implemented identically by the web ``FakeCardTerminalClient``
(``web/packages/shared/lib/src/card-terminal/fake.ts``):

=======  ==============================================================================
other    approved (raw mask ``860031******1234`` — BIN ``860031``, ``uzcard``, no ``card_type``)
``001``  declined ``51`` "Mablag' yetarli emas"
``002``  timeout; ``get_status`` → approved
``003``  timeout; ``get_status`` / ``get_last_transaction`` give nothing (manager closes it)
``004``  busy (``CardTerminalError('CARD_TERMINAL_BUSY')``, nothing recorded)
``005``  approved for 1 000.00 so'm less (→ ``CARD_AMOUNT_MISMATCH``, auto ``void``)
``006``  approved, but a later ``void`` of it fails (``CARD_VOID_FAILED``)
``007``  cancelled on the terminal
``008``  terminal error
``009``  approved, the terminal reports ``card_type='social'``
``010``  timeout; ``get_status`` → not found (``declined``, ``decline_code='not_found'``)
``011``  declined ``05`` "Rad etildi"
=======  ==============================================================================

Tests can override the next purchase with :meth:`script`. The same ``attempt_id`` returns the journalled
result without touching the "terminal" again (``calls`` counts terminal hits). PAN/track/CVV never exist here.
"""

from __future__ import annotations

import hashlib
from collections import Counter, deque
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from app.modules.integrations.card_terminal.application.ports import (
    CardPurchaseRequest,
    CardRefundRequest,
    CardTerminalError,
    CardTxResult,
    CardVoidRequest,
    SchemeTotal,
    SettlementResult,
    TerminalHealth,
    TerminalRef,
)

Outcome = Literal[
    "approved", "approved_social", "amount_mismatch", "declined_51", "declined_05", "cancelled", "error",
    "busy", "timeout_then_approved", "timeout_then_not_found", "timeout_unresolved", "approved_void_fails",
]  # fmt: skip
BY_ENDING: dict[int, Outcome] = {
    1: "declined_51", 2: "timeout_then_approved", 3: "timeout_unresolved", 4: "busy", 5: "amount_mismatch",
    6: "approved_void_fails", 7: "cancelled", 8: "error", 9: "approved_social", 10: "timeout_then_not_found",
    11: "declined_05",
}  # fmt: skip
TID = "T0000001"
MID = "M000000000001"
RAW_MASK = "860031******1234"


def outcome_for(amount_tiyin: int) -> Outcome:
    return BY_ENDING.get(amount_tiyin // 100 % 1000, "approved")


def _rrn(attempt_id: UUID) -> str:
    return f"{attempt_id.int % 10**12:012d}"


def _approval_code(attempt_id: UUID) -> str:
    return hashlib.sha256(attempt_id.bytes).hexdigest()[:6].upper()


@dataclass
class _Journal:
    result: CardTxResult
    status_answer: CardTxResult | None  # what get_status returns while the journal says "unknown"
    void_fails: bool = False


class FakeCardTerminalAdapter:
    def __init__(self) -> None:
        self.calls: Counter[str] = Counter()
        self.health_status: Literal["online", "busy", "offline", "error"] = "online"
        self.settlement_skew_tiyin = 0
        self._script: deque[Outcome] = deque()
        self._journal: dict[UUID, _Journal] = {}
        self._last: CardTxResult | None = None
        self._batch: list[CardTxResult] = []
        self._batch_no = 0

    def script(self, *outcomes: Outcome) -> None:
        """Force the outcomes of the next purchases (FIFO), overriding the amount table."""
        self._script.extend(outcomes)

    def _approved(
        self, req_id: UUID, kind: Literal["purchase", "refund", "void"], amount: int
    ) -> CardTxResult:
        return CardTxResult(
            attempt_id=req_id, kind=kind, status="approved", amount_tiyin=amount,
            approval_code=_approval_code(req_id), rrn=_rrn(req_id), stan=f"{req_id.int % 10**6:06d}",
            card_mask=RAW_MASK, card_scheme="uzcard", entry_mode="contactless", tid=TID, mid=MID,
            acquirer="FAKEBANK", tx_at=datetime.now(UTC),
        )  # fmt: skip

    async def purchase(self, req: CardPurchaseRequest) -> CardTxResult:
        if req.attempt_id in self._journal:  # idempotent replay: no second terminal hit
            return self._journal[req.attempt_id].result
        outcome = self._script.popleft() if self._script else outcome_for(req.amount_tiyin)
        if outcome == "busy":
            raise CardTerminalError("CARD_TERMINAL_BUSY")
        self.calls["purchase"] += 1
        approved = self._approved(req.attempt_id, "purchase", req.amount_tiyin)
        status_answer: CardTxResult | None = None
        void_fails = False
        if outcome in ("approved", "approved_void_fails"):
            result = approved
            void_fails = outcome == "approved_void_fails"
        elif outcome == "approved_social":
            result = approved.model_copy(update={"card_type": "social"})
        elif outcome == "amount_mismatch":
            result = approved.model_copy(update={"amount_tiyin": req.amount_tiyin - 100_000})
        elif outcome in ("declined_51", "declined_05"):
            code = outcome[-2:]
            message = "Mablag' yetarli emas" if code == "51" else "Rad etildi"
            result = CardTxResult(
                attempt_id=req.attempt_id, kind="purchase", status="declined", amount_tiyin=req.amount_tiyin,
                decline_code=code, decline_message=message, tid=TID, card_scheme="uzcard",
            )  # fmt: skip
        elif outcome in ("cancelled", "error"):
            result = CardTxResult(
                attempt_id=req.attempt_id,
                kind="purchase",
                status=outcome,
                amount_tiyin=req.amount_tiyin,
                tid=TID,
            )
        else:  # timeouts
            result = CardTxResult(attempt_id=req.attempt_id, kind="purchase", status="timeout", tid=TID)
            if outcome == "timeout_then_approved":
                status_answer = approved
            elif outcome == "timeout_then_not_found":
                status_answer = CardTxResult(
                    attempt_id=req.attempt_id,
                    kind="purchase",
                    status="declined",
                    decline_code="not_found",
                    tid=TID,
                )
        self._journal[req.attempt_id] = _Journal(result, status_answer, void_fails)
        if result.status == "approved":
            self._last = result
            self._batch.append(result)
        elif status_answer is not None and status_answer.status == "approved":
            self._last = status_answer
            self._batch.append(status_answer)
        return result

    async def get_status(self, attempt_id: UUID) -> CardTxResult:
        self.calls["get_status"] += 1
        entry = self._journal.get(attempt_id)
        if entry is None:
            return CardTxResult(
                attempt_id=attempt_id, kind="purchase", status="declined", decline_code="not_found"
            )
        if entry.result.status == "timeout":
            if entry.status_answer is None:
                return CardTxResult(attempt_id=attempt_id, kind=entry.result.kind, status="unknown")
            return entry.status_answer
        return entry.result

    async def get_last_transaction(self, terminal: TerminalRef) -> CardTxResult | None:
        self.calls["get_last_transaction"] += 1
        return self._last

    async def void(self, req: CardVoidRequest) -> CardTxResult:
        if req.attempt_id in self._journal:
            return self._journal[req.attempt_id].result
        self.calls["void"] += 1
        original = self._journal.get(req.original_attempt_id)
        if original is None or original.void_fails:
            result = CardTxResult(
                attempt_id=req.attempt_id, kind="void", status="declined", amount_tiyin=req.amount_tiyin,
                decline_code="void_failed", decline_message="Bekor qilib bo'lmadi", tid=TID,
            )  # fmt: skip
        else:
            result = self._approved(req.attempt_id, "void", req.amount_tiyin).model_copy(
                update={"card_mask": None, "card_scheme": None}
            )
            self._batch = [r for r in self._batch if r.attempt_id != req.original_attempt_id]
        self._journal[req.attempt_id] = _Journal(result, None)
        return result

    async def refund(self, req: CardRefundRequest) -> CardTxResult:
        if req.attempt_id in self._journal:
            return self._journal[req.attempt_id].result
        self.calls["refund"] += 1
        result = self._approved(req.attempt_id, "refund", req.amount_tiyin)
        self._journal[req.attempt_id] = _Journal(result, None)
        self._batch.append(result)
        return result

    async def settlement(self, terminal: TerminalRef) -> SettlementResult:
        self.calls["settlement"] += 1
        purchases = [r for r in self._batch if r.kind == "purchase"]
        refunds = [r for r in self._batch if r.kind == "refund"]
        p_total = sum(r.amount_tiyin or 0 for r in purchases) + self.settlement_skew_tiyin
        r_total = sum(r.amount_tiyin or 0 for r in refunds)
        self._batch_no += 1
        self._batch = []
        return SettlementResult(
            tid=TID, batch_no=f"{self._batch_no:06d}", count=len(purchases), total_tiyin=p_total,
            by_scheme=[SchemeTotal(card_scheme="uzcard", count=len(purchases), total_tiyin=max(p_total, 0))],
            settled_at=datetime.now(UTC), refund_count=len(refunds), refund_total_tiyin=r_total,
        )  # fmt: skip

    async def health(self, terminal: TerminalRef) -> TerminalHealth:
        self.calls["health"] += 1
        return TerminalHealth(
            status=self.health_status, tid=TID, last_tx_at=None if self._last is None else self._last.tx_at
        )
