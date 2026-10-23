/**
 * Card payment state machine (24 §6.5) with the FakeCardTerminalClient and in-memory card_attempts —
 * QT-M01-24…31, -33, -34 client side (31 §0.1 names), B3-T04, B3-T05.
 */
import { allSettled, fork } from "effector";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import {
  createFakeCardTerminalClient,
  type CardBinRule,
  type FakeCardTerminalClient,
  type TerminalInfo,
} from "@shared/lib/card-terminal";
import type { Money } from "@shared/lib/money";

import {
  $cardAttempt,
  $cardPaymentOutcome,
  $manualApprovalNeeded,
  cancelPressed,
  cardOutcomeConsumed,
  cardPaymentRestored,
  cardPaymentStarted,
  configureCardPayment,
  $cardRecoveryOpen,
  cardRecoveryRequested,
  danglingAttached,
  danglingVoided,
  needsFlush,
  orphanDanglingFx,
  managerResolved,
  manualConfirmed,
  manualRequested,
  retryPressed,
  saleCancelled,
  verifyApproverFx,
  type ApprovalRef,
  type CardPaymentDeps,
  type RecordTxBody,
  type StoredAttempt,
} from "./index.ts";

const FAKE_TERMINAL: TerminalInfo = {
  id: "t-1",
  name: "T1",
  adapter: "fake",
  driver: "fake",
  local_id: null,
  tid: "T0000001",
  is_default: true,
  status: "active",
  capabilities: { last_transaction: true, void: true },
};

interface World {
  deps: CardPaymentDeps;
  fake: FakeCardTerminalClient;
  attempts: Map<string, StoredAttempt>;
  recorded: RecordTxBody[];
  online: boolean;
  terminals: TerminalInfo[];
  policy: "allow" | "manager_approval" | "forbid";
  rules: CardBinRule[];
}

function world(): World {
  const w = {} as World;
  w.fake = createFakeCardTerminalClient({ delayMs: 0, sleep: () => Promise.resolve() });
  w.attempts = new Map();
  w.recorded = [];
  w.online = true;
  w.terminals = [FAKE_TERMINAL];
  w.policy = "manager_approval";
  w.rules = [];
  w.deps = {
    client: () => w.fake,
    terminals: () => Promise.resolve(w.terminals),
    fallbackPolicy: () => Promise.resolve(w.policy),
    binRules: () => Promise.resolve(w.rules),
    agent: () => ({ status: "online", cardTerminalEnabled: true, terminals: [] }),
    attempts: {
      put: (a) => {
        w.attempts.set(a.attempt_id, structuredClone(a));
        return Promise.resolve();
      },
      update: (id, patch) => {
        const cur = w.attempts.get(id);
        if (!cur) return Promise.reject(new Error("missing"));
        w.attempts.set(id, { ...cur, ...structuredClone(patch) });
        return Promise.resolve();
      },
      remove: (id) => {
        const cur = w.attempts.get(id);
        if (cur && (cur.status === "pending" || cur.status === "unknown")) {
          return Promise.reject(new Error("CARD_OUTCOME_UNKNOWN"));
        }
        w.attempts.delete(id);
        return Promise.resolve();
      },
      unresolved: (tid) =>
        Promise.resolve(
          [...w.attempts.values()].filter(
            (a) => (a.status === "pending" || a.status === "unknown") && (!tid || a.card_terminal_id === tid),
          ),
        ),
      list: () => Promise.resolve([...w.attempts.values()]),
      get: (id) => Promise.resolve(w.attempts.get(id)),
    },
    recordTx: (body) => {
      w.recorded.push(structuredClone(body));
      return Promise.resolve({});
    },
    isOnline: () => w.online,
    fiscalBlocked: () => false,
    verifyPin: (_u, pin) => Promise.resolve(pin === "1234" ? { ok: true } : { ok: false, reason: "invalid" }),
    hasPermission: (userId) => Promise.resolve(userId === "manager-1"),
    approvers: () => Promise.resolve([{ userId: "manager-1", name: "Menejer" }]),
    now: () => Date.now(),
    sleep: () => Promise.resolve(),
  };
  return w;
}

