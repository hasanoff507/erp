"""Deterministic test/CI adapter (22 §1.1). Records exactly what it was sent."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.modules.ai.application.ports import AiRequestContext, ModelT


@dataclass
class FakeAiProvider:
    reply: str = "OK"
    structured_reply: dict[str, Any] = field(default_factory=dict)
    sent: list[dict[str, Any]] = field(default_factory=list)

    async def complete(
        self, system: str, user: str, *, context: AiRequestContext, model: str | None = None
    ) -> str:
        self.sent.append({"method": "complete", "system": system, "user": user, "feature": context.feature})
        return self.reply

    async def complete_structured(
        self,
        system: str,
        user: str,
        schema: type[ModelT],
        *,
        context: AiRequestContext,
        model: str | None = None,
    ) -> ModelT:
        self.sent.append({"method": "complete_structured", "system": system, "user": user})
        return schema.model_validate(self.structured_reply)

    async def vision_extract(
        self,
        image: bytes,
        schema: type[ModelT],
        instructions: str,
        *,
        context: AiRequestContext,
        model: str | None = None,
    ) -> ModelT:
        self.sent.append(
            {"method": "vision_extract", "instructions": instructions, "image_bytes": len(image)}
        )
        return schema.model_validate(self.structured_reply)
