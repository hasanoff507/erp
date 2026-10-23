"""Composition of the tenant-keys slice (23 §1 ``wiring.py``; contract ``.claude-scratch/b5/contracts/
tenant-integrations.md``).

Public entry points: :func:`build_tenant_integrations` (``app.state.tenant_integrations``),
:func:`tenant_secrets` (the reader other slices call inside their own transaction) and
:func:`integration_status` (BO-14 read model).
"""

from __future__ import annotations

import importlib
from collections.abc import Mapping
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db.session import Database
from app.modules.auth.wiring import build_cipher
from app.modules.integrations.tenant_keys.application import service
from app.modules.integrations.tenant_keys.application.ports import CredentialVerifier
from app.modules.integrations.tenant_keys.application.service import (
    TenantIntegrationsService,
    TenantSecretReader,
)
from app.modules.integrations.tenant_keys.infrastructure.sql import SqlTenantSecretRepository

log = structlog.get_logger(__name__)

__all__ = ["TenantSecretReader", "build_tenant_integrations", "integration_status", "tenant_secrets"]

# optional provider checks published by other slices (``verify_tenant_credentials`` in their wiring)
_VERIFIER_MODULES: Mapping[str, str] = {
    "faktura_uz": "app.modules.integrations.einvoice.wiring",
    "didox": "app.modules.integrations.einvoice.wiring",
    "crpt": "app.modules.integrations.marking.wiring",
}


def _verifiers(settings: Settings) -> dict[str, CredentialVerifier]:
    out: dict[str, CredentialVerifier] = {}
    for kind, module_name in _VERIFIER_MODULES.items():
        try:
            module = importlib.import_module(module_name)
        except ImportError:
            continue
        fn = getattr(module, "verify_tenant_credentials", None)
        if fn is None:
            continue

        async def verify(provider_kind: str, secret: Mapping[str, str], _fn: Any = fn) -> None:
            await _fn(settings, provider_kind, secret)

        out[kind] = verify
    return out


def tenant_secrets(settings: Settings) -> TenantSecretReader:
    return TenantSecretReader(SqlTenantSecretRepository(), build_cipher(settings))


def build_tenant_integrations(settings: Settings, db: Database) -> TenantIntegrationsService:
    return TenantIntegrationsService(
        db.session_factory, SqlTenantSecretRepository(), build_cipher(settings), settings.kek_version,
        _verifiers(settings),
    )  # fmt: skip


async def integration_status(s: AsyncSession) -> dict[str, Any]:
    """BO-14 (20 #40a ``integrations``) inside the caller's tenant transaction — no secret values."""
    return await service.integration_status(SqlTenantSecretRepository(), s)
