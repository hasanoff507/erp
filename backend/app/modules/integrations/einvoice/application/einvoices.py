"""E-invoices (19 §19 incoming, 18 §14a outgoing; 21 §2, §5; 13 §2.8, §2.22, §2.24; US-M01-06, US-M07-03,
US-M10-03, QT-M01-09, QT-M07-09).

Incoming (``direction='in'``, created by the operator poll — :mod:`.inbox`): ``received`` →
``sign-challenge``/``submit-signed`` → ``signed`` → ``accept`` (``202``,
``outbox_jobs(kind='einvoice_accept')``)
→ ``accepted``; ``reject`` (``received``/``signed``, ``202``) → ``rejected``. ``PATCH …/risk-flag`` lets the
Buxgalter set ``green``/``red`` (audit ``einvoice.risk_flag_set``); ``green`` releases the deferred input-VAT
credit of the linked posted receipt (:class:`.vat_credit.VatCredit`).

Outgoing (``direction='out'``): ``draft`` (``POST /einvoices``, ``POST /einvoices/from-receipt`` or the B2B
credit-sale hook) → ``signed`` → ``send`` (``202``, ``outbox_jobs(kind='einvoice_send')``) → ``sent`` →
``accepted``/``rejected`` (status poll); ``cancel`` — ``draft``/``signed`` only (a sent EHF is cancelled in
the operator cabinet). No ledger / VAT rows (13 §2.22, §2.24): the receipt already carries output VAT; one
active outgoing EHF per document (``uq_einvoice_out_per_doc`` → ``409 EINVOICE_ALREADY_LINKED``).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
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
from app.core.money import money, money_str, percent, percent_str, price_str, qty, qty_str
from app.modules.accounting.domain.calendar import business_today
from app.modules.integrations.einvoice.application.common import (
    DOC_JOB,
    EINVOICE_ACCEPT,
    EINVOICE_SEND,
    Enqueue,
    JobEnqueuer,
    decode_cursor,
    enqueue_after_commit,
    invalid,
    invalid_state,
    iso,
    m2,
    not_found,
    opt,
    page_out,
    ts,
)
from app.modules.integrations.einvoice.application.records import (
    EDocsRepository,
    EInvoice,
    Page,
    SaleForInvoice,
)
from app.modules.integrations.einvoice.application.signing import Signer
from app.modules.integrations.einvoice.application.vat_credit import VatCredit
from app.modules.integrations.einvoice.domain.documents import (
    EINVOICE_OUT_CANCELLABLE,
    EINVOICE_REJECTABLE,
    EINVOICE_SIGNABLE,
    InvoiceLine,
    invoice_totals,
    sale_line_net,
)

ENTITY: Final = "einvoices"
ALLOWED_VAT_RATES: Final = (Decimal("0.00"), Decimal("12.00"))


@dataclass(frozen=True, slots=True)
class OutLineInput:
    name: str
    qty: Decimal
    price: Decimal  # unit price without VAT (4 dp)
    vat_rate: Decimal
    product_id: UUID | None = None
    mxik: str | None = None
    unit_code: str | None = None


@dataclass(frozen=True, slots=True)
class OutInput:
    counterparty_id: UUID
    doc_date: date | None
    related_doc_type: str | None
    related_doc_id: UUID | None
    lines: Sequence[OutLineInput] | None


def einvoice_json(e: EInvoice, *, full: bool = False) -> dict[str, Any]:
    body: dict[str, Any] = {
        "id": str(e.id),
        "direction": e.direction,
        "operator": e.operator,
        "operator_doc_id": e.operator_doc_id,
        "counterparty_id": str(e.counterparty_id),
        "counterparty": {
            "id": str(e.counterparty_id),
            "name": e.counterparty_name,
            "stir": e.counterparty_stir,
        },
        "status": e.status,
        "risk_flag": e.risk_flag,
        "factura_type": e.factura_type,
        "related_einvoice_id": opt(e.related_einvoice_id),
        "related_doc_type": e.related_doc_type,
        "related_doc_id": opt(e.related_doc_id),
        "number": e.number,
        "doc_date": iso(e.doc_date),
        "total_amount": m2(e.total_amount),
        "vat_amount": m2(e.vat_amount),
        "signed_at": ts(e.signed_at),
        "signed_by": opt(e.signed_by),
        "last_error": e.last_error if e.job_status in ("failed", "retry") else None,
        "created_at": ts(e.created_at),
        "updated_at": ts(e.updated_at),
    }
    if full:
        body["payload"] = dict(e.payload)
    return body


def signing_document(e: EInvoice) -> dict[str, Any]:
    """What the E-IMZO signature covers (21 §5): requisites, amounts, lines and the current status."""
    return {
        "direction": e.direction,
        "operator_doc_id": e.operator_doc_id,
        "number": e.number,
        "doc_date": iso(e.doc_date),
        "counterparty_stir": e.counterparty_stir,
        "status": e.status,
        "total_amount": m2(e.total_amount),
        "vat_amount": m2(e.vat_amount),
        "factura_type": e.factura_type,
        "lines": list(e.payload.get("lines") or []),
    }


def _line_json(ln: InvoiceLine, line_no: int) -> dict[str, Any]:
    return {
        "line_no": line_no,
        "product_id": ln.product_id,
        "name": ln.name,
        "mxik": ln.mxik,
        "unit_code": ln.unit_code,
        "qty": qty_str(ln.qty),
        "price": price_str(ln.net_amount / ln.qty) if ln.qty else price_str(Decimal("0")),
        "net_amount": money_str(ln.net_amount),
        "vat_rate": percent_str(ln.vat_rate),
        "vat_amount": money_str(ln.vat_amount),
        "total_amount": money_str(ln.total),
        "marking_codes": [ln.marking_code] if ln.marking_code else [],
    }


def sale_invoice_lines(sale: SaleForInvoice) -> list[InvoiceLine]:
    """The receipt's lines less posted returns (13 §2.22: the e-invoice never exceeds the receipt)."""
    out: list[InvoiceLine] = []
    for ln in sale.lines:
        left_qty = qty(Decimal(ln["qty"]) - Decimal(ln["returned_qty"]))
        left_total = money(Decimal(ln["line_total"]) - Decimal(ln["returned_total"]))
        left_vat = money(Decimal(ln["vat_amount"]) - Decimal(ln["returned_vat"]))
        if left_qty <= 0 or left_total <= 0:
            continue
        out.append(
            InvoiceLine(
                name=str(ln["name"] or ""),
                qty=left_qty,
                net_amount=sale_line_net(left_total, left_vat),
                vat_rate=percent(ln["vat_rate"]),
                vat_amount=left_vat,
                product_id=opt(ln["product_id"]),
                mxik=ln["mxik"],
                unit_code=ln["unit_code"],
                marking_code=ln["marking_code"],
            )
        )
    return out


