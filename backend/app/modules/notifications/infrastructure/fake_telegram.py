"""In-process Telegram fake (local/test/staging only — ``ERP_TELEGRAM_FAKE``, refused in prod; qaror #34).

Records every message instead of calling the Bot API; the text goes to the structured log
(``dev_telegram_message``) so a developer sees what would have been sent. Test hooks: ``fail_with`` (every
call returns that failure class), ``blocked_chats`` (those chats answer ``blocked`` — the user blocked the
bot).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import structlog

from app.modules.notifications.application.ports import ErrorKind, TelegramSendResult

log = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class SentMessage:
    chat_id: str
    text: str


@dataclass(slots=True)
class FakeTelegram:
    sent: list[SentMessage] = field(default_factory=list)
    fail_with: ErrorKind | None = None
    retry_after_s: int | None = None
    blocked_chats: set[str] = field(default_factory=set)
    calls: int = 0

    async def send_message(self, chat_id: str, text: str) -> TelegramSendResult:
        self.calls += 1
        if self.fail_with is not None:
            return TelegramSendResult(False, self.fail_with, "fake failure", self.retry_after_s)
        if chat_id in self.blocked_chats:
            return TelegramSendResult(False, "blocked", "Forbidden: bot was blocked by the user")
        self.sent.append(SentMessage(chat_id, text))
        log.warning("dev_telegram_message", chat_id=chat_id, dev_text=text)
        return TelegramSendResult(True)

    def to(self, chat_id: str) -> list[str]:
        return [m.text for m in self.sent if m.chat_id == chat_id]
