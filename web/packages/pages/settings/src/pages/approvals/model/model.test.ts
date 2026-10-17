import { allSettled, fork } from "effector";
import { describe, expect, it } from "vitest";

import { ApiError } from "@shared/api";

import {
  $approveErrors,
  $busy,
  $kindCounts,
  $pendingCount,
  $rejectErrors,
  $requests,
  $resolvedToday,
  $status,
  $visible,
  approveFx,
  approveSubmitted,
  contextLines,
  docTypeKey,
  isDue,
  isPinValid,
  isReasonValid,
  kindChanged,
  listRequestsFx,
  listResolvedFx,
  minutesLeft,
  pageMounted,
  pinErrorCleared,
  rejectFx,
  rejectSubmitted,
  requestedValue,
  resolvedOn,
  tabChanged,
  type ApprovalRequest,
  type ApproveRequest,
  type ListRequest,
  type RejectRequest,
} from "./index.ts";

const TODAY = "2026-10-17";
const NOW = Date.parse("2026-10-17T10:00:00Z");

function req(id: string, patch: Partial<ApprovalRequest> = {}): ApprovalRequest {
  return {
    id,
    branch_id: "b-1",
    kind: "discount_over_limit",
    permission_code: "discount.approve",
    requested_value: "8.0000",
    context: { requested_pct: "8.00", amount: "38880.00" },
    linked_doc_type: null,
    linked_doc_id: null,
    device_id: "d-1",
    status: "pending",
    requested_by: "u-cashier",
    requested_by_name: "Dilnoza R.",
    requested_at: "2026-10-17T09:55:00Z",
    expires_at: "2026-10-17T10:10:00Z",
    resolved_by: null,
    resolved_at: null,
    reject_reason: null,
    consumed_at: null,
    ...patch,
  };
}

const pinInvalid = new ApiError({ status: 400, code: "PIN_INVALID", messageKey: "errors.pin_invalid" });
const alreadyResolved = new ApiError({
  status: 409,
  code: "APPROVAL_REQUEST_ALREADY_RESOLVED",
  messageKey: "errors.approval_request_already_resolved",
});

function scope({
  pending = [req("r-1"), req("r-2", { kind: "cash_withdrawal_over_limit", requested_value: "336000.0000" })],
  approve,
  reject,
}: {
  pending?: ApprovalRequest[];
  approve?: (r: ApproveRequest) => unknown;
  reject?: (r: RejectRequest) => unknown;
} = {}) {
  const listCalls: ListRequest[] = [];
  const approveCalls: ApproveRequest[] = [];
  const rejectCalls: RejectRequest[] = [];
  let queue = pending;
  const s = fork({
    handlers: [
      [
        listRequestsFx,
        (r: ListRequest) => {
          listCalls.push(r);
          return { items: r.tab === "pending" ? queue : [], next_cursor: null };
        },
      ],
      [
        listResolvedFx,
        () => [
          req("x-1", { status: "approved", resolved_at: "2026-10-17T08:00:00Z" }),
          req("x-2", { status: "rejected", resolved_at: "2026-10-16T08:00:00Z" }),
        ],
      ],
      [
        approveFx,
        (r: ApproveRequest) => {
          approveCalls.push(r);
          if (approve) return approve(r);
          queue = queue.filter((q) => q.id !== r.id);
          return { id: r.id, status: "approved", resolved_by: "u-mgr", resolved_at: "2026-10-17T10:01:00Z" };
        },
      ],
      [
        rejectFx,
        (r: RejectRequest) => {
          rejectCalls.push(r);
          if (reject) return reject(r);
          queue = queue.filter((q) => q.id !== r.id);
          return { id: r.id, status: "rejected" };
        },
      ],
    ],
  });
  return { s, listCalls, approveCalls, rejectCalls };
}

