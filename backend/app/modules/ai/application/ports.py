"""``AiProvider`` port (22 §1).

Raw adapters implement :class:`RawAiProvider`; the rest of the system only ever
gets a :class:`~app.modules.ai.application.provider.MaskedAiProvider`, which
puts the mandatory PII masking layer in front of every call (qaror #61).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, TypeVar
from uuid import UUID

from pydantic import BaseModel

ModelT = TypeVar("ModelT", bound=BaseModel)


class AiProviderUnavailable(Exception):  # noqa: N818 — name fixed by 22 §1
    """The provider failed; callers degrade to "AI temporarily unavailable" (22 §1)."""


@dataclass(frozen=True, slots=True)
class AiRequestContext:
    tenant_id: UUID
    user_id: UUID | None
    feature: str  # "AI-01", "AI-03", ...
    locale: str = "uz"
    # tenants.settings.ai_cross_border_enabled — gates images only (qaror #61)
    cross_border_enabled: bool = False


class RawAiProvider(Protocol):
    """Adapter contract. Receives only already-masked text."""

    async def complete(
        self, system: str, user: str, *, context: AiRequestContext, model: str | None = None
    ) -> str: ...

    async def complete_structured(
        self,
        system: str,
        user: str,
        schema: type[ModelT],
        *,
        context: AiRequestContext,
        model: str | None = None,
    ) -> ModelT: ...

    async def vision_extract(
        self,
        image: bytes,
        schema: type[ModelT],
        instructions: str,
        *,
        context: AiRequestContext,
        model: str | None = None,
    ) -> ModelT: ...
