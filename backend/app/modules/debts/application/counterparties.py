"""Counterparties directory (18 §11.2–11.4 — the single source; 19 §9 supplier view, US-M08-05, BO-04/BO-06).

One table/one resource for customers and suppliers (``is_customer``/``is_supplier``, 11 §5). Every
write runs in one ``tenant_transaction`` with its audit row and the staged idempotency response
(23 §3). Permissions that depend on the body or on the stored row (18 §11.2/§11.4) are decided here
from the caller's grants; the static ones are route dependencies.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Final
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.audit import record_audit
from app.core.auth.principal import Principal
from app.core.db.base import uuid7
from app.core.db.session import tenant_transaction
from app.core.error_codes import ErrorCode
from app.core.errors import AppError, ErrorDetail
from app.core.idempotency import stage_response
from app.core.money import money_str
from app.modules.debts.application.ports import CounterpartyFilter, CounterpartyRepository
from app.modules.debts.application.register import DebtRegister
from app.modules.debts.domain.counterparties import (
    COUNTERPARTY_KINDS,
    FULL_CUSTOMER_FIELDS,
    LIMIT_FIELDS,
    Counterparty,
    normalize_phone,
    valid_stir,
)
from app.modules.integrations.einvoice.application.ports import EInvoicePort, EInvoiceProviderError

# the codes that decide counterparty writes (18 §11.2/§11.4); the API resolves which of them the caller has
DEBTS_CREATE: Final = "debts.create"
DEBTS_LIMIT_MANAGE: Final = "debts.limit.manage"
PURCHASES_CREATE: Final = "purchases.create"
WRITE_PERMISSIONS: Final = (DEBTS_CREATE, DEBTS_LIMIT_MANAGE, PURCHASES_CREATE)

COUNTERPARTY_FIELDS: Final = (
    "kind",
    "name",
    "phone",
    "stir",
    "legal_address",
    "bank_account",
    "bank_mfo",
    "vat_payer",
    "is_customer",
    "is_supplier",
    "credit_limit",
    "standing_discount_pct",
    "notify_consent",
    "note",
)
_NOT_NULL: Final = frozenset({"kind", "name", "is_customer", "is_supplier", "notify_consent"})


@dataclass(frozen=True, slots=True)
class Page:
    items: list[dict[str, Any]]
    total: int
    page: int
    size: int

    def as_json(self) -> dict[str, Any]:
        return {"items": self.items, "total": self.total, "page": self.page, "size": self.size}


def _invalid(field: str, key: str) -> AppError:
    return AppError(ErrorCode.VALIDATION_ERROR, details=[ErrorDetail(field=field, message_key=key)])


invalid_field = _invalid


def _denied(code: str) -> AppError:
    return AppError(ErrorCode.PERMISSION_DENIED, params={"permission": code})


def _not_found(field: str | None = None) -> AppError:
    details = [ErrorDetail(field=field, message_key="validation.not_found")] if field else []
    return AppError(ErrorCode.NOT_FOUND, params={"resource": "counterparty"}, details=details)


def _ts(value: datetime | None) -> str | None:
    return None if value is None else value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _dec(value: Decimal | None) -> str | None:
    return None if value is None else money_str(value)


def counterparty_json(cp: Counterparty) -> dict[str, Any]:
    return {
        "id": str(cp.id),
        "kind": cp.kind,
        "name": cp.name,
        "phone": cp.phone,
        "stir": cp.stir,
        "legal_address": cp.legal_address,
        "bank_account": cp.bank_account,
        "bank_mfo": cp.bank_mfo,
        "vat_payer": cp.vat_payer,
        "is_customer": cp.is_customer,
        "is_supplier": cp.is_supplier,
        "credit_limit": _dec(cp.credit_limit),
        "standing_discount_pct": _dec(cp.standing_discount_pct),
        "notify_consent": cp.notify_consent,
        "notify_consent_at": _ts(cp.notify_consent_at),
        "note": cp.note,
        "archived_at": _ts(cp.archived_at),
        "created_at": _ts(cp.created_at),
        "updated_at": _ts(cp.updated_at),
        "version": cp.version,
    }


def _audit_view(values: Mapping[str, Any]) -> dict[str, Any]:
    return {k: (str(v) if isinstance(v, Decimal | UUID | datetime) else v) for k, v in values.items()}


def required_for_create(values: Mapping[str, Any]) -> set[str]:
    """18 §11.2 — supplier: ``purchases.create``; quick customer (name+phone): ``debts.create``;
    full customer (STIR, bank, limit) and any limit/discount: ``debts.limit.manage``.
    """
    needed: set[str] = set()
    if values.get("is_supplier"):
        needed.add(PURCHASES_CREATE)
    if values.get("is_customer"):
        full = any(values.get(f) is not None for f in FULL_CUSTOMER_FIELDS)
        needed.add(DEBTS_LIMIT_MANAGE if full else DEBTS_CREATE)
    if any(values.get(f) is not None for f in LIMIT_FIELDS):
        needed.add(DEBTS_LIMIT_MANAGE)
    if not needed:  # neither customer nor supplier (e.g. a bank/acquirer) — directory maintenance
        needed.add(DEBTS_LIMIT_MANAGE)
    return needed


def check_update_allowed(current: Counterparty, changes: Mapping[str, Any], grants: frozenset[str]) -> None:
    """18 §11.4: ``debts.limit.manage`` — anything; ``purchases.create`` — supplier rows only, and never
    the credit limit / standing discount or the customer flag."""
    if DEBTS_LIMIT_MANAGE in grants:
        return
    customer_fields = LIMIT_FIELDS | {"is_customer"}
    if PURCHASES_CREATE in grants and current.is_supplier and not (customer_fields & changes.keys()):
        return
    raise _denied(DEBTS_LIMIT_MANAGE)


def check_archive_allowed(current: Counterparty, grants: frozenset[str]) -> None:
    """18 §11.4: ``debts.limit.manage`` / ``debts.create`` — any row; ``purchases.create`` — suppliers."""
    if grants & {DEBTS_LIMIT_MANAGE, DEBTS_CREATE}:
        return
    if PURCHASES_CREATE in grants and current.is_supplier:
        return
    raise _denied(DEBTS_CREATE)


def validate_row(row: dict[str, Any]) -> None:
    """Normalises ``phone``/``stir`` in place and checks the merged row (18 §11.2, 19 §9, 12 CHECKs)."""
    for field in _NOT_NULL:
        if row.get(field) is None:
            raise _invalid(field, "validation.required")
    name = row["name"]
    if not isinstance(name, str) or not name.strip():
        raise _invalid("name", "validation.required")
    row["name"] = name.strip()
    if row["kind"] not in COUNTERPARTY_KINDS:
        raise _invalid("kind", "validation.enum")
    phone = row.get("phone")
    if phone is not None and str(phone).strip():
        normalized = normalize_phone(str(phone))
        if normalized is None:
            raise _invalid("phone", "validation.phone_format")
        row["phone"] = normalized
    else:
        row["phone"] = None
        if row["is_customer"] and not row["is_supplier"]:
            raise _invalid("phone", "validation.required")  # 18 §11.2: name + phone for a customer
    stir = row.get("stir")
    if stir is not None and str(stir).strip():
        row["stir"] = str(stir).strip()
        if not valid_stir(row["stir"]):
            raise _invalid("stir", "validation.stir_format")
    else:
        row["stir"] = None
        if row["kind"] == "company":
            raise _invalid("stir", "validation.required")  # 19 §9: company → 9-digit STIR
    for field in ("legal_address", "bank_account", "bank_mfo", "note"):
        value = row.get(field)
        row[field] = value.strip() or None if isinstance(value, str) else value
    limit = row.get("credit_limit")
    if limit is not None and Decimal(limit) < 0:
        raise _invalid("credit_limit", "validation.min_value")
    pct = row.get("standing_discount_pct")
    if pct is not None and not Decimal(0) <= Decimal(pct) <= Decimal(100):
        raise _invalid("standing_discount_pct", "validation.range")


class CounterpartyDirectory:
    """Reference checks for other modules' documents (runs in the caller's transaction)."""

    def __init__(self, repo: CounterpartyRepository) -> None:
        self._repo = repo

    async def get(self, s: AsyncSession, counterparty_id: UUID) -> Counterparty | None:
        return await self._repo.get(s, counterparty_id)

    async def require_supplier(
        self, s: AsyncSession, counterparty_id: UUID, *, field: str = "supplier_id"
    ) -> Counterparty:
        """Active supplier, else: missing (RLS) → ``404 NOT_FOUND{resource:counterparty}``; archived →
        ``409 RESOURCE_ARCHIVED``; not a supplier → ``422 VALIDATION_ERROR`` (``validation.not_a_supplier``).
        """
        cp = await self._active(s, counterparty_id, field)
        if not cp.is_supplier:
            raise _invalid(field, "validation.not_a_supplier")
        return cp

    async def require_customer(
        self, s: AsyncSession, counterparty_id: UUID, *, field: str = "counterparty_id"
    ) -> Counterparty:
        cp = await self._active(s, counterparty_id, field)
        if not cp.is_customer:
            raise _invalid(field, "validation.not_a_customer")
        return cp

    async def _active(self, s: AsyncSession, counterparty_id: UUID, field: str) -> Counterparty:
        cp = await self._repo.get(s, counterparty_id)
        if cp is None:
            raise _not_found(field)
        if cp.archived_at is not None:
            raise AppError(
                ErrorCode.RESOURCE_ARCHIVED,
                params={"resource": "counterparty"},
                details=[ErrorDetail(field=field, message_key="validation.archived")],
            )
        return cp


class CounterpartyService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        repo: CounterpartyRepository,
        register: DebtRegister,
        einvoice: EInvoicePort,
    ) -> None:
        self._sf = session_factory
        self._repo = repo
        self._register = register
        self._einvoice = einvoice

    # --- reads ------------------------------------------------------------------------------------
    async def list_page(self, actor: Principal, flt: CounterpartyFilter, page: int, size: int) -> Page:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            rows, total = await self._repo.list_page(s, flt, (page - 1) * size, size)
        items = [
            counterparty_json(r.counterparty)
            | {
                "receivable_balance": money_str(r.receivable_balance),
                "payable_balance": money_str(r.payable_balance),
            }
            for r in rows
        ]
        return Page(items, total, page, size)

    async def get(self, actor: Principal, counterparty_id: UUID) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            cp = await self._repo.get(s, counterparty_id)
        if cp is None:
            raise _not_found()
        return counterparty_json(cp)

    async def debt_balance(self, actor: Principal, counterparty_id: UUID) -> dict[str, str]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            if await self._repo.get(s, counterparty_id) is None:
                raise _not_found()
            balances = await self._register.balances(s, counterparty_id)
        return {"payable": money_str(balances["payable"]), "receivable": money_str(balances["receivable"])}

    # --- writes -----------------------------------------------------------------------------------
    async def create(
        self, actor: Principal, values: Mapping[str, Any], grants: frozenset[str], ip: str | None
    ) -> dict[str, Any]:
        row = {k: values.get(k) for k in COUNTERPARTY_FIELDS}
        row["is_supplier"] = bool(row["is_supplier"])
        row["is_customer"] = (
            (not row["is_supplier"]) if row["is_customer"] is None else bool(row["is_customer"])
        )
        row["notify_consent"] = bool(row["notify_consent"])
        missing = sorted(required_for_create(row) - grants)
        if missing:
            raise _denied(missing[0])
        validate_row(row)
        counterparty_id = uuid7()
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            await self._repo.insert(
                s,
                {
                    **row,
                    "id": counterparty_id,
                    "tenant_id": actor.tenant_id,
                    "notify_consent_at": datetime.now(UTC) if row["notify_consent"] else None,
                },
            )
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="counterparty.created",
                entity="counterparties",
                entity_id=counterparty_id,
                after=_audit_view(row),
                ip=ip,
            )
            body = counterparty_json(await self._load(s, counterparty_id))
            stage_response(body, 201)
        return body

    async def update(
        self,
        actor: Principal,
        counterparty_id: UUID,
        version: int,
        changes: Mapping[str, Any],
        grants: frozenset[str],
        ip: str | None,
    ) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            current = await self._repo.get(s, counterparty_id, lock=True)
            if current is None:
                raise _not_found()
            check_update_allowed(current, changes, grants)
            if current.archived_at is not None:
                raise AppError(ErrorCode.RESOURCE_ARCHIVED, params={"resource": "counterparty"})
            if current.version != version:
                raise AppError(ErrorCode.VERSION_CONFLICT, params={"current_version": current.version})
            merged = {k: getattr(current, k) for k in COUNTERPARTY_FIELDS} | dict(changes)
            validate_row(merged)
            values = {k: merged[k] for k in changes}
            if "notify_consent" in values and values["notify_consent"] != current.notify_consent:
                values["notify_consent_at"] = datetime.now(UTC) if values["notify_consent"] else None
            if values and not await self._repo.update(s, counterparty_id, version, values):
                raise AppError(ErrorCode.VERSION_CONFLICT, params={"current_version": current.version})
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="counterparty.updated",
                entity="counterparties",
                entity_id=counterparty_id,
                before=_audit_view({k: getattr(current, k) for k in changes}),
                after=_audit_view({k: merged[k] for k in changes}),
                ip=ip,
            )
            body = counterparty_json(await self._load(s, counterparty_id))
            stage_response(body)
        return body

    async def set_archived(
        self,
        actor: Principal,
        counterparty_id: UUID,
        archived: bool,
        reason: str | None,
        grants: frozenset[str],
        ip: str | None,
    ) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            current = await self._repo.get(s, counterparty_id, lock=True)
            if current is None:
                raise _not_found()
            check_archive_allowed(current, grants)
            if (current.archived_at is not None) != archived:
                await self._repo.set_archived(s, counterparty_id, archived)
                await record_audit(
                    s,
                    tenant_id=actor.tenant_id,
                    user_id=actor.user_id,
                    action="counterparty.archived" if archived else "counterparty.unarchived",
                    entity="counterparties",
                    entity_id=counterparty_id,
                    after={"reason": reason},
                    ip=ip,
                )
            body = counterparty_json(await self._load(s, counterparty_id))
            stage_response(body)
        return body

    async def lookup_by_stir(self, actor: Principal, stir: str) -> dict[str, Any]:
        """19 §9: suggest-only — the operator is asked outside any transaction, nothing is saved."""
        stir = stir.strip()
        if not valid_stir(stir):
            raise _invalid("stir", "validation.stir_format")
        try:
            company = await self._einvoice.lookup_company(stir)
        except EInvoiceProviderError as exc:
            raise AppError(
                ErrorCode.EINVOICE_PROVIDER_UNAVAILABLE, params={"operation": "lookup_by_stir"}
            ) from exc
        if company is None:
            raise AppError(ErrorCode.NOT_FOUND, params={"resource": "company"})
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            existing = await self._repo.find_by_stir(s, stir)
        return {
            "stir": company.stir,
            "kind": "company",
            "name": company.name,
            "legal_address": company.legal_address,
            "bank_account": company.bank_account,
            "bank_mfo": company.bank_mfo,
            "vat_payer": company.vat_payer,
            "director_name": company.director_name,
            "existing_counterparty_id": str(existing) if existing else None,
        }

    async def _load(self, s: AsyncSession, counterparty_id: UUID) -> Counterparty:
        cp = await self._repo.get(s, counterparty_id)
        assert cp is not None
        return cp
