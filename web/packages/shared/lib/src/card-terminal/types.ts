/**
 * `CardTerminalPort` DTOs (21 §9.4, 24 §6.5) — field-for-field mirror of the backend Pydantic contract
 * `backend/app/modules/integrations/card_terminal/application/ports.py` (wire names, snake_case). The
 * mirror is checked by `contract.test.ts` (it reads ports.py / schemas.py). Amounts at the port boundary are
 * integer tiyin; `CardResult` (18 §2.7) carries Money strings. No PAN / track / CVV field exists anywhere.
 */
import type { Money } from "#/money/index.ts";

export type PortStatus = "approved" | "declined" | "cancelled" | "timeout" | "unknown" | "error";
export type CardScheme = "uzcard" | "humo" | "visa" | "mastercard" | "unionpay" | "mir" | "other";
export type CardTypeValue = "personal" | "corporate" | "social" | "unknown";
export type CardTypeSource = "terminal" | "bin_table";
export type EntryMode = "chip" | "contactless" | "magstripe" | "fallback";
export type HealthStatus = "online" | "busy" | "offline" | "error";
export type TxKind = "purchase" | "refund" | "void";
export type TxStatus = "pending" | "approved" | "declined" | "unknown" | "voided";
export type ResolvedBy = "auto" | "status_query" | "manager";
export type TerminalAdapter = "agent_ecr" | "cloud" | "android_intent" | "softpos" | "fake";

/** 21 §9.4 "Taymautlar" (ms). */
export const CARD_TIMEOUTS = Object.freeze({
  connect: 5_000,
  purchase: 120_000,
  refundVoid: 60_000,
  health: 3_000,
  agentLongPoll: 125_000,
  status: 10_000,
  cancelPending: 5_000,
});

export interface TerminalRef {
  card_terminal_id: string;
  local_id: string | null;
}

export interface CardPurchaseRequest {
  attempt_id: string;
  terminal: TerminalRef;
  amount_tiyin: number;
  currency: "UZS";
  cash_register_id: string;
  client_event_id: string;
  receipt_seq?: number | null;
}

export interface CardRefundRequest {
  attempt_id: string;
  terminal: TerminalRef;
  amount_tiyin: number;
  original_rrn?: string | null;
  original_attempt_id?: string | null;
}

export interface CardVoidRequest {
  attempt_id: string;
  terminal: TerminalRef;
  amount_tiyin: number;
  original_attempt_id: string;
}

export interface CardTxResult {
  attempt_id: string;
  kind: TxKind;
  status: PortStatus;
  amount_tiyin: number | null;
  approval_code: string | null;
  rrn: string | null;
  stan: string | null;
  /** May arrive un-normalised from a driver (`860031******1234`) — `toCardResult` makes it 4+4. */
  card_mask: string | null;
  card_scheme: CardScheme | null;
  card_type: CardTypeValue | null;
  entry_mode: EntryMode | null;
  tid: string | null;
  mid: string | null;
  acquirer: string | null;
  tx_at: string | null;
  decline_code: string | null;
  decline_message: string | null;
  slip_text?: string | null;
}

export interface SchemeTotal {
  card_scheme: CardScheme;
  count: number;
  total_tiyin: number;
}

export interface SettlementResult {
  tid: string | null;
  batch_no: string | null;
  count: number;
  total_tiyin: number;
  by_scheme: SchemeTotal[];
  settled_at: string;
  refund_count?: number;
  refund_total_tiyin?: number;
}

export interface TerminalHealth {
  status: HealthStatus;
  tid: string | null;
  last_tx_at: string | null;
  message?: string | null;
}

/** `CardResult` (18 §2.7) — what goes into `payments[].card_result` and `POST /card-terminal-transactions`. */
export interface CardResult {
  attempt_id: string;
  card_terminal_id: string;
  kind: TxKind;
  original_attempt_id: string | null;
  status: Exclude<TxStatus, "pending">;
  amount: Money;
  approval_code: string | null;
  rrn: string | null;
  stan: string | null;
  card_mask: string | null;
  card_scheme: CardScheme | null;
  card_type: CardTypeValue | null;
  card_type_source: CardTypeSource | null;
  entry_mode: EntryMode | null;
  tid: string | null;
  mid: string | null;
  acquirer: string | null;
  tx_at: string | null;
  resolved_by: ResolvedBy;
  decline_code: string | null;
  decline_message: string | null;
  slip_text: string | null;
}

/** `platform.card_bin_rules` row as delivered by the settings pull scope (memory-only lookup). */
export interface CardBinRule {
  bin_prefix: string;
  card_type: Exclude<CardTypeValue, "unknown">;
  card_scheme?: CardScheme | null;
  valid_from: string;
  valid_to?: string | null;
}

/** A row of `GET /v1/card/terminals` (21 §16.1). */
export interface AgentCardTerminal {
  local_id: string;
  driver: string;
  host: string | null;
  tid: string | null;
  status: HealthStatus;
}

/** The terminal a POS uses (from `card_terminals` — pull scope `settings` / `GET /card-terminals`). */
export interface TerminalInfo {
  id: string;
  name: string;
  adapter: TerminalAdapter;
  driver: string;
  local_id: string | null;
  tid: string | null;
  host?: string | null;
  is_default?: boolean;
  status?: string;
  capabilities?: Partial<Record<string, boolean>>;
}
