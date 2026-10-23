"""Current Terms of Use / consent text versions (qaror #61, 12 ``platform.terms_versions``).

The signup form (07 BO-21 ②) and BO-14 must send the *current* version back
(``/auth/signup``, ``POST /tenant/consents``), so the SPA reads it here first.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True, slots=True)
class TermsVersion:
    kind: str
    version: str
    text_url: str
    text_sha256: str
    effective_from: datetime


class TermsReader(Protocol):
    async def current(self, session: AsyncSession) -> list[TermsVersion]: ...


async def current_terms(reader: TermsReader, session: AsyncSession) -> list[TermsVersion]:
    """Every ``is_current`` row, one per kind (``terms``, ``privacy``, ``ai_cross_border``)."""
    return sorted(await reader.current(session), key=lambda t: t.kind)
