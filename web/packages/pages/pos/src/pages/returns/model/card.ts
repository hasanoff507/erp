/**
 * Card refund of a return (18 §7.1 `refund_card`, §2.7, §16a.3; 16 §2.1; 21 §9.4; qaror #71/#64):
 * an integrated `refund` on the register's terminal (agent / fake adapter) with a local `card_attempts` row
 * written BEFORE the terminal call; approved → `refund_card.card_entry_mode='integrated'` + `card_result`,
 * the attempt leaves in the same transaction as `return.created` (`removeCardAttemptIds`). Declined → the
 * attempt is removed, the cashier retries or takes another method. No answer → the attempt stays
 * `unknown` and blocks (CARD_OUTCOME_UNKNOWN) — never a second refund. Manual (no terminal or the
 * integrated path closed) — amount only, `manual_reason`, `card_manual_approval` per `card_manual_fallback`.
 */
import {
  newAttemptId,
  pickTerminal,
  terminalRef,
  toCardResult,
  type CardResult,
  type CardTerminalClient,
  type CardTxResult,
  type TerminalInfo,
} from "@shared/lib/card-terminal";
import { toTiyin, type Money } from "@shared/lib/money";

export interface CardRefundDeps {
  terminals(cashRegisterId: string): Promise<TerminalInfo[]>;
  client(terminal: TerminalInfo): CardTerminalClient | null;
  fallbackPolicy(): Promise<"allow" | "manager_approval" | "forbid">;
  putAttempt(a: Record<string, unknown> & { attempt_id: string }): Promise<void>;
  updateAttempt(id: string, patch: Record<string, unknown>): Promise<unknown>;
  removeAttempt(id: string): Promise<void>;
  recordTx(body: Record<string, unknown>): Promise<unknown>;
  isOnline(): boolean;
  now(): string;
  sleep(ms: number): Promise<void>;
}

export type CardRoute =
  | { kind: "integrated"; terminal: TerminalInfo }
  /** No active terminal bound to the register → standalone, never needs an approval. */
  | { kind: "standalone" };

export async function cardRoute(deps: CardRefundDeps, cashRegisterId: string): Promise<CardRoute> {
  const terminal = pickTerminal(await deps.terminals(cashRegisterId));
  if (!terminal) return { kind: "standalone" };
  return { kind: "integrated", terminal };
}

export type RefundOutcome =
  | { status: "approved"; attemptId: string; cardResult: CardResult }
  | { status: "declined"; code: string | null }
  | { status: "unknown"; attemptId: string }
  | { status: "unavailable" };

const STATUS_TRIES = 3;

export async function runCardRefund(
  deps: CardRefundDeps,
  input: {
    terminal: TerminalInfo;
    amount: Money;
    cashRegisterId: string;
    shiftId: string;
    originalRrn: string | null;
  },
): Promise<RefundOutcome> {
  const client = deps.client(input.terminal);
  if (!client) return { status: "unavailable" };
  const attemptId = newAttemptId();
  const ref = terminalRef(input.terminal);
  await deps.putAttempt({
    attempt_id: attemptId,
    card_terminal_id: input.terminal.id,
    local_id: input.terminal.local_id,
    kind: "refund",
    amount: input.amount,
    client_event_id: null,
    status: "pending",
    started_at: deps.now(),
    original_attempt_id: null,
    result: null,
    resolved_by: null,
  });
  let tx: CardTxResult | null = null;
  let resolvedBy: "auto" | "status_query" = "auto";
  try {
    tx = await client.refund({
      attempt_id: attemptId,
      terminal: ref,
      amount_tiyin: toTiyin(input.amount),
      original_rrn: input.originalRrn,
      original_attempt_id: null,
    });
  } catch (e) {
    const code = (e as { code?: string }).code ?? null;
    // never reached the terminal → nothing happened; a lost answer → ask the terminal (safe status query)
    if (code === "CARD_TERMINAL_UNREACHABLE" || code === "CARD_TERMINAL_BUSY") {
      await deps.updateAttempt(attemptId, { status: "declined" });
      await deps.removeAttempt(attemptId);
      return { status: "unavailable" };
    }
    tx = null;
  }
  for (let i = 0; (!tx || tx.status === "timeout" || tx.status === "unknown") && i < STATUS_TRIES; i += 1) {
    await deps.sleep(2_000);
    try {
      tx = await client.getStatus(attemptId, ref);
      resolvedBy = "status_query";
    } catch {
      tx = null;
    }
  }
  if (!tx || tx.status === "timeout" || tx.status === "unknown") {
    await deps.updateAttempt(attemptId, { status: "unknown" });
    return { status: "unknown", attemptId };
  }
  const result = toCardResult(tx, {
    cardTerminalId: input.terminal.id,
    requestedAmount: input.amount,
    resolvedBy,
  });
  if (result.status !== "approved") {
    await deps.updateAttempt(attemptId, { status: "declined", result });
    await deps.removeAttempt(attemptId);
    return { status: "declined", code: result.decline_code };
  }
  await deps.updateAttempt(attemptId, { status: "approved", result, resolved_by: resolvedBy });
  if (deps.isOnline()) {
    // best effort (18 §16a.3) — the event carries the same result anyway
    void deps
      .recordTx({
        id: attemptId,
        card_terminal_id: input.terminal.id,
        cash_register_id: input.cashRegisterId,
        shift_id: input.shiftId,
        kind: "refund",
        original_transaction_id: null,
        amount: input.amount,
        client_event_id: null,
        requested_at: deps.now(),
        status: null,
        result,
        card_manual_approval: null,
      })
      .catch(() => undefined);
  }
  return { status: "approved", attemptId, cardResult: result };
}

/** `manual_reason` of a terminalsiz refund (18 §4.1 enum). */
export function manualReasonFor(route: CardRoute, outcome: RefundOutcome | null): string {
  if (route.kind === "standalone") return "standalone_terminal";
  return outcome?.status === "unavailable" ? "terminal_offline" : "terminal_error";
}

/** Manual card on a register WITH a terminal: forbid → refused; manager_approval → approval needed. */
export function manualPolicyNeed(
  route: CardRoute,
  policy: "allow" | "manager_approval" | "forbid",
): "none" | "approval" | "forbidden" {
  if (route.kind === "standalone") return "none";
  if (policy === "forbid") return "forbidden";
  return policy === "manager_approval" ? "approval" : "none";
}
