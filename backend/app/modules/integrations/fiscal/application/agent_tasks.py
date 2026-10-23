"""Local-bridge fiscal state through the Do'kon agenti (21 §1, §16; 16 §6; 23 §4.2; qaror #60, #68).

The FM signs on the device; the server learns the FM state and the OFD acknowledgements from three agent
tasks (``purpose='device_service'``, ``AgentTaskPort``, contract 1):

* ``fiscal.status`` — cron every 5 min per register bound to an agent (``cash_registers.fiscal_agent_id``)
  and right after a BO-12 binding: result → ``fm_state``, ``fm_receipts_pending``; ``acked[]`` →
  ``fiscal_receipts.ofd_acked_at`` by ``(tenant_id, fm_terminal_id, fm_receipt_seq)``; the register's
  ``last_unacked_receipt_at`` is recomputed from the server's receipts (the 48 h timer, 16 §6);
* ``fiscal.resend_unsent`` — automatically at the 40 h stage of the oldest unacked receipt (one task per
  receipt) and from BO-14; result ``acked[]`` as above;
* ``fiscal.zreport`` — a local-bridge Z-report row without FM requisites (``shift.closed``) → result
  ``ZReport`` fills that ``fiscal_receipts(kind='z_report')`` row.

Partner cloud / fake (server-side providers): :class:`ProviderAckPoller` asks the provider
(``resend_unsent``) for every register with fiscalized-but-unacked receipts — DoD-05 on that path.

Result handlers run inside the agent result (A-05) transaction; a result for a register not bound to the
reporting agent changes nothing (audit ``fiscal.status_foreign_agent``).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any, Final
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.audit import record_audit
from app.core.db.base import uuid7
from app.core.db.session import tenant_transaction
from app.core.error_codes import ErrorCode
from app.core.errors import AppError, ErrorDetail
from app.modules.integrations.fiscal.application.metrics import AGENT_RESULTS, OFD_ACKS
from app.modules.integrations.fiscal.application.outbox import EventRecorderPort, acknowledge
from app.modules.integrations.fiscal.application.ports import (
    AgentTaskPort,
    CashRegisterRef,
    FiscalPort,
    FiscalProviderError,
    FiscalRepository,
    RegisterBinding,
)
from app.modules.integrations.fiscal.domain.boundary import (
    LOCKED_STATES,
    Acked,
    BoundaryError,
    parse_resend_result,
    parse_status_result,
    parse_zreport_result,
)

log = structlog.get_logger(__name__)

STATUS: Final = "fiscal.status"
RESEND: Final = "fiscal.resend_unsent"
ZREPORT: Final = "fiscal.zreport"
KINDS: Final = (STATUS, RESEND, ZREPORT)
STATUS_EXPIRES_S: Final = 900  # a fiscal.status not leased in 15 min is stale — the next cron run re-asks
RESEND_AFTER_STAGE: Final = 40  # 21 §16: the server queues fiscal.resend_unsent from the 40 h stage
NOTIFY_KIND: Final = "offline_48h"  # the M18 fiscal kind (21 §11); FM lock → stage "fm_locked"
PRIORITY: Final = {STATUS: 60, RESEND: 40, ZREPORT: 50}

TaskHandler = Callable[[AsyncSession, UUID, UUID, Any, Any], Awaitable[None]]


def _invalid(exc: BoundaryError) -> AppError:
    return AppError(
        ErrorCode.VALIDATION_ERROR, details=[ErrorDetail(field=exc.field, message_key=exc.message_key)]
    )


def task_payload(task: Any) -> Mapping[str, Any]:
    """The task's payload whatever the agent module passes (row mapping / dataclass / dict)."""
    raw = task.get("payload", task) if isinstance(task, Mapping) else getattr(task, "payload", None)
    return raw if isinstance(raw, Mapping) else {}


def _uuid(raw: object) -> UUID | None:
    try:
        return raw if isinstance(raw, UUID) else UUID(str(raw))
    except (TypeError, ValueError):
        return None


