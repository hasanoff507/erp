/**
 * The card payment state machine (24 §6.5 diagram) — sample() only.
 *
 * idle ─Karta─▶ checking ─ready─▶ pending ─approved=─▶ approved ─(sale.created)─▶ idle
 *                                  pending ─approved≠─▶ voiding ─▶ declined (CARD_AMOUNT_MISMATCH) | void_failed
 *                                  pending ─declined/cancelled/error─▶ declined ─Qayta yuborish─▶ pending (new id)
 *                                  pending ─timeout─▶ unknown ─status─▶ approved | declined | unknown
 *                                  unknown ─manager─▶ resolved_manual | declined
 * checking ─no terminal─▶ manual_confirm (standalone) · ─unreachable/busy─▶ unavailable ─▶ manual_confirm ─▶ manual
 * approved ─sale cancelled─▶ voiding ─▶ voided | void_failed
 * `purchaseFx` is reachable only from `checking` (ready) and `declined` (retry) — never from pending/unknown.
 */
import { combine, createEvent, sample } from "effector";
import { interval } from "patronum";

import { compareMoney } from "@shared/lib/money";
import { $isOnline } from "@shared/state/network";

import {
  cancelPendingFx,
  flushAttemptsFx,
  getStatusFx,
  loadApproversFx,
  managerResolveFx,
  markOrphanFx,
  nowMs,
  preparePurchaseFx,
  purchaseFx,
  recordTxFx,
  restoreFx,
  startFx,
  verifyApproverFx,
  voidFx,
} from "../effects/index.ts";
import {
  cancelPressed,
  cardOutcomeConsumed,
  cardPaymentClosed,
  cardPaymentRestored,
  cardPaymentStarted,
  clockTicked,
  cardRecoveryClosed,
  cardRecoveryRequested,
  danglingAttached,
  danglingVoided,
  managerResolved,
  manualConfirmed,
  manualRequested,
  retryPressed,
  saleCancelled,
  statusCheckRequested,
} from "../events/index.ts";
import { manualApprovalNeeded, manualReasonFor, outcomeOf, routeResult } from "../lib/index.ts";
import { $approvalError, $approvers, $cardAttempt, $cardRecoveryOpen, $now } from "../stores/index.ts";
import { IDLE, PURCHASE_LIMIT_S, type CardAttemptState, type CardPhase } from "../types/index.ts";

const STARTABLE: ReadonlySet<CardPhase> = new Set(["idle", "voided", "unavailable", "declined"]);
const CLOSABLE: ReadonlySet<CardPhase> = new Set([
  "idle",
  "declined",
  "voided",
  "unavailable",
  "manual_confirm",
  "void_failed",
]);
/** Esc / close are disabled while the terminal may still take money (07 POS-03). */
const LOCKED: ReadonlySet<CardPhase> = new Set(["checking", "pending", "unknown", "voiding", "dangling"]);

export const $cardPhase = $cardAttempt.map((s) => s.phase);
export const $cardPaymentOutcome = $cardAttempt.map(outcomeOf);
/** SYNC-03: «Joriy chekka biriktirish» is possible only for a receipt of the same amount. */
export const $danglingAttachable = $cardAttempt.map(
  (s) =>
    s.phase === "dangling" &&
    s.offer !== null &&
    s.amount !== null &&
    compareMoney(s.offer.amount, s.amount) === 0,
);
export const $cardPanelLocked = $cardAttempt.map((s) => LOCKED.has(s.phase));
export const $canRetry = $cardAttempt.map((s) => s.phase === "declined" && s.terminal !== null);
export const $canCancelOnTerminal = $cardAttempt.map((s) => s.phase === "pending");
export const $manualApprovalNeeded = $cardAttempt.map((s) =>
  s.manualReason ? manualApprovalNeeded(s.policy, s.manualReason) : null,
);
/** Seconds since the amount was sent (countdown "mm:ss / 02:00"). */
export const $elapsedS = combine($cardAttempt, $now, (s, now) =>
  s.sentAt === null || now < s.sentAt ? 0 : Math.min(PURCHASE_LIMIT_S, Math.floor((now - s.sentAt) / 1000)),
);

