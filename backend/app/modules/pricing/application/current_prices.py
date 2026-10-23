"""Current retail price of a page of products (19 §1 ``current_price``, §4 resolution rules).

Used by the catalog list (``GET /products``) inside the caller's ``tenant_transaction`` — one
batched query per page, never one per product.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import BranchScope
from app.modules.pricing.application.ports import PricingRepository


class CurrentPriceReader:
    def __init__(self, repo: PricingRepository) -> None:
        self._repo = repo

    async def branch_for(self, s: AsyncSession, scope: BranchScope) -> UUID | None:
        """``X-Branch-Id``; else the default branch (all-branch users) or the user's only branch;
        otherwise ``None`` — global prices only (same choice as the price-change doc branch, 19 §4)."""
        if scope.current is not None:
            return scope.current
        if scope.unrestricted:
            return await self._repo.default_branch_id(s)
        if len(scope.allowed) == 1:
            return scope.allowed[0]
        return None

    async def __call__(
        self, s: AsyncSession, product_ids: Sequence[UUID], scope: BranchScope
    ) -> dict[UUID, Decimal]:
        if not product_ids:
            return {}
        branch_id = await self.branch_for(s, scope)
        return await self._repo.current_prices(s, product_ids, branch_id, datetime.now(UTC))
