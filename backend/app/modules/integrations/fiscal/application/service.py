"""``FiscalService`` implementation (contracts.py) — the posting-side half of the fiscal package.

* :meth:`FiscalServiceImpl.assert_can_issue` — ``FISCAL_DEVICE_LOCKED`` (``cash_registers.fm_state ≠ 'ok'``)
  and the 48 h rule (``FISCAL_OFFLINE_48H_BLOCKED``, 18 §4.10, 16 §6). With ``ERP_FISCAL_PROVIDER=fake`` an
  ``unknown`` state (a new register) is resolved once through the in-process fake FM
  (``get_device_status``) and stored; real providers (Bosqich 5) keep ``unknown`` = locked.
* :meth:`FiscalServiceImpl.record` — the ``fiscal_receipts`` row (+ ``outbox_jobs(kind='ofd_send')`` for
  the server-side providers), ``receipt_seq`` conflict rules (QT-SEQ-01, QT-M01-23), one Z per shift.
* :meth:`FiscalServiceImpl.enqueue` — after commit, the SAQ ``fiscal_ofd_send`` job per receipt.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any, Final, Literal, Protocol
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.base import uuid7
from app.core.db.session import session_tenant_id
from app.core.error_codes import ErrorCode
from app.core.errors import AppError, ErrorDetail
from app.modules.integrations.fiscal.application.contracts import (
    FiscalKind,
    FiscalReceiptRef,
    PaymentForm,
)
from app.modules.integrations.fiscal.application.ports import (
    CashRegisterRef,
    FiscalPort,
    FiscalRepository,
)
from app.modules.integrations.fiscal.domain.rules import is_blocked

log = structlog.get_logger(__name__)

OFD_SEND_JOB: Final = "fiscal_ofd_send"
OFD_SWEEP_JOB: Final = "fiscal_ofd_sweep"
MONITOR_JOB: Final = "fiscal_unacked_monitor"
SERVER_SIDE: Final = frozenset({"fake", "partner_cloud"})
_RESULT_KEYS: Final = ("fm_terminal_id", "fm_receipt_seq", "fiscal_sign", "qr_url", "fiscal_at")


class JobEnqueuer(Protocol):
    async def enqueue(self, job: str, tenant_id: UUID, **kwargs: Any) -> None: ...


def _invalid(field: str, key: str) -> AppError:
    return AppError(ErrorCode.VALIDATION_ERROR, details=[ErrorDetail(field=field, message_key=key)])


def _parse_dt(raw: object) -> datetime:
    if isinstance(raw, datetime):
        value = raw
    else:
        try:
            value = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except ValueError:
            raise _invalid("fiscal_result.fiscal_at", "validation.datetime") from None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def parse_fiscal_result(raw: Mapping[str, Any]) -> dict[str, Any]:
    """``{fm_terminal_id, fm_receipt_seq, fiscal_sign, qr_url, fiscal_at}`` of a local-bridge FM (18 §4.1)."""
    missing = [k for k in _RESULT_KEYS if raw.get(k) in (None, "")]
    if missing:
        raise _invalid(f"fiscal_result.{missing[0]}", "validation.required")
    extra = sorted(set(raw) - set(_RESULT_KEYS))
    if extra:
        raise _invalid(f"fiscal_result.{extra[0]}", "validation.extra_forbidden")
    try:
        seq = int(str(raw["fm_receipt_seq"]))
    except ValueError:
        raise _invalid("fiscal_result.fm_receipt_seq", "validation.int_parsing") from None
    if seq <= 0:
        raise _invalid("fiscal_result.fm_receipt_seq", "validation.greater_than")
    return {
        "fm_terminal_id": str(raw["fm_terminal_id"])[:64],
        "fm_receipt_seq": seq,
        "fiscal_sign": str(raw["fiscal_sign"])[:64],
        "qr_url": str(raw["qr_url"])[:500],
        "fiscal_at": _parse_dt(raw["fiscal_at"]),
    }


class FiscalServiceImpl:
    def __init__(
        self,
        repo: FiscalRepository,
        port: FiscalPort,
        provider: str,
        queue: JobEnqueuer | None,
    ) -> None:
        self._repo = repo
        self._port = port
        self._provider = provider
        self._queue = queue

    @property
    def provider(self) -> str:
        return self._provider

    @property
    def server_side(self) -> bool:
        return self._provider in SERVER_SIDE

    # --- contract -----------------------------------------------------------------------------------
    async def assert_can_issue(self, s: AsyncSession, *, cash_register_id: UUID, at: datetime) -> None:
        register = await self._repo.register(s, cash_register_id)
        if register is None:
            raise AppError(ErrorCode.NOT_FOUND, params={"resource": "cash_register"})
        state = register.fm_state
        if state == "unknown" and self._provider == "fake":
            status = await self._port.get_device_status(
                CashRegisterRef(register.id, register.tenant_id, register.fiscal_module_id)
            )
            state = status.fm_state
            await self._repo.set_fm_state(s, register.id, state)
        if state != "ok":
            raise AppError(ErrorCode.FISCAL_DEVICE_LOCKED, params={"fm_state": state})
        oldest = await self._repo.oldest_unacked(s, cash_register_id)
        if oldest is not None and is_blocked(oldest[1], at):
            raise AppError(
                ErrorCode.FISCAL_OFFLINE_48H_BLOCKED,
                params={
                    "cash_register_id": str(cash_register_id),
                    "oldest_unacked_at": oldest[1].isoformat(),
                },
            )

    async def record(
        self,
        s: AsyncSession,
        *,
        kind: FiscalKind,
        doc_id: UUID,
        cash_register_id: UUID,
        shift_id: UUID,
        receipt_seq: int | None,
        payment_form: PaymentForm | None,
        payload: Mapping[str, Any],
        fiscal_result: Mapping[str, Any] | None,
        is_offline: bool,
        offline_since: datetime | None,
        delivery: Literal["printed", "electronic"] = "printed",
        delivery_reason: str | None = None,
        created_at: datetime | None = None,
    ) -> FiscalReceiptRef:
        tenant_id = session_tenant_id(s)
        if tenant_id is None:
            raise RuntimeError("FiscalService.record() outside a tenant transaction")
        body = dict(payload)
        renumbered_from: int | None = None
        result = parse_fiscal_result(fiscal_result) if fiscal_result is not None else None
        if kind == "z_report":
            if await self._repo.z_exists(s, shift_id):
                raise _invalid("shift_id", "validation.z_report_exists")
            receipt_seq, payment_form = None, None
        else:
            if receipt_seq is None or receipt_seq <= 0:
                raise _invalid("receipt_seq", "validation.required")
            if payment_form is None:
                raise _invalid("payments", "validation.payment_form_required")
            if await self._repo.seq_taken(s, cash_register_id, shift_id, receipt_seq):
                if result is None:
                    raise AppError(ErrorCode.RECEIPT_SEQ_CONFLICT, params={"receipt_seq": receipt_seq})
                renumbered_from = receipt_seq
                receipt_seq = await self._repo.max_seq(s, cash_register_id, shift_id) + 1
                body["device_receipt_seq"] = renumbered_from
        if delivery == "electronic" and not delivery_reason:
            raise _invalid("delivery_reason", "validation.required")
        at = created_at or datetime.now(UTC)
        receipt_id = uuid7()
        row: dict[str, Any] = {
            "id": receipt_id, "tenant_id": tenant_id, "kind": kind,
            "sale_id": doc_id if kind in ("sale", "credit_sale") else None,
            "return_id": doc_id if kind == "return" else None,
            "debt_payment_id": doc_id if kind == "debt_settlement" else None,
            "cash_register_id": cash_register_id, "shift_id": shift_id, "receipt_seq": receipt_seq,
            "payload": json.dumps(body, default=str, ensure_ascii=False), "payment_form": payment_form,
            "delivery": delivery, "delivery_reason": delivery_reason if delivery == "electronic" else None,
            "offline_since": (offline_since or at) if is_offline else None,
            "status": "fiscalized" if result else "pending", "created_at": at,
            "fm_terminal_id": result["fm_terminal_id"] if result else None,
            "fm_receipt_seq": result["fm_receipt_seq"] if result else None,
            "fiscal_sign": result["fiscal_sign"] if result else None,
            "qr_url": result["qr_url"] if result else None,
            "fiscal_at": result["fiscal_at"] if result else None,
            "sent_at": result["fiscal_at"] if result else None,
        }  # fmt: skip
        await self._repo.insert_receipt(s, row)
        if result is None and self.server_side:
            await self._repo.insert_job(s, tenant_id, receipt_id)
        return FiscalReceiptRef(
            id=receipt_id,
            status=row["status"],
            receipt_seq=receipt_seq,
            fm_receipt_seq=row["fm_receipt_seq"],
            fiscal_sign=row["fiscal_sign"],
            qr_url=row["qr_url"],
            ofd_acked_at=None,
            renumbered_from=renumbered_from,
        )

    async def enqueue(self, tenant_id: UUID, receipt_ids: Sequence[UUID]) -> None:
        if self._queue is None or not self.server_side:
            return
        for rid in dict.fromkeys(receipt_ids):
            try:
                await self._queue.enqueue(OFD_SEND_JOB, tenant_id, receipt_id=str(rid))
            except Exception:  # the per-minute sweeper picks the job up
                log.warning("fiscal_enqueue_failed", receipt_id=str(rid), exc_info=True)