describe("BO-16 approvals queue model (18 §9.3–§9.5, B3-T15)", () => {
  it("mount → pending queue + today's resolved; kind chips count the loaded requests", async () => {
    const { s, listCalls } = scope();
    await allSettled(pageMounted, { scope: s, params: { today: TODAY, now: NOW } });
    expect(listCalls).toEqual([{ tab: "pending", cursor: null, silent: false }]);
    expect(s.getState($requests).map((r) => r.id)).toEqual(["r-1", "r-2"]);
    expect(s.getState($kindCounts).discount_over_limit).toBe(1);
    expect(s.getState($kindCounts).cash_withdrawal_over_limit).toBe(1);
    expect(s.getState($resolvedToday).map((r) => r.id)).toEqual(["x-1"]);

    await allSettled(kindChanged, { scope: s, params: "cash_withdrawal_over_limit" });
    expect(s.getState($visible).map((r) => r.id)).toEqual(["r-2"]);
    // Another tab resets the chip and asks the server for that status.
    await allSettled(tabChanged, { scope: s, params: "rejected" });
    expect(listCalls.at(-1)).toEqual({ tab: "rejected", cursor: null, silent: false });
    expect(s.getState($visible)).toEqual([]);
  });

  it("approve with PIN: the request leaves the queue, the resolved list is refreshed", async () => {
    const { s, approveCalls } = scope();
    await allSettled(pageMounted, { scope: s, params: { today: TODAY, now: NOW } });
    await allSettled(approveSubmitted, { scope: s, params: { id: "r-1", pin: "1234" } });
    expect(approveCalls).toEqual([{ id: "r-1", pin: "1234" }]);
    expect(s.getState($requests).map((r) => r.id)).toEqual(["r-2"]);
    expect(s.getState($busy)).toEqual([]);
    expect(s.getState($approveErrors)).toEqual({});
  });

  it("an invalid PIN (not 4–6 digits) is never sent", async () => {
    const { s, approveCalls } = scope();
    await allSettled(pageMounted, { scope: s, params: { today: TODAY, now: NOW } });
    await allSettled(approveSubmitted, { scope: s, params: { id: "r-1", pin: "12a" } });
    await allSettled(approveSubmitted, { scope: s, params: { id: "r-1", pin: "1234567" } });
    expect(approveCalls).toEqual([]);
  });

  it("PIN_INVALID stays on the card (and is cleared on typing); the request stays pending", async () => {
    const { s } = scope({
      approve: () => {
        throw pinInvalid;
      },
    });
    await allSettled(pageMounted, { scope: s, params: { today: TODAY, now: NOW } });
    await allSettled(approveSubmitted, { scope: s, params: { id: "r-1", pin: "9999" } });
    expect(s.getState($approveErrors)["r-1"]?.code).toBe("PIN_INVALID");
    expect(s.getState($requests).map((r) => r.id)).toEqual(["r-1", "r-2"]);
    await allSettled(pinErrorCleared, { scope: s, params: "r-1" });
    expect(s.getState($approveErrors)).toEqual({});
  });

  it("decided elsewhere (409 ALREADY_RESOLVED) → the queue is reloaded", async () => {
    const { s, listCalls } = scope({
      approve: () => {
        throw alreadyResolved;
      },
    });
    await allSettled(pageMounted, { scope: s, params: { today: TODAY, now: NOW } });
    await allSettled(approveSubmitted, { scope: s, params: { id: "r-1", pin: "1234" } });
    expect(listCalls).toHaveLength(2);
    expect(s.getState($status)).toBe("idle");
  });

  it("reject needs a reason (trimmed); the request leaves the queue", async () => {
    const { s, rejectCalls } = scope();
    await allSettled(pageMounted, { scope: s, params: { today: TODAY, now: NOW } });
    await allSettled(rejectSubmitted, { scope: s, params: { id: "r-2", reason: "   " } });
    expect(rejectCalls).toEqual([]);
    await allSettled(rejectSubmitted, { scope: s, params: { id: "r-2", reason: "  Bank orqali  " } });
    expect(rejectCalls).toEqual([{ id: "r-2", reason: "Bank orqali" }]);
    expect(s.getState($requests).map((r) => r.id)).toEqual(["r-1"]);
    expect(s.getState($rejectErrors)).toEqual({});
  });
});

