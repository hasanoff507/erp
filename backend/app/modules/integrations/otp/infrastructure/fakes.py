"""Recording Telegram/SMS fakes — local development only (qaror #34, 27 Bosqich 1).

Enabled only by ``ERP_OTP_DEV_FAKES=true``; ``Settings`` refuses that flag in staging/prod. Nothing
leaves the process: messages are kept in memory (``FakeOutbox``) and the developer reads the code
from the structured log (``dev_otp_message``).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import structlog

log = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class FakeMessage:
    channel: str
    destination: str
    text: str


@dataclass(slots=True)
class FakeOutbox:
    messages: list[FakeMessage] = field(default_factory=list)

    def last_to(self, destination: str) -> FakeMessage | None:
        for message in reversed(self.messages):
            if message.destination == destination:
                return message
        return None


class FakeSender:
    def __init__(self, channel: str, outbox: FakeOutbox, *, fail: bool = False) -> None:
        self._channel = channel
        self._outbox = outbox
        self.fail = fail

    async def send(self, destination: str, text: str) -> bool:
        if self.fail:
            return False
        self._outbox.messages.append(FakeMessage(self._channel, destination, text))
        log.warning("dev_otp_message", channel=self._channel, dev_text=text)
        return True
