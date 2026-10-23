"""Contract 5 (``.claude-scratch/b5/contracts/edocs.md``): hooks other modules call inside their own posting
transaction, and the e-document counts for BO-02 / period readiness."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.integrations.einvoice.application.einvoices import draft_for_credit_sale
from app.modules.integrations.einvoice.application.records import EDocsRepository


class EInvoiceHooksPort(Protocol):
    async def on_b2b_credit_sale_posted(
        self, s: AsyncSession, tenant_id: UUID, sale_id: UUID
    ) -> UUID | None: ...


class EInvoiceHooks:
    def __init__(self, repo: EDocsRepository) -> None:
        self._repo = repo

    async def on_b2b_credit_sale_posted(self, s: AsyncSession, tenant_id: UUID, sale_id: UUID) -> UUID | None:
        """US-M01-06: an outgoing ``draft`` for a posted credit sale to a company (13 §2.24, no posting)."""
        return await draft_for_credit_sale(self._repo, s, tenant_id, sale_id)

    async def alerts(self, s: AsyncSession) -> dict[str, int]:
        return await self._repo.alerts(s)
