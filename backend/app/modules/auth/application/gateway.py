"""Resource Server: Bearer JWT or BFF cookie → :class:`Principal` (14 §2.1, §5; 23 §3 steps 2–3)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Final
from uuid import UUID

from starlette.requests import Request

from app.core.auth.principal import Principal
from app.core.auth.tokens import CsrfTokens, SessionCookieSigner
from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from app.modules.auth.application.bff import BffService
from app.modules.auth.application.keys import AccessTokenCodec, InvalidAccessTokenError
from app.modules.auth.application.revocation import RevocationCache, TokenRevokedError
from app.modules.auth.application.subscription import SubscriptionStatusService
from app.modules.auth.application.tokens import RequestMeta
from app.modules.auth.domain.constants import CSRF_HEADER, SID_COOKIE
from app.modules.auth.domain.scopes import scope_to_set
from app.modules.auth.infrastructure.repositories import AuthRepository

SAFE_METHODS: Final = frozenset({"GET", "HEAD", "OPTIONS"})
_BEARER_CHALLENGE: Final = {"WWW-Authenticate": 'Bearer error="invalid_token"'}


def request_meta(request: Request) -> RequestMeta:
    ip = request.client.host if request.client else None
    return RequestMeta(ip=ip, user_agent=(request.headers.get("user-agent") or "")[:512] or None)


def _uuid(value: Any) -> UUID | None:
    try:
        return UUID(str(value)) if value else None
    except ValueError:
        return None


class ErpAuthGateway:
    def __init__(
        self,
        *,
        codec: AccessTokenCodec,
        revocation: RevocationCache,
        subscriptions: SubscriptionStatusService,
        repo: AuthRepository,
        bff: BffService,
        cookies: SessionCookieSigner,
        csrf: CsrfTokens,
    ) -> None:
        self._codec = codec
        self._revocation = revocation
        self._subs = subscriptions
        self._repo = repo
        self._bff = bff
        self._cookies = cookies
        self._csrf = csrf

    async def authenticate(self, request: Request) -> Principal:
        header = request.headers.get("authorization")
        if header is not None:
            scheme, _, token = header.partition(" ")
            if scheme.lower() != "bearer" or not token.strip():
                raise AppError(ErrorCode.UNAUTHORIZED, headers=_BEARER_CHALLENGE)
            claims = await self._verify(token.strip(), bearer=True)
            return self._principal(claims, via_cookie=False)

        sid = self._cookies.unsign(request.cookies.get(SID_COOKIE))
        if sid is None:
            raise AppError(ErrorCode.UNAUTHORIZED)
        # 15 §1.3 / 23 §3 step 2: CSRF before anything else on cookie-authenticated writes
        if request.method not in SAFE_METHODS and not self._csrf.verify(
            request.headers.get(CSRF_HEADER), sid
        ):
            raise AppError(ErrorCode.CSRF_INVALID)
        session = await self._bff.fresh_session(sid, request_meta(request))
        if session is None:
            raise AppError(ErrorCode.UNAUTHORIZED)
        claims = await self._verify(session.access_token, bearer=False)
        if claims.get("sid") != str(sid):
            raise AppError(ErrorCode.UNAUTHORIZED)
        return self._principal(claims, via_cookie=True)

    async def peek_tenant(self, request: Request) -> UUID | None:
        """Idempotency tenant (23 §3): a revoked token/session gets no replay — it falls through to 401."""
        try:
            header = request.headers.get("authorization")
            if header is not None:
                scheme, _, token = header.partition(" ")
                if scheme.lower() != "bearer":
                    return None
                claims = await self._codec.verify(token.strip())
                await self._revocation.check(claims)
                return _uuid(claims.get("tenant_id"))
            sid = self._cookies.unsign(request.cookies.get(SID_COOKIE))
            if sid is None:
                return None
            session = await self._bff.session(sid)
            if session is None:
                return None
            # the stored token may be past ``exp`` (refreshed later in authenticate); only revocation matters
            claims = await self._codec.verify(session.access_token, verify_exp=False)
            if claims.get("sid") != str(sid):
                return None
            await self._revocation.check(claims)
            return _uuid(session.tenant_id)
        except (InvalidAccessTokenError, TokenRevokedError, ValueError, KeyError):
            return None

    async def subscription_status(self, tenant_id: UUID) -> str:
        return await self._subs.status(tenant_id)

    async def permission_limits(self, principal: Principal, code: str) -> list[Decimal | None]:
        return await self._repo.permission_limits(principal.tenant_id, principal.user_id, code)

    async def branch_ids(self, principal: Principal) -> tuple[UUID, ...] | None:
        ctx = await self._repo.membership_context(principal.tenant_id, principal.user_id)
        if ctx is None or ctx.status != "active":
            return None
        return ctx.branch_ids

    def csrf_token(self, sid: UUID) -> str:
        return self._csrf.issue(sid)

    # --- helpers ---------------------------------------------------------------------------------
    async def _verify(self, token: str, *, bearer: bool) -> dict[str, Any]:
        headers = _BEARER_CHALLENGE if bearer else None
        try:
            claims = await self._codec.verify(token)
        except InvalidAccessTokenError as exc:
            code = ErrorCode.TOKEN_EXPIRED if exc.reason == "expired" else ErrorCode.UNAUTHORIZED
            raise AppError(code, headers=headers) from exc
        try:
            await self._revocation.check(claims)
        except TokenRevokedError as exc:
            raise AppError(ErrorCode.TOKEN_REVOKED, headers=headers) from exc
        return claims

    @staticmethod
    def _principal(claims: dict[str, Any], *, via_cookie: bool) -> Principal:
        user_id, tenant_id = _uuid(claims.get("sub")), _uuid(claims.get("tenant_id"))
        if user_id is None or tenant_id is None:
            raise AppError(ErrorCode.UNAUTHORIZED)
        return Principal(
            user_id=user_id,
            tenant_id=tenant_id,
            client_id=str(claims["client_id"]),
            scopes=scope_to_set(str(claims.get("scope", ""))),
            roles=tuple(str(r) for r in claims.get("roles") or ()),
            branch_ids=tuple(b for b in (_uuid(x) for x in claims.get("branch_ids") or ()) if b is not None),
            sid=_uuid(claims.get("sid")),
            device_id=_uuid(claims.get("device_id")),
            jti=str(claims["jti"]),
            issued_at=int(claims["iat"]),
            expires_at=int(claims["exp"]),
            sub_status=claims.get("sub_status"),
            via_cookie=via_cookie,
        )