def _ref(reg: RegisterBinding) -> dict[str, Any]:
    """Task payload head: ``{cash_register_id, local_id}`` — ``local_id`` = ``fiscal_local_device_id`` =
    ``capabilities.fiscal.devices[].local_id`` (the agent does not know server ids)."""
    return {"cash_register_id": str(reg.id), "local_id": reg.local_id}


# --- dispatch -------------------------------------------------------------------------------------------
class FiscalAgentDispatcher:
    """Queues the ``fiscal.*`` tasks of a register's agent. Background callers (cron, posting) never fail on a
    disabled/revoked agent — the task is skipped and logged; BO-14 (``strict``) gets the error."""

    def __init__(self, tasks: AgentTaskPort | None) -> None:
        self._tasks = tasks

    @property
    def available(self) -> bool:
        return self._tasks is not None

    async def _enqueue(
        self,
        s: AsyncSession,
        tenant_id: UUID,
        reg: RegisterBinding,
        kind: str,
        payload: dict[str, Any],
        dedupe_key: str,
        *,
        strict: bool = False,
        created_by: UUID | None = None,
        expires_in_s: int | None = 86400,
    ) -> UUID | None:
        if reg.agent_id is None or reg.local_id is None:
            if strict:
                raise AppError(ErrorCode.DOC_INVALID_STATE, params={"reason": "no_fiscal_agent"})
            return None
        if self._tasks is None:
            if strict:
                raise AppError(ErrorCode.AGENT_CAPABILITY_DISABLED, params={"capability": "fiscal"})
            log.info("fiscal_agent_tasks_unavailable", kind=kind, cash_register_id=str(reg.id))
            return None
        try:
            async with s.begin_nested():
                return await self._tasks.enqueue(
                    s, tenant_id, reg.agent_id, kind, payload, priority=PRIORITY[kind], dedupe_key=dedupe_key,
                    created_by=created_by, expires_in_s=expires_in_s,
                )  # fmt: skip
        except AppError as exc:
            if strict:
                raise
            log.warning(
                "fiscal_agent_task_skipped", kind=kind, cash_register_id=str(reg.id), code=exc.code.value
            )
            return None

    async def status(
        self, s: AsyncSession, tenant_id: UUID, reg: RegisterBinding, at: datetime | None = None
    ) -> UUID | None:
        # one open fiscal.status per register: an offline agent never piles tasks up (contract 1 dedupe);
        # ``at`` is kept for the cron signature (the dedupe is by open task, not by time slot)
        return await self._enqueue(
            s, tenant_id, reg, STATUS, _ref(reg), f"{STATUS}:{reg.id}", expires_in_s=STATUS_EXPIRES_S
        )

    async def resend(
        self,
        s: AsyncSession,
        tenant_id: UUID,
        reg: RegisterBinding,
        key: str,
        *,
        strict: bool = False,
        created_by: UUID | None = None,
    ) -> UUID | None:
        return await self._enqueue(
            s,
            tenant_id,
            reg,
            RESEND,
            _ref(reg),
            f"{RESEND}:{reg.id}:{key}",
            strict=strict,
            created_by=created_by,
        )

    async def zreport(
        self, s: AsyncSession, tenant_id: UUID, reg: RegisterBinding, shift_id: UUID, receipt_id: UUID
    ) -> UUID | None:
        return await self._enqueue(
            s,
            tenant_id,
            reg,
            ZREPORT,
            {**_ref(reg), "shift_id": str(shift_id)},
            f"{ZREPORT}:{receipt_id}",
        )


