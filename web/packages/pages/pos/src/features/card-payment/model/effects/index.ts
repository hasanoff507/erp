/**
 * Card payment effects (24 §6.5): healthFx, purchaseFx, getStatusFx (+ getLastTransaction), cancelPendingFx,
 * voidFx, recordTxFx, managerResolveFx, verifyApproverFx, restoreFx, flushAttemptsFx.
 * `purchase` is called from exactly one place (purchaseFx) and never repeated for the same attempt.
 * Local attempts (Dexie `card_attempts`, 16 §2.1) are written BEFORE the terminal is called.
 */
import { createEffect } from "effector";

import {
  CardTerminalError,
  isCardTerminalError,
  timeoutResult,
  managerCardResult,
  newAttemptId,
  pickTerminal,
  terminalRef,
  toCardResult,
  type CardResult,
  type TerminalInfo,
} from "@shared/lib/card-terminal";
import { toTiyin, type Money } from "@shared/lib/money";

import { defaultCardPaymentDeps } from "../lib/deps.ts";
import { agentAvailability, danglingOf, needsFlush, recordBody, storedAttempt } from "../lib/index.ts";
import {
  APPROVE_PERMISSION,
  STATUS_QUERY_GAP_MS,
  STATUS_QUERY_TRIES,
  type ApprovalRef,
  type CardAttemptState,
  type CardPaymentDeps,
  type FallbackPolicy,
  type StartInput,
  type StoredAttempt,
  type TerminalChipStatus,
} from "../types/index.ts";

let deps: CardPaymentDeps | null = null;

/** Refusals that prove the purchase never reached the card (24 §6.5 HTTP map). */
const NOT_STARTED: ReadonlySet<string> = new Set([
  "CARD_TERMINAL_BUSY",
  "CARD_TERMINAL_UNREACHABLE",
  "CARD_OUTCOME_UNKNOWN",
  "AGENT_NOT_PAIRED",
]);

function unknownResult(attemptId: string, cardTerminalId: string, amount: Money): CardResult {
  return {
    ...managerCardResult({ attemptId, cardTerminalId, amount, passed: false }),
    status: "unknown",
    resolved_by: "status_query",
    decline_code: null,
  };
}

/** Current time of the injected clock (countdown). */
export const nowMs = (): number => d().now();

/** Wire the real (or test) collaborators once — POS app layer / tests. */
export function configureCardPayment(next: CardPaymentDeps | null): void {
  deps = next;
}

function d(): CardPaymentDeps {
  deps ??= defaultCardPaymentDeps();
  return deps;
}

export type StartOutcome =
  | { kind: "standalone" }
  | { kind: "blocked"; terminal: TerminalInfo; attempt: StoredAttempt; policy: FallbackPolicy }
  | {
      kind: "unavailable";
      terminal: TerminalInfo;
      code: string;
      chip: TerminalChipStatus;
      policy: FallbackPolicy;
    }
  | { kind: "ready"; terminal: TerminalInfo; policy: FallbackPolicy };

/** "Karta" pressed: terminal choice (18 §16a.1), unresolved attempts, agent state, `health` (≤ 3 s). */
export const startFx = createEffect<StartInput, StartOutcome>(async (input) => {
  const deps = d();
  const terminal = pickTerminal(await deps.terminals(input.cashRegisterId));
  if (!terminal) return { kind: "standalone" };
  const policy = await deps.fallbackPolicy();
  if (deps.fiscalBlocked()) {
    // 16 §2.1: a register that cannot print a receipt does not start a purchase
    return {
      kind: "unavailable",
      terminal,
      code: "FISCAL_OFFLINE_48H_BLOCKED",
      chip: "unknown",
      policy: "forbid",
    };
  }
  const blocked = (await deps.attempts.unresolved(terminal.id))[0];
  if (blocked) return { kind: "blocked", terminal, attempt: blocked, policy };
  const agent = agentAvailability(terminal, deps.agent());
  if (!agent.ok) return { kind: "unavailable", terminal, code: agent.code, chip: agent.chip, policy };
  const client = deps.client(terminal);
  if (!client)
    return { kind: "unavailable", terminal, code: "CARD_TERMINAL_UNREACHABLE", chip: "offline", policy };
  try {
    const health = await client.health(terminalRef(terminal));
    if (health.status === "online") return { kind: "ready", terminal, policy };
    return {
      kind: "unavailable",
      terminal,
      code: health.status === "busy" ? "CARD_TERMINAL_BUSY" : "CARD_TERMINAL_UNREACHABLE",
      chip: health.status,
      policy,
    };
  } catch (error) {
    const code = isCardTerminalError(error) ? error.code : "CARD_TERMINAL_UNREACHABLE";
    return {
      kind: "unavailable",
      terminal,
      code,
      chip: code === "CARD_TERMINAL_BUSY" ? "busy" : "offline",
      policy,
    };
  }
});

