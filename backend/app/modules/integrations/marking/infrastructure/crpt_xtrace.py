"""``CrptXtraceAdapter`` — the real CRPT Turon (xTrace Open API) adapter — ⛔ 26 #40 (OQ-025).

The xTrace Open API v1.45.0 exists (bearer key from the tenant's CRPT cabinet; operations: code info
``public/api/cod/private/codes`` / ``/public/codes``, counterparty check, transfer, aggregation — 21 §4), but
there is no public Swagger, no test environment, and the verify method, the ``label`` format, the write-off
method and the SaaS integrator key are still open (Xat 2, 26 #40). No wire protocol is invented here: every
call answers ``MarkingProviderError(kind='transient')`` ("CRPT did not answer") —
``POST /marking-codes/verify``
then follows ``MARKING_PRECHECK`` (``warn`` → sale continues, ``block`` → 503) and the notices wait in the
outbox. The contract tests (``tests/integration/test_marking_contract.py``) run against this adapter once it
is implemented (``ERP_TEST_CRPT_API_KEY``).
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from app.modules.integrations.marking.application.ports import (
    MarkingAcceptResult,
    MarkingProviderError,
    MarkingResult,
    MarkingVerifyResult,
)

BLOCKED = "CRPT Turon xTrace adapter is not available yet (26 #40)"


class CrptXtraceAdapter:
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key  # bearer key of the tenant's CRPT cabinet (21 §4); host/paths — 26 #40

    async def verify_code(self, code: str) -> MarkingVerifyResult:
        raise MarkingProviderError(BLOCKED)

    async def accept(self, codes: Sequence[str], receipt_id: UUID) -> MarkingAcceptResult:
        raise MarkingProviderError(BLOCKED)

    async def supplier_return(self, codes: Sequence[str], return_id: UUID) -> MarkingResult:
        raise MarkingProviderError(BLOCKED)

    async def write_off(self, codes: Sequence[str], write_off_id: UUID) -> MarkingResult:
        raise MarkingProviderError(BLOCKED)