// --- start ----------------------------------------------------------------------------------------
sample({
  clock: cardPaymentStarted,
  source: $cardAttempt,
  filter: (s) => STARTABLE.has(s.phase),
  fn: (_, input) => input,
  target: startFx,
});
$cardAttempt.on(startFx, (_, input) => ({
  ...IDLE,
  phase: "checking",
  amount: input.amount,
  clientEventId: input.clientEventId,
  cashRegisterId: input.cashRegisterId,
  shiftId: input.shiftId,
  receiptSeq: input.receiptSeq ?? null,
}));
$cardAttempt.on(startFx.doneData, (s, r): CardAttemptState => {
  switch (r.kind) {
    case "standalone":
      return { ...s, phase: "manual_confirm", policy: "standalone", manualReason: "standalone_terminal" };
    case "blocked":
      return {
        ...s,
        phase: "unknown",
        terminal: r.terminal,
        policy: r.policy,
        attemptId: r.attempt.attempt_id,
        amount: r.attempt.amount as CardAttemptState["amount"],
        clientEventId: r.attempt.client_event_id,
        errorCode: "CARD_OUTCOME_UNKNOWN",
        terminalStatus: "unknown",
      };
    case "unavailable":
      return {
        ...s,
        phase: "unavailable",
        terminal: r.terminal,
        policy: r.policy,
        errorCode: r.code,
        terminalStatus: r.chip,
      };
    case "ready":
      return { ...s, terminal: r.terminal, policy: r.policy, terminalStatus: "online" };
  }
});
$cardAttempt.on(startFx.fail, (s) => ({
  ...s,
  phase: "unavailable",
  errorCode: "CARD_TERMINAL_UNREACHABLE",
  terminalStatus: "offline",
}));

sample({
  clock: startFx.doneData,
  source: $cardAttempt,
  filter: (s, r) => r.kind === "ready" && s.phase === "checking",
  fn: (s) => s,
  target: preparePurchaseFx,
});
sample({
  clock: startFx.doneData,
  source: $cardAttempt,
  filter: (_, r) => r.kind === "blocked",
  fn: (s) => s,
  target: getStatusFx,
});

// --- purchase (only from checking or declined) ---------------------------------------------------------
sample({
  clock: retryPressed,
  source: $cardAttempt,
  filter: (s) => s.phase === "declined" && s.terminal !== null,
  target: preparePurchaseFx,
});
$cardAttempt.on(preparePurchaseFx.doneData, (s, { attemptId, sentAt }) => ({
  ...s,
  phase: "pending",
  attemptId,
  sentAt,
  result: null,
  errorCode: null,
  terminalStatus: "online",
  voidOf: null,
}));
$cardAttempt.on(preparePurchaseFx.fail, (s) => ({
  ...s,
  phase: "unavailable",
  errorCode: "CARD_TERMINAL_UNREACHABLE",
}));
sample({
  clock: preparePurchaseFx.done,
  source: $cardAttempt,
  filter: (s) => s.phase === "pending",
  target: purchaseFx,
});

// countdown
const { tick } = interval({
  timeout: 1000,
  start: preparePurchaseFx.done,
  stop: purchaseFx.finally,
  leading: true,
});
sample({ clock: tick, fn: () => nowMs(), target: clockTicked });
$now.on(clockTicked, (_, now) => now);

function afterResult(s: CardAttemptState, result: NonNullable<CardAttemptState["result"]>): CardAttemptState {
  if (s.amount === null) return s;
  switch (routeResult(result, s.amount)) {
    case "approved":
      return { ...s, phase: "approved", result, errorCode: null, terminalStatus: "online" };
    case "amount_mismatch":
      return { ...s, phase: "voiding", result, errorCode: "CARD_AMOUNT_MISMATCH", voidOf: s.attemptId };
    case "declined":
      return { ...s, phase: "declined", result, errorCode: "CARD_DECLINED", terminalStatus: "online" };
    case "unknown":
      return { ...s, phase: "unknown", result, errorCode: "CARD_OUTCOME_UNKNOWN", terminalStatus: "unknown" };
  }
}

$cardAttempt.on(purchaseFx.doneData, (s, out) =>
  "notStarted" in out
    ? {
        ...s,
        phase: "unavailable",
        attemptId: null,
        sentAt: null,
        errorCode: out.notStarted,
        terminalStatus: out.notStarted === "CARD_TERMINAL_BUSY" ? "busy" : "offline",
      }
    : afterResult(s, out.result),
);
$cardAttempt.on(purchaseFx.fail, (s) => ({
  ...s,
  phase: "unknown",
  errorCode: "CARD_OUTCOME_UNKNOWN",
  terminalStatus: "unknown",
}));

// unknown → status query (also on demand)
sample({
  clock: [purchaseFx.done, purchaseFx.fail],
  source: $cardAttempt,
  filter: (s) => s.phase === "unknown",
  target: getStatusFx,
});
sample({
  clock: statusCheckRequested,
  source: $cardAttempt,
  filter: (s) => s.phase === "unknown",
  target: getStatusFx,
});
$cardAttempt.on(getStatusFx.doneData, (s, result) =>
  s.phase === "unknown" && result.status !== "unknown" ? afterResult(s, result) : s,
);

