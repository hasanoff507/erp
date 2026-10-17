"""Telegram linking (US-M18-01, 20 #66–#68, 15 §1.4, 21 §11).

* ``link-start`` — a one-time ``link_code`` (``secrets``, 22 chars, TTL 10 min — qaror #54) for the caller;
  the deep link ``https://t.me/<bot>?start=<code>`` opens the bot. A new code replaces the user's previous
  one.
* the bot webhook — ``/start <code>``: the code is taken atomically (single use), the membership and
  ``telegram.link`` are re-checked, ``telegram_links (tenant_id, user_id) ← chat_id`` is written and audited
  (``telegram_linked``) in one tenant transaction. The reply goes back in the webhook response itself.
* status / unlink (``revoked_at = now()``; audit ``telegram_unlinked``).

A blocked user's link is revoked by the auth module through :func:`revoke_user_links` (QT-M18-05), and the
sender re-checks the membership before each message anyway.
"""

from __future__ import annotations

import secrets
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.audit import record_audit
from app.core.auth.principal import Principal
from app.core.db.session import tenant_transaction
from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from app.core.idempotency import stage_response
from app.modules.notifications.application.ports import LinkCodeStore, LinkGrant, NotificationRepository
from app.modules.notifications.domain.policy import LINK_CODE
from app.modules.notifications.domain.render import help_text, lang_of, link_failed_text, linked_text

log = structlog.get_logger(__name__)

UPDATE_DEDUPE_TTL_S = 86_400  # Telegram re-delivers an unanswered update for up to 24 h


@dataclass(frozen=True, slots=True)
class LinkStarted:
    link_code: str
    bot_url: str
    expires_at: datetime

    def as_json(self) -> dict[str, Any]:
        return {
            "link_code": self.link_code,
            "bot_url": self.bot_url,
            "expires_at": self.expires_at.isoformat(),
        }


def _ts(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


class TelegramLinkService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        repo: NotificationRepository,
        codes: LinkCodeStore,
        *,
        bot_username: str,
        code_ttl_s: int,
    ) -> None:
        self._sf = session_factory
        self._repo = repo
        self._codes = codes
        self._bot = bot_username.lstrip("@")
        self._ttl = code_ttl_s

    # --- REST ---------------------------------------------------------------------------------------
    async def start(self, actor: Principal) -> LinkStarted:
        code = secrets.token_urlsafe(16)  # 22 chars of [A-Za-z0-9_-]
        await self._codes.put(code, LinkGrant(actor.tenant_id, actor.user_id), self._ttl)
        started = LinkStarted(
            code, f"https://t.me/{self._bot}?start={code}", datetime.now(UTC) + timedelta(seconds=self._ttl)
        )
        stage_response(started.as_json(), 201)  # journalled after the response (no DB write here)
        return started

    async def status(self, actor: Principal) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            row = await self._repo.get_link(s, actor.tenant_id, actor.user_id)
        if row is None or row.revoked_at is not None:
            return {"linked": False, "chat_id": None, "linked_at": None}
        return {"linked": True, "chat_id": row.chat_id, "linked_at": _ts(row.linked_at)}

    async def unlink(self, actor: Principal, ip: str | None) -> None:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            if not await self._repo.revoke_link(s, actor.tenant_id, actor.user_id):
                raise AppError(ErrorCode.NOT_FOUND)
            await record_audit(
                s, tenant_id=actor.tenant_id, user_id=actor.user_id, action="telegram_unlinked",
                entity="telegram_links", entity_id=actor.user_id, ip=ip,
            )  # fmt: skip
            stage_response(None, 204)

    # --- webhook ------------------------------------------------------------------------------------
    async def handle_update(self, update: Mapping[str, Any]) -> dict[str, Any]:
        """One Telegram ``Update``; returns the webhook reply (a ``sendMessage`` call or ``{}``)."""
        update_id = update.get("update_id")
        if isinstance(update_id, int) and await self._codes.seen_update(update_id, UPDATE_DEDUPE_TTL_S):
            return {}
        try:
            return await self._handle(update)
        except Exception:
            if isinstance(update_id, int):  # let Telegram's re-delivery be processed
                await self._codes.forget_update(update_id)
            raise

    async def _handle(self, update: Mapping[str, Any]) -> dict[str, Any]:
        message = update.get("message")
        if not isinstance(message, Mapping):
            return {}  # edited messages, my_chat_member, … — nothing to do
        chat = message.get("chat")
        sender = message.get("from")
        text = message.get("text")
        if not isinstance(chat, Mapping) or chat.get("type") != "private" or not isinstance(text, str):
            return {}  # links only from a private chat with the user himself
        chat_id = str(chat.get("id"))
        lang = lang_of(sender.get("language_code") if isinstance(sender, Mapping) else None)
        command, _, argument = text.strip().partition(" ")
        if command.split("@", 1)[0] != "/start" or not argument.strip():
            return _reply(chat_id, help_text(lang))
        return _reply(chat_id, await self._bind(argument.strip(), chat_id, lang))

    async def _bind(self, code: str, chat_id: str, lang: str) -> str:
        if not LINK_CODE.match(code):
            return link_failed_text(lang)
        grant = await self._codes.take(code)
        if grant is None:
            return link_failed_text(lang)
        async with self._sf() as s, tenant_transaction(s, grant.tenant_id, user_id=grant.user_id):
            if not await self._repo.member_can_link(s, grant.tenant_id, grant.user_id):
                log.info("telegram_link_refused", reason="membership_or_permission")
                return link_failed_text(lang)
            await self._repo.upsert_link(s, grant.tenant_id, grant.user_id, chat_id)
            await record_audit(
                s, tenant_id=grant.tenant_id, user_id=grant.user_id, action="telegram_linked",
                entity="telegram_links", entity_id=grant.user_id, after={"chat_id": chat_id},
            )  # fmt: skip
            tenant_name, user_name, locale = await self._repo.names(s, grant.tenant_id, grant.user_id)
        return linked_text(tenant_name, user_name, lang_of(locale))


def _reply(chat_id: str, text: str) -> dict[str, Any]:
    """Telegram accepts a Bot API call as the webhook response body — no outbound request needed."""
    return {"method": "sendMessage", "chat_id": chat_id, "text": text}


async def revoke_user_links(
    repo: NotificationRepository, s: AsyncSession, tenant_id: UUID, user_id: UUID
) -> bool:
    """QT-M18-05: the user was blocked/removed — revoke the Telegram link in the caller's transaction."""
    return await repo.revoke_link(s, tenant_id, user_id)