def _seller(stir: str | None, name: str | None) -> dict[str, Any]:
    return {"stir": stir, "name": name}


async def insert_out(
    repo: EDocsRepository,
    s: AsyncSession,
    *,
    tenant_id: UUID,
    counterparty_id: UUID,
    sale: SaleForInvoice | None,
    lines: Sequence[InvoiceLine],
    doc_date: date | None,
    source: str,
) -> UUID:
    """Insert an outgoing ``draft``; a sale-linked one through ``uq_einvoice_out_per_doc``
    (``409 EINVOICE_ALREADY_LINKED`` when another active one exists)."""
    seller_stir, seller_name = await repo.tenant_stir(s)
    cp = await repo.counterparty(s, counterparty_id)
    total, vat = invoice_totals(lines)
    payload = {
        "source": source,
        "seller": _seller(seller_stir, seller_name),
        "buyer": {"stir": cp.stir if cp else None, "name": cp.name if cp else None},
        "receipt_number": sale.number if sale else None,
        "lines": [_line_json(ln, i + 1) for i, ln in enumerate(lines)],
        "total_amount": money_str(total),
        "vat_amount": money_str(vat),
    }
    row = {
        "id": uuid7(),
        "tenant_id": tenant_id,
        "direction": "out",
        "operator": "faktura",
        "counterparty_id": counterparty_id,
        "related_doc_type": "sales" if sale else None,
        "related_doc_id": sale.id if sale else None,
        "status": "draft",
        "doc_date": doc_date or (sale.doc_date if sale else business_today()),
        "total_amount": total,
        "vat_amount": vat,
        "payload": payload,
    }
    if sale is None:
        await repo.insert_einvoice(s, row)
        return UUID(str(row["id"]))
    got = await repo.insert_out_once(s, row)
    if got is None:
        raise AppError(ErrorCode.EINVOICE_ALREADY_LINKED, params={"related_doc_id": str(sale.id)})
    return got


