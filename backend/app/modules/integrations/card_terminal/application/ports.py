"""``CardTerminalPort`` contract (21 §9.4, 23 §1 item 16) and the repository port of the card slice.

The Pydantic DTOs below are the single source of the port schema: the web POS TypeScript types
(``web/packages/shared/lib/src/card-terminal/types.ts``) and the agent's C# DTOs mirror them field by
field. Amounts at the port boundary are integer tiyin (01 #26); the API (``CardResult``, 18 §2.7) uses
``Money`` strings. ``purchase`` is never retried automatically; ``get_status``/``health``/``settlement``
are safe to repeat (3 × 2 s).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

PortStatus = Literal["approved", "declined", "cancelled", "timeout", "unknown", "error"]
CardScheme = Literal["uzcard", "humo", "visa", "mastercard", "unionpay", "mir", "other"]
CardTypeValue = Literal["personal", "corporate", "social", "unknown"]
EntryMode = Literal["chip", "contactless", "magstripe", "fallback"]
HealthStatus = Literal["online", "busy", "offline", "error"]
TxKind = Literal["purchase", "refund", "void"]

# 21 §9.4 "Taymautlar"
CONNECT_TIMEOUT_S = 5
PURCHASE_TIMEOUT_S = 120
REFUND_VOID_TIMEOUT_S = 60
HEALTH_TIMEOUT_S = 3
AGENT_LONG_POLL_S = 125


class _Dto(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class TerminalRef(_Dto):
    card_terminal_id: UUID
    local_id: str | None = None


class CardPurchaseRequest(_Dto):
    attempt_id: UUID = Field(
        description="UUIDv7, written locally before the call; ERN/order ref on the terminal"
    )
    terminal: TerminalRef
    amount_tiyin: int = Field(gt=0)
    currency: Literal["UZS"] = "UZS"
    cash_register_id: UUID
    client_event_id: UUID
    receipt_seq: int | None = None


class CardRefundRequest(_Dto):
    attempt_id: UUID
    terminal: TerminalRef
    amount_tiyin: int = Field(gt=0)
    original_rrn: str | None = None
    original_attempt_id: UUID | None = None


class CardVoidRequest(_Dto):
    attempt_id: UUID
    terminal: TerminalRef
    amount_tiyin: int = Field(gt=0)
    original_attempt_id: UUID


class CardTxResult(_Dto):
    """What a terminal adapter returns. ``card_mask`` may arrive un-normalised (``860031******1234``) —
    :func:`app.modules.integrations.card_terminal.domain.model.normalize_mask` makes it 4+4 and keeps the
    BIN only in memory."""

    attempt_id: UUID
    kind: TxKind
    status: PortStatus
    amount_tiyin: int | None = None
    approval_code: str | None = None
    rrn: str | None = None
    stan: str | None = None
    card_mask: str | None = None
    card_scheme: CardScheme | None = None
    card_type: CardTypeValue | None = None
    entry_mode: EntryMode | None = None
    tid: str | None = None
    mid: str | None = None
    acquirer: str | None = None
    tx_at: datetime | None = None
    decline_code: str | None = None
    decline_message: str | None = None
    slip_text: str | None = None


class SchemeTotal(_Dto):
    card_scheme: CardScheme
    count: int = Field(ge=0)
    total_tiyin: int = Field(ge=0)


class SettlementResult(_Dto):
    tid: str | None
    batch_no: str | None
    count: int = Field(ge=0)
    total_tiyin: int
    by_scheme: list[SchemeTotal] = Field(default_factory=list)
    settled_at: datetime
    refund_count: int = Field(default=0, ge=0)
    refund_total_tiyin: int = Field(default=0, ge=0)


class TerminalHealth(_Dto):
    status: HealthStatus
    tid: str | None = None
    last_tx_at: datetime | None = None
    message: str | None = None


class CardTerminalError(Exception):
    """Transport-level failure of an adapter (``CARD_TERMINAL_UNREACHABLE``/``_BUSY``/``_TIMEOUT``)."""

    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code


class CardTerminalPort(Protocol):
    async def purchase(self, req: CardPurchaseRequest) -> CardTxResult: ...  # never retried automatically

    async def refund(self, req: CardRefundRequest) -> CardTxResult: ...

    async def void(self, req: CardVoidRequest) -> CardTxResult: ...  # same day, before settlement

    async def get_status(self, attempt_id: UUID) -> CardTxResult: ...  # resolves "unknown"

    async def get_last_transaction(self, terminal: TerminalRef) -> CardTxResult | None: ...

    async def settlement(self, terminal: TerminalRef) -> SettlementResult: ...

    async def health(self, terminal: TerminalRef) -> TerminalHealth: ...


# --- persistence port ------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TerminalRow:
    id: UUID
    tenant_id: UUID
    branch_id: UUID
    cash_register_id: UUID | None
    name: str
    vendor: str
    model: str | None
    adapter: str
    driver: str
    agent_id: UUID | None
    local_id: str | None
    host: str | None
    port: int | None
    vendor_terminal_ref: str | None
    tid: str | None
    mid: str | None
    acquirer_counterparty_id: UUID | None
    status: str
    is_default: bool
    capabilities: Mapping[str, Any]
    health_status: str
    health_checked_at: datetime | None
    version: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class TxRow:
    id: UUID
    tenant_id: UUID
    branch_id: UUID
    card_terminal_id: UUID
    cash_register_id: UUID | None
    shift_id: UUID | None
    device_id: UUID | None
    kind: str
    original_transaction_id: UUID | None
    amount: Decimal
    approved_amount: Decimal | None
    status: str
    approval_code: str | None
    rrn: str | None
    stan: str | None
    card_mask: str | None
    card_scheme: str | None
    card_type: str | None
    card_type_source: str | None
    entry_mode: str | None
    tid: str | None
    mid: str | None
    acquirer: str | None
    decline_code: str | None
    decline_message: str | None
    resolved_by: str | None
    resolved_by_user_id: UUID | None
    client_event_id: UUID | None
    doc_type: str | None
    doc_id: UUID | None
    settlement_id: UUID | None
    requested_at: datetime
    tx_at: datetime | None
    resolved_at: datetime | None
    created_by: UUID
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class SettlementRow:
    id: UUID
    card_terminal_id: UUID
    status: str
    net_total: Decimal
    expected_total: Decimal
    variance: Decimal


@dataclass(frozen=True, slots=True)
class TerminalFilter:
    branch_ids: Sequence[UUID]  # empty = all
    branch_id: UUID | None
    cash_register_id: UUID | None
    status: str | None


@dataclass(frozen=True, slots=True)
class OrphanRow:
    id: UUID
    card_terminal_id: UUID
    branch_id: UUID
    device_id: UUID | None
    client_event_id: UUID | None
    amount: Decimal
    rrn: str | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class AgentRow:
    """A Do'kon agent as the card slice needs it (``app.onec_agents``; 34 §14.2 ``capabilities``)."""

    id: UUID
    device_id: UUID
    status: str  # active | revoked
    capabilities: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class SweepTerminal:
    """An active ``agent_ecr`` terminal whose agent can take ``card.*`` tasks."""

    id: UUID
    agent_id: UUID
    local_id: str
    branch_id: UUID