async def apply_acks(
    repo: FiscalRepository, s: AsyncSession, acked: Iterable[Acked], source: str = "agent"
) -> int:
    """``acked[]`` → ``ofd_acked_at`` (first ack wins), marking codes → ``sold`` and the registers'
    ``last_unacked_receipt_at`` recomputed in this transaction (the block lifts at once, 16 §6)."""
    count = 0
    for a in acked:
        receipt_id = await repo.ack_fm(s, a.fm_terminal_id, a.fm_receipt_seq, a.acked_at)
        if receipt_id is None:
            continue  # unknown here yet (not synced) or acked before — the next status repeats it
        row = await repo.get(s, receipt_id)
        if row is not None:
            await acknowledge(repo, s, row, a.acked_at)
        count += 1
    if count:
        OFD_ACKS.labels(source).inc(count)
    return count


def _unwrap(result: Any) -> tuple[str, Mapping[str, Any], Any]:
    """``AgentTaskResult`` (contract 1: ``outcome``, ``data``, ``error``) or a bare ``data`` mapping."""
    if isinstance(result, Mapping):
        return "done", result, None
    data = getattr(result, "data", None)
    return (
        str(getattr(result, "outcome", "done")),
        data if isinstance(data, Mapping) else {},
        getattr(result, "error", None),
    )


def _adapted(kind: str, handler: TaskHandler) -> TaskHandler:
    """The A-05 entry point (contract 1): a ``failed``/``unknown`` outcome or a malformed result is audited
    and skipped — never raised (raising rolls back the A-05 and the agent re-sends the same result
    forever)."""

    async def run(s: AsyncSession, tenant_id: UUID, agent_id: UUID, task: Any, result: Any) -> None:
        outcome, data, error = _unwrap(result)
        task_id = getattr(task, "id", None)
        base = {"kind": kind, "task_id": str(task_id) if task_id else None, "agent_id": str(agent_id)}
        if outcome != "done":
            await record_audit(
                s, tenant_id=tenant_id, action="fiscal.agent_task_failed", entity="onec_agents",
                entity_id=agent_id, after={**base, "outcome": outcome, "error": error},
            )  # fmt: skip
            AGENT_RESULTS.labels(kind).inc()
            return
        try:
            async with s.begin_nested():
                await handler(s, tenant_id, agent_id, task, data)
        except AppError as exc:
            details = [{"field": d.field, "message_key": d.message_key} for d in exc.details]
            await record_audit(
                s, tenant_id=tenant_id, action="fiscal.agent_result_invalid", entity="onec_agents",
                entity_id=agent_id, after={**base, "code": exc.code.value, "details": details},
            )  # fmt: skip
            log.warning("fiscal_agent_result_invalid", **base, code=exc.code.value)
        AGENT_RESULTS.labels(kind).inc()

    return run


