"""Display data of ``GET /auth/session`` (14 §20, 06 §1.9, BO-01/BO-02).

The endpoint is also the ~30 s heartbeat (14 §16.1.4), so the profile part is
cached in Redis per (tenant, user) for ``PROFILE_CACHE_S``. The cached
``permissions`` only hide buttons in the UI; every request is still authorized
by ``require_permission`` against the live database.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Final
from uuid import UUID

import structlog
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.modules.auth.application.ports import AuthStore

log = structlog.get_logger(__name__)

PROFILE_CACHE_S: Final = 60
_UZ_PHONE: Final = re.compile(r"^\+998(\d{2})\d{5}(\d{2})$")


def mask_phone(phone: str) -> str:
    """``+998901234567`` → ``+998 90 *** ** 67`` (operator code and the last two digits)."""
    m = _UZ_PHONE.match(phone)
    if m:
        return f"+998 {m.group(1)} *** ** {m.group(2)}"
    return f"*** {phone[-2:]}" if len(phone) >= 2 else "***"


@dataclass(frozen=True, slots=True)
class BranchView:
    id: str
    name: str


@dataclass(frozen=True, slots=True)
class SessionProfile:
    user_id: str
    full_name: str
    phone_masked: str
    tenant_id: str
    tenant_name: str
    branches: tuple[BranchView, ...]
    roles: tuple[str, ...]
    permissions: tuple[str, ...]


class SessionProfileService:
    def __init__(self, repo: AuthStore, redis: Callable[[], Redis]) -> None:
        self._repo = repo
        self._redis = redis

    @staticmethod
    def _key(tenant_id: UUID, user_id: UUID) -> str:
        return f"auth:profile:{tenant_id}:{user_id}"

    async def profile(self, tenant_id: UUID, user_id: UUID) -> SessionProfile | None:
        """``None`` when the user has no active membership in the tenant."""
        key = self._key(tenant_id, user_id)
        try:
            raw = await self._redis().get(key)
        except RedisError:
            log.warning("session_profile_cache_unavailable")
            raw = None
        if raw:
            data = json.loads(raw)
            data["branches"] = tuple(BranchView(**b) for b in data["branches"])
            data["roles"] = tuple(data["roles"])
            data["permissions"] = tuple(data["permissions"])
            return SessionProfile(**data)

        row = await self._repo.session_profile(tenant_id, user_id)
        if row is None or row.membership.status != "active":
            return None
        profile = SessionProfile(
            user_id=str(user_id),
            full_name=row.full_name,
            phone_masked=mask_phone(row.phone),
            tenant_id=str(tenant_id),
            tenant_name=row.tenant_name,
            branches=tuple(BranchView(str(b.branch_id), b.name) for b in row.branches),
            roles=row.membership.role_codes,
            permissions=tuple(sorted(row.membership.permission_codes)),
        )
        try:
            await self._redis().set(key, json.dumps(asdict(profile)), ex=PROFILE_CACHE_S)
        except RedisError:
            log.warning("session_profile_cache_unavailable")
        return profile

    async def forget(self, tenant_id: UUID, user_id: UUID) -> None:
        try:
            await self._redis().delete(self._key(tenant_id, user_id))
        except RedisError:
            log.warning("session_profile_cache_unavailable")
