"""Signed values bound to a BFF session (15 §1.3, 14 §2.1).

* ``__Host-sid`` cookie — the session id, signed (itsdangerous ``Signer``).
* CSRF synchronizer token — ``GET /api/v1/auth/csrf``; signed with a separate
  salt, bound to the sid, so a rotated session invalidates old tokens. No CSRF
  cookie (not double-submit).
"""

from __future__ import annotations

import hmac
from uuid import UUID

from itsdangerous import BadSignature, Signer, URLSafeTimedSerializer


class SessionCookieSigner:
    def __init__(self, secret: str) -> None:
        self._signer = Signer(secret, salt="erp.sid")

    def sign(self, sid: UUID) -> str:
        return self._signer.sign(str(sid)).decode("ascii")

    def unsign(self, value: str | None) -> UUID | None:
        if not value:
            return None
        try:
            return UUID(self._signer.unsign(value).decode("ascii"))
        except (BadSignature, ValueError):
            return None


class CsrfTokens:
    def __init__(self, secret: str, max_age_s: int) -> None:
        self._serializer = URLSafeTimedSerializer(secret, salt="erp.csrf")
        self._max_age = max_age_s

    def issue(self, sid: UUID) -> str:
        return self._serializer.dumps(str(sid))

    def verify(self, token: str | None, sid: UUID) -> bool:
        if not token:
            return False
        try:
            value = self._serializer.loads(token, max_age=self._max_age)
        except BadSignature:
            return False
        return isinstance(value, str) and hmac.compare_digest(value, str(sid))