// automatic void: amount mismatch (24 §6.5) or the cashier cancelled an approved sale (21 §9.4)
const voidRequested = createEvent();
sample({
  clock: saleCancelled,
  source: $cardAttempt,
  filter: (s) => s.phase === "approved",
  target: voidRequested,
});
$cardAttempt.on(voidRequested, (s) => ({ ...s, phase: "voiding", voidOf: s.attemptId }));
sample({
  clock: [purchaseFx.doneData, getStatusFx.doneData, voidRequested],
  source: $cardAttempt,
  filter: (s) => s.phase === "voiding",
  target: voidFx,
});
/**
 * Void went through → declined (amount mismatch, retry allowed) or voided (sale cancelled).
 * Void failed → CARD_VOID_FAILED: after a cancelled sale the payment stays approved and the sale is NOT
 * cancelled (21 §9.4); after an amount mismatch the money is held by a wrong-amount purchase — a manager
 * handles it and the attempt goes to the server as an orphan (card_orphan_transaction after 24 h).
 */
$cardAttempt.on(voidFx.doneData, (s, { result }) => {
  const mismatch = s.errorCode === "CARD_AMOUNT_MISMATCH";
  if (result.status === "approved") {
    return mismatch
      ? { ...s, phase: "declined" as const }
      : { ...s, phase: "voided" as const, errorCode: null, dangling: false };
  }
  // a dangling purchase whose void failed goes to the server as an orphan (SYNC-03)
  return mismatch || s.dangling
    ? { ...s, phase: "void_failed" as const, errorCode: "CARD_VOID_FAILED" }
    : { ...s, phase: "approved" as const, voidOf: null, errorCode: "CARD_VOID_FAILED" };
});
$cardAttempt.on(voidFx.fail, (s) =>
  s.errorCode === "CARD_AMOUNT_MISMATCH" || s.dangling
    ? { ...s, phase: "void_failed", errorCode: "CARD_VOID_FAILED" }
    : { ...s, phase: "approved", voidOf: null, errorCode: "CARD_VOID_FAILED" },
);
sample({
  clock: [voidFx.done, voidFx.fail],
  source: $cardAttempt,
  filter: (s) => s.phase === "void_failed" && s.attemptId !== null,
  fn: (s) => s.attemptId ?? "",
  target: markOrphanFx,
});

// --- server record (online, best effort; 16 §2.1 cleanup) ----------------------------------------------
sample({
  clock: [purchaseFx.doneData, getStatusFx.doneData],
  source: $cardAttempt,
  filter: (s) =>
    (s.phase === "approved" || s.phase === "declined") && s.attemptId !== null && s.voidOf === null,
  fn: (s) => ({
    attemptId: s.attemptId ?? "",
    cashRegisterId: s.cashRegisterId,
    shiftId: s.shiftId,
    // approved stays local until its sale event takes it (removeCardAttemptIds); declined leaves now
    removeAfter: s.phase === "declined",
    dropIfOffline: s.phase === "declined",
  }),
  target: recordTxFx,
});
sample({
  clock: [voidFx.finally, markOrphanFx.finally],
  source: $cardAttempt,
  fn: (s) => ({ cashRegisterId: s.cashRegisterId, shiftId: s.shiftId }),
  target: flushAttemptsFx,
});

// cancel on the terminal (the purchase then resolves as cancelled → declined)
sample({
  clock: cancelPressed,
  source: $cardAttempt,
  filter: (s) => s.phase === "pending",
  target: cancelPendingFx,
});

// --- manager resolution of an unknown attempt (18 §16a.4) -------------------------------------------
sample({
  clock: managerResolved,
  source: $cardAttempt,
  filter: (s) => s.phase === "unknown",
  fn: (state, { passed, approval }) => ({ state, passed, approval }),
  target: managerResolveFx,
});
$cardAttempt.on(managerResolveFx.done, (s, { params, result }) =>
  params.passed
    ? { ...s, phase: "resolved_manual", result, approval: params.approval, errorCode: null }
    : { ...s, phase: "declined", result, approval: params.approval, errorCode: "CARD_DECLINED" },
);
sample({
  clock: managerResolveFx.done,
  source: $cardAttempt,
  fn: (s, { params }) => ({
    attemptId: s.attemptId ?? "",
    cashRegisterId: s.cashRegisterId,
    shiftId: s.shiftId,
    approval: params.approval,
    removeAfter: true,
  }),
  target: recordTxFx,
});