const start = (amount: string) => ({
  amount: amount as Money,
  clientEventId: "ev-1",
  cashRegisterId: "cr-1",
  shiftId: "sh-1",
});

const MANAGER: ApprovalRef = {
  mode: "local_pin",
  approved_by: "manager-1",
  pin_verified_locally: true,
  approval_request_id: null,
};

let w: World;
beforeEach(() => {
  w = world();
  configureCardPayment(w.deps);
});
afterEach(() => configureCardPayment(null));

const PAN_FREE = (value: unknown) => {
  const text = JSON.stringify(value);
  expect(text).not.toContain("860031"); // BIN never kept
  expect(text).not.toMatch(/\b\d{13,19}\b/); // no PAN-like digit run
};

describe("card payment — integrated terminal (qaror #71)", () => {
  it("test_qt_m01_24_integrated_card_approved: one purchase, approved result, attempt kept for sale.created", async () => {
    const scope = fork();
    await allSettled(cardPaymentStarted, { scope, params: start("12000.00") });
    const s = scope.getState($cardAttempt);
    expect(s.phase).toBe("approved");
    expect(w.fake.calls.purchase).toBe(1);
    const outcome = scope.getState($cardPaymentOutcome);
    expect(outcome?.mode).toBe("integrated");
    if (outcome?.mode !== "integrated") throw new Error("not integrated");
    expect(outcome.cardResult).toMatchObject({
      status: "approved",
      amount: "12000.00",
      card_mask: "8600********1234",
      card_scheme: "uzcard",
      card_type: "unknown",
      card_type_source: "bin_table",
      resolved_by: "auto",
    });
    const stored = w.attempts.get(outcome.attemptId);
    expect(stored?.status).toBe("approved"); // leaves with the sale event (removeCardAttemptIds)
    expect(w.recorded).toHaveLength(1);
    expect(w.recorded[0]).toMatchObject({ id: outcome.attemptId, kind: "purchase", status: null });
    PAN_FREE([...w.attempts.values(), w.recorded]);
    await allSettled(cardOutcomeConsumed, { scope });
    expect(scope.getState($cardAttempt).phase).toBe("idle");
  });

  it("test_qt_m01_25_declined_retry_new_attempt_and_cancel_on_terminal", async () => {
    const scope = fork();
    await allSettled(cardPaymentStarted, { scope, params: start("12001.00") });
    const first = scope.getState($cardAttempt);
    expect(first.phase).toBe("declined");
    expect(first.errorCode).toBe("CARD_DECLINED");
    expect(first.result?.decline_message).toBe("Mablag' yetarli emas");
    expect(w.attempts.has(first.attemptId ?? "")).toBe(false); // shown, recorded, dropped
    w.fake.fakeCardScenario("approved");
    await allSettled(retryPressed, { scope });
    const second = scope.getState($cardAttempt);
    expect(second.phase).toBe("approved");
    expect(second.attemptId).not.toBe(first.attemptId);
    expect(w.fake.calls.purchase).toBe(2);
  });

  it("cancel-pending while waiting ends the attempt as declined (decline_code cancelled)", async () => {
    w.fake = createFakeCardTerminalClient({ delayMs: 30 });
    const scope = fork();
    const run = allSettled(cardPaymentStarted, { scope, params: start("12000.00") });
    for (let i = 0; i < 50 && scope.getState($cardAttempt).phase !== "pending"; i++) {
      await new Promise((r) => setTimeout(r, 2));
    }
    await allSettled(cancelPressed, { scope });
    await run;
    const s = scope.getState($cardAttempt);
    expect(s.phase).toBe("declined");
    expect(s.result?.decline_code).toBe("cancelled");
  });

  it("test_qt_m01_26_timeout_unknown_status_query_no_auto_retry", async () => {
    const scope = fork();
    await allSettled(cardPaymentStarted, { scope, params: start("12002.00") });
    const s = scope.getState($cardAttempt);
    expect(s.phase).toBe("approved");
    expect(s.result?.resolved_by).toBe("status_query");
    expect(w.fake.calls.purchase).toBe(1);
    expect(w.fake.calls.getStatus).toBeGreaterThanOrEqual(1);
  });

  it("unresolved unknown blocks a new purchase and survives a reload", async () => {
    const scope = fork();
    await allSettled(cardPaymentStarted, { scope, params: start("12003.00") });
    const s = scope.getState($cardAttempt);
    expect(s.phase).toBe("unknown");
    expect(s.errorCode).toBe("CARD_OUTCOME_UNKNOWN");
    expect(w.attempts.get(s.attemptId ?? "")?.status).toBe("unknown"); // blocks logout (16 §12)
    await allSettled(retryPressed, { scope }); // "Qayta yuborish" is off in unknown
    expect(w.fake.calls.purchase).toBe(1);
    // a reload: a new scope restores the blocking attempt from card_attempts
    const reloaded = fork();
    await allSettled(cardPaymentRestored, {
      scope: reloaded,
      params: { cashRegisterId: "cr-1", shiftId: "sh-1" },
    });
    expect(reloaded.getState($cardAttempt)).toMatchObject({ phase: "unknown", attemptId: s.attemptId });
    // pressing Karta again on that terminal → still blocked, no purchase
    const again = fork();
    await allSettled(cardPaymentStarted, { scope: again, params: start("500.00") });
    expect(again.getState($cardAttempt)).toMatchObject({
      phase: "unknown",
      attemptId: s.attemptId,
      amount: "12003.00",
    });
    expect(w.fake.calls.purchase).toBe(1);
  });

  it("test_qt_m01_27_manager_resolves_unknown_without_card_data", async () => {
    const scope = fork();
    await allSettled(cardPaymentStarted, { scope, params: start("12003.00") });
    const attemptId = scope.getState($cardAttempt).attemptId;
    await allSettled(managerResolved, { scope, params: { passed: true, approval: MANAGER } });
    expect(scope.getState($cardAttempt).phase).toBe("resolved_manual");
    expect(scope.getState($cardPaymentOutcome)).toEqual({
      mode: "manual",
      manualReason: "unknown_result",
      approval: MANAGER,
      amount: "12003.00",
      attemptId,
    });
    const body = w.recorded.at(-1);
    expect(body?.card_manual_approval).toEqual(MANAGER);
    expect(body?.result).toMatchObject({
      resolved_by: "manager",
      status: "approved",
      rrn: null,
      card_mask: null,
      card_type: null,
    });
    expect(w.attempts.has(attemptId ?? "")).toBe(false); // on the server now

    const other = fork();
    await allSettled(cardPaymentStarted, { scope: other, params: start("3003.00") });
    await allSettled(managerResolved, { scope: other, params: { passed: false, approval: MANAGER } });
    expect(other.getState($cardAttempt)).toMatchObject({ phase: "declined" });
    expect(other.getState($cardAttempt).result?.decline_code).toBe("not_found");
  });

  it("test_qt_m01_30_amount_mismatch_auto_void", async () => {
    const scope = fork();
    await allSettled(cardPaymentStarted, { scope, params: start("12005.00") });
    const s = scope.getState($cardAttempt);
    expect(s.phase).toBe("declined");
    expect(s.errorCode).toBe("CARD_AMOUNT_MISMATCH");
    expect(w.fake.calls.void).toBe(1);
    expect(scope.getState($cardPaymentOutcome)).toBeNull();
    const kinds = w.recorded.map((r) => `${r.kind}:${r.result?.status ?? "-"}`).sort();
    expect(kinds).toEqual(["purchase:approved", "void:approved"]);
    expect(w.attempts.size).toBe(0); // both reached the server
  });

  it("test_qt_m01_29_sale_cancelled_auto_void_and_void_failed", async () => {
    const scope = fork();
    await allSettled(cardPaymentStarted, { scope, params: start("12000.00") });
    await allSettled(saleCancelled, { scope });
    expect(scope.getState($cardAttempt).phase).toBe("voided");
    expect(w.fake.calls.void).toBe(1);
    const failing = fork();
    await allSettled(cardPaymentStarted, { scope: failing, params: start("12006.00") });
    await allSettled(saleCancelled, { scope: failing });
    // the void failed: the sale is NOT cancelled, the payment stays approved
    expect(failing.getState($cardAttempt)).toMatchObject({
      phase: "approved",
      errorCode: "CARD_VOID_FAILED",
    });
  });

  it("test_qt_m01_33_card_type_from_bin_rules_on_device", async () => {
    w.rules = [{ bin_prefix: "860031", card_type: "corporate", valid_from: "2026-01-01" }];
    const scope = fork();
    await allSettled(cardPaymentStarted, { scope, params: start("12000.00") });
    expect(scope.getState($cardAttempt).result).toMatchObject({
      card_type: "corporate",
      card_type_source: "bin_table",
    });
    PAN_FREE([...w.attempts.values()]);
  });

  it("test_qt_m01_34_offline_purchase_via_agent_no_server_calls", async () => {
    w.online = false;
    const scope = fork();
    await allSettled(cardPaymentStarted, { scope, params: start("12000.00") });
    expect(scope.getState($cardAttempt).phase).toBe("approved");
    expect(w.recorded).toHaveLength(0);
    expect(scope.getState($cardPaymentOutcome)?.mode).toBe("integrated");
  });
});

