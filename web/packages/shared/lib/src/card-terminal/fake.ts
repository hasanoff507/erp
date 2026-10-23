/**
 * `FakeCardTerminalClient` — in-browser terminal emulator for dev, vitest, Playwright, staging and demo
 * (24 §6.5). Deterministic by the last three digits of the amount in so'm (same table as the backend
 * `FakeCardTerminalAdapter`):
 *
 *   other → approved after `delayMs` (raw mask `860031******1234`, uzcard, no card_type)
 *   001 declined 51 · 002 timeout → status approved · 003 timeout, unresolvable · 004 busy
 *   005 approved 1 000 so'm less · 006 approved, later void fails · 007 cancelled · 008 error
 *   009 approved, card_type social · 010 timeout → status not_found · 011 declined 05
 *
 * `fakeCardScenario(...)` overrides the next purchases. The same `attempt_id` returns the journalled result
 * (no second terminal hit — `calls.purchase`). `cancelPending` during the wait ends it as `cancelled`.
 */
import { CardTerminalError, type CardTerminalClient } from "./port.ts";
import type { CardTxResult, SettlementResult, TerminalHealth } from "./types.ts";

export type FakeOutcome =
  | "approved"
  | "declined_51"
  | "timeout_then_approved"
  | "timeout_unresolved"
  | "busy"
  | "amount_mismatch"
  | "approved_void_fails"
  | "cancelled"
  | "error"
  | "approved_social"
  | "timeout_then_not_found"
  | "declined_05";

const BY_ENDING: Readonly<Record<number, FakeOutcome>> = {
  1: "declined_51",
  2: "timeout_then_approved",
  3: "timeout_unresolved",
  4: "busy",
  5: "amount_mismatch",
  6: "approved_void_fails",
  7: "cancelled",
  8: "error",
  9: "approved_social",
  10: "timeout_then_not_found",
  11: "declined_05",
};

export const FAKE_TID = "T0000001";
export const FAKE_RAW_MASK = "860031******1234";

export function fakeOutcomeFor(amountTiyin: number): FakeOutcome {
  return BY_ENDING[Math.floor(amountTiyin / 100) % 1000] ?? "approved";
}

function rrnOf(attemptId: string): string {
  let h = 0n;
  for (const ch of attemptId.replace(/-/g, ""))
    h = (h * 16n + BigInt("0123456789abcdef".indexOf(ch))) % 10n ** 12n;
  return h.toString().padStart(12, "0");
}

function approvalOf(attemptId: string): string {
  return attemptId.replace(/-/g, "").slice(-6).toUpperCase();
}

interface Journal {
  result: CardTxResult;
  statusAnswer: CardTxResult | null;
  voidFails: boolean;
}

export interface FakeCardTerminalClient extends CardTerminalClient {
  readonly calls: Record<"purchase" | "getStatus" | "void" | "refund" | "health" | "cancelPending", number>;
  healthStatus: TerminalHealth["status"];
  /** Force the next purchase outcomes (FIFO), overriding the amount table. */
  fakeCardScenario(...outcomes: FakeOutcome[]): void;
}

export interface FakeOptions {
  delayMs?: number;
  sleep?: (ms: number, signal?: AbortSignal) => Promise<void>;
  now?: () => Date;
}

/** A terminal round-trip is always asynchronous. */
const yieldTick = (): Promise<void> => Promise.resolve();

function defaultSleep(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve) => {
    const timer = setTimeout(resolve, ms);
    signal?.addEventListener(
      "abort",
      () => {
        clearTimeout(timer);
        resolve();
      },
      { once: true },
    );
  });
}

function base(attemptId: string, kind: CardTxResult["kind"]): CardTxResult {
  return {
    attempt_id: attemptId,
    kind,
    status: "approved",
    amount_tiyin: null,
    approval_code: null,
    rrn: null,
    stan: null,
    card_mask: null,
    card_scheme: null,
    card_type: null,
    entry_mode: null,
    tid: FAKE_TID,
    mid: "M000000000001",
    acquirer: "FAKEBANK",
    tx_at: null,
    decline_code: null,
    decline_message: null,
  };
}