class CardRepository(Protocol):
    # Do'kon agent (read-only; 0028 store_agent)
    async def agent(self, s: AsyncSession, agent_id: UUID) -> AgentRow | None: ...
    async def agent_terminals(self, s: AsyncSession, agent_id: UUID) -> list[TerminalRow]: ...
    async def settlement_sweep_terminals(
        self, s: AsyncSession, business_date: date
    ) -> list[SweepTerminal]: ...
    async def status_sweep_agents(self, s: AsyncSession) -> list[UUID]: ...
    async def update_health(self, s: AsyncSession, terminal_id: UUID, health_status: str) -> None: ...
    # terminals
    async def terminal(
        self, s: AsyncSession, terminal_id: UUID, *, lock: bool = False
    ) -> TerminalRow | None: ...
    async def list_terminals(
        self, s: AsyncSession, flt: TerminalFilter, page: int, size: int
    ) -> tuple[list[TerminalRow], int]: ...
    async def insert_terminal(self, s: AsyncSession, values: Mapping[str, Any]) -> None: ...
    async def update_terminal(
        self, s: AsyncSession, terminal_id: UUID, values: Mapping[str, Any]
    ) -> None: ...
    async def clear_default(self, s: AsyncSession, cash_register_id: UUID, except_id: UUID) -> None: ...
    async def active_terminal_count(self, s: AsyncSession, cash_register_id: UUID) -> int: ...
    async def register_branch(self, s: AsyncSession, cash_register_id: UUID) -> UUID | None: ...
    async def manual_fallback_setting(self, s: AsyncSession) -> str | None: ...
    async def device_register(self, s: AsyncSession, device_id: UUID) -> UUID | None: ...
    async def approval_request_resolver(self, s: AsyncSession, request_id: UUID) -> UUID | None: ...
    async def shift_exists(self, s: AsyncSession, shift_id: UUID) -> bool: ...
    async def tid_taken(self, s: AsyncSession, tid: str, exclude: UUID) -> bool: ...
    async def agent_local_taken(
        self, s: AsyncSession, agent_id: UUID, local_id: str, exclude: UUID
    ) -> bool: ...
    # transactions
    async def tx(self, s: AsyncSession, tx_id: UUID, *, lock: bool = False) -> TxRow | None: ...
    async def insert_tx(self, s: AsyncSession, values: Mapping[str, Any]) -> None: ...
    async def update_tx(self, s: AsyncSession, tx_id: UUID, values: Mapping[str, Any]) -> None: ...
    async def clone_tx(
        self,
        s: AsyncSession,
        source_id: UUID,
        new_id: UUID,
        *,
        doc: tuple[str, UUID],
        client_event_id: UUID | None,
    ) -> None: ...
    async def unresolved_on_terminal(
        self, s: AsyncSession, terminal_id: UUID, exclude: UUID
    ) -> list[str]: ...
    async def unresolved_in_shift(self, s: AsyncSession, shift_id: UUID) -> int: ...
    async def rrn_taken(self, s: AsyncSession, tid: str, rrn: str, exclude: UUID) -> UUID | None: ...
    async def bin_rule_type(self, s: AsyncSession, bin_value: str, on: date) -> str | None: ...
    async def doc_by_client_event(
        self, s: AsyncSession, client_event_id: UUID
    ) -> tuple[str, UUID] | None: ...
    async def manager_resolved_by_event(self, s: AsyncSession, client_event_id: UUID) -> list[TxRow]: ...
    # settlements
    async def settlement(self, s: AsyncSession, settlement_id: UUID) -> SettlementRow | None: ...
    async def unbatched_totals(self, s: AsyncSession, terminal_id: UUID) -> tuple[int, Decimal, Decimal]: ...
    async def insert_settlement(self, s: AsyncSession, values: Mapping[str, Any]) -> SettlementRow: ...
    async def stamp_settlement(self, s: AsyncSession, terminal_id: UUID, settlement_id: UUID) -> None: ...
    # orphan sweep
    async def orphans(self, s: AsyncSession, older_than: datetime, limit: int) -> list[OrphanRow]: ...
    async def orphan_reported(self, s: AsyncSession, tx_id: UUID) -> bool: ...
    async def insert_sync_exception(
        self,
        s: AsyncSession,
        *,
        kind: str,
        device_id: UUID | None,
        client_event_id: UUID | None,
        doc_type: str | None,
        doc_id: UUID | None,
        details: Mapping[str, Any],
    ) -> None: ...
