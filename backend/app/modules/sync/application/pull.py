"""``GET /sync/pull`` (16 §1, §3.2; 18 §17) — snapshot + delta in one mechanism.

* **delta scopes** (catalog, barcodes, prices, customers, stock, marking_codes, fiscal) — rows ordered per
  stream by ``(updated_at, key)``; one response holds at most ``page_size`` rows over all requested streams
  (``has_more`` → call again). A stream without a position in the cursor starts from scratch (snapshot:
  archived/stale rows omitted); with a position it delivers every change after it (incl. tombstones —
  ``deleted: true``). Rows newer than ``now − settle`` wait for the next pull, so a transaction that
  commits late with an earlier ``updated_at`` is never skipped.
* **snapshot scopes** (permissions, limits, shift, settings) — one object replacing the whole local
  table, ``null`` when its digest equals the cursor's.

Every pull marks the device seen (``devices.last_seen_at``).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Final
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.auth.principal import Principal
from app.core.db.session import tenant_transaction
from app.core.error_codes import ErrorCode
from app.core.errors import AppError, ErrorDetail
from app.modules.branches.domain.tenant_settings import effective_settings
from app.modules.sync.application.ports import PullContext, PullReader, StaffPinSource, SyncStore
from app.modules.sync.application.push import SCOPE_SYNC, check_device, require_device
from app.modules.sync.domain.cursor import (
    DELTA_SCOPES,
    CursorError,
    PullCursor,
    ScopeError,
    digest,
    parse_scopes,
)

# 20 #29 TenantSettings / 11 §2: weight-barcode templates when the tenant set none (22 = weight, 21 = amount)
DEFAULT_WEIGHT_TEMPLATES: Final[list[dict[str, Any]]] = [
    {
        "prefixes": ["22"],
        "item_code_len": 5,
        "value_len": 5,
        "value_kind": "WEIGHT",
        "decimals": 3,
        "enabled": True,
    },
    {
        "prefixes": ["21"],
        "item_code_len": 5,
        "value_len": 5,
        "value_kind": "AMOUNT",
        "decimals": 0,
        "enabled": True,
    },
]
# permission codes that carry a limit (15 §2.2) — the ``limits`` scope
LIMITED_CODES: Final = (
    "discount.give", "discount.approve", "returns.approve", "debts.approve", "cash.withdraw", "cash.deposit",
    "stock.writeoff", "prices.approve", "expenses.approve",
)  # fmt: skip


@dataclass(frozen=True, slots=True)
class PullConfig:
    default_page_size: int = 500
    max_page_size: int = 1000
    settle_s: float = 2.0


def _invalid(field: str, key: str) -> AppError:
    return AppError(ErrorCode.VALIDATION_ERROR, details=[ErrorDetail(field=field, message_key=key)])


def _iso(value: Any) -> Any:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z") if isinstance(value, datetime) else value


def weight_version(templates: Sequence[Mapping[str, Any]]) -> str:
    raw = json.dumps(list(templates), sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


class PullService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        store: SyncStore,
        reader: PullReader,
        pins: StaffPinSource | None,
        config: PullConfig,
    ) -> None:
        self._sf = session_factory
        self._store = store
        self._reader = reader
        self.pins = pins
        self._cfg = config

    async def pull(
        self, principal: Principal, scope: str | None, cursor: str | None, page_size: int | None
    ) -> dict[str, Any]:
        device_id = require_device(principal)
        if not principal.has_scope(SCOPE_SYNC):
            raise AppError(ErrorCode.PERMISSION_DENIED, params={"reason": "sync_scope_missing"})
        try:
            scopes = parse_scopes(scope)
        except ScopeError as exc:
            raise _invalid("scope", "validation.enum") from exc
        try:
            state = PullCursor.decode(cursor)
        except CursorError as exc:
            raise _invalid("cursor", "validation.cursor_invalid") from exc
        size = page_size or self._cfg.default_page_size
        if not 1 <= size <= self._cfg.max_page_size:
            raise _invalid("page_size", "validation.range")
        async with self._sf() as s, tenant_transaction(s, principal.tenant_id, user_id=principal.user_id):
            device = check_device(await self._store.device(s, device_id))
            await self._store.touch_seen(s, device_id)
            now, cutoff = await self._store.settle_cutoff(s, self._cfg.settle_s)
            assert device.branch_id is not None
            ctx = PullContext(
                tenant_id=principal.tenant_id,
                device_id=device_id,
                branch_id=device.branch_id,
                cash_register_id=device.cash_register_id,
                settle_before=cutoff,
                now=now,
            )
            out: dict[str, Any] = {
                "cursor": "",
                "has_more": False,
                "server_time": _iso(now),
                "device": {
                    "id": str(device_id),
                    "branch_id": str(device.branch_id),
                    "cash_register_id": str(device.cash_register_id) if device.cash_register_id else None,
                },
            }
            remaining = size
            staff: list[dict[str, Any]] | None = None
            for name in scopes:
                if name in DELTA_SCOPES:
                    rows: list[dict[str, Any]] = []
                    for stream in DELTA_SCOPES[name]:
                        if remaining <= 0:
                            out["has_more"] = True
                            break
                        found = await self._reader.stream(
                            s, stream, ctx, state.positions.get(stream), remaining + 1
                        )
                        if len(found) > remaining:
                            out["has_more"] = True
                            found = found[:remaining]
                        if found:
                            state.positions[stream] = found[-1].position
                        rows.extend(r.data for r in found)
                        remaining -= len(found)
                    out[name] = rows
                    continue
                if name in ("permissions", "limits") and staff is None:
                    staff = await self._staff(s, ctx)
                obj = await self._snapshot(s, name, ctx, staff or [])
                value = digest(obj)
                if state.digests.get(name) == value:
                    out[name] = None
                else:
                    out[name] = {"digest": value, **obj}
                    state.digests[name] = value
        out["cursor"] = state.encode()
        return out

    # --- snapshot objects -------------------------------------------------------------------------
    async def _staff(self, s: AsyncSession, ctx: PullContext) -> list[dict[str, Any]]:
        return await self._reader.staff(s, ctx)

    async def _snapshot(
        self, s: AsyncSession, name: str, ctx: PullContext, staff: list[dict[str, Any]]
    ) -> dict[str, Any]:
        if name == "permissions":
            return await self._permissions(s, ctx, staff)
        if name == "limits":
            return {"users": [_limits(m) for m in staff]}
        if name == "shift":
            return await self._reader.shift(s, ctx)
        return self._settings(await self._reader.settings(s, ctx))

    async def _permissions(
        self, s: AsyncSession, ctx: PullContext, staff: list[dict[str, Any]]
    ) -> dict[str, Any]:
        pins: dict[UUID, Any] = {}
        source = "unavailable"
        if self.pins is not None:
            pins = {p.user_id: p for p in await self.pins.for_branch(s, ctx.tenant_id, ctx.branch_id)}
            source = "auth"
        rows = []
        for member in staff:
            uid = UUID(member["user_id"])
            pin = pins.get(uid)
            active = member["status"] == "active" and (pin.active if pin is not None else True)
            rows.append(
                {
                    "user_id": member["user_id"],
                    "full_name": member["full_name"],
                    "role_ids": member["role_ids"],
                    "role_codes": member["role_codes"],
                    "branch_ids": member["branch_ids"],
                    "active": active,
                    "must_change_pin": bool(pin.must_change_pin) if pin is not None else False,
                    "pin_local_hash": pin.pin_local_hash if pin is not None and active else None,
                    "permissions": member["permissions"] if active else [],
                }
            )
        return {"staff_source": source, "staff": rows}

    def _settings(self, raw: Mapping[str, Any]) -> dict[str, Any]:
        stored = dict(raw["tenant_settings"])
        tenant = dict(raw["tenant"])
        eff = effective_settings(stored, str(tenant.get("legal_form") or "llc"))
        templates = stored.get("weight_barcode_templates")
        if not isinstance(templates, list) or not templates:
            templates = DEFAULT_WEIGHT_TEMPLATES
        terminals = list(raw["card_terminals"])
        register = raw["cash_register"]
        bound = register is not None and any(
            t.get("cash_register_id") == register["id"] for t in terminals if t.get("status") == "active"
        )
        # 16 §2.1: the policy applies only on a register with an active terminal; otherwise always allowed
        fallback = (
            str(stored.get("card_manual_fallback") or eff["card_manual_fallback"]) if bound else "allow"
        )
        return {
            "tenant": tenant,
            "tenant_settings": stored,
            "weight_barcode_templates": templates,
            "weight_barcode_version": weight_version(templates),
            "card_manual_fallback": fallback,
            "marking_precheck": eff["marking_precheck"],
            "negative_stock_policy": eff["negative_stock_policy"],
            "discount_rules": list(raw["discount_rules"]),
            "subscription": raw["subscription"],
            "branch": raw["branch"],
            "cash_register": register,
            "card_terminals": terminals,
            "card_bin_rules": list(raw["card_bin_rules"]),
        }


def _limits(member: Mapping[str, Any]) -> dict[str, Any]:
    limits: dict[str, Any] = {}
    if member["status"] == "active":
        for perm in member["permissions"]:
            if perm["code"] in LIMITED_CODES:
                limits[perm["code"]] = perm["limit_value"]
    return {"user_id": member["user_id"], "limits": limits}