describe("BO-16 «Kutilmoqda (N)» on every tab (UX-14)", () => {
  it("the pending count survives a tab switch and drops on a local decision", async () => {
    const { s } = scope();
    expect(s.getState($pendingCount)).toBeNull();
    await allSettled(pageMounted, { scope: s, params: { today: TODAY, now: NOW } });
    expect(s.getState($pendingCount)).toBe(2);
    await allSettled(approveSubmitted, { scope: s, params: { id: "r-1", pin: "1234" } });
    expect(s.getState($pendingCount)).toBe(1);
    await allSettled(tabChanged, { scope: s, params: "approved" });
    expect(s.getState($requests)).toEqual([]);
    expect(s.getState($pendingCount)).toBe(1);
  });
});

describe("BO-16 lib", () => {
  it("requested value: percent kinds → pct, others → amount (context fallback)", () => {
    expect(requestedValue(req("a"))).toEqual({ pct: "8.0000" });
    expect(
      requestedValue(
        req("b", { kind: "return_over_limit", requested_value: null, context: { amount: "140000.00" } }),
      ),
    ).toEqual({ amount: "140000.00" });
    expect(
      requestedValue(req("c", { kind: "card_manual_entry", requested_value: null, context: {} })),
    ).toBeNull();
  });

  it("context lines: cash reason enum, manual card reason enum, free text, lines; ids are not shown", () => {
    expect(
      contextLines(
        req("a", {
          kind: "cash_withdrawal_over_limit",
          context: { amount: "1.00", reason: "collection", cash_register_id: "cr-1" },
        }),
      ),
    ).toEqual([{ key: "reason", value: "collection" }]);
    expect(
      contextLines(req("b", { kind: "card_manual_entry", context: { manual_reason: "terminal_offline" } })),
    ).toEqual([{ key: "manualReason", value: "terminal_offline" }]);
    expect(
      contextLines(req("c", { kind: "return_over_limit", context: { reason: "Muddati o'tgan" } })),
    ).toEqual([{ key: "comment", value: "Muddati o'tgan" }]);
    expect(contextLines(req("d", { kind: "price_change", context: { lines: [{}, {}] } }))).toEqual([
      { key: "lines", count: 2 },
    ]);
    expect(docTypeKey("cash_movements")).toBe("cash_movements");
    expect(docTypeKey("something_else")).toBe("other");
  });

  it("time left, due, PIN/reason validation, today's resolved", () => {
    expect(minutesLeft("2026-10-17T10:10:00Z", NOW)).toBe(10);
    expect(minutesLeft("2026-10-17T09:59:00Z", NOW)).toBe(0);
    expect(isDue(req("a", { expires_at: "2026-10-17T09:00:00Z" }), NOW)).toBe(true);
    expect(isDue(req("a", { status: "approved", expires_at: "2026-10-17T09:00:00Z" }), NOW)).toBe(false);
    expect(isPinValid("1234")).toBe(true);
    expect(isPinValid("123456")).toBe(true);
    expect(isPinValid("123")).toBe(false);
    expect(isReasonValid(" x ")).toBe(true);
    expect(isReasonValid("x".repeat(1001))).toBe(false);
    const list = [
      req("a", { status: "approved", resolved_at: "2026-10-17T05:00:00Z" }),
      req("b", { status: "rejected", resolved_at: "2026-10-17T07:00:00Z" }),
      req("b", { status: "rejected", resolved_at: "2026-10-17T07:00:00Z" }),
      req("c", { status: "approved", resolved_at: "2026-10-15T07:00:00Z" }),
    ];
    expect(resolvedOn(list, TODAY).map((r) => r.id)).toEqual(["b", "a"]);
  });
});