export const healthFx = createEffect(async (terminal: TerminalInfo) => {
  const client = d().client(terminal);
  if (!client) throw new Error("CARD_TERMINAL_UNREACHABLE");
  return client.health(terminalRef(terminal));
});

/** New attempt id + the local `pending` row, before anything reaches the terminal. */
export const preparePurchaseFx = createEffect(async (s: CardAttemptState) => {
  const deps = d();
  if (!s.terminal || !s.amount) throw new Error("no terminal");
  const sentAt = deps.now();
  const attemptId = newAttemptId(sentAt);
  await deps.attempts.put(
    storedAttempt({
      attemptId,
      terminal: s.terminal,
      kind: "purchase",
      amount: s.amount,
      clientEventId: s.clientEventId,
      startedAt: sentAt,
      cashRegisterId: s.cashRegisterId,
      shiftId: s.shiftId,
    }),
  );
  return { attemptId, sentAt };
});

async function persistResult(attemptId: string, result: CardResult): Promise<void> {
  await d().attempts.update(attemptId, {
    status: result.status,
    result: result as unknown as Record<string, unknown>,
    resolved_by: result.status === "unknown" ? null : result.resolved_by,
  });
}

export type PurchaseOutcome = { result: CardResult } | { notStarted: string };

/**
 * `POST /v1/card/purchase` (agent) / Fake — ONE call per attempt; a lost answer resolves as `unknown`.
 * A typed refusal before anything started (busy, unreachable, not paired) closes the local row as declined.
 */
export const purchaseFx = createEffect(async (s: CardAttemptState): Promise<PurchaseOutcome> => {
  const deps = d();
  if (!s.terminal || !s.amount || !s.attemptId || !s.cashRegisterId) throw new Error("not prepared");
  const client = deps.client(s.terminal);
  let tx;
  try {
    if (!client) throw new CardTerminalError("CARD_TERMINAL_UNREACHABLE");
    tx = await client.purchase({
      attempt_id: s.attemptId,
      terminal: terminalRef(s.terminal),
      amount_tiyin: toTiyin(s.amount),
      currency: "UZS",
      cash_register_id: s.cashRegisterId,
      client_event_id: s.clientEventId ?? s.attemptId,
      ...(s.receiptSeq != null ? { receipt_seq: s.receiptSeq } : {}),
    });
  } catch (error) {
    if (isCardTerminalError(error) && NOT_STARTED.has(error.code)) {
      await deps.attempts.update(s.attemptId, { status: "declined", resolved_by: "auto" });
      await deps.attempts.remove(s.attemptId);
      return { notStarted: error.code };
    }
    // anything else: we cannot know whether the terminal took the money
    tx = timeoutResult(s.attemptId);
  }
  const result = toCardResult(tx, {
    cardTerminalId: s.terminal.id,
    requestedAmount: s.amount,
    resolvedBy: "auto",
    binRules: await deps.binRules(),
  });
  await persistResult(s.attemptId, result);
  return { result };
});

/** Unknown → `get_status` 3 × 2 s, then `get_last_transaction` (if the terminal can) — 18 §16a.4. */
export const getStatusFx = createEffect(async (s: CardAttemptState): Promise<CardResult> => {
  const deps = d();
  if (!s.terminal || !s.amount || !s.attemptId) throw new Error("no attempt");
  const client = deps.client(s.terminal);
  const map = (tx: Parameters<typeof toCardResult>[0]) =>
    deps.binRules().then((rules) =>
      toCardResult(tx, {
        cardTerminalId: s.terminal?.id ?? "",
        requestedAmount: s.amount as Money,
        resolvedBy: "status_query",
        binRules: rules,
      }),
    );
  let last: CardResult | null = null;
  if (client) {
    for (let i = 0; i < STATUS_QUERY_TRIES; i++) {
      if (i > 0) await deps.sleep(STATUS_QUERY_GAP_MS);
      try {
        last = await map(await client.getStatus(s.attemptId, terminalRef(s.terminal)));
        if (last.status !== "unknown") break;
      } catch {
        // safe to ask again
      }
    }
    if ((!last || last.status === "unknown") && s.terminal.capabilities?.last_transaction !== false) {
      try {
        const tx = await client.getLastTransaction(terminalRef(s.terminal), s.attemptId);
        if (tx && tx.attempt_id === s.attemptId) last = await map(tx);
      } catch {
        // stays unknown
      }
    }
  }
  const result: CardResult = last ?? unknownResult(s.attemptId, s.terminal.id, s.amount);
  if (result.status !== "unknown") await persistResult(s.attemptId, result);
  return result;
});