async def draft_for_credit_sale(
    repo: EDocsRepository, s: AsyncSession, tenant_id: UUID, sale_id: UUID
) -> UUID | None:
    """Contract 5a (US-M01-06, 18 §14a, 13 §2.24): a posted sale to a ``company`` with a ``debt`` payment gets
    an outgoing ``draft`` in the caller's transaction; idempotent; never raises for business reasons."""
    sale = await repo.sale(s, sale_id)
    if sale is None or sale.status != "posted" or sale.counterparty_id is None or not sale.has_debt_payment:
        return None
    cp = await repo.counterparty(s, sale.counterparty_id)
    if cp is None or cp.kind != "company":
        return None
    existing = await repo.active_out_for(s, "sales", sale.id)
    if existing is not None:
        return existing
    lines = sale_invoice_lines(sale)
    if not lines:
        return None
    try:
        return await insert_out(
            repo,
            s,
            tenant_id=tenant_id,
            counterparty_id=cp.id,
            sale=sale,
            lines=lines,
            doc_date=sale.doc_date,
            source="b2b_credit_sale",
        )
    except AppError:  # a concurrent draft won the unique index — return it
        return await repo.active_out_for(s, "sales", sale.id)


class EInvoiceService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        repo: EDocsRepository,
        signer: Signer,
        vat: VatCredit,
        queue: JobEnqueuer | None = None,
    ) -> None:
        self._sf = session_factory
        self._repo = repo
        self._signer = signer
        self._vat = vat
        self._queue = queue

    # --- reads ---------------------------------------------------------------------------------------
    async def list_page(
        self,
        actor: Principal,
        *,
        direction: str | None,
        status: str | None,
        risk_flag: str | None,
        cursor: str | None,
        limit: int,
    ) -> dict[str, Any]:
        page = Page(decode_cursor(cursor), limit + 1)
        filters = {"direction": direction, "status": status, "risk_flag": risk_flag}
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            rows = await self._repo.einvoices(s, filters, page)
        return page_out(rows, limit, einvoice_json)

    async def get(self, actor: Principal, einvoice_id: UUID) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            e = await self._repo.einvoice(s, einvoice_id)
        if e is None:
            raise not_found("einvoice")
        return einvoice_json(e, full=True)

    async def direction_of(self, actor: Principal, einvoice_id: UUID) -> str:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            e = await self._repo.einvoice(s, einvoice_id)
        if e is None:
            raise not_found("einvoice")
        return e.direction

    # --- risk flag (19 §19, 13 §2.8) ---------------------------------------------------------------------
    async def set_risk_flag(
        self, actor: Principal, einvoice_id: UUID, flag: str, note: str, ip: str | None
    ) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            e = await self._locked(s, einvoice_id)
            if e.direction != "in":
                raise invalid_state(e.direction, "in", reason="outgoing_einvoice")
            released = Decimal("0.00")
            if flag != e.risk_flag:
                await self._repo.update_einvoice(s, e.id, {"risk_flag": flag})
                if flag == "green":
                    released = await self._vat.release_on_green(s, actor.tenant_id, e.id, business_today())
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="einvoice.risk_flag_set",
                entity=ENTITY,
                entity_id=e.id,
                ip=ip,
                before={"risk_flag": e.risk_flag},
                after={"risk_flag": flag, "note": note, "vat_released": money_str(released)},
            )
            body = {"id": str(e.id), "risk_flag": flag, "vat_released": money_str(released)}
            stage_response(body)
        return body

    # --- signing (21 §5) --------------------------------------------------------------------------------
    async def sign_challenge(self, actor: Principal, einvoice_id: UUID) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            e = await self._repo.einvoice(s, einvoice_id)
            if e is None:
                raise not_found("einvoice")
            self._check_signable(e)
        return await self._signer.challenge(
            actor.tenant_id, actor.user_id, ENTITY, e.id, "sign", signing_document(e)
        )

    def _check_signable(self, e: EInvoice) -> None:
        if e.status == "signed":
            raise AppError(ErrorCode.EINVOICE_ALREADY_SIGNED)
        allowed = EINVOICE_SIGNABLE[e.direction]
        if e.status not in allowed:
            raise invalid_state(e.status, "|".join(sorted(allowed)))
        if e.direction == "out" and not e.counterparty_stir:
            raise AppError(ErrorCode.EINVOICE_COUNTERPARTY_INCOMPLETE, params={"missing": ["stir"]})

    async def submit_signed(
        self, actor: Principal, einvoice_id: UUID, challenge_id: str, pkcs7: str, ip: str | None
    ) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            e = await self._repo.einvoice(s, einvoice_id)
            if e is None:
                raise not_found("einvoice")
            self._check_signable(e)
        doc_hash = await self._signer.take(
            challenge_id,
            tenant_id=actor.tenant_id,
            user_id=actor.user_id,
            entity=ENTITY,
            entity_id=e.id,
            action="sign",
        )
        signature = await self._signer.verify(doc_hash, pkcs7)
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            e = await self._locked(s, einvoice_id)
            self._check_signable(e)
            self._signer.check_unchanged(signature, ENTITY, e.id, "sign", signing_document(e))
            now = datetime.now(UTC)
            await self._repo.update_einvoice(
                s, e.id, {"status": "signed", "signed_at": now, "signed_by": actor.user_id}
            )
            await self._repo.insert_signature(
                s,
                {
                    "tenant_id": actor.tenant_id,
                    "entity": ENTITY,
                    "entity_id": e.id,
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
                action="einvoice.sign",
                entity=ENTITY,
                entity_id=e.id,
                ip=ip,
                before={"status": e.status},
                after={
                    "status": "signed",
                    "document_hash": signature.document_hash,
                    "certificate_serial": signature.certificate_serial,
                    "signer_tin": signature.signer_tin,
                },
            )
            body = {"id": str(e.id), "status": "signed", "signed_at": ts(now)}
            stage_response(body)
        return body

    # --- incoming: accept / reject (19 §19) ----------------------------------------------------------------
    async def accept(self, actor: Principal, einvoice_id: UUID, ip: str | None) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            e = _check_acceptable(await self._get(s, einvoice_id))
            job_id = await self._repo.queue_job(
                s,
                actor.tenant_id,
                EINVOICE_ACCEPT,
                {"einvoice_id": str(e.id), "action": "accept"},
                f"{EINVOICE_ACCEPT}:{e.id}",
                actor.user_id,
            )
            e = _check_acceptable(await self._locked(s, einvoice_id))  # outbox job → e-invoice (worker order)
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="einvoice.accept_requested",
                entity=ENTITY,
                entity_id=e.id,
                ip=ip,
                after={"job_id": str(job_id)},
            )
            body = {"id": str(e.id), "status": "queued", "job_id": str(job_id)}
            stage_response(body, 202)
        await enqueue_after_commit(self._queue, actor.tenant_id, [Enqueue(DOC_JOB, job_id)])
        return body

    async def reject(
        self, actor: Principal, einvoice_id: UUID, reason: str, ip: str | None
    ) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            e = _check_rejectable(await self._get(s, einvoice_id))
            job_id = await self._repo.queue_job(
                s,
                actor.tenant_id,
                EINVOICE_ACCEPT,
                {"einvoice_id": str(e.id), "action": "reject", "reason": reason},
                f"{EINVOICE_ACCEPT}:{e.id}",
                actor.user_id,
            )
            e = _check_rejectable(await self._locked(s, einvoice_id))
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="einvoice.reject_requested",
                entity=ENTITY,
                entity_id=e.id,
                ip=ip,
                after={"job_id": str(job_id), "reason": reason},
            )
            body = {"id": str(e.id), "status": "queued", "job_id": str(job_id)}
            stage_response(body, 202)
        await enqueue_after_commit(self._queue, actor.tenant_id, [Enqueue(DOC_JOB, job_id)])
        return body

    # --- outgoing: create / from-receipt / send / cancel (18 §14a)
    # -------------------------------------------
    async def create_out(self, actor: Principal, data: OutInput, ip: str | None) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            cp = await self._repo.counterparty(s, data.counterparty_id)
            if cp is None:
                raise not_found("counterparty")
            if cp.archived:
                raise AppError(ErrorCode.RESOURCE_ARCHIVED, params={"resource": "counterparty"})
            if not cp.stir:
                raise AppError(ErrorCode.EINVOICE_COUNTERPARTY_INCOMPLETE, params={"missing": ["stir"]})
            sale: SaleForInvoice | None = None
            if data.related_doc_id is not None:
                if data.related_doc_type != "sales":
                    raise invalid("related_doc_type", "validation.invalid_choice")
                sale = await self._posted_sale(s, data.related_doc_id)
            lines = self._out_lines(data, sale)
            einvoice_id = await insert_out(
                self._repo,
                s,
                tenant_id=actor.tenant_id,
                counterparty_id=cp.id,
                sale=sale,
                lines=lines,
                doc_date=data.doc_date,
                source="manual",
            )
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="einvoice.created",
                entity=ENTITY,
                entity_id=einvoice_id,
                ip=ip,
                after={
                    "direction": "out",
                    "counterparty_id": str(cp.id),
                    "related_doc_id": opt(data.related_doc_id),
                },
            )
            e = await self._repo.einvoice(s, einvoice_id)
            assert e is not None
            body = einvoice_json(e, full=True)
            stage_response(body, 201)
        return body

    async def from_receipt(
        self, actor: Principal, sale_id: UUID, counterparty_id: UUID, ip: str | None
    ) -> dict[str, Any]:
        return await self.create_out(
            actor,
            OutInput(
                counterparty_id=counterparty_id,
                doc_date=None,
                related_doc_type="sales",
                related_doc_id=sale_id,
                lines=None,
            ),
            ip,
        )

    def _out_lines(self, data: OutInput, sale: SaleForInvoice | None) -> list[InvoiceLine]:
        receipt_lines = sale_invoice_lines(sale) if sale is not None else None
        if data.lines:
            lines = []
            for index, ln in enumerate(data.lines):
                rate = percent(ln.vat_rate)
                if rate not in ALLOWED_VAT_RATES:
                    raise invalid(f"lines[{index}].vat_rate", "validation.vat_rate_invalid")
                if qty(ln.qty) <= 0:
                    raise invalid(f"lines[{index}].qty", "validation.positive")
                net = money(qty(ln.qty) * ln.price)
                lines.append(
                    InvoiceLine(
                        name=ln.name,
                        qty=qty(ln.qty),
                        net_amount=net,
                        vat_rate=rate,
                        vat_amount=money(net * rate / Decimal("100")),
                        product_id=opt(ln.product_id),
                        mxik=ln.mxik,
                        unit_code=ln.unit_code,
                    )
                )
            if receipt_lines is not None:
                total, _ = invoice_totals(lines)
                receipt_total, _ = invoice_totals(receipt_lines)
                if total > receipt_total:
                    raise AppError(
                        ErrorCode.EINVOICE_AMOUNT_EXCEEDS_RECEIPT,
                        params={"amount": money_str(total), "receipt_amount": money_str(receipt_total)},
                    )
            return lines
        if receipt_lines is None:
            raise invalid("lines", "validation.required")
        if not receipt_lines:
            raise AppError(
                ErrorCode.EINVOICE_AMOUNT_EXCEEDS_RECEIPT, params={"amount": "0.00", "receipt_amount": "0.00"}
            )
        return receipt_lines

    async def _posted_sale(self, s: AsyncSession, sale_id: UUID) -> SaleForInvoice:
        sale = await self._repo.sale(s, sale_id)
        if sale is None:
            raise not_found("sale")
        if sale.status != "posted":
            raise invalid_state(sale.status, "posted", reason="sale_not_posted")
        if await self._repo.active_out_for(s, "sales", sale.id) is not None:
            raise AppError(ErrorCode.EINVOICE_ALREADY_LINKED, params={"related_doc_id": str(sale.id)})
        return sale

    async def send(self, actor: Principal, einvoice_id: UUID, ip: str | None) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            e = _check_sendable(await self._get(s, einvoice_id))
            job_id = await self._repo.queue_job(
                s,
                actor.tenant_id,
                EINVOICE_SEND,
                {"einvoice_id": str(e.id)},
                f"{EINVOICE_SEND}:{e.id}",
                actor.user_id,
            )
            e = _check_sendable(await self._locked(s, einvoice_id))
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="einvoice.send_requested",
                entity=ENTITY,
                entity_id=e.id,
                ip=ip,
                after={"job_id": str(job_id)},
            )
            body = {"id": str(e.id), "status": "queued", "job_id": str(job_id)}
            stage_response(body, 202)
        await enqueue_after_commit(self._queue, actor.tenant_id, [Enqueue(DOC_JOB, job_id)])
        return body

    async def cancel(
        self, actor: Principal, einvoice_id: UUID, reason: str, ip: str | None
    ) -> dict[str, Any]:
        async with self._sf() as s, tenant_transaction(s, actor.tenant_id, user_id=actor.user_id):
            e = await self._locked(s, einvoice_id)
            if e.direction != "out":
                raise invalid_state(e.direction, "out", reason="incoming_einvoice")
            if e.status not in EINVOICE_OUT_CANCELLABLE or e.job_status in ("queued", "running", "retry"):
                raise invalid_state(e.status, "draft|signed", reason="cancel_in_operator")
            await self._repo.update_einvoice(s, e.id, {"status": "cancelled"})
            await record_audit(
                s,
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                action="einvoice.cancelled",
                entity=ENTITY,
                entity_id=e.id,
                ip=ip,
                before={"status": e.status},
                after={"status": "cancelled", "reason": reason},
            )
            body = {"id": str(e.id), "status": "cancelled"}
            stage_response(body)
        return body

    # --- helpers ---------------------------------------------------------------------------------------
    async def _get(self, s: AsyncSession, einvoice_id: UUID) -> EInvoice:
        e = await self._repo.einvoice(s, einvoice_id)
        if e is None:
            raise not_found("einvoice")
        return e

    async def _locked(self, s: AsyncSession, einvoice_id: UUID) -> EInvoice:
        e = await self._repo.einvoice(s, einvoice_id, lock=True)
        if e is None:
            raise not_found("einvoice")
        return e


def _check_acceptable(e: EInvoice) -> EInvoice:
    if e.direction != "in":
        raise invalid_state(e.direction, "in", reason="outgoing_einvoice")
    if e.status == "received":
        raise AppError(ErrorCode.EINVOICE_NOT_SIGNED)
    if e.status != "signed":
        raise invalid_state(e.status, "signed")
    return e


def _check_rejectable(e: EInvoice) -> EInvoice:
    if e.direction != "in":
        raise invalid_state(e.direction, "in", reason="outgoing_einvoice")
    if e.status not in EINVOICE_REJECTABLE:
        raise invalid_state(e.status, "received|signed")
    return e


def _check_sendable(e: EInvoice) -> EInvoice:
    if e.direction != "out":
        raise invalid_state(e.direction, "out", reason="incoming_einvoice")
    if e.status == "draft":
        raise AppError(ErrorCode.EINVOICE_NOT_SIGNED)
    if e.status != "signed":
        raise invalid_state(e.status, "signed")
    return e
