/**
 * Card payment state machine types (24 §6.5, 07 POS-03; qaror #71/#64). PAN-free by construction: the only
 * card data ever held is the terminal result (`CardResult`: mask 4+4, RRN, approval code, scheme, type).
 */
import type {
  CardBinRule,
  CardResult,
  CardTerminalClient,
  HealthStatus,
  TerminalInfo,
} from "@shared/lib/card-terminal";
import type { Money } from "@shared/lib/money";

export type CardPhase =
  /** nothing in progress */
  | "idle"
  /** terminal / agent health is being checked (≤ 3 s) */
  | "checking"
  /** amount sent, waiting for the customer / bank (120 s countdown) */
  | "pending"
  /** terminal approved the requested amount → fiscal receipt → sale.created */
  | "approved"
  /** declined / cancelled / error / amount mismatch (voided) / manager "not passed" → retry or another method */
  | "declined"
  /** no answer: status queries run, a new purchase is blocked (CARD_OUTCOME_UNKNOWN) */
  | "unknown"
  /** automatic void in progress (amount mismatch or the cashier cancelled the sale) */
  | "voiding"
  /** the cashier cancelled the sale and the void went through */
  | "voided"
  /** CARD_VOID_FAILED — the sale is not cancelled, a manager must handle it */
  | "void_failed"
  /** integrated path closed (unreachable / busy / not paired) — manual card per policy */
  | "unavailable"
  /** "Karta terminalsiz qabul qilindi" confirmation (approval dialog when the policy needs it) */
  | "manual_confirm"
  /** manual (no-details) card payment confirmed */
  | "manual"
  /** unknown attempt closed by a manager as "passed" — payment is manual / unknown_result */
  | "resolved_manual"
  /**
   * SYNC-03: an APPROVED purchase found after a reload that no sale took (not in the outbox — approved rows
   * leave card_attempts with their sale event). Offer: attach to the current receipt (same amount) or void.
   */
  | "dangling";

export type ManualReason = "standalone_terminal" | "terminal_offline" | "terminal_error" | "unknown_result";
export type FallbackPolicy = "standalone" | "allow" | "manager_approval" | "forbid";
export type TerminalChipStatus = HealthStatus | "unknown";

/** `ApprovalRef` (18 §2.4) — only the local PIN path lives here; remote requests are BO-16's. */
export interface ApprovalRef {
  mode: "local_pin" | "remote_request";
  approved_by: string | null;
  pin_verified_locally: boolean | null;
  approval_request_id: string | null;
}

export interface CardAttemptState {
  phase: CardPhase;
  attemptId: string | null;
  terminal: TerminalInfo | null;
  amount: Money | null;
  clientEventId: string | null;
  cashRegisterId: string | null;
  shiftId: string | null;
  receiptSeq: number | null;
  /** ms epoch when the amount was sent (countdown base). */
  sentAt: number | null;
  /** last terminal result (approved / declined / unknown) — PAN-free. */
  result: CardResult | null;
  /** `CARD_*` catalog code shown to the cashier. */
  errorCode: string | null;
  terminalStatus: TerminalChipStatus;
  policy: FallbackPolicy | null;
  manualReason: ManualReason | null;
  approval: ApprovalRef | null;
  /** the purchase attempt an automatic void refers to */
  voidOf: string | null;
  /** the attempt is a dangling approved purchase (SYNC-03) */
  dangling: boolean;
  /** «Karta» pressed while a dangling purchase waits — the current receipt it could be attached to */
  offer: StartInput | null;
}

export const IDLE: CardAttemptState = Object.freeze({
  phase: "idle",
  attemptId: null,
  terminal: null,
  amount: null,
  clientEventId: null,
  cashRegisterId: null,
  shiftId: null,
  receiptSeq: null,
  sentAt: null,
  result: null,
  errorCode: null,
  terminalStatus: "unknown",
  policy: null,
  manualReason: null,
  approval: null,
  voidOf: null,
  dangling: false,
  offer: null,
});

/** What the POS-03 sale flow puts into `payments[]` (18 §4.1). */
export type CardPaymentOutcome =
  | { mode: "integrated"; attemptId: string; cardResult: CardResult; amount: Money }
  | {
      mode: "manual";
      manualReason: ManualReason;
      approval: ApprovalRef | null;
      amount: Money;
      attemptId: string | null;
    };

export interface StartInput {
  amount: Money;
  clientEventId: string;
  cashRegisterId: string;
  shiftId: string | null;
  receiptSeq?: number | null;
}

/** Locally stored attempt (Dexie `card_attempts`, 16 §2.1) — mirror of `@shared/offline` `CardAttempt`. */
export interface StoredAttempt {
  attempt_id: string;
  card_terminal_id: string;
  local_id?: string | null;
  kind: "purchase" | "refund" | "void";
  amount: string;
  client_event_id: string | null;
  status: "pending" | "approved" | "declined" | "unknown" | "voided";
  started_at: string;
  original_attempt_id?: string | null;
  result?: Record<string, unknown> | null;
  resolved_by?: "auto" | "status_query" | "manager" | null;
  [extra: string]: unknown;
}

/** `POST /card-terminal-transactions` body (18 §16a.3). */
export interface RecordTxBody {
  id: string;
  card_terminal_id: string;
  cash_register_id: string | null;
  shift_id: string | null;
  kind: "purchase" | "refund" | "void";
  original_transaction_id: string | null;
  amount: string;
  client_event_id: string | null;
  requested_at: string;
  status: "pending" | null;
  result: CardResult | null;
  card_manual_approval: ApprovalRef | null;
}

export interface AgentView {
  status: "online" | "offline" | "not_installed" | "unpaired";
  cardTerminalEnabled: boolean;
  terminals: { local_id: string; status: HealthStatus }[];
}

/** Everything the model talks to — injected (tests use the Fake client and in-memory stores). */
export interface CardPaymentDeps {
  client(terminal: TerminalInfo): CardTerminalClient | null;
  terminals(cashRegisterId: string): Promise<TerminalInfo[]>;
  fallbackPolicy(): Promise<"allow" | "manager_approval" | "forbid">;
  binRules(): Promise<CardBinRule[]>;
  agent(): AgentView;
  attempts: {
    put(a: StoredAttempt): Promise<void>;
    update(id: string, patch: Partial<StoredAttempt>): Promise<unknown>;
    remove(id: string): Promise<void>;
    unresolved(cardTerminalId?: string): Promise<StoredAttempt[]>;
    list(): Promise<StoredAttempt[]>;
    get(id: string): Promise<StoredAttempt | undefined>;
  };
  recordTx(body: RecordTxBody): Promise<unknown>;
  isOnline(): boolean;
  /** `$fiscalLadder.level === "blocked48"` — no receipt, so no purchase (16 §2.1). */
  fiscalBlocked(): boolean;
  verifyPin(
    userId: string,
    pin: string,
  ): Promise<{ ok: boolean; reason?: string; attemptsLeft?: number; lockedUntil?: string }>;
  hasPermission(userId: string, code: string): Promise<boolean>;
  /** Active staff of this branch holding `card.manual_entry.approve` (local PIN dialog). */
  approvers(): Promise<{ userId: string; name: string }[]>;
  now(): number;
  sleep(ms: number): Promise<void>;
}

export const PURCHASE_LIMIT_S = 120;
export const STATUS_QUERY_TRIES = 3;
export const STATUS_QUERY_GAP_MS = 2_000;
export const APPROVE_PERMISSION = "card.manual_entry.approve";
