"""Do'kon agent ``card_terminal`` capability — server side (qaror #71; 21 §16, 23 §4.2, 34 §14.3).

* ``card.status`` (every 5 min, cron ``card_status_sweep``) — payload
  ``{"terminals":[{card_terminal_id, local_id}]}`` (all of the agent's ``agent_ecr`` terminals); result
  ``{terminals:[{card_terminal_id, local_id, status, tid, last_tx_at}], unresolved:[CardTxResult +
  resolved_by + local_id]}`` →
  ``card_terminals.health_status``/``health_checked_at``; an ``unresolved`` item that the terminal answered
  (``approved``/``declined``) closes the ``pending``/``unknown`` attempt with ``resolved_by='status_query'``.
  A failed task → every named terminal ``offline`` (``CARD_TERMINAL_BUSY`` → ``busy``).
* ``card.settlement`` (shift closed without the POS, or cron ``card_settlement_sweep`` at 23:30 Tashkent for
  terminals without a settlement of the day) — payload ``{card_terminal_id, local_id, shift_id?}``; result
  ``SettlementResult`` (``count``/``total_tiyin`` — purchases, ``refund_count``/``refund_total_tiyin`` —
  refunds, as in the POS ``settlementItem`` mapping) → ``card_terminal_settlements`` through
  :class:`SettlementWriter` (``id`` = task id, ``created_by`` NULL, ``device_id`` = the agent's device;
  ``expected_*``/``variance``/``status``; mismatch →
  audit ``card.settlement.mismatch`` + M18). A failed task → a ``failed`` settlement row.

Handlers never raise for a bad result (that would roll back A-05 and the agent would resend it forever) —
they record ``sync_exceptions(kind='card_result_mismatch', details.reason='malformed_result')`` instead.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, Final, Protocol
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.db.session import tenant_transaction
from app.core.errors import AppError
from app.modules.integrations.card_terminal.application.contracts import SettlementInput
from app.modules.integrations.card_terminal.application.ports import (
    AgentRow,
    CardRepository,
    CardTxResult,
    TerminalRow,
)
from app.modules.integrations.card_terminal.application.schemas import card_result_from_port
from app.modules.integrations.card_terminal.application.settlements import SettlementWriter
from app.modules.integrations.card_terminal.application.transactions import ENTITY, TxWriter
from app.modules.integrations.card_terminal.domain.model import (
    HEALTH_STATUSES,
    tashkent_date,
)

STATUS_KIND: Final = "card.status"
SETTLEMENT_KIND: Final = "card.settlement"
STATUS_PRIORITY: Final = 100  # periodic
SETTLEMENT_PRIORITY: Final = 50


class AgentTasks(Protocol):
    """``AgentTaskPort`` of the agent slice (contracts/agent-tasks.md §1) — structural, the part we use."""

    async def enqueue(
        self,
        s: AsyncSession,
        tenant_id: UUID,
        agent_id: UUID,
        kind: str,
        payload: dict[str, Any],
        *,
        priority: int = 100,
        not_before: datetime | None = None,
        dedupe_key: str | None = None,
        created_by: UUID | None = None,
        expires_in_s: int | None = 86400,
        timeout_s: int | None = None,
    ) -> UUID: ...


class TaskView(Protocol):
    """``AgentTaskView`` (contracts/agent-tasks.md §2) — the fields the card handlers read."""

    @property
    def id(self) -> UUID: ...
    @property
    def kind(self) -> str: ...
    @property
    def payload(self) -> dict[str, Any]: ...


class TaskResult(Protocol):
    """``AgentTaskResult`` (contracts/agent-tasks.md §2)."""

    @property
    def outcome(self) -> str: ...  # done | failed | unknown
    @property
    def data(self) -> dict[str, Any]: ...
    @property
    def error(self) -> dict[str, Any] | None: ...


@dataclass(frozen=True, slots=True)
class SweepReport:
    enqueued: int
    skipped: int


def _tiyin(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _uuid(value: object) -> UUID | None:
    try:
        return UUID(str(value)) if value is not None else None
    except ValueError:
        return None


def _money(tiyin: int) -> Decimal:
    return (Decimal(tiyin) / 100).quantize(Decimal("0.01"))


class CardAgentService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        repo: CardRepository,
        tasks: AgentTasks,
        settlements: SettlementWriter,
    ) -> None:
        self._sf = session_factory
        self._repo = repo
        self._tasks = tasks
        self._settlements = settlements
        self._writer = TxWriter(repo)

    # --- enqueue ------------------------------------------------------------------------------------
    async def enqueue_status(
        self, s: AsyncSession, tenant_id: UUID, agent_id: UUID, *, created_by: UUID | None = None
    ) -> UUID | None:
        terminals = [t for t in await self._repo.agent_terminals(s, agent_id) if t.status == "active"]
        if not terminals:
            return None
        payload = {"terminals": [{"card_terminal_id": str(t.id), "local_id": t.local_id} for t in terminals]}
        return await self._tasks.enqueue(
            s, tenant_id, agent_id, STATUS_KIND, payload, priority=STATUS_PRIORITY,
            dedupe_key=f"{STATUS_KIND}:{agent_id}", created_by=created_by, expires_in_s=600,
        )  # fmt: skip

    async def enqueue_settlement(
        self,
        s: AsyncSession,
        tenant_id: UUID,
        terminal: TerminalRow,
        *,
        business_date: date,
        shift_id: UUID | None = None,
        created_by: UUID | None = None,
    ) -> UUID:
        if terminal.adapter != "agent_ecr" or terminal.agent_id is None or terminal.local_id is None:
            raise ValueError("card.settlement needs an agent_ecr terminal")
        payload: dict[str, Any] = {"card_terminal_id": str(terminal.id), "local_id": terminal.local_id}
        if shift_id is not None:
            payload["shift_id"] = str(shift_id)
        return await self._tasks.enqueue(
            s, tenant_id, terminal.agent_id, SETTLEMENT_KIND, payload, priority=SETTLEMENT_PRIORITY,
            dedupe_key=f"{SETTLEMENT_KIND}:{terminal.id}:{business_date.isoformat()}", created_by=created_by,
        )  # fmt: skip

    async def status_sweep(self, tenant_id: UUID) -> SweepReport:
        """Cron ``card_status_sweep`` (every 5 min): one deduplicated ``card.status`` per capable agent."""
        enqueued = skipped = 0
        async with self._sf() as s, tenant_transaction(s, tenant_id):
            for agent_id in await self._repo.status_sweep_agents(s):
                try:
                    if await self.enqueue_status(s, tenant_id, agent_id) is not None:
                        enqueued += 1
                except AppError:  # revoked between the query and the enqueue
                    skipped += 1
        return SweepReport(enqueued, skipped)

    async def settlement_sweep(self, tenant_id: UUID, *, business_date: date) -> SweepReport:
        """Cron ``card_settlement_sweep`` (23:30 Tashkent): terminals without a settlement of the day."""
        enqueued = skipped = 0
        async with self._sf() as s, tenant_transaction(s, tenant_id):
            for row in await self._repo.settlement_sweep_terminals(s, business_date):
                terminal = await self._repo.terminal(s, row.id)
                if terminal is None:
                    continue
                try:
                    await self.enqueue_settlement(s, tenant_id, terminal, business_date=business_date)
                    enqueued += 1
                except AppError:
                    skipped += 1
        return SweepReport(enqueued, skipped)

    # --- result handlers (run inside the A-05 transaction) -------------------------------------------
    async def handle_status(
        self, s: AsyncSession, tenant_id: UUID, agent_id: UUID, task: TaskView, result: TaskResult
    ) -> None:
        agent = await self._repo.agent(s, agent_id)
        own = {t.id: t for t in await self._repo.agent_terminals(s, agent_id)}
        by_local = {t.local_id: t for t in own.values() if t.local_id}
        if result.outcome != "done":
            code = str((result.error or {}).get("code") or "")
            health = "busy" if code == "CARD_TERMINAL_BUSY" else "offline"
            for named in _named_terminals(task.payload, own):
                await self._repo.update_health(s, named, health)
            return
        data = result.data if isinstance(result.data, Mapping) else {}
        for item in data.get("terminals") or []:
            if not isinstance(item, Mapping):
                continue
            terminal = own.get(_uuid(item.get("card_terminal_id")) or UUID(int=0)) or by_local.get(
                str(item.get("local_id") or "")
            )
            status = item.get("status")
            if terminal is not None and status in HEALTH_STATUSES:
                await self._repo.update_health(s, terminal.id, str(status))
        for raw in data.get("unresolved") or []:
            await self._resolve(s, tenant_id, agent, own, by_local, raw)

    async def _resolve(
        self,
        s: AsyncSession,
        tenant_id: UUID,
        agent: AgentRow | None,
        own: Mapping[UUID, TerminalRow],
        by_local: Mapping[str, TerminalRow],
        raw: object,
    ) -> None:
        device_id = None if agent is None else agent.device_id
        item = dict(raw) if isinstance(raw, Mapping) else {}
        attempt_id = _uuid(item.get("attempt_id"))
        tx = None if attempt_id is None else await self._repo.tx(s, attempt_id, lock=True)
        if tx is None or tx.card_terminal_id not in own or tx.status not in ("pending", "unknown"):
            return  # unknown attempt, another agent's terminal, or already final — nothing to do
        port = {k: v for k, v in item.items() if k in CardTxResult.model_fields}
        try:
            parsed = CardTxResult.model_validate(port)
        except ValidationError as exc:
            await self._malformed(
                s, tx.id, device_id, item, [".".join(map(str, e["loc"])) for e in exc.errors()]
            )
            return
        if parsed.status not in ("approved", "declined", "cancelled", "error"):
            return  # still unknown on the terminal too
        terminal = own[tx.card_terminal_id]
        amount = int((tx.amount * 100).to_integral_value())
        card_result = card_result_from_port(
            parsed, card_terminal_id=terminal.id, requested_amount_tiyin=amount, resolved_by="status_query",
            original_attempt_id=tx.original_transaction_id,
        )  # fmt: skip
        try:
            await self._writer.resolve_from_agent(
                s, tenant_id=tenant_id, terminal=terminal, tx=tx, card_result=card_result, device_id=device_id
            )
        except AppError as exc:
            await self._malformed(
                s, tx.id, device_id, item, [d.field or "" for d in exc.details] or [exc.code.value]
            )

    async def _malformed(
        self,
        s: AsyncSession,
        tx_id: UUID,
        device_id: UUID | None,
        item: Mapping[str, Any],
        fields: Sequence[str],
    ) -> None:
        await self._repo.insert_sync_exception(
            s, kind="card_result_mismatch", device_id=device_id, client_event_id=None, doc_type=ENTITY,
            doc_id=tx_id,
            details={"reason": "malformed_result", "source": STATUS_KIND, "fields": list(fields),
                     "terminal_response": _scrub(item)},
        )  # fmt: skip

    async def handle_settlement(
        self, s: AsyncSession, tenant_id: UUID, agent_id: UUID, task: TaskView, result: TaskResult
    ) -> None:
        agent = await self._repo.agent(s, agent_id)
        device_id = None if agent is None else agent.device_id
        payload = task.payload if isinstance(task.payload, Mapping) else {}
        terminal_id = _uuid(payload.get("card_terminal_id"))
        terminal = None if terminal_id is None else await self._repo.terminal(s, terminal_id)
        if terminal is None or terminal.agent_id != agent_id:
            return
        shift_id = _uuid(payload.get("shift_id"))
        data = result.data if isinstance(result.data, Mapping) else {}
        now = datetime.now(UTC)
        if result.outcome != "done":
            item = SettlementInput(
                id=task.id, card_terminal_id=terminal.id, shift_id=shift_id, batch_no=None,
                business_date=tashkent_date(now), settled_at=now, purchase_count=0,
                purchase_total=Decimal("0.00"), refund_count=0, refund_total=Decimal("0.00"), failed=True,
                terminal_response={"error": result.error or {}, "outcome": result.outcome},
            )  # fmt: skip
        else:
            total, refund_total = _tiyin(data.get("total_tiyin")), _tiyin(data.get("refund_total_tiyin")) or 0
            count, refund_count = _tiyin(data.get("count")), _tiyin(data.get("refund_count")) or 0
            settled_at = _parse_dt(data.get("settled_at"))
            if total is None or count is None or settled_at is None or count < 0 or refund_total < 0:
                await self._repo.insert_sync_exception(
                    s, kind="card_result_mismatch", device_id=device_id, client_event_id=None,
                    doc_type="card_terminals", doc_id=terminal.id,
                    details={"reason": "malformed_result", "source": SETTLEMENT_KIND, "task_id": str(task.id),
                             "terminal_response": _scrub(data)},
                )  # fmt: skip
                return
            batch = data.get("batch_no")
            item = SettlementInput(
                id=task.id, card_terminal_id=terminal.id, shift_id=shift_id,
                batch_no=str(batch)[:32] if batch else None, business_date=tashkent_date(settled_at),
                settled_at=settled_at, purchase_count=count, purchase_total=_money(total),
                refund_count=refund_count,
                refund_total=_money(refund_total), terminal_response=_scrub(data),
            )  # fmt: skip
        if shift_id is not None and not await self._repo.shift_exists(s, shift_id):
            item = SettlementInput(**{**_fields(item), "shift_id": None})
        try:
            async with s.begin_nested():  # a rejected insert must not abort the A-05 transaction
                await self._settlements.record(
                    s, tenant_id=tenant_id, branch_id=terminal.branch_id, item=item, actor_user_id=None,
                    device_id=device_id, client_event_id=None,
                )  # fmt: skip
        except AppError as exc:  # e.g. the same batch_no already reported by the POS
            await self._repo.insert_sync_exception(
                s, kind="card_result_mismatch", device_id=device_id, client_event_id=None,
                doc_type="card_terminals", doc_id=terminal.id,
                details={"reason": "settlement_rejected", "code": exc.code.value, "task_id": str(task.id),
                         "fields": [d.field for d in exc.details], "batch_no": item.batch_no},
            )  # fmt: skip


def _named_terminals(payload: object, own: Mapping[UUID, TerminalRow]) -> list[UUID]:
    items = payload.get("terminals") if isinstance(payload, Mapping) else None
    if not isinstance(items, list) or not items:
        return [t.id for t in own.values() if t.status == "active"]
    named = [_uuid(i.get("card_terminal_id")) for i in items if isinstance(i, Mapping)]
    return [t for t in named if t is not None and t in own]


def _parse_dt(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


_PAN_KEYS: Final = frozenset({"pan", "track", "track2", "cvv", "pin_block", "card_number"})


def _scrub(value: Mapping[str, Any]) -> dict[str, Any]:
    """Keep the raw result for review without anything PAN-like (15 §9.3)."""
    return {k: v for k, v in value.items() if str(k).lower() not in _PAN_KEYS}


def _fields(item: SettlementInput) -> dict[str, Any]:
    return {name: getattr(item, name) for name in SettlementInput.__dataclass_fields__}