// --- manual card without details (21 §9.2) ------------------------------------------------------------
$cardAttempt.on(manualRequested, (s) => {
  if (s.phase !== "unavailable" && s.phase !== "declined") return s;
  const reason = manualReasonFor(s.phase === "declined" ? "CARD_DECLINED" : s.errorCode);
  if (s.errorCode === "FISCAL_OFFLINE_48H_BLOCKED") return s;
  if (manualApprovalNeeded(s.policy, reason) === null) return { ...s, errorCode: "CARD_MANUAL_NOT_ALLOWED" };
  return { ...s, phase: "manual_confirm", manualReason: reason };
});
$cardAttempt.on(manualConfirmed, (s, { approval }) => {
  if (s.phase !== "manual_confirm" || !s.manualReason) return s;
  const needed = manualApprovalNeeded(s.policy, s.manualReason);
  if (needed === null) return { ...s, errorCode: "CARD_MANUAL_NOT_ALLOWED" };
  if (needed && !approval) return { ...s, errorCode: "CARD_MANUAL_APPROVAL_REQUIRED" };
  return { ...s, phase: "manual", approval, errorCode: null };
});

// approval dialog (local PIN)
$approvers.on(loadApproversFx.doneData, (_, list) => list);
$approvalError
  .on(verifyApproverFx, () => null)
  .on(verifyApproverFx.failData, (_, e) => e.message)
  .reset(cardPaymentStarted, cardOutcomeConsumed, cardPaymentClosed);

// --- leave / reset ---------------------------------------------------------------------------------
sample({
  clock: cardOutcomeConsumed,
  source: $cardAttempt,
  filter: (s) => s.phase === "approved" || s.phase === "manual" || s.phase === "resolved_manual",
  fn: () => IDLE,
  target: $cardAttempt,
});
sample({
  clock: cardPaymentClosed,
  source: $cardAttempt,
  filter: (s) => CLOSABLE.has(s.phase),
  fn: () => IDLE,
  target: $cardAttempt,
});

// --- reload / reconnect ----------------------------------------------------------------------------
sample({ clock: cardPaymentRestored, source: $cardAttempt, fn: (s) => s.attemptId, target: restoreFx });
$cardAttempt.on(restoreFx.doneData, (s, found) =>
  found && (s.phase === "idle" || s.phase === "checking")
    ? {
        ...IDLE,
        phase: found.kind,
        dangling: found.kind === "dangling",
        result:
          found.kind === "dangling" ? ((found.attempt.result ?? null) as CardAttemptState["result"]) : null,
        terminal: found.terminal,
        policy: found.policy,
        attemptId: found.attempt.attempt_id,
        amount: found.attempt.amount as CardAttemptState["amount"],
        clientEventId: found.attempt.client_event_id,
        cashRegisterId:
          typeof found.attempt.cash_register_id === "string" ? found.attempt.cash_register_id : null,
        shiftId: typeof found.attempt.shift_id === "string" ? found.attempt.shift_id : null,
        errorCode: found.kind === "unknown" ? "CARD_OUTCOME_UNKNOWN" : null,
      }
    : s,
);

// --- SYNC-03: an approved purchase no sale took (found after a reload) ---------------------------------
$cardAttempt.on(cardPaymentStarted, (s, input) => (s.phase === "dangling" ? { ...s, offer: input } : s));
$cardAttempt.on(danglingAttached, (s) =>
  s.phase === "dangling" && s.offer && s.amount && compareMoney(s.offer.amount, s.amount) === 0
    ? {
        ...s,
        phase: "approved",
        dangling: false,
        clientEventId: s.offer.clientEventId,
        cashRegisterId: s.cashRegisterId ?? s.offer.cashRegisterId,
        shiftId: s.shiftId ?? s.offer.shiftId,
        receiptSeq: s.offer.receiptSeq ?? null,
        offer: null,
      }
    : s,
);
sample({
  clock: danglingVoided,
  source: $cardAttempt,
  filter: (s) => s.phase === "dangling",
  target: voidRequested,
});
sample({
  clock: restoreFx.doneData,
  source: $cardAttempt,
  filter: (s, found) => found !== null && s.phase === "unknown",
  fn: (s) => s,
  target: getStatusFx,
});
const backOnline = sample({ clock: $isOnline.updates, filter: Boolean });
sample({
  clock: [cardPaymentRestored, backOnline],
  source: $cardAttempt,
  fn: (s) => ({ cashRegisterId: s.cashRegisterId, shiftId: s.shiftId }),
  target: flushAttemptsFx,
});

// --- recovery dialog (SYNC-03; 16 §12 logout blocker) ------------------------------------------------
sample({ clock: cardRecoveryRequested, source: $cardAttempt, fn: (s) => s.attemptId, target: restoreFx });
$cardRecoveryOpen
  .on(restoreFx.doneData, (open, found) => (found ? true : open))
  .reset(cardPaymentStarted, cardRecoveryClosed, cardOutcomeConsumed, cardPaymentClosed);
