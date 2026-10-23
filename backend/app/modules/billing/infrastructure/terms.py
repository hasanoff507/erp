"""SQL for ``platform.terms_versions`` (global table, ``erp_app`` has SELECT only — 12 §4.4)."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.billing.application.terms import TermsVersion

_CURRENT = text(
    "SELECT kind, version, text_url, text_sha256, effective_from FROM platform.terms_versions "
    "WHERE is_current ORDER BY kind"
)


class SqlTermsReader:
    async def current(self, session: AsyncSession) -> list[TermsVersion]:
        rows = await session.execute(_CURRENT)
        return [TermsVersion(r[0], r[1], r[2], r[3], r[4]) for r in rows]