describe("terminalsiz karta (rekvizitsiz) — policy (21 §9.2, QT-M01-31, B3-T05)", () => {
  it("standalone register: manual card at once, no approval", async () => {
    w.terminals = [];
    w.policy = "forbid";
    const scope = fork();
    await allSettled(cardPaymentStarted, { scope, params: start("12000.00") });
    expect(scope.getState($cardAttempt)).toMatchObject({
      phase: "manual_confirm",
      manualReason: "standalone_terminal",
    });
    expect(scope.getState($manualApprovalNeeded)).toBe(false);
    await allSettled(manualConfirmed, { scope, params: { approval: null } });
    expect(scope.getState($cardPaymentOutcome)).toEqual({
      mode: "manual",
      manualReason: "standalone_terminal",
      approval: null,
      amount: "12000.00",
      attemptId: null,
    });
    expect(w.fake.calls.purchase).toBe(0);
  });

  it("test_qt_m01_31_manual_policy_on_a_terminal_register", async () => {
    w.fake.healthStatus = "offline";
    const scope = fork();
    await allSettled(cardPaymentStarted, { scope, params: start("12000.00") });
    expect(scope.getState($cardAttempt)).toMatchObject({
      phase: "unavailable",
      errorCode: "CARD_TERMINAL_UNREACHABLE",
      terminalStatus: "offline",
    });
    await allSettled(manualRequested, { scope });
    expect(scope.getState($cardAttempt)).toMatchObject({
      phase: "manual_confirm",
      manualReason: "terminal_offline",
    });
    expect(scope.getState($manualApprovalNeeded)).toBe(true);
    await allSettled(manualConfirmed, { scope, params: { approval: null } });
    expect(scope.getState($cardAttempt).errorCode).toBe("CARD_MANUAL_APPROVAL_REQUIRED");
    await allSettled(manualConfirmed, { scope, params: { approval: MANAGER } });
    expect(scope.getState($cardPaymentOutcome)).toMatchObject({
      mode: "manual",
      manualReason: "terminal_offline",
      approval: MANAGER,
    });

    w.policy = "forbid";
    const forbid = fork();
    await allSettled(cardPaymentStarted, { scope: forbid, params: start("12000.00") });
    await allSettled(manualRequested, { scope: forbid });
    expect(forbid.getState($cardAttempt)).toMatchObject({
      phase: "unavailable",
      errorCode: "CARD_MANUAL_NOT_ALLOWED",
    });

    w.policy = "allow";
    const allow = fork();
    await allSettled(cardPaymentStarted, { scope: allow, params: start("12000.00") });
    await allSettled(manualRequested, { scope: allow });
    await allSettled(manualConfirmed, { scope: allow, params: { approval: null } });
    expect(allow.getState($cardAttempt).phase).toBe("manual");
  });

  it("busy terminal → CARD_TERMINAL_BUSY, nothing sent; local PIN approval needs the right and the PIN", async () => {
    w.fake.healthStatus = "busy";
    const scope = fork();
    await allSettled(cardPaymentStarted, { scope, params: start("12000.00") });
    expect(scope.getState($cardAttempt)).toMatchObject({
      phase: "unavailable",
      errorCode: "CARD_TERMINAL_BUSY",
      terminalStatus: "busy",
    });
    expect(w.fake.calls.purchase).toBe(0);
    await expect(verifyApproverFx({ userId: "cashier-1", pin: "1234" })).rejects.toThrow("APPROVAL_INVALID");
    await expect(verifyApproverFx({ userId: "manager-1", pin: "0000" })).rejects.toThrow("PIN_INVALID");
    expect(await verifyApproverFx({ userId: "manager-1", pin: "1234" })).toEqual(MANAGER);
  });
});

