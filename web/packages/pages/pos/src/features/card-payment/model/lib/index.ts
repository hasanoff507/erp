/** Pure helpers of the card payment state machine (24 §6.5). */
import type { CardResult, TerminalInfo } from "@shared/lib/card-terminal";
import { compareMoney, type Money } from "@shared/lib/money";

import type {
  AgentView,
  ApprovalRef,
  CardAttemptState,
  CardPaymentOutcome,
  FallbackPolicy,
  ManualReason,
  RecordTxBody,
  StoredAttempt,
  TerminalChipStatus,
} from "../types/index.ts";

/** `mm:ss` of a duration in seconds. */
export function clock(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

/** Where a terminal result leads (approved with a different amount → automatic void). */
export function routeResult(
  result: CardResult,
  requested: Money,
): "approved" | "amount_mismatch" | "declined" | "unknown" {
  if (result.status === "approved") {
    return compareMoney(result.amount, requested) === 0 ? "approved" : "amount_mismatch";
  }
  if (result.status === "declined") return "declined";
  return "unknown";
}

/** 24 §6.5 `$agentStatus` rule for an `agent_ecr` terminal (fake / others skip it). */
export function agentAvailability(
  terminal: TerminalInfo,
  agent: AgentView,
): { ok: true } | { ok: false; code: string; chip: TerminalChipStatus } {
  if (terminal.adapter !== "agent_ecr") return { ok: true };
  if (agent.status === "unpaired") return { ok: false, code: "AGENT_NOT_PAIRED", chip: "offline" };
  if (agent.status !== "online" || !agent.cardTerminalEnabled) {
    return { ok: false, code: "CARD_TERMINAL_UNREACHABLE", chip: "offline" };
  }
  const row = agent.terminals.find((t) => t.local_id === terminal.local_id);
  if (!row) return { ok: false, code: "CARD_TERMINAL_UNREACHABLE", chip: "offline" };
  if (row.status === "busy") return { ok: false, code: "CARD_TERMINAL_BUSY", chip: "busy" };
  if (row.status !== "online") return { ok: false, code: "CARD_TERMINAL_UNREACHABLE", chip: row.status };
  return { ok: true };
}

/** Reason for a manual card on a register with a bound terminal (21 §9.2). */
export function manualReasonFor(code: string | null): ManualReason {
  return code === "CARD_TERMINAL_BUSY" || code === "CARD_TERMINAL_UNREACHABLE" || code === "AGENT_NOT_PAIRED"
    ? "terminal_offline"
    : "terminal_error";
}

/** Does a manual card need the manager's `card_manual_entry` approval? `null` → forbidden. */
export function manualApprovalNeeded(policy: FallbackPolicy | null, reason: ManualReason): boolean | null {
  if (reason === "standalone_terminal" || policy === "standalone") return false;
  if (reason === "unknown_result") return true;
  if (policy === "forbid") return null;
  return policy !== "allow";
}

export function outcomeOf(s: CardAttemptState): CardPaymentOutcome | null {
  if (s.amount === null) return null;
  if (s.phase === "approved" && s.result && s.attemptId) {
    return { mode: "integrated", attemptId: s.attemptId, cardResult: s.result, amount: s.amount };
  }
  if (s.phase === "manual" && s.manualReason) {
    return {
      mode: "manual",
      manualReason: s.manualReason,
      approval: s.approval,
      amount: s.amount,
      attemptId: null,
    };
  }
  if (s.phase === "resolved_manual") {
    return {
      mode: "manual",
      manualReason: "unknown_result",
      approval: s.approval,
      amount: s.amount,
      attemptId: s.attemptId,
    };
  }
  return null;
}

export function storedAttempt(input: {
  attemptId: string;
  terminal: TerminalInfo;
  kind: StoredAttempt["kind"];
  amount: Money;
  clientEventId: string | null;
  startedAt: number;
  originalAttemptId?: string | null;
  cashRegisterId?: string | null;
  shiftId?: string | null;
}): StoredAttempt {
  return {
    attempt_id: input.attemptId,
    card_terminal_id: input.terminal.id,
    local_id: input.terminal.local_id,
    kind: input.kind,
    amount: input.amount,
    client_event_id: input.clientEventId,
    status: "pending",
    started_at: new Date(input.startedAt).toISOString(),
    original_attempt_id: input.originalAttemptId ?? null,
    result: null,
    resolved_by: null,
    cash_register_id: input.cashRegisterId ?? null,
    shift_id: input.shiftId ?? null,
  };
}

export function recordBody(
  attempt: StoredAttempt,
  extra: { cashRegisterId: string | null; shiftId: string | null; approval?: ApprovalRef | null },
): RecordTxBody {
  const result = (attempt.result ?? null) as CardResult | null;
  const storedRegister = typeof attempt.cash_register_id === "string" ? attempt.cash_register_id : null;
  const storedShift = typeof attempt.shift_id === "string" ? attempt.shift_id : null;
  return {
    id: attempt.attempt_id,
    card_terminal_id: attempt.card_terminal_id,
    cash_register_id: storedRegister ?? extra.cashRegisterId,
    shift_id: storedShift ?? extra.shiftId,
    kind: attempt.kind,
    original_transaction_id: attempt.original_attempt_id ?? null,
    amount: attempt.amount,
    client_event_id: attempt.client_event_id,
    requested_at: attempt.started_at,
    status: result ? null : "pending",
    result,
    card_manual_approval: extra.approval ?? null,
  };
}

/** Rows of `card_attempts` that still have to reach the server (16 §2.1 cleanup rules). */
export function needsFlush(a: StoredAttempt): boolean {
  if (a.status === "pending" || a.status === "unknown") return false;
  if (a.status === "approved" && a.kind === "purchase" && a.resolved_by !== "manager" && a.orphan !== true) {
    // an approved purchase leaves with its sale event (removeCardAttemptIds); a cancelled sale voids it
    return false;
  }
  return a.synced !== true;
}

/**
 * SYNC-03: approved purchases still in `card_attempts` are, by construction, not in the outbox (an approved
 * row leaves in the same Dexie transaction its sale event enters it — `removeCardAttemptIds`). Except the one
 * the current screen holds, each of them is a payment no sale took: attach, void or send as an orphan.
 */
export function danglingOf(
  attempts: readonly StoredAttempt[],
  currentAttemptId: string | null,
): StoredAttempt[] {
  return attempts.filter(
    (a) =>
      a.kind === "purchase" &&
      a.status === "approved" &&
      a.resolved_by !== "manager" &&
      a.orphan !== true &&
      a.attempt_id !== currentAttemptId,
  );
}