/** Same as getStatusFx — kept separate for the `capabilities.last_transaction` button. */
export const getLastTransactionFx = getStatusFx;

/** "Terminalda bekor qilish" — `POST /v1/card/cancel-pending`; the purchase then ends as cancelled. */
export const cancelPendingFx = createEffect(async (s: CardAttemptState) => {
  if (!s.terminal || !s.attemptId) return "not_cancellable" as const;
  const client = d().client(s.terminal);
  return client ? client.cancelPending(s.attemptId) : ("not_cancellable" as const);
});

/** Automatic void (amount mismatch / the cashier cancelled the sale) — the only two cases (21 §9.4). */
export const voidFx = createEffect(
  async (s: CardAttemptState): Promise<{ voidId: string; result: CardResult }> => {
    const deps = d();
    if (!s.terminal || !s.attemptId || !s.result) throw new Error("nothing to void");
    const client = deps.client(s.terminal);
    const voidId = newAttemptId(deps.now());
    const amount = s.result.amount;
    await deps.attempts.put(
      storedAttempt({
        attemptId: voidId,
        terminal: s.terminal,
        kind: "void",
        amount,
        clientEventId: s.clientEventId,
        startedAt: deps.now(),
        originalAttemptId: s.attemptId,
        cashRegisterId: s.cashRegisterId,
        shiftId: s.shiftId,
      }),
    );
    let result: CardResult;
    try {
      if (!client) throw new Error("CARD_TERMINAL_UNREACHABLE");
      const tx = await client.void({
        attempt_id: voidId,
        terminal: terminalRef(s.terminal),
        amount_tiyin: toTiyin(amount),
        original_attempt_id: s.attemptId,
      });
      result = toCardResult(tx, {
        cardTerminalId: s.terminal.id,
        requestedAmount: amount,
        resolvedBy: "auto",
        originalAttemptId: s.attemptId,
      });
    } catch {
      result = {
        ...managerCardResult({ attemptId: voidId, cardTerminalId: s.terminal.id, amount, passed: false }),
        kind: "void",
        original_attempt_id: s.attemptId,
        resolved_by: "auto",
        decline_code: "error",
      };
    }
    if (result.status === "unknown") {
      result = { ...result, status: "declined", decline_code: "error" };
    }
    await persistResult(voidId, result);
    if (result.status === "approved")
      await deps.attempts.update(s.attemptId, { status: "voided", synced: false });
    return { voidId, result };
  },
);

/** `POST /api/v1/card-terminal-transactions` (online only, best effort); success marks the row synced. */
export const recordTxFx = createEffect(
  async (input: {
    attemptId: string;
    cashRegisterId: string | null;
    shiftId: string | null;
    approval?: ApprovalRef | null;
    removeAfter?: boolean;
    /** 16 §2.1: a declined attempt is just shown and dropped when there is no network. */
    dropIfOffline?: boolean;
  }) => {
    const deps = d();
    if (!deps.isOnline()) {
      if (input.dropIfOffline) await deps.attempts.remove(input.attemptId);
      return false;
    }
    const attempt = await deps.attempts.get(input.attemptId);
    if (!attempt) return false;
    await deps.recordTx(
      recordBody(attempt, {
        cashRegisterId: input.cashRegisterId,
        shiftId: input.shiftId,
        approval: input.approval ?? null,
      }),
    );
    if (input.removeAfter) await deps.attempts.remove(input.attemptId);
    else await deps.attempts.update(input.attemptId, { synced: true });
    return true;
  },
);

/** Manager closes an `unknown` attempt from the terminal slip — nothing about the card is typed. */
export const managerResolveFx = createEffect(
  async (input: { state: CardAttemptState; passed: boolean; approval: ApprovalRef }): Promise<CardResult> => {
    const { state: s } = input;
    if (!s.terminal || !s.attemptId || !s.amount) throw new Error("no attempt");
    const result = managerCardResult({
      attemptId: s.attemptId,
      cardTerminalId: s.terminal.id,
      amount: s.amount,
      passed: input.passed,
    });
    await d().attempts.update(s.attemptId, {
      status: result.status,
      result: result as unknown as Record<string, unknown>,
      resolved_by: "manager",
      approval: input.approval,
    });
    return result;
  },
);

