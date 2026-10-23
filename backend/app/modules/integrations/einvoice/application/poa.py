"""Powers of attorney — e-ishonchnoma (19 §8a; 21 §6; 12 ``powers_of_attorney``; BP-01 1a; qaror #63).

``POST`` (``purchases.create``) → ``pending_signature``; ``sign-challenge``/``submit-signed``
(``einvoice.sign``, E-IMZO) → ``sending`` + ``outbox_jobs(kind='poa_send')`` → the worker
(``EInvoicePort.send_power_of_attorney``) → ``sent`` (``number``, ``operator_doc_id``, ``sent_at``) or
``failed`` (``last_error``; re-sign → ``sending``); the supplier's answer is polled → ``accepted`` /
``rejected`` (``responded_at``, ``reject_reason``). ``cancel`` — ``draft``/``pending_signature`` only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any, Final
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.audit import record_audit
from app.core.auth.principal import Principal
from app.core.db.base import uuid7
from app.core.db.session import tenant_transaction
from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from app.core.idempotency import stage_response
from app.core.permissions import BranchScope
from app.modules.accounting.domain.calendar import business_today
from app.modules.integrations.einvoice.application.common import (
    DOC_JOB,
    POA_SEND,
    Enqueue,
    JobEnqueuer,
    decode_cursor,
    enqueue_after_commit,
    invalid,
    invalid_state,
    iso,
    not_found,
    opt,
    page_out,
    ts,
)
from app.modules.integrations.einvoice.application.records import EDocsRepository, Page, PowerOfAttorney
from app.modules.integrations.einvoice.application.signing import Signer
from app.modules.integrations.einvoice.domain.documents import POA_CANCELLABLE, POA_SIGNABLE, poa_valid_to

ENTITY: Final = "powers_of_attorney"


@dataclass(frozen=True, slots=True)
class PoaInput:
    supplier_id: UUID
    employee_user_id: UUID
    doc_date: date
    purchase_order_id: UUID | None = None
    valid_from: date | None = None
    valid_to: date | None = None


def poa_json(p: PowerOfAttorney) -> dict[str, Any]:
    return {
        "id": str(p.id),
        "branch_id": str(p.branch_id),
        "purchase_order_id": opt(p.purchase_order_id),
        "supplier_id": str(p.supplier_id),
        "supplier": {"id": str(p.supplier_id), "name": p.supplier_name, "stir": p.supplier_stir},
        "employee_user_id": str(p.employee_user_id),
        "employee_name": p.employee_name,
        "doc_date": iso(p.doc_date),
        "valid_from": iso(p.valid_from),
        "valid_to": iso(p.valid_to),
        "number": p.number,
        "operator_doc_id": p.operator_doc_id,
        "status": p.status,
        "last_error": p.last_error,
        "signed_at": ts(p.signed_at),
        "sent_at": ts(p.sent_at),
        "responded_at": ts(p.responded_at),
        "reject_reason": p.reject_reason,
        "created_at": ts(p.created_at),
        "version": p.version,
    }


def _document(p: PowerOfAttorney) -> dict[str, Any]:
    return {
        "supplier_id": str(p.supplier_id),
        "supplier_stir": p.supplier_stir,
        "employee_user_id": str(p.employee_user_id),
        "employee_name": p.employee_name,
        "purchase_order_id": opt(p.purchase_order_id),
        "doc_date": iso(p.doc_date),
        "valid_from": iso(p.valid_from),
        "valid_to": iso(p.valid_to),
        "status": p.status,
    }


def _check_scope(scope: BranchScope, branch_id: UUID) -> None:
    if not scope.unrestricted and branch_id not in scope.allowed:
        raise AppError(ErrorCode.BRANCH_SCOPE_DENIED)


class PowerOfAttorneyService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        repo: EDocsRepository,
        signer: Signer,
        queue: JobEnqueuer | None = None,
    ) -> None:
        self._sf = session_factory
        self._repo = repo
        self._signer = signer
        self._queue = queue

    async def create(
        self, actor: Principal, scope: BranchScope, data: PoaInput, ip: str | None
    ) -> dict[str, Any]:
        valid_from = data.valid_from or business_today()
        valid_to = data.valid_to or poa_valid_to(valid_from)
        if valid_to < valid_from:
            raise invalid("valid_to", "validation.valid_to_before_valid_from")
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            supplier = await self._repo.counterparty(s, data.supplier_id)
            if supplier is None:
                raise not_found("counterparty")
            if supplier.archived:
                raise AppError(ErrorCode.RESOURCE_ARCHIVED, params={"resource": "counterparty"})
            branch_id = scope.current
            if data.purchase_order_id is not None:
                po = await self._repo.purchase_order_supplier(s, data.purchase_order_id)
                if po is None:
                    raise not_found("purchase_order")
                if po[0] != data.supplier_id:
                    raise invalid("supplier_id", "validation.supplier_mismatch")
                branch_id = po[1]
            if branch_id is None:
                raise invalid("X-Branch-Id", "validation.required")
            _check_scope(scope, branch_id)
            if not await self._repo.tenant_user_exists(s, data.employee_user_id):
                raise not_found("user")
            poa_id = uuid7()
            await self._repo.insert_poa(
                s,
                {
                    "id": poa_id,
                    "tenant_id": actor.tenant_id,
                    "branch_id": branch_id,
                    "purchase_order_id": data.purchase_order_id,
                    "supplier_id": data.supplier_id,
                    "employee_user_id": data.employee_user_id,
                    "doc_date": data.doc_date,
                    "valid_from": valid_from,
                    "valid_to": valid_to,
                    "status": "pending_signature",
                    "created_by": actor.user_id,
                },
            )
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="power_of_attorney.created",
                entity=ENTITY,
                entity_id=poa_id,
                ip=ip,
                after={
                    "supplier_id": str(data.supplier_id),
                    "employee_user_id": str(data.employee_user_id),
                    "valid_from": valid_from.isoformat(),
                    "valid_to": valid_to.isoformat(),
                },
            )
            body = poa_json(await self._load(s, poa_id))
            stage_response(body, 201)
        return body

    async def list_page(
        self,
        actor: Principal,
        scope: BranchScope,
        *,
        purchase_order_id: UUID | None,
        supplier_id: UUID | None,
        status: str | None,
        cursor: str | None,
        limit: int,
    ) -> dict[str, Any]:
        page = Page(decode_cursor(cursor), limit + 1)
        filters: dict[str, Any] = {
            "purchase_order_id": purchase_order_id,
            "supplier_id": supplier_id,
            "status": status,
            "branch_ids": None if scope.unrestricted else tuple(scope.allowed),
        }
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            rows = await self._repo.poas(s, filters, page)
        return page_out(rows, limit, poa_json)

    async def get(self, actor: Principal, scope: BranchScope, poa_id: UUID) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            p = await self._repo.poa(s, poa_id)
        if p is None:
            raise not_found("power_of_attorney")
        _check_scope(scope, p.branch_id)
        return poa_json(p)

    async def sign_challenge(self, actor: Principal, scope: BranchScope, poa_id: UUID) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            p = await self._repo.poa(s, poa_id)
        if p is None:
            raise not_found("power_of_attorney")
        _check_scope(scope, p.branch_id)
        if p.status not in POA_SIGNABLE:
            raise invalid_state(p.status, "pending_signature|failed")
        return await self._signer.challenge(
            actor.tenant_id, actor.user_id, ENTITY, p.id, "sign", _document(p)
        )

    async def submit_signed(
        self,
        actor: Principal,
        scope: BranchScope,
        poa_id: UUID,
        challenge_id: str,
        pkcs7: str,
        ip: str | None,
    ) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            p = await self._repo.poa(s, poa_id)
        if p is None:
            raise not_found("power_of_attorney")
        _check_scope(scope, p.branch_id)
        if p.status not in POA_SIGNABLE:
            raise invalid_state(p.status, "pending_signature|failed")
        doc_hash = await self._signer.take(
            challenge_id,
            tenant_id=actor.tenant_id,
            user_id=actor.user_id,
            entity=ENTITY,
            entity_id=p.id,
            action="sign",
        )
        signature = await self._signer.verify(doc_hash, pkcs7)
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            job_id = await self._repo.queue_job(
                s, actor.tenant_id, POA_SEND, {"poa_id": str(p.id)}, f"{POA_SEND}:{p.id}", actor.user_id
            )
            current = await self._repo.poa(s, poa_id, lock=True)
            assert current is not None
            if current.status not in POA_SIGNABLE:
                raise invalid_state(current.status, "pending_signature|failed")
            self._signer.check_unchanged(signature, ENTITY, current.id, "sign", _document(current))
            now = datetime.now(UTC)
            await self._repo.update_poa(s, p.id, {"status": "sending", "signed_at": now, "last_error": None})
            await self._repo.insert_signature(
                s,
                {
                    "tenant_id": actor.tenant_id,
                    "entity": ENTITY,
                    "entity_id": p.id,
                    "action": "sign",
                    "document_hash": signature.document_hash,
                    "signature_pkcs7": signature.pkcs7,
                    "certificate_serial": signature.certificate_serial,
                    "signer_tin": signature.signer_tin,
                    "signed_by": actor.user_id,
                },
            )
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="power_of_attorney.sign",
                entity=ENTITY,
                entity_id=p.id,
                ip=ip,
                before={"status": current.status},
                after={"status": "sending", "document_hash": signature.document_hash, "job_id": str(job_id)},
            )
            body = {"id": str(p.id), "status": "sending"}
            stage_response(body, 202)
        await enqueue_after_commit(self._queue, actor.tenant_id, [Enqueue(DOC_JOB, job_id)])
        return body

    async def cancel(
        self, actor: Principal, scope: BranchScope, poa_id: UUID, reason: str, ip: str | None
    ) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            p = await self._repo.poa(s, poa_id, lock=True)
            if p is None:
                raise not_found("power_of_attorney")
            _check_scope(scope, p.branch_id)
            if p.status not in POA_CANCELLABLE:
                raise invalid_state(p.status, "draft|pending_signature")
            await self._repo.update_poa(s, p.id, {"status": "cancelled"})
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="power_of_attorney.cancelled",
                entity=ENTITY,
                entity_id=p.id,
                ip=ip,
                before={"status": p.status},
                after={"status": "cancelled", "reason": reason},
            )
            body = {"id": str(p.id), "status": "cancelled"}
            stage_response(body)
        return body

    async def _load(self, s: AsyncSession, poa_id: UUID) -> PowerOfAttorney:
        p = await self._repo.poa(s, poa_id)
        assert p is not None
        return p
