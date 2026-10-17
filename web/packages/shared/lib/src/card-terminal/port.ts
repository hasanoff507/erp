/**
 * `CardTerminalClient` — the web POS side of `CardTerminalPort` (21 §9.4, 24 §6.5) plus `cancelPending` and
 * `listTerminals` (agent local API, 21 §16.1). Adapters: `agent_ecr` → {@link createAgentCardTerminalClient},
 * `fake` → {@link createFakeCardTerminalClient} (never in production, except demo — 24 §6.5).
 *
 * Error model: `purchase` NEVER rejects for a lost answer — a timeout / dropped connection / agent `504`
 * after the request was sent resolves as `{status: "timeout"}` (→ `unknown`, then `getStatus`). It rejects
 * with {@link CardTerminalError} only when the purchase certainly did not start (busy, unreachable before
 * sending, unpaired, outcome unknown on the terminal). `purchase` is never retried by the client.
 */
import type {
  AgentCardTerminal,
  CardPurchaseRequest,
  CardRefundRequest,
  CardTxResult,
  CardVoidRequest,
  SettlementResult,
  TerminalHealth,
  TerminalRef,
} from "./types.ts";

export type CardErrorCode =
  | "CARD_TERMINAL_UNREACHABLE"
  | "CARD_TERMINAL_BUSY"
  | "CARD_TERMINAL_TIMEOUT"
  | "CARD_OUTCOME_UNKNOWN"
  | "CARD_AMOUNT_MISMATCH"
  | "CARD_VOID_FAILED"
  | "AGENT_NOT_PAIRED";

/** i18n: catalog codes → `common:errors.<code lowercase>`; `AGENT_NOT_PAIRED` → `pos:cardPayment.errors.unpaired`. */
export class CardTerminalError extends Error {
  readonly code: CardErrorCode;
  readonly messageKey: string;

  constructor(code: CardErrorCode, options: { cause?: unknown; messageKey?: string } = {}) {
    super(code, options.cause !== undefined ? { cause: options.cause } : undefined);
    this.name = "CardTerminalError";
    this.code = code;
    this.messageKey =
      options.messageKey ??
      (code === "AGENT_NOT_PAIRED"
        ? "pos:cardPayment.errors.unpaired"
        : `common:errors.${code.toLowerCase()}`);
  }
}

export const isCardTerminalError = (e: unknown): e is CardTerminalError => e instanceof CardTerminalError;

export interface CallOptions {
  signal?: AbortSignal;
}

export interface CardTerminalClient {
  readonly adapter: "agent_ecr" | "fake";
  health(terminal: TerminalRef): Promise<TerminalHealth>;
  purchase(req: CardPurchaseRequest, options?: CallOptions): Promise<CardTxResult>;
  refund(req: CardRefundRequest): Promise<CardTxResult>;
  void(req: CardVoidRequest): Promise<CardTxResult>;
  getStatus(attemptId: string, terminal: TerminalRef): Promise<CardTxResult>;
  /** Accepted only when the last transaction carries `attemptId` (24 §6.5); otherwise `null`. */
  getLastTransaction(terminal: TerminalRef, attemptId: string): Promise<CardTxResult | null>;
  cancelPending(attemptId: string): Promise<"cancelled" | "not_cancellable">;
  settlement(terminal: TerminalRef): Promise<SettlementResult>;
  listTerminals(): Promise<AgentCardTerminal[]>;
}

/** A synthetic "no answer" result for a sent purchase (→ `unknown`, never a retry). */
export function timeoutResult(attemptId: string, kind: CardTxResult["kind"] = "purchase"): CardTxResult {
  return {
    attempt_id: attemptId,
    kind,
    status: "timeout",
    amount_tiyin: null,
    approval_code: null,
    rrn: null,
    stan: null,
    card_mask: null,
    card_scheme: null,
    card_type: null,
    entry_mode: null,
    tid: null,
    mid: null,
    acquirer: null,
    tx_at: null,
    decline_code: null,
    decline_message: null,
  };
}