export function createFakeCardTerminalClient({
  delayMs = 3_000,
  sleep = defaultSleep,
  now = () => new Date(),
}: FakeOptions = {}): FakeCardTerminalClient {
  const journal = new Map<string, Journal>();
  const script: FakeOutcome[] = [];
  const cancels = new Map<string, AbortController>();
  let last: CardTxResult | null = null;
  let batch: CardTxResult[] = [];
  let batchNo = 0;

  const approved = (attemptId: string, kind: CardTxResult["kind"], amount: number): CardTxResult => ({
    ...base(attemptId, kind),
    status: "approved",
    amount_tiyin: amount,
    approval_code: approvalOf(attemptId),
    rrn: rrnOf(attemptId),
    stan: rrnOf(attemptId).slice(-6),
    card_mask: kind === "void" ? null : FAKE_RAW_MASK,
    card_scheme: kind === "void" ? null : "uzcard",
    entry_mode: "contactless",
    tx_at: now().toISOString(),
  });

  const client: FakeCardTerminalClient = {
    adapter: "fake",
    calls: { purchase: 0, getStatus: 0, void: 0, refund: 0, health: 0, cancelPending: 0 },
    healthStatus: "online",
    fakeCardScenario: (...outcomes) => void script.push(...outcomes),

    async health() {
      await yieldTick();
      client.calls.health += 1;
      return { status: client.healthStatus, tid: FAKE_TID, last_tx_at: last?.tx_at ?? null };
    },

    async purchase(req, options = {}) {
      const known = journal.get(req.attempt_id);
      if (known) return known.result;
      const outcome = script.shift() ?? fakeOutcomeFor(req.amount_tiyin);
      if (outcome === "busy") throw new CardTerminalError("CARD_TERMINAL_BUSY");
      client.calls.purchase += 1;
      const cancel = new AbortController();
      cancels.set(req.attempt_id, cancel);
      const both = new AbortController();
      const abort = () => both.abort();
      cancel.signal.addEventListener("abort", abort, { once: true });
      options.signal?.addEventListener("abort", abort, { once: true });
      try {
        await sleep(delayMs, both.signal);
      } finally {
        cancels.delete(req.attempt_id);
      }
      if (options.signal?.aborted) {
        // the POS dropped the long request: the terminal outcome is unknown to it
        const ok = approved(req.attempt_id, "purchase", req.amount_tiyin);
        journal.set(req.attempt_id, {
          result: { ...base(req.attempt_id, "purchase"), status: "timeout" },
          statusAnswer: ok,
          voidFails: false,
        });
        last = ok;
        batch.push(ok);
        return { ...base(req.attempt_id, "purchase"), status: "timeout" };
      }
      if (cancel.signal.aborted) {
        const result = {
          ...base(req.attempt_id, "purchase"),
          status: "cancelled" as const,
          amount_tiyin: req.amount_tiyin,
        };
        journal.set(req.attempt_id, { result, statusAnswer: null, voidFails: false });
        return result;
      }
      const ok = approved(req.attempt_id, "purchase", req.amount_tiyin);
      let result: CardTxResult;
      let statusAnswer: CardTxResult | null = null;
      switch (outcome) {
        case "approved":
        case "approved_void_fails":
          result = ok;
          break;
        case "approved_social":
          result = { ...ok, card_type: "social" };
          break;
        case "amount_mismatch":
          result = { ...ok, amount_tiyin: req.amount_tiyin - 100_000 };
          break;
        case "declined_51":
        case "declined_05": {
          const code = outcome.slice(-2);
          result = {
            ...base(req.attempt_id, "purchase"),
            status: "declined",
            amount_tiyin: req.amount_tiyin,
            card_scheme: "uzcard",
            decline_code: code,
            decline_message: code === "51" ? "Mablag' yetarli emas" : "Rad etildi",
          };
          break;
        }
        case "cancelled":
        case "error":
          result = { ...base(req.attempt_id, "purchase"), status: outcome, amount_tiyin: req.amount_tiyin };
          break;
        default:
          result = { ...base(req.attempt_id, "purchase"), status: "timeout" };
          if (outcome === "timeout_then_approved") statusAnswer = ok;
          if (outcome === "timeout_then_not_found") {
            statusAnswer = {
              ...base(req.attempt_id, "purchase"),
              status: "declined",
              decline_code: "not_found",
            };
          }
      }
      journal.set(req.attempt_id, { result, statusAnswer, voidFails: outcome === "approved_void_fails" });
      const settled =
        result.status === "approved" ? result : statusAnswer?.status === "approved" ? statusAnswer : null;
      if (settled) {
        last = settled;
        batch.push(settled);
      }
      return result;
    },

    async getStatus(attemptId) {
      await yieldTick();
      client.calls.getStatus += 1;
      const entry = journal.get(attemptId);
      if (!entry) return { ...base(attemptId, "purchase"), status: "declined", decline_code: "not_found" };
      if (entry.result.status === "timeout") {
        return entry.statusAnswer ?? { ...base(attemptId, entry.result.kind), status: "unknown" };
      }
      return entry.result;
    },

    async getLastTransaction(_terminal, attemptId) {
      await yieldTick();
      const entry = journal.get(attemptId);
      if (!entry || entry.result.status !== "timeout") return last?.attempt_id === attemptId ? last : null;
      return entry.statusAnswer && entry.statusAnswer.status !== "unknown" ? entry.statusAnswer : null;
    },

    async cancelPending(attemptId) {
      await yieldTick();
      client.calls.cancelPending += 1;
      const pending = cancels.get(attemptId);
      if (!pending) return "not_cancellable";
      pending.abort();
      return "cancelled";
    },

    async void(req) {
      await yieldTick();
      const known = journal.get(req.attempt_id);
      if (known) return known.result;
      client.calls.void += 1;
      const original = journal.get(req.original_attempt_id);
      let result: CardTxResult;
      if (!original || original.voidFails) {
        result = {
          ...base(req.attempt_id, "void"),
          status: "declined",
          amount_tiyin: req.amount_tiyin,
          decline_code: "void_failed",
          decline_message: "Bekor qilib bo'lmadi",
        };
      } else {
        result = approved(req.attempt_id, "void", req.amount_tiyin);
        batch = batch.filter((r) => r.attempt_id !== req.original_attempt_id);
      }
      journal.set(req.attempt_id, { result, statusAnswer: null, voidFails: false });
      return result;
    },

    async refund(req) {
      await yieldTick();
      const known = journal.get(req.attempt_id);
      if (known) return known.result;
      client.calls.refund += 1;
      const result = approved(req.attempt_id, "refund", req.amount_tiyin);
      journal.set(req.attempt_id, { result, statusAnswer: null, voidFails: false });
      batch.push(result);
      return result;
    },

    async settlement(): Promise<SettlementResult> {
      await yieldTick();
      const purchases = batch.filter((r) => r.kind === "purchase");
      const refunds = batch.filter((r) => r.kind === "refund");
      const total = purchases.reduce((s, r) => s + (r.amount_tiyin ?? 0), 0);
      batchNo += 1;
      batch = [];
      return {
        tid: FAKE_TID,
        batch_no: String(batchNo).padStart(6, "0"),
        count: purchases.length,
        total_tiyin: total,
        by_scheme: [{ card_scheme: "uzcard", count: purchases.length, total_tiyin: total }],
        settled_at: now().toISOString(),
        refund_count: refunds.length,
        refund_total_tiyin: refunds.reduce((s, r) => s + (r.amount_tiyin ?? 0), 0),
      };
    },

    async listTerminals() {
      await yieldTick();
      return [{ local_id: "fake-1", driver: "fake", host: null, tid: FAKE_TID, status: client.healthStatus }];
    },
  };
  return client;
}
