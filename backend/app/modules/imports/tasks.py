"""SAQ jobs of the imports module (registered in ``app/workers/jobs/__init__.py``, 23 §4).

``ctx["db"]`` comes from the worker startup; ``ctx["settings"]`` may override
the process settings (tests). Each job manages its own tenant transactions so
a failure can still be recorded on the job row (``status='failed'``).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.core.config import Settings, get_settings
from app.core.db.session import Database, TenantContextError
from app.core.permissions import BranchScope
from app.modules.imports.wiring import ImportService, build_import_service


def _uuid(raw: object, what: str) -> UUID:
    if isinstance(raw, UUID):
        return raw
    try:
        return UUID(str(raw))
    except ValueError as exc:
        if what == "tenant_id":
            raise TenantContextError(f"invalid tenant_id: {raw!r}") from exc
        raise


def _service(ctx: dict[str, Any]) -> ImportService:
    settings: Settings = ctx.get("settings") or get_settings()
    db: Database = ctx["db"]
    return build_import_service(settings, db.session_factory)


async def import_jobs_validate(
    ctx: dict[str, Any], *, tenant_id: object = None, job_id: str
) -> dict[str, Any]:
    tid = _uuid(tenant_id, "tenant_id")
    result: dict[str, Any] = await _service(ctx).run_validate(tid, _uuid(job_id, "job_id"))
    return result


async def import_jobs_commit(
    ctx: dict[str, Any],
    *,
    tenant_id: object = None,
    job_id: str,
    user_id: str,
    skip_error_rows: bool = True,
    branch_ids: list[str] | None = None,
) -> dict[str, Any]:
    """``branch_ids`` — the committing actor's branch scope (``[]`` = every branch)."""
    tid = _uuid(tenant_id, "tenant_id")
    scope = BranchScope(allowed=tuple(_uuid(b, "branch_id") for b in branch_ids or ()), current=None)
    result: dict[str, Any] = await _service(ctx).run_commit(
        tid, _uuid(job_id, "job_id"), _uuid(user_id, "user_id"), skip_error_rows, scope
    )
    return result
