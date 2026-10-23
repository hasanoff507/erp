"""E-TTN documents (19 §20; 21 §3, §5; qaror #63; QT-M06-07; BO-03 / BO-15 / POS-09 actions).

* outgoing (internal transfer, written by ``transfers`` ``post``): ``pending_signature`` →
  ``sign-challenge``/``submit-signed`` (sender's E-IMZO) → ``sending`` + ``outbox_jobs(kind='ettn_send')`` →
  ``registered`` (``operator_doc_id`` → ``transfers.ettn_ref``) → the receiving branch ``accept``/``reject``
  after the transfer is received → ``accepted``/``rejected``; ``sending → failed → submit-signed`` again;
* ``register-manual`` — the e-TTN was made in the operator cabinet (operator API without a TTN type, or the
  operator is down): ``registered`` + ``transfers.ettn_ref``, audit ``ettn.registered_manually``;
* incoming (operator poll, separate from the EHF): ``received`` → signed ``accept``/``reject`` →
  ``outbox_jobs(kind='ettn_accept')`` → ``accepted``/``rejected``. A combined EHF+TTN (``einvoice_id``) is
  accepted with its e-invoice (19 §19), not here.

Lock order (SEC-03, same as the ``ettn_send`` worker and transfer cancel): transfer → outbox job → e-TTN.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any, Final, Literal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.audit import record_audit
from app.core.auth.principal import Principal
from app.core.db.session import tenant_transaction
from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from app.core.idempotency import stage_response
from app.core.permissions import BranchScope
from app.modules.integrations.einvoice.application.common import (
    DOC_JOB,
    ETTN_ACCEPT,
    ETTN_JOB,
    ETTN_SEND,
    Enqueue,
    JobEnqueuer,
    decode_cursor,
    enqueue_after_commit,
    invalid_state,
    iso,
    not_found,
    opt,
    page_out,
    ts,
)
from app.modules.integrations.einvoice.application.records import EDocsRepository, EttnDoc, Page
from app.modules.integrations.einvoice.application.signing import Signer
from app.modules.integrations.einvoice.domain.documents import (
    ETTN_MANUAL_BLOCKED,
    ETTN_RESPONDABLE,
    ETTN_SIGNABLE,
    SignAction,
)

ENTITY: Final = "ettn_documents"
Action = Literal["accept", "reject"]


def ettn_json(x: EttnDoc, *, full: bool = False) -> dict[str, Any]:
    body: dict[str, Any] = {
        "id": str(x.id),
        "direction": x.direction,
        "transport_type": x.transport_type,
        "status": x.status,
        "operator_doc_id": x.operator_doc_id,
        "transfer_id": opt(x.transfer_id),
        "einvoice_id": opt(x.einvoice_id),
        "counterparty_id": opt(x.counterparty_id),
        "receipt_id": opt(x.receipt_id),
        "doc_date": iso(x.doc_date),
        "signed_at": ts(x.signed_at),
        "last_error": x.last_error,
        "created_at": ts(x.created_at),
    }
    if full:
        body["payload"] = dict(x.payload)
    return body


def _document(x: EttnDoc) -> dict[str, Any]:
    return {
        "direction": x.direction,
        "transport_type": x.transport_type,
        "transfer_id": opt(x.transfer_id),
        "operator_doc_id": x.operator_doc_id,
        "status": x.status,
        "payload": dict(x.payload),
    }


def _check_scope(scope: BranchScope, x: EttnDoc, *, receiving: bool = False) -> None:
    if x.transfer_id is None or scope.unrestricted:
        return
    branch = x.transfer_to_branch_id if receiving else x.transfer_from_branch_id
    if branch not in scope.allowed:
        raise AppError(ErrorCode.BRANCH_SCOPE_DENIED)


class EttnDocService:
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

    # --- reads -----------------------------------------------------------------------------------------
    async def list_page(
        self,
        actor: Principal,
        *,
        direction: str | None,
        status: str | None,
        transfer_id: UUID | None,
        cursor: str | None,
        limit: int,
    ) -> dict[str, Any]:
        page = Page(decode_cursor(cursor), limit + 1)
        filters = {"direction": direction, "status": status, "transfer_id": transfer_id}
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            rows = await self._repo.ettns(s, filters, page)
        return page_out(rows, limit, ettn_json)

    async def get(self, actor: Principal, ettn_id: UUID) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            x = await self._repo.ettn(s, ettn_id)
        if x is None:
            raise not_found("ettn_document")
        return ettn_json(x, full=True)

    async def direction_of(self, actor: Principal, ettn_id: UUID) -> str:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            x = await self._repo.ettn(s, ettn_id)
        if x is None:
            raise not_found("ettn_document")
        return x.direction

    # --- sign + send (sender) ------------------------------------------------------------------------------
    async def sign_challenge(
        self, actor: Principal, scope: BranchScope, ettn_id: UUID, action: Action | None
    ) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            x = await self._repo.ettn(s, ettn_id)
            if x is None:
                raise not_found("ettn_document")
            if action is None:
                _check_scope(scope, x)
                self._check_sendable(x)
            else:
                _check_scope(scope, x, receiving=True)
                self._check_respondable(x)
        sign_action: SignAction = action or "sign"
        return await self._signer.challenge(
            actor.tenant_id, actor.user_id, ENTITY, x.id, sign_action, _document(x)
        )

    @staticmethod
    def _check_sendable(x: EttnDoc) -> None:
        if x.direction != "out" or x.status not in ETTN_SIGNABLE:
            raise invalid_state(x.status, "pending_signature|failed")
        if x.transfer_status == "cancelled":
            raise invalid_state("cancelled", "posted", reason="transfer_cancelled")

    @staticmethod
    def _check_respondable(x: EttnDoc) -> None:
        if x.einvoice_id is not None:
            raise invalid_state(x.status, "received|registered", reason="combined_with_einvoice")
        if x.status not in ETTN_RESPONDABLE[x.direction]:
            raise invalid_state(x.status, "|".join(sorted(ETTN_RESPONDABLE[x.direction])))
        if x.direction == "out" and x.transfer_status not in ("received", "discrepancy"):
            raise invalid_state(
                x.transfer_status or "missing", "received|discrepancy", reason="transfer_not_received"
            )

    async def submit_signed(
        self,
        actor: Principal,
        scope: BranchScope,
        ettn_id: UUID,
        challenge_id: str,
        pkcs7: str,
        ip: str | None,
    ) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            x = await self._repo.ettn(s, ettn_id)
            if x is None:
                raise not_found("ettn_document")
            _check_scope(scope, x)
            self._check_sendable(x)
        doc_hash = await self._signer.take(
            challenge_id,
            tenant_id=actor.tenant_id,
            user_id=actor.user_id,
            entity=ENTITY,
            entity_id=x.id,
            action="sign",
        )
        signature = await self._signer.verify(doc_hash, pkcs7)
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            if x.transfer_id is not None:  # transfer → outbox job → e-TTN (SEC-03)
                await self._repo.lock_transfer(s, x.transfer_id)
            current = await self._repo.ettn(s, ettn_id)
            if current is None:
                raise not_found("ettn_document")
            self._check_sendable(current)
            self._signer.check_unchanged(signature, ENTITY, current.id, "sign", _document(current))
            job_id = await self._repo.queue_job(
                s,
                actor.tenant_id,
                ETTN_SEND,
                {"ettn_id": str(x.id), "transfer_id": opt(x.transfer_id)},
                f"{ETTN_SEND}:{x.id}",
                actor.user_id,
            )
            await self._repo.ettn(s, ettn_id, lock=True)
            now = datetime.now(UTC)
            await self._repo.update_ettn(s, x.id, {"status": "sending", "signed_at": now, "last_error": None})
            await self._repo.insert_signature(s, _sig_row(actor, x.id, "sign", signature))
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="ettn.sign",
                entity=ENTITY,
                entity_id=x.id,
                ip=ip,
                before={"status": current.status},
                after={"status": "sending", "document_hash": signature.document_hash, "job_id": str(job_id)},
            )
            body = {"id": str(x.id), "status": "sending", "signed_at": ts(now)}
            stage_response(body, 202)
        await enqueue_after_commit(self._queue, actor.tenant_id, [Enqueue(ETTN_JOB, job_id)])
        return body

    # --- manual registration ---------------------------------------------------------------------------
    async def register_manual(
        self,
        actor: Principal,
        scope: BranchScope,
        ettn_id: UUID,
        operator_doc_id: str,
        doc_date: date,
        ip: str | None,
    ) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            x = await self._repo.ettn(s, ettn_id)
            if x is None:
                raise not_found("ettn_document")
            _check_scope(scope, x)
            if x.transfer_id is not None:
                await self._repo.lock_transfer(s, x.transfer_id)
            # a still-queued ettn_send job finds the e-TTN registered and closes itself ("nothing to send")
            current = await self._repo.ettn(s, ettn_id, lock=True)
            assert current is not None
            if current.direction != "out" or current.status in ETTN_MANUAL_BLOCKED:
                raise invalid_state(current.status, "pending_signature|sending|failed")
            await self._repo.update_ettn(
                s,
                x.id,
                {
                    "status": "registered",
                    "operator_doc_id": operator_doc_id,
                    "doc_date": doc_date,
                    "last_error": None,
                },
            )
            if x.transfer_id is not None:
                await self._repo.set_transfer_ettn_ref(s, x.transfer_id, operator_doc_id)
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="ettn.registered_manually",
                entity=ENTITY,
                entity_id=x.id,
                ip=ip,
                before={"status": current.status},
                after={
                    "status": "registered",
                    "operator_doc_id": operator_doc_id,
                    "doc_date": doc_date.isoformat(),
                },
            )
            refreshed = await self._repo.ettn(s, x.id)
            assert refreshed is not None
            body = ettn_json(refreshed)
            stage_response(body)
        return body

    # --- receiver accept / reject ----------------------------------------------------------------------
    async def respond(
        self,
        actor: Principal,
        scope: BranchScope,
        ettn_id: UUID,
        action: Action,
        challenge_id: str,
        pkcs7: str,
        reason: str | None,
        ip: str | None,
    ) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            x = await self._repo.ettn(s, ettn_id)
            if x is None:
                raise not_found("ettn_document")
            _check_scope(scope, x, receiving=True)
            self._check_respondable(x)
        doc_hash = await self._signer.take(
            challenge_id,
            tenant_id=actor.tenant_id,
            user_id=actor.user_id,
            entity=ENTITY,
            entity_id=x.id,
            action=action,
        )
        signature = await self._signer.verify(doc_hash, pkcs7)
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            if x.transfer_id is not None:
                await self._repo.lock_transfer(s, x.transfer_id)
            job_id = await self._repo.queue_job(
                s,
                actor.tenant_id,
                ETTN_ACCEPT,
                {"ettn_id": str(x.id), "action": action, "reason": reason},
                f"{ETTN_ACCEPT}:{x.id}",
                actor.user_id,
            )
            current = await self._repo.ettn(s, ettn_id, lock=True)
            assert current is not None
            self._check_respondable(current)
            self._signer.check_unchanged(signature, ENTITY, current.id, action, _document(current))
            await self._repo.insert_signature(s, _sig_row(actor, x.id, action, signature))
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action=f"ettn.{action}_requested",
                entity=ENTITY,
                entity_id=x.id,
                ip=ip,
                after={"job_id": str(job_id), "reason": reason, "document_hash": signature.document_hash},
            )
            body = {"id": str(x.id), "status": "queued", "job_id": str(job_id)}
            stage_response(body, 202)
        await enqueue_after_commit(self._queue, actor.tenant_id, [Enqueue(DOC_JOB, job_id)])
        return body


def _sig_row(actor: Principal, entity_id: UUID, action: str, signature: Any) -> dict[str, Any]:
    return {
        "tenant_id": actor.tenant_id,
        "entity": ENTITY,
        "entity_id": entity_id,
        "action": action,
        "document_hash": signature.document_hash,
        "signature_pkcs7": signature.pkcs7,
        "certificate_serial": signature.certificate_serial,
        "signer_tin": signature.signer_tin,
        "signed_by": actor.user_id,
    }
