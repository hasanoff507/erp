"""FM emulator (21 §1, 27 B5-T02 "FM emulyatori CI'da"; MVP/CI code — never in prod).

One :class:`FmEmulator` models what a fiscal module does that matters to the server:

* signs every receipt — online or not (``online=False``: the FM signs, the OFD packet waits); the result
  is **idempotent** per receipt key (a retried call returns the same ``fm_receipt_seq`` / ``fiscal_sign``);
* keeps the list of receipts not yet acknowledged by the OFD (``list_unsent``), sends them on
  ``resend_unsent`` when ``online`` (→ ``acked[]``), and reports ``fm_state`` / pending / oldest unacked;
* locks itself when the oldest unacked receipt is ≥ 48 h old at ``clock()`` (``fm_state='locked'``, FM side of
  qaror #43) or when ``state`` is forced (``locked`` / ``memory_full`` / ``ack_overdue``);
* opens/closes the FM shift (Z number per terminal).

Terminal id: ``ZZ`` + 12 digits (14 characters, the test FM prefix of 21 §1); fiscal sign — 12 digits;
QR — the ``ofd.soliq.uz/check`` format. Amounts arrive in **tiyin** (``int``) — the caller converts.
"""

from __future__ import annotations

import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from app.modules.integrations.fiscal.domain.rules import OFFLINE_BLOCK_HOURS, qr_url

FORCED_STATES = frozenset({"locked", "memory_full", "ack_overdue"})


def _now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


@dataclass
class Signed:
    terminal_id: str
    fm_receipt_seq: int
    fiscal_at: datetime
    fiscal_sign: str
    qr_url: str
    amount_tiyin: int
    acked_at: datetime | None = None


@dataclass
class FmEmulator:
    terminal_id: str
    online: bool = True
    state: str = "ok"  # ok | locked | memory_full | ack_overdue (forced); "ok" lets the 48 h rule decide
    clock: Callable[[], datetime] = _now
    receipts: dict[str, Signed] = field(default_factory=dict)  # idempotency key → signed receipt
    shift_open: bool = False
    z_number: int = 0
    _seq: int = field(default_factory=lambda: int(time.time() * 1000))

    # --- state ------------------------------------------------------------------------------------------
    def unsent(self) -> list[Signed]:
        return sorted(
            (r for r in self.receipts.values() if r.acked_at is None), key=lambda r: r.fm_receipt_seq
        )

    def fm_state(self) -> str:
        if self.state in FORCED_STATES:
            return self.state
        oldest = self.unsent()
        if oldest and self.clock() - oldest[0].fiscal_at >= timedelta(hours=OFFLINE_BLOCK_HOURS):
            return "locked"
        return "ok"

    def status(self) -> dict[str, Any]:
        pending = self.unsent()
        return {
            "fm_state": self.fm_state(),
            "pending_count": len(pending),
            "oldest_unacked_at": pending[0].fiscal_at if pending else None,
        }

    # --- operations -------------------------------------------------------------------------------------
    def sign(self, key: str, amount_tiyin: int) -> Signed:
        if not isinstance(amount_tiyin, int) or isinstance(amount_tiyin, bool):
            raise TypeError("the FM takes integer tiyin (qaror #26)")
        done = self.receipts.get(key)
        if done is not None:
            return done
        if self.fm_state() != "ok":
            raise PermissionError(f"FM {self.terminal_id} is {self.fm_state()}")
        at = self.clock()
        self._seq = max(self._seq + 1, int(time.time() * 1000))
        sign = f"{secrets.randbelow(10**12):012d}"
        signed = Signed(
            self.terminal_id,
            self._seq,
            at,
            sign,
            qr_url(self.terminal_id, self._seq, at, sign),
            amount_tiyin,
            at if self.online else None,
        )
        self.receipts[key] = signed
        return signed

    def resend(self) -> dict[str, Any]:
        """Send the unsent packets: online → every one acked now; offline → all fail."""
        pending = self.unsent()
        if not self.online:
            return {"sent": 0, "failed": len(pending), "acked": []}
        at = self.clock()
        for r in pending:
            r.acked_at = at
        acked = [
            {"fm_terminal_id": r.terminal_id, "fm_receipt_seq": r.fm_receipt_seq, "acked_at": at}
            for r in pending
        ]
        return {"sent": len(pending), "failed": 0, "acked": acked}

    def open_shift(self) -> datetime:
        self.shift_open = True
        return self.clock()

    def close_shift(self, totals: dict[str, Any] | None = None) -> dict[str, Any]:
        self.z_number += 1
        self.shift_open = False
        return {
            "fm_terminal_id": self.terminal_id,
            "z_number": self.z_number,
            "totals": totals or {"sale": 0, "return": 0, "by_payment_form": {}},
            "closed_at": self.clock(),
        }


def emulator_terminal_id(seed: int) -> str:
    return f"ZZ{seed % 10**12:012d}"
