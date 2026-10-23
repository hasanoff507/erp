/* eslint-disable @typescript-eslint/require-await -- in-memory fakes of async collaborators */
/**
 * POS-07 (07; 18 §3.2, §16a.6; 16 §2.1; US-M01-04; QT-M01-06/-07 client side): close blocked by an
 * unresolved card attempt (CARD_OUTCOME_UNKNOWN), terminal settlements in `card_settlements[]`, ONE
 * `shift.closed` with exactly the 18 §3.2 fields, Z-report from the push result, Z print document.
 */
import { describe, expect, it } from "vitest";

import { createFakeCardTerminalClient, type TerminalInfo } from "@shared/lib/card-terminal";
import type { Money } from "@shared/lib/money";
import type { ZReport } from "@shared/models";

import type { ShiftCount } from "#/entities/pos-session/index.ts";

import {
  closeShift,
  heldCloseCount,
  shiftClosedPayload,
  tashkentDate,
  zFromPush,
  zReceiptDoc,
  type CloseDeps,
} from "./index.ts";

const SHIFT = {
  id: "s-1",
  cash_register_id: "cr-1",
  shift_no: 214,
  opened_at: "2026-10-17T03:00:00Z",
  opened_by: "u-1",
  status: "open" as const,
  opening_cash: "200000.00",
};
const COUNT: ShiftCount = {
  shiftId: "s-1",
  countedCash: "480000.00" as Money,
  countedCardTotal: "400000.00" as Money,
  varianceNote: " Kamomad — tekshiriladi ",
  expectedCash: "500000.00" as Money,
  variance: "-20000.00" as Money,
};
const TERMINAL: TerminalInfo = {
  id: "t-1",
  name: "T1",
  adapter: "fake",
  driver: "fake",
  local_id: null,
  tid: "T0000001",
  is_default: true,
  status: "active",
  capabilities: {},
};
const Z: ZReport = {
  expected_cash: "500000.00",
  counted_cash: "480000.00",
  variance: "-20000.00",
  totals_by_method: {
    cash: "2412500.00",
    card: "1543500.00",
    uzqr: "0.00",
    click: "615000.00",
    payme: "0.00",
    uzum: "0.00",
    debt: "210000.00",
  },
  card_split: { integrated: "1143500.00", manual: "400000.00" },
  card_settlements: [],
  vat_total: "500000.00",
  discount_total: "0.00",
  returns_total: "66000.00",
  sales_count: 121,
  returns_count: 2,
};

function deps(over: Partial<CloseDeps> = {}): CloseDeps & { enqueued: unknown[] } {
  const enqueued: unknown[] = [];
  return {
    enqueued,
    unresolvedAttempts: async () => 0,
    terminals: async () => [TERMINAL],
    client: () => createFakeCardTerminalClient({ sleep: () => Promise.resolve() }),
    enqueue: async (payload) => (enqueued.push(payload), { clientEventId: "ce-close" }),
    markClosed: async () => undefined,
    awaitResult: async (id) => ({
      client_event_id: id,
      status: "accepted",
      server: { id: "s-1", shift_no: 214, z_report: Z },
    }),
    zReport: async () => {
      throw new Error("not used");
    },
    now: () => "2026-10-17T16:05:00Z",
    ...over,
  };
}

describe("closeShift", () => {
  it("an unresolved card attempt blocks the close (CARD_OUTCOME_UNKNOWN) — nothing is enqueued", async () => {
    const d = deps({ unresolvedAttempts: async () => 1 });
    expect(await closeShift(d, { shift: SHIFT, count: COUNT, actorUserId: "u-1" })).toEqual({
      ok: false,
      error: "CARD_OUTCOME_UNKNOWN",
    });
    expect(d.enqueued).toEqual([]);
  });

  it("settles the bound terminal, sends ONE shift.closed (18 §3.2) and returns the server Z-report", async () => {
    const d = deps();
    const r = await closeShift(d, { shift: SHIFT, count: COUNT, actorUserId: "u-1" });
    expect(r.ok).toBe(true);
    expect(d.enqueued).toHaveLength(1);
    const payload = d.enqueued[0] as Record<string, unknown>;
    expect(Object.keys(payload).sort()).toEqual(
      ["card_settlements", "counted_card_total", "counted_cash", "shift_id", "variance_note"].sort(),
    );
    expect(payload).toMatchObject({
      shift_id: "s-1",
      counted_cash: "480000.00",
      counted_card_total: "400000.00",
      variance_note: "Kamomad — tekshiriladi",
    });
    const settlements = payload.card_settlements as Record<string, unknown>[];
    expect(settlements).toHaveLength(1);
    expect(settlements[0]).toMatchObject({
      card_terminal_id: "t-1",
      status: null,
      purchase_count: 0,
      purchase_total: "0.00",
    });
    expect(r.ok && r.z).toEqual(Z);
  });

  it("a terminal that cannot settle is reported as status=failed; the close goes on", async () => {
    const failing = createFakeCardTerminalClient({ sleep: () => Promise.resolve() });
    failing.settlement = () =>
      Promise.reject(Object.assign(new Error("x"), { code: "CARD_TERMINAL_UNREACHABLE" }));
    const d = deps({ client: () => failing });
    const r = await closeShift(d, { shift: SHIFT, count: COUNT, actorUserId: "u-1" });
    expect(r.ok && r.settlements[0]).toMatchObject({
      status: "failed",
      terminal_response: { error: "CARD_TERMINAL_UNREACHABLE" },
    });
  });

  it("offline: no push result → local Z (null from push)", () => {
    expect(zFromPush(null)).toBeNull();
    expect(zFromPush({ client_event_id: "x", status: "rejected", server: null })).toBeNull();
  });

  it("variance 0 → note null; Tashkent business date", () => {
    expect(shiftClosedPayload("s-1", { ...COUNT, varianceNote: "  " }, []).variance_note).toBeNull();
    expect(tashkentDate("2026-10-17T20:30:00Z")).toBe("2026-10-18");
  });

  it("Z print document: kind z_report, card integrated / terminalsiz apart, fiscal pending", () => {
    const doc = zReceiptDoc(
      { source: "server", shiftId: "s-1", shiftNo: 214, report: Z, fiscalStatus: "pending" },
      {
        storeName: "Baraka",
        branchName: "Chilonzor-3",
        cashierName: "Dilnoza R.",
        registerName: "Kassa 1",
        at: "2026-10-17T16:05:00Z",
      },
    );
    expect(doc.kind).toBe("z_report");
    expect(doc.fiscalPending).toBe(true);
    expect(doc.zReport?.cardSplit).toEqual({ integrated: "1143500.00", manual: "400000.00" });
    expect(doc.zReport?.variance).toBe("-20000.00");
    expect(doc.lines).toEqual([]);
  });
});

describe("ACC-01 held shift close", () => {
  it("counts the earlier documents the shift.closed waits for (by shift id or by its event id)", () => {
    const held = [{ clientEventId: "ce-close", shiftId: null, waitingFor: ["ce-1", "ce-2"] }];
    expect(heldCloseCount(held, "s-1", "ce-close")).toBe(2);
    expect(heldCloseCount([{ clientEventId: "x", shiftId: "s-1", waitingFor: ["ce-1"] }], "s-1", null)).toBe(
      1,
    );
    expect(heldCloseCount([], "s-1", "ce-close")).toBe(0);
  });
});
