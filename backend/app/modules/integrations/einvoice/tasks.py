"""SAQ jobs of the e-invoice integration (registered in ``app/workers/jobs/__init__.py``, 23 §4)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.core.config import Settings, get_settings
from app.core.db.session import Database, TenantContextError
from app.modules.integrations.einvoice.wiring import doc_outbox_service, ettn_outbox_service, inbox_poller


def _tenant(raw: object) -> UUID:
    try:
        return raw if isinstance(raw, UUID) else UUID(str(raw))
    except ValueError as exc:
        raise TenantContextError(f"invalid tenant_id: {raw!r}") from exc


def _settings(ctx: dict[str, Any]) -> Settings:
    settings: Settings = ctx.get("settings") or get_settings()
    return settings


async def einvoice_ettn_send(ctx: dict[str, Any], *, tenant_id: object = None, job_id: str) -> dict[str, Any]:
    """Register one outgoing e-TTN (``outbox_jobs(kind='ettn_send')``, 21 §3)."""
    db: Database = ctx["db"]
    service = ettn_outbox_service(db.session_factory, _settings(ctx), ctx.get("einvoice_port"))
    outcome = await service.run(_tenant(tenant_id), UUID(job_id))
    return outcome.as_json() if outcome else {"skipped": True}


async def einvoice_ettn_sweep(ctx: dict[str, Any], *, tenant_id: object = None) -> dict[str, Any]:
    """Cron backstop: every due ``ettn_send`` job of the tenant (retries, lost enqueues, dead workers)."""
    db: Database = ctx["db"]
    service = ettn_outbox_service(db.session_factory, _settings(ctx), ctx.get("einvoice_port"))
    done = await service.process_due(_tenant(tenant_id))
    return {"processed": len(done), "statuses": [o.status for o in done]}


async def einvoice_doc_send(ctx: dict[str, Any], *, tenant_id: object = None, job_id: str) -> dict[str, Any]:
    """One signed e-document job (``einvoice_send`` / ``einvoice_accept`` / ``poa_send`` / "
    "``ettn_accept``)."""
    db: Database = ctx["db"]
    service = doc_outbox_service(db.session_factory, _settings(ctx), ctx.get("einvoice_port"))
    outcome = await service.run(_tenant(tenant_id), UUID(job_id))
    return outcome.as_json() if outcome else {"skipped": True}


async def einvoice_doc_sweep(ctx: dict[str, Any], *, tenant_id: object = None) -> dict[str, Any]:
    """Cron backstop: every due signed-document job of the tenant (retries, lost enqueues, dead workers)."""
    db: Database = ctx["db"]
    service = doc_outbox_service(db.session_factory, _settings(ctx), ctx.get("einvoice_port"))
    done = await service.process_due(_tenant(tenant_id))
    return {"processed": len(done), "statuses": [o.status for o in done]}


async def einvoice_poll(ctx: dict[str, Any], *, tenant_id: object = None) -> dict[str, Any]:
    """Operator poll of one tenant (21 §2: incoming EHF, answers to sent EHF / e-ishonchnoma)."""
    db: Database = ctx["db"]
    result = await inbox_poller(db.session_factory, _settings(ctx), ctx.get("einvoice_port")).run(
        _tenant(tenant_id)
    )
    return result.as_json()
