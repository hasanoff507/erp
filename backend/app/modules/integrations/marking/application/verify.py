"""``POST /marking-codes/verify`` — the pre-sale code check (18 §15, 21 §4.1, qaror #62; US-M01-03).

Stores nothing about the code: (1) local checks in one read transaction — format (``MARKING_CODE_INVALID``,
the same rule as ``sale.created``) and "already sold in this tenant" (``marking_codes.status IN
('sold','pending_verification')`` → ``409 MARKING_CODE_ALREADY_SOLD``); (2) ``MarkingPort.verify_code`` with
``timeout=3s`` and no retry, outside any transaction; (3) the ``MARKING_PRECHECK`` decision:

* valid — ``200 {valid: true}`` in every mode;
* invalid — ``warn``: ``200 {valid: false, details.reason, warnings}`` + audit; ``block``:
  ``409 MARKING_VERIFY_FAILED``;
* no answer — ``warn``: ``200 {valid: null, warnings}`` + audit; ``block``:
  ``503 MARKING_VERIFY_UNAVAILABLE``.

The ``warn`` audit (``marking.precheck_failed``, 15 §6.1) is written in a second transaction together with the
Idempotency-Key journal row. A tenant without a CRPT key counts as "CRPT did not answer".
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.audit import record_audit
from app.core.auth.principal import Principal
from app.core.db.session import tenant_transaction
from app.core.error_codes import ErrorCode
from app.core.errors import AppError, ErrorDetail
from app.core.idempotency import stage_response
from app.modules.integrations.marking.application.ports import (
    MarkingPort,
    MarkingPortProvider,
    MarkingProviderError,
    MarkingVerifyResult,
)
from app.modules.integrations.marking.application.repository import MarkingRepository
from app.modules.integrations.marking.domain import rules
from app.modules.integrations.marking.domain.gs1 import Gs1Error, parse
from app.modules.sales.domain.calc import marking_code_valid

log = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class VerifyRequest:
    code: str
    product_id: UUID | None = None


class MarkingVerifyService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        repo: MarkingRepository,
        ports: MarkingPortProvider,
        *,
        timeout_s: float = 3.0,
    ) -> None:
        self._sf = session_factory
        self._repo = repo
        self._ports = ports
        self._timeout = timeout_s

    async def verify(self, actor: Principal, req: VerifyRequest) -> dict[str, Any]:
        device_id = actor.device_id
        if not marking_code_valid(req.code):
            raise AppError(ErrorCode.MARKING_CODE_INVALID, params={"line": "code"})
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            if req.product_id is not None:
                product = await self._repo.product(s, req.product_id)
                if product is None:
                    raise AppError(
                        ErrorCode.VALIDATION_ERROR,
                        details=[ErrorDetail(field="product_id", message_key="validation.not_found")],
                    )
                if not product.is_marked:
                    raise AppError(
                        ErrorCode.VALIDATION_ERROR,
                        details=[ErrorDetail(field="code", message_key="validation.marking_code_unexpected")],
                    )
            if await self._repo.code_taken(s, req.code):
                raise AppError(ErrorCode.MARKING_CODE_ALREADY_SOLD, params={"codes": [req.code]})
            mode = rules.mode_of(await self._repo.precheck_mode(s))
            port = await self._ports.for_tenant(s, actor.tenant_id)
        result = await self._call(port, req.code)
        valid = None if result is None else result.valid
        decision = rules.decide(mode, valid)
        reason = None if result is None or result.valid else (result.reason or "not_found")
        if decision.outcome == "fail":
            raise AppError(ErrorCode.MARKING_VERIFY_FAILED, params={"reason": reason})
        if decision.outcome == "unavailable":
            raise AppError(ErrorCode.MARKING_VERIFY_UNAVAILABLE)
        body = _body(req, result, warned=decision.outcome == "warn")
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            if decision.audit:
                await record_audit(
                    s,
                    tenant_id=actor.tenant_id,
                    user_id=actor.user_id,
                    action="marking.precheck_failed",
                    entity="marking_codes",
                    entity_id=None,
                    device_id=device_id,
                    after={
                        "code": req.code,
                        "valid": valid,
                        "reason": reason if valid is False else "timeout",
                        "mode": mode,
                        "product_id": str(req.product_id) if req.product_id else None,
                    },
                )
            stage_response(body, 200)
        return body

    async def _call(self, port: MarkingPort | None, code: str) -> MarkingVerifyResult | None:
        if port is None:
            return None
        try:
            return await asyncio.wait_for(port.verify_code(code), timeout=self._timeout)
        except TimeoutError:
            log.info("marking_verify_timeout")
            return None
        except MarkingProviderError as exc:
            log.warning("marking_verify_provider_error", kind=exc.kind)
            return None


def _body(req: VerifyRequest, result: MarkingVerifyResult | None, *, warned: bool) -> dict[str, Any]:
    try:
        parsed = parse(req.code)
        gtin, serial = parsed.gtin, parsed.serial
    except Gs1Error:
        gtin = serial = None
    details: dict[str, Any] = {"gtin": gtin, "serial": serial}
    if result is not None and not result.valid:
        details["reason"] = result.reason or "not_found"
    return {
        "valid": None if result is None else result.valid,
        "status": None if result is None else result.status,
        "details": details,
        "warnings": [rules.WARNING] if warned else [],
    }