describe("SYNC-03 — an approved purchase no sale took is surfaced after a reload", () => {
  async function approvedThenReload(amount: string) {
    const first = fork();
    await allSettled(cardPaymentStarted, { scope: first, params: start(amount) });
    const attemptId = first.getState($cardAttempt).attemptId;
    expect(w.attempts.get(attemptId ?? "")?.status).toBe("approved"); // never reached the outbox
    const reloaded = fork();
    await allSettled(cardPaymentRestored, {
      scope: reloaded,
      params: { cashRegisterId: "cr-1", shiftId: "sh-1" },
    });
    return { reloaded, attemptId };
  }

  it("restore offers the dangling purchase; void → void attempt recorded, the row leaves (logout unblocked)", async () => {
    const { reloaded, attemptId } = await approvedThenReload("12000.00");
    expect(reloaded.getState($cardAttempt)).toMatchObject({ phase: "dangling", attemptId, dangling: true });
    expect(reloaded.getState($cardRecoveryOpen)).toBe(true); // surfaced without opening POS-03
    await allSettled(danglingVoided, { scope: reloaded });
    expect(reloaded.getState($cardAttempt).phase).toBe("voided");
    expect(w.fake.calls.void).toBe(1);
    expect(w.recorded.map((r) => r.kind).sort()).toEqual(["purchase", "purchase", "void"]);
    expect(w.attempts.size).toBe(0);
  });

  it("attach to the current receipt only for the same amount", async () => {
    const { reloaded, attemptId } = await approvedThenReload("12000.00");
    await allSettled(cardPaymentStarted, {
      scope: reloaded,
      params: { ...start("15000.00"), clientEventId: "ev-2" },
    });
    await allSettled(danglingAttached, { scope: reloaded });
    expect(reloaded.getState($cardAttempt).phase).toBe("dangling");
    await allSettled(cardPaymentStarted, {
      scope: reloaded,
      params: { ...start("12000.00"), clientEventId: "ev-3" },
    });
    await allSettled(danglingAttached, { scope: reloaded });
    expect(reloaded.getState($cardAttempt)).toMatchObject({
      phase: "approved",
      attemptId,
      clientEventId: "ev-3",
    });
    expect(reloaded.getState($cardPaymentOutcome)?.mode).toBe("integrated");
    expect(w.fake.calls.purchase).toBe(1);
  });

  it("void failed → orphan, flushed to the server", async () => {
    const { reloaded } = await approvedThenReload("12006.00");
    await allSettled(danglingVoided, { scope: reloaded });
    expect(reloaded.getState($cardAttempt)).toMatchObject({
      phase: "void_failed",
      errorCode: "CARD_VOID_FAILED",
    });
    expect(w.attempts.size).toBe(0); // orphan + failed void sent (online)
  });

  it("logout resolver offline: dangling → orphan → needsFlush", async () => {
    await approvedThenReload("12000.00");
    w.online = false;
    await orphanDanglingFx({ cashRegisterId: "cr-1", shiftId: "sh-1" });
    const [row] = [...w.attempts.values()];
    expect(row?.orphan).toBe(true);
    expect(row && needsFlush(row)).toBe(true);
  });
});

it("logout blocker: cardRecoveryRequested surfaces a dangling purchase in the recovery dialog", async () => {
  const first = fork();
  await allSettled(cardPaymentStarted, { scope: first, params: start("12000.00") });
  const fresh = fork();
  await allSettled(cardRecoveryRequested, { scope: fresh });
  expect(fresh.getState($cardRecoveryOpen)).toBe(true);
  expect(fresh.getState($cardAttempt).phase).toBe("dangling");
});