# --- result handlers ------------------------------------------------------------------------------------
class FiscalTaskHandlers:
    def __init__(self, repo: FiscalRepository, events: EventRecorderPort) -> None:
        self._repo = repo
        self._events = events

    def as_registry(self) -> dict[str, TaskHandler]:
        return {STATUS: _adapted(STATUS, self.status), RESEND: _adapted(RESEND, self.resend),
                ZREPORT: _adapted(ZREPORT, self.zreport)}  # fmt: skip

    async def _register(
        self, s: AsyncSession, tenant_id: UUID, agent_id: UUID, raw_id: object, kind: str
    ) -> RegisterBinding | None:
        register_id = _uuid(raw_id)
        reg = await self._repo.binding(s, register_id) if register_id else None
        if reg is None or reg.agent_id != agent_id:
            log.warning(
                "fiscal_result_foreign_agent", kind=kind, agent_id=str(agent_id), register=str(raw_id)
            )
            await record_audit(
                s,
                tenant_id=tenant_id,
                action="fiscal.status_foreign_agent",
                entity="onec_agents",
                entity_id=agent_id,
                after={"kind": kind, "cash_register_id": str(raw_id)},
            )
            return None
        return reg

    async def status(
        self, s: AsyncSession, tenant_id: UUID, agent_id: UUID, task: Any, result: Mapping[str, Any]
    ) -> None:
        try:
            res = parse_status_result(result)
        except BoundaryError as exc:
            raise _invalid(exc) from None
        reg = await self._register(
            s, tenant_id, agent_id, task_payload(task).get("cash_register_id") or res.cash_register_id, STATUS
        )
        if reg is None:
            return
        await self._repo.set_fm_status(s, reg.id, res.fm_state, res.pending_count)
        if res.fm_state != reg.fm_state:
            await record_audit(
                s,
                tenant_id=tenant_id,
                action="fiscal.fm_state_changed",
                entity="cash_registers",
                entity_id=reg.id,
                before={"fm_state": reg.fm_state},
                after={
                    "fm_state": res.fm_state,
                    "pending_count": res.pending_count,
                    "agent_id": str(agent_id),
                },
            )
            if res.fm_state in LOCKED_STATES:
                at = datetime.now(UTC)
                await self._events.record_event(
                    s,
                    tenant_id,
                    NOTIFY_KIND,
                    {
                        "cash_register_id": str(reg.id),
                        "branch_id": str(reg.branch_id),
                        "name": reg.name,
                        "stage": "fm_locked",
                        "fm_state": res.fm_state,
                    },
                    f"fiscal_fm:{reg.id}:{res.fm_state}:{at:%Y%m%d%H%M}",
                )
        await apply_acks(self._repo, s, res.acked)
        oldest = await self._repo.oldest_unacked(s, reg.id)
        await self._repo.set_last_unacked(s, reg.id, oldest[1] if oldest else None)

    async def resend(
        self, s: AsyncSession, tenant_id: UUID, agent_id: UUID, task: Any, result: Mapping[str, Any]
    ) -> None:
        try:
            res = parse_resend_result(result)
        except BoundaryError as exc:
            raise _invalid(exc) from None
        reg = await self._register(s, tenant_id, agent_id, task_payload(task).get("cash_register_id"), RESEND)
        if reg is None:
            return
        acked = await apply_acks(self._repo, s, res.acked)
        oldest = await self._repo.oldest_unacked(s, reg.id)
        await self._repo.set_last_unacked(s, reg.id, oldest[1] if oldest else None)
        await record_audit(
            s,
            tenant_id=tenant_id,
            action="fiscal.resend_unsent",
            entity="cash_registers",
            entity_id=reg.id,
            after={"sent": res.sent, "failed": res.failed, "acked": acked, "agent_id": str(agent_id)},
        )

    async def zreport(
        self, s: AsyncSession, tenant_id: UUID, agent_id: UUID, task: Any, result: Mapping[str, Any]
    ) -> None:
        payload = task_payload(task)
        try:
            z = parse_zreport_result(result)
        except BoundaryError as exc:
            raise _invalid(exc) from None
        reg = await self._register(s, tenant_id, agent_id, payload.get("cash_register_id"), ZREPORT)
        shift_id = _uuid(payload.get("shift_id"))
        if reg is None or shift_id is None:
            return
        fm_z = {"z_number": z.z_number, "totals": dict(z.totals), "closed_at": z.closed_at.isoformat()}
        row = await self._repo.z_of_shift(s, shift_id)
        if row is None:  # the shift closed without a Z row (21 §16: the agent's ZReport creates it)
            receipt_id = uuid7()
            await self._repo.insert_receipt(
                s,
                {
                    "id": receipt_id,
                    "tenant_id": tenant_id,
                    "kind": "z_report",
                    "sale_id": None,
                    "return_id": None,
                    "debt_payment_id": None,
                    "cash_register_id": reg.id,
                    "shift_id": shift_id,
                    "receipt_seq": None,
                    "fm_terminal_id": None,
                    "fm_receipt_seq": None,
                    "fiscal_at": None,
                    "payload": "{}",
                    "fiscal_sign": None,
                    "qr_url": None,
                    "payment_form": None,
                    "delivery": "printed",
                    "delivery_reason": None,
                    "sent_at": None,
                    "offline_since": None,
                    "status": "pending",
                    "created_at": z.closed_at,
                },
            )
        elif row.cash_register_id != reg.id or row.status == "fiscalized":
            return  # another register's shift, or already filled (idempotent)
        else:
            receipt_id = row.id
        await self._repo.set_z_fiscalized(s, receipt_id, z.fm_terminal_id, z.closed_at, fm_z)


