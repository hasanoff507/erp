"""Shared helpers of the branches application layer."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.core.error_codes import ErrorCode
from app.core.errors import AppError, ErrorDetail


def not_found(resource: str) -> AppError:
    return AppError(ErrorCode.NOT_FOUND, params={"resource": resource})


def archived(resource: str) -> AppError:
    return AppError(ErrorCode.RESOURCE_ARCHIVED, params={"resource": resource})


def invalid(field: str, message_key: str, **params: object) -> AppError:
    return AppError(
        ErrorCode.VALIDATION_ERROR,
        params=params or None,
        details=[ErrorDetail(field=field, message_key=message_key)],
    )


def check_version(current: int, sent: int) -> None:
    """17 §8: optimistic locking; the server version goes back in ``params.current_version``."""
    if current != sent:
        raise AppError(ErrorCode.VERSION_CONFLICT, params={"current_version": current})


def check_branch_scope(allowed: tuple[UUID, ...], branch_id: UUID | None) -> None:
    """15 §2.4: ``memberships.branch_ids`` empty = every branch; otherwise only the listed ones."""
    if allowed and branch_id not in allowed:
        raise AppError(ErrorCode.BRANCH_SCOPE_DENIED, params={"branch_id": str(branch_id)})


def scoped_branch_ids(allowed: tuple[UUID, ...], branch_id: UUID | None) -> tuple[UUID, ...] | None:
    """Branch filter of a list endpoint: the requested branch (checked) or the caller's scope (None = all)."""
    if branch_id is not None:
        check_branch_scope(allowed, branch_id)
        return (branch_id,)
    return allowed or None


def iso(value: datetime | None) -> str | None:
    return None if value is None else value.isoformat().replace("+00:00", "Z")
