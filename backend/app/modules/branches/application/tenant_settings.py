"""Tenant settings — BO-14, Bosqich 1 part (20 #40a, #40b, #40c, #40h; qaror #61, QT-M17-08).

``ai_cross_border_enabled`` changes **only** through :meth:`TenantSettingsService.record_consent`
(append-only ``consents`` row + the settings flag in one transaction); ``go_live_date`` and
``accepted_terms_*`` are read-only here.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import asdict, dataclass
from datetime import date
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.audit import record_audit
from app.core.auth.principal import Principal
from app.core.db.session import tenant_transaction
from app.core.idempotency import stage_response
from app.modules.branches.application.common import check_version, invalid, iso, not_found
from app.modules.branches.application.ports import IntegrationRow, TenantRow, TenantSettingsRepository
from app.modules.branches.domain.model import next_month_start, tashkent_today
from app.modules.branches.domain.tenant_settings import effective_settings, merge_settings

# 20 #40d provider → tenant_secrets.kind
_PROVIDERS = ("faktura_uz", "crpt", "click", "payme", "uzum", "uzqr")

# the BO-14 read model of integrations/tenant_keys (20 #40a): {kind: {status, connected_at, last_ok_at, …}}
IntegrationStatusReader = Callable[[AsyncSession], Awaitable[Mapping[str, Any]]]


@dataclass(frozen=True, slots=True)
class TenantPatch:
    version: int
    name: str | None = None
    legal_form: str | None = None
    settings: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class TaxRegimeView:
    regime: str
    valid_from: date


@dataclass(frozen=True, slots=True)
class ConsentView:
    purpose: str
    terms_version: str
    accepted: bool
    at: str | None
    ai_cross_border_enabled: bool


def _settings_body(row: TenantRow) -> dict[str, Any]:
    """``TenantSettings`` (20 M13a/M14 table)."""
    return {
        "name": row.name,
        "legal_form": row.legal_form,
        "go_live_date": row.go_live_date,
        "accepted_terms_version": row.accepted_terms_version,
        "accepted_terms_at": iso(row.accepted_terms_at),
        "settings": effective_settings(row.settings, row.legal_form),
        "version": row.version,
    }


def _integrations(rows: list[IntegrationRow], ofd_connected: bool) -> dict[str, Any]:
    """Connection status only — secrets never leave the server (20 #40a)."""
    by_kind: dict[str, list[IntegrationRow]] = {}
    for row in rows:
        by_kind.setdefault(row.kind, []).append(row)
    out: dict[str, Any] = {"ofd": {"status": "connected" if ofd_connected else "not_connected"}}
    for kind in _PROVIDERS:
        found = by_kind.get(kind, [])
        entry: dict[str, Any] = {
            "status": "connected" if found else "not_connected",
            "connected_at": iso(min(r.connected_at for r in found)) if found else None,
        }
        if kind == "crpt":
            # the key is envelope-encrypted; key_last4 needs the 40d write path to store it (not in Bosqich 1)
            entry = {"status": entry["status"], "key_last4": None}
        if kind == "uzqr":
            entry["cash_register_ids"] = sorted(str(r.cash_register_id) for r in found if r.cash_register_id)
        out[kind] = entry
    return out


class TenantSettingsService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        repo: TenantSettingsRepository,
        integration_status: IntegrationStatusReader | None = None,
    ) -> None:
        self._sf = session_factory
        self._repo = repo
        self._integration_status = integration_status

    async def get(self, actor: Principal) -> dict[str, Any]:
        today = tashkent_today()
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            row = await self._repo.get_tenant(s, actor.tenant_id)
            if row is None:
                raise not_found("tenants")
            regimes = await self._repo.tax_regimes(s, actor.tenant_id)
            ofd = await self._repo.ofd_connected(s, actor.tenant_id)
            if self._integration_status is not None:  # 20 #40a: tenant_keys read model (incl. didox, last_*)
                status = dict(await self._integration_status(s))
                integration_block = {"ofd": {"status": "connected" if ofd else "not_connected"}, **status}
            else:
                integration_block = _integrations(await self._repo.integrations(s, actor.tenant_id), ofd)
        current = None
        for valid_from, regime in regimes:  # ascending
            if valid_from <= today:
                current = regime
        return {
            **_settings_body(row),
            "tax_regime": {
                "current": current,
                "history": [{"regime": r, "valid_from": v} for v, r in sorted(regimes, reverse=True)],
            },
            "integrations": integration_block,
        }

    async def update(self, actor: Principal, patch: TenantPatch, ip: str | None) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            row = await self._repo.get_tenant(s, actor.tenant_id, for_update=True)
            if row is None:
                raise not_found("tenants")
            check_version(row.version, patch.version)
            fields: dict[str, Any] = {}
            if patch.name is not None and patch.name != row.name:
                fields["name"] = patch.name
            if patch.legal_form is not None and patch.legal_form != row.legal_form:
                fields["legal_form"] = patch.legal_form
            if patch.settings:
                merged = merge_settings(row.settings, patch.settings)
                if merged != row.settings:
                    fields["settings"] = merged
            body_row = row
            if fields:
                version = await self._repo.update_tenant(s, actor.tenant_id, fields)
                body_row = TenantRow(
                    name=fields.get("name", row.name),
                    legal_form=fields.get("legal_form", row.legal_form),
                    go_live_date=row.go_live_date,
                    accepted_terms_version=row.accepted_terms_version,
                    accepted_terms_at=row.accepted_terms_at,
                    settings=fields.get("settings", row.settings),
                    version=version,
                )
                before = _settings_body(row)
                after = _settings_body(body_row)
                changed = [k for k in ("name", "legal_form") if before[k] != after[k]]
                changed += [
                    f"settings.{k}"
                    for k in after["settings"]
                    if before["settings"][k] != after["settings"][k]
                ]
                await record_audit(
                    s,
                    tenant_id=actor.tenant_id,
                    user_id=actor.user_id,
                    action="tenant_settings_updated",
                    entity="tenants",
                    entity_id=actor.tenant_id,
                    before=before,
                    after={**after, "changed": changed},
                    ip=ip,
                )
            body = _settings_body(body_row)
            stage_response(body)
        return body

    async def schedule_tax_regime(
        self, actor: Principal, regime: str, valid_from: date, ip: str | None
    ) -> TaxRegimeView:
        # 20 #40c: a voluntary switch takes effect from the 1st of the next month only
        if valid_from != next_month_start(tashkent_today()):
            raise invalid("valid_from", "validation.next_month_start_required")
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            await self._repo.upsert_tax_regime(s, actor.tenant_id, valid_from, regime, actor.user_id)
            result = TaxRegimeView(regime, valid_from)
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="tax_regime_change_scheduled",
                entity="tenants",
                entity_id=actor.tenant_id,
                after={"regime": regime, "valid_from": valid_from.isoformat()},
                ip=ip,
            )
            stage_response(asdict(result), 201)
        return result

    async def record_consent(
        self, actor: Principal, purpose: str, terms_version: str, accepted: bool, ip: str | None
    ) -> ConsentView:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            current = await self._repo.current_terms_version(s, purpose)
            if terms_version != current:
                raise invalid(
                    "terms_version", "validation.terms_version_not_current", current_version=current
                )
            row = await self._repo.get_tenant(s, actor.tenant_id, for_update=True)
            if row is None:
                raise not_found("tenants")
            at = await self._repo.insert_consent(
                s, actor.tenant_id, actor.user_id, purpose, terms_version, accepted, ip
            )
            before = bool(row.settings.get("ai_cross_border_enabled", False))
            if before != accepted:
                await self._repo.update_tenant(
                    s,
                    actor.tenant_id,
                    {"settings": merge_settings(row.settings, {"ai_cross_border_enabled": accepted})},
                )
            result = ConsentView(purpose, terms_version, accepted, iso(at), accepted)
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="consent.ai_cross_border_changed",
                entity="consents",
                entity_id=actor.tenant_id,
                before={"ai_cross_border_enabled": before},
                after={"ai_cross_border_enabled": accepted, "terms_version": terms_version},
                ip=ip,
            )
            stage_response(asdict(result), 201)
        return result