# --- cron: fiscal.status sweep, provider ack poller -----------------------------------------------------
class AgentStatusSweep:
    """Every 5 min: one ``fiscal.status`` per register bound to an agent (deduped per 5-minute slot)."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        repo: FiscalRepository,
        dispatcher: FiscalAgentDispatcher,
    ) -> None:
        self._sf = session_factory
        self._repo = repo
        self._dispatch = dispatcher

    async def run(self, tenant_id: UUID, at: datetime | None = None) -> dict[str, int]:
        queued = 0
        async with self._sf() as s, tenant_transaction(s, tenant_id):
            registers = await self._repo.bound_registers(s)
            for reg in registers:
                queued += int(await self._dispatch.status(s, tenant_id, reg, at) is not None)
        return {"registers": len(registers), "queued": queued}


class ProviderAckPoller:
    """Server-side providers (``partner_cloud``, ``fake``): ``resend_unsent`` per register with fiscalized but
    unacked receipts; ``acked[]`` → ``ofd_acked_at`` (the partner's FM signs offline too — 21 §1)."""

    def __init__(
        self, session_factory: async_sessionmaker[AsyncSession], repo: FiscalRepository, port: FiscalPort
    ) -> None:
        self._sf = session_factory
        self._repo = repo
        self._port = port

    async def run(self, tenant_id: UUID) -> dict[str, int]:
        async with self._sf() as s, tenant_transaction(s, tenant_id):
            registers = await self._repo.unacked_by_register(s, provider_side=True)
        acked = failed = 0
        for register_id, _ in registers:  # the provider is never called inside a business transaction
            try:
                res = await self._port.resend_unsent(CashRegisterRef(register_id, tenant_id))
            except FiscalProviderError as exc:
                failed += 1
                log.info("fiscal_resend_failed", cash_register_id=str(register_id), kind=exc.kind)
                continue
            async with self._sf() as s, tenant_transaction(s, tenant_id):
                acked += await apply_acks(self._repo, s, res.acked, "provider")
        return {"registers": len(registers), "acked": acked, "failed": failed}


# --- contract 4: readiness and alerts --------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class FiscalReadiness:
    period: str
    pending_fiscal_receipts: int
    not_fiscalized: int
    unacked: int
    oldest_unacked_at: datetime | None

    @property
    def blocked(self) -> bool:
        return self.pending_fiscal_receipts > 0


@dataclass(frozen=True, slots=True)
class FiscalAlerts:
    fiscal_unacked: int
    fiscal_blocked: int
    fiscal_device_locked: int
    fiscal_failed: int


def period_bounds(period: str) -> tuple[date, date]:
    try:
        year, month = (int(x) for x in period.split("-", 1))
        start = date(year, month, 1)
    except ValueError:
        raise AppError(ErrorCode.VALIDATION_ERROR, params={"field": "period"}) from None
    end = date(year + (month == 12), month % 12 + 1, 1)
    return start, date.fromordinal(end.toordinal() - 1)


async def readiness(repo: FiscalRepository, s: AsyncSession, period: str) -> FiscalReadiness:
    start, end = period_bounds(period)
    not_fiscalized, unacked, oldest = await repo.readiness(s, start, end)
    return FiscalReadiness(period, not_fiscalized + unacked, not_fiscalized, unacked, oldest)


async def alerts(
    repo: FiscalRepository, s: AsyncSession, at: datetime, branch_ids: tuple[UUID, ...] | None
) -> FiscalAlerts:
    return FiscalAlerts(*(await repo.alert_counts(s, at, branch_ids)))
