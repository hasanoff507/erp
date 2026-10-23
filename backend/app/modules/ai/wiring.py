"""AI module wiring: the only place a raw adapter is constructed (22 §1.1)."""

from __future__ import annotations

from app.core.config import Settings
from app.modules.ai.application.ports import RawAiProvider
from app.modules.ai.application.provider import MaskedAiProvider
from app.modules.ai.infrastructure.fake_provider import FakeAiProvider


def build_ai_provider(settings: Settings) -> MaskedAiProvider:
    """Pick the adapter by ``ai_mode``; the masking wrapper is not optional (qaror #61)."""
    raw: RawAiProvider
    if settings.ai_mode == "fake":
        raw = FakeAiProvider()
    else:
        # cli/api adapters come with the first AI feature; they must be wrapped too
        raise NotImplementedError(f"AI mode {settings.ai_mode!r} adapter is not implemented yet")
    return MaskedAiProvider(raw)
