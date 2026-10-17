"""Per-request context (request id, tenant, user) shared by logging and errors."""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any
from uuid import UUID

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
tenant_id_var: ContextVar[UUID | None] = ContextVar("tenant_id", default=None)
user_id_var: ContextVar[UUID | None] = ContextVar("user_id", default=None)
# 14 §4.3: the device session's own user while a PIN-verified actor acts (audit `on_behalf_session_user`)
session_user_var: ContextVar[UUID | None] = ContextVar("session_user", default=None)


def current_request_id() -> str | None:
    return request_id_var.get()


@dataclass(slots=True)
class PendingIdempotency:
    """The ``Idempotency-Key`` of the running write request (23 §3).

    Set by :class:`app.core.idempotency.IdempotencyMiddleware`; the route stages
    its response with :func:`app.core.idempotency.stage_response` and
    ``tenant_transaction`` inserts the ``idempotency_keys`` row right before its
    COMMIT, so the journal row and the business write commit or roll back together.
    """

    tenant_id: UUID
    key: str
    request_hash: str
    status: int | None = None
    body: Any = None
    unit_of_work: object | None = None  # the tenant_transaction that staged the response
    recorded: bool = False


idempotency_var: ContextVar[PendingIdempotency | None] = ContextVar("idempotency", default=None)


# the innermost open ``tenant_transaction`` of this task (identity token only)
unit_of_work_var: ContextVar[object | None] = ContextVar("unit_of_work", default=None)


class IdempotencyConflictError(Exception):
    """Another request with the same key committed first; this transaction is rolled back."""
