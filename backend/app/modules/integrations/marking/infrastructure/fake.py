"""``FakeMarkingAdapter`` — CRPT Turon emulator for dev/CI (``ERP_MARKING_PROVIDER=fake``; refused in prod).

It understands real code structure through the GS1 parser (:mod:`..domain.gs1`): a value that is not an
Asl belgisi unit code (GTIN with a valid check digit + serial + crypto elements) is ``not_found``; a code
with an ``(17)`` expiry date in the past is ``expired``; everything else is ``in_stock``. Notices are
idempotent by document id (the same ``crpt_doc_id`` for a repeated call).

Test knobs (instance attributes, the process-wide instance is :func:`..wiring.fake_marking_adapter`):
``statuses`` — ``code → reason`` overrides of ``verify_code`` (``already_sold`` / ``expired`` / …);
``fail`` — ``None`` | ``"transient"`` | ``"auth"`` | ``"validation"`` (every call raises);
``delay_s`` — seconds every call sleeps first (the 3 s verify timeout); ``reject`` — codes CRPT refuses in a
notice; ``calls`` — ``(method, code-or-doc-id)`` log; :meth:`reset`.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta, timezone
from uuid import UUID

from app.modules.integrations.marking.application.ports import (
    MarkingAcceptResult,
    MarkingProviderError,
    MarkingResult,
    MarkingVerifyResult,
)
from app.modules.integrations.marking.domain.gs1 import Gs1Error, parse

_TASHKENT = timezone(timedelta(hours=5))


class FakeMarkingAdapter:
    def __init__(self) -> None:
        self.statuses: dict[str, str] = {}
        self.fail: str | None = None
        self.delay_s: float = 0.0
        self.reject: set[str] = set()
        self.calls: list[tuple[str, str]] = []
        self.today: datetime | None = None  # clock of the expiry check (None → now)

    def reset(self) -> None:
        self.__init__()  # type: ignore[misc]

    async def _enter(self, method: str, key: str) -> None:
        self.calls.append((method, key))
        if self.delay_s:
            await asyncio.sleep(self.delay_s)
        if self.fail is not None:
            kind = self.fail if self.fail in ("transient", "auth", "validation") else "transient"
            raise MarkingProviderError(f"fake CRPT: {self.fail}", kind=kind)  # type: ignore[arg-type]

    def _reason(self, code: str) -> tuple[str | None, str | None]:
        """``(reason or None, gtin)`` of one code."""
        if code in self.statuses:
            try:
                gtin = parse(code).gtin
            except Gs1Error:
                gtin = None
            return self.statuses[code], gtin
        try:
            parsed = parse(code)
        except Gs1Error:
            return "not_found", None
        if not parsed.is_marking_code:
            return "not_found", parsed.gtin
        expiry = parsed.expiry
        today = (self.today or datetime.now(UTC)).astimezone(_TASHKENT).date()
        if expiry is not None and expiry < today:
            return "expired", parsed.gtin
        return None, parsed.gtin

    async def verify_code(self, code: str) -> MarkingVerifyResult:
        await self._enter("verify_code", code)
        reason, gtin = self._reason(code)
        if reason is None:
            return MarkingVerifyResult(valid=True, status="in_stock", gtin=gtin)
        status = {
            "already_sold": "sold",
            "written_off": "written_off",
            "returned_to_supplier": "returned_to_supplier",
        }.get(reason, "unknown")
        return MarkingVerifyResult(valid=False, status=status, reason=reason, gtin=gtin)  # type: ignore[arg-type]

    def _refused(self, codes: Sequence[str]) -> tuple[str, ...]:
        return tuple(c for c in codes if c in self.reject or self._reason(c)[0] in ("not_found", "expired"))

    async def accept(self, codes: Sequence[str], receipt_id: UUID) -> MarkingAcceptResult:
        await self._enter("accept", str(receipt_id))
        bad = self._refused(codes)
        if bad:
            return MarkingAcceptResult("rejected", None, bad, "codes not acceptable")
        return MarkingAcceptResult("accepted", f"FAKE-ACC-{receipt_id.hex[-12:]}")

    async def supplier_return(self, codes: Sequence[str], return_id: UUID) -> MarkingResult:
        await self._enter("supplier_return", str(return_id))
        bad = self._refused(codes)
        if bad:
            return MarkingResult("rejected", None, bad, "codes not acceptable")
        return MarkingResult("accepted", f"FAKE-RET-{return_id.hex[-12:]}")

    async def write_off(self, codes: Sequence[str], write_off_id: UUID) -> MarkingResult:
        await self._enter("write_off", str(write_off_id))
        bad = self._refused(codes)
        if bad:
            return MarkingResult("rejected", None, bad, "codes not acceptable")
        return MarkingResult("accepted", f"FAKE-WO-{write_off_id.hex[-12:]}")
