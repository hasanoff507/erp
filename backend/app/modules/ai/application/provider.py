"""The only ``AiProvider`` the application gets (22 §1, §7; qaror #61).

``MaskedAiProvider`` wraps a raw adapter; every prompt is masked before it is
handed over and every answer is unmasked on the way back. The composition root
(:func:`app.modules.ai.wiring.build_ai_provider`) always returns the wrapped
provider — there is no configuration that returns a raw adapter.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from typing import Any

from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from app.modules.ai.application.ports import AiRequestContext, ModelT, RawAiProvider
from app.modules.ai.privacy.masking import PiiMasker, PiiValue, TokenGlossary


class MaskedAiProvider:
    def __init__(
        self, raw: RawAiProvider, glossary_factory: Callable[[], TokenGlossary] | None = None
    ) -> None:
        self._raw = raw
        self._glossary_factory = glossary_factory

    def _masker(self, pii: Iterable[PiiValue]) -> PiiMasker:
        masker = PiiMasker(self._glossary_factory() if self._glossary_factory else None)
        masker.register_all(pii)
        return masker

    async def complete(
        self,
        system: str,
        user: str,
        *,
        context: AiRequestContext,
        pii: Iterable[PiiValue] = (),
        tool_results: Any = None,
        model: str | None = None,
    ) -> str:
        masker = self._masker(pii)
        prompt = _with_tool_results(masker, user, tool_results)
        answer = await self._raw.complete(masker.mask_text(system), prompt, context=context, model=model)
        return masker.unmask_text(answer)

    async def complete_structured(
        self,
        system: str,
        user: str,
        schema: type[ModelT],
        *,
        context: AiRequestContext,
        pii: Iterable[PiiValue] = (),
        tool_results: Any = None,
        model: str | None = None,
    ) -> ModelT:
        masker = self._masker(pii)
        prompt = _with_tool_results(masker, user, tool_results)
        result = await self._raw.complete_structured(
            masker.mask_text(system), prompt, schema, context=context, model=model
        )
        return schema.model_validate(masker.unmask_payload(result.model_dump(mode="json")))

    async def vision_extract(
        self,
        image: bytes,
        schema: type[ModelT],
        instructions: str,
        *,
        context: AiRequestContext,
        model: str | None = None,
    ) -> ModelT:
        # images cannot be masked: sent only with the tenant's cross-border consent (qaror #61)
        if not context.cross_border_enabled:
            raise AppError(ErrorCode.AI_CONSENT_REQUIRED)
        masker = self._masker(())
        result = await self._raw.vision_extract(
            image, schema, masker.mask_text(instructions), context=context, model=model
        )
        return result


def _with_tool_results(masker: PiiMasker, user: str, tool_results: Any) -> str:
    # tool results first: their PII keys register values that may also appear in the question
    masked_results = masker.mask_payload(tool_results) if tool_results is not None else None
    prompt = masker.mask_text(user)
    if masked_results is None:
        return prompt
    return f"{prompt}\n\n<tool_results>\n{json.dumps(masked_results, ensure_ascii=False)}\n</tool_results>"