/** Local PIN of a manager/owner holding `card.manual_entry.approve` (16 §2.1 offline approval). */
export const verifyApproverFx = createEffect(
  async (input: { userId: string; pin: string }): Promise<ApprovalRef> => {
    const deps = d();
    if (!(await deps.hasPermission(input.userId, APPROVE_PERMISSION))) throw new Error("APPROVAL_INVALID");
    const res = await deps.verifyPin(input.userId, input.pin);
    if (!res.ok) throw new Error(res.reason === "locked" ? "PIN_LOCKED" : "PIN_INVALID");
    return {
      mode: "local_pin",
      approved_by: input.userId,
      pin_verified_locally: true,
      approval_request_id: null,
    };
  },
);

export const loadApproversFx = createEffect(() => d().approvers());

/** Page (re)open: an unresolved attempt keeps blocking and its status query restarts (16 §2.1). */
async function terminalOf(attempt: StoredAttempt): Promise<TerminalInfo> {
  const terminals =
    typeof attempt.cash_register_id === "string" ? await d().terminals(attempt.cash_register_id) : [];
  return (
    terminals.find((t) => t.id === attempt.card_terminal_id) ??
    ({
      id: attempt.card_terminal_id,
      name: "",
      adapter: "cloud",
      driver: "",
      local_id: attempt.local_id ?? null,
      tid: null,
    } satisfies TerminalInfo)
  );
}

export type RestoreOutcome = {
  kind: "unknown" | "dangling";
  attempt: StoredAttempt;
  terminal: TerminalInfo;
  policy: FallbackPolicy;
} | null;

/**
 * Page (re)open (16 §2.1): an unresolved attempt keeps blocking and its status query restarts; otherwise an
 * approved purchase no sale took (SYNC-03) is surfaced for attach / void.
 */
export const restoreFx = createEffect(
  async (currentAttemptId: string | null = null): Promise<RestoreOutcome> => {
    const deps = d();
    const unresolved = (await deps.attempts.unresolved())[0];
    const dangling = unresolved ? undefined : danglingOf(await deps.attempts.list(), currentAttemptId)[0];
    const attempt = unresolved ?? dangling;
    if (!attempt) return null;
    return {
      kind: unresolved ? "unknown" : "dangling",
      attempt,
      terminal: await terminalOf(attempt),
      policy: await deps.fallbackPolicy(),
    };
  },
);

/** Dangling approved purchases (logout / device-revoke blocker UI, 16 §12). */
export const danglingAttemptsFx = createEffect(async (currentAttemptId: string | null = null) =>
  danglingOf(await d().attempts.list(), currentAttemptId),
);

/**
 * Logout / revoke resolver when neither attach nor void is possible: every dangling purchase becomes an
 * `orphan` and is sent with `POST /card-terminal-transactions` (the server sweep raises
 * `card_orphan_transaction`); the rows leave `card_attempts` once the server has them.
 */
export const orphanDanglingFx = createEffect(
  async (ctx: { cashRegisterId: string | null; shiftId: string | null }) => {
    const deps = d();
    for (const a of danglingOf(await deps.attempts.list(), null)) {
      await deps.attempts.update(a.attempt_id, { orphan: true, synced: false });
    }
    return ctx;
  },
);

/** An approved purchase no sale will take (void failed after an amount mismatch) — server review (16 §2.1). */
export const markOrphanFx = createEffect(async (attemptId: string) => {
  await d().attempts.update(attemptId, { orphan: true, synced: false });
});

/** Final attempts not yet on the server (voided, declined, manager-resolved) — sent when online. */
export const flushAttemptsFx = createEffect(
  async (ctx: { cashRegisterId: string | null; shiftId: string | null }) => {
    const deps = d();
    if (!deps.isOnline()) return 0;
    let sent = 0;
    for (const a of await deps.attempts.list()) {
      if (!needsFlush(a)) continue;
      try {
        const approval = (a.approval as ApprovalRef | undefined) ?? null;
        await deps.recordTx(recordBody(a, { ...ctx, approval }));
        await deps.attempts.remove(a.attempt_id);
        sent += 1;
      } catch {
        // stays for the next flush
      }
    }
    return sent;
  },
);
