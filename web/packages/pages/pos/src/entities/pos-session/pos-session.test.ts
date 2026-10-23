/* eslint-disable @typescript-eslint/require-await -- in-memory fakes of async collaborators */
/**
 * POS session entity (contracts/pos-session.md): local shift totals (offline `running_totals`, 18 §3.3,
 * US-M16-02 expected cash), shift numbers, limit checks (18 §2.4), denominations (POS-15), hotkey routing
 * (07 "Klaviatura") and the session model (sessionStorage cashier, staff snapshot lock-out).
 */
import { allSettled, fork } from "effector";
import { describe, expect, it } from "vitest";

import type { StaffRow } from "@shared/offline";

import {
  cashVariance,
  denominationsTotal,
  eventShiftId,
  limitCovers,
  localShiftTotals,
  nextShiftNo,
  type ShiftEventRow,
} from "./lib/index.ts";
import {
  $posCashier,
  $posSessionStatus,
  $posShift,
  cashierLocked,
  cashierSignedIn,
  configurePosSession,
  posSessionStarted,
  staffRefreshed,
  $posKeysLocked,
  deviceForeign,
  posKeysLocked,
  shiftClosedLocally,
  type PosCashier,
  type PosSessionDeps,
  type StoredCashier,
} from "./model/index.ts";
import { loadShiftSnapshot } from "./model/shift-data.ts";

const SHIFT = "shift-1";
const ev = (
  type: string,
  payload: Record<string, unknown>,
  extra: Partial<ShiftEventRow> = {},
): ShiftEventRow => ({
  client_event_id: `ce-${Math.random()}`,
  type,
  created_at: "2026-10-17T05:00:00.000Z",
  status: "pending",
  retryable: null,
  payload: { shift_id: SHIFT, ...payload },
  ...extra,
});

describe("localShiftTotals — offline running totals (18 §3.3, US-M16-02)", () => {
  it("expected cash = opening + cash sales − cash refunds + deposits − withdrawals; card split by entry mode", () => {
    const sale1 = ev("sale.created", {
      payments: [
        { method: "cash", amount: "120000.00" },
        { method: "card", amount: "30000.00", card_entry_mode: "integrated" },
      ],
    });
    const sale2 = ev("sale.created", {
      payments: [{ method: "card", amount: "40000.00", card_entry_mode: "manual" }],
    });
    const sale3 = ev("sale.created", {
      payments: [
        { method: "click", amount: "10000.00" },
        { method: "debt", amount: "5000.00" },
      ],
    });
    const ret = ev("return.created", { sale_id: "s", refund_method: "cash" });
    const dep = ev("cash_movement.created", {
      id: "m1",
      direction: "in",
      reason: "deposit",
      amount: "50000.00",
    });
    const out = ev("cash_movement.created", {
      id: "m2",
      direction: "out",
      reason: "collection",
      amount: "100000.00",
    });
    const rejected = ev(
      "sale.created",
      { payments: [{ method: "cash", amount: "999.00" }] },
      { status: "rejected", retryable: false },
    );
    const totals = localShiftTotals(
      "200000.00",
      [sale1, sale2, sale3, ret, dep, out, rejected],
      [
        {
          client_event_id: ret.client_event_id,
          kind: "return",
          shift_id: SHIFT,
          total: "12000.00",
          summary: { refund_method: "cash", money_part: "12000.00" },
        },
      ],
    );
    expect(totals.salesCount).toBe(3);
    expect(totals.totalsByMethod.cash).toBe("120000.00");
    expect(totals.cardSplit).toEqual({ integrated: "30000.00", manual: "40000.00" });
    expect(totals.cashReturns).toBe("12000.00");
    expect(totals.cashIn).toBe("50000.00");
    expect(totals.cashOut).toBe("100000.00");
    // 200 000 + 120 000 − 12 000 + 50 000 − 100 000
    expect(totals.expectedCash).toBe("258000.00");
    const rows = Object.fromEntries(totals.rows.map((r) => [r.key, r]));
    expect(rows.card_integrated?.sales).toBe("30000.00");
    expect(rows.card_manual?.sales).toBe("40000.00");
    expect(rows.qr?.sales).toBe("10000.00");
    expect(rows.debt?.sales).toBe("5000.00");
    expect(rows.cash?.net).toBe("108000.00");
    expect(totals.movements.map((m) => m.reason).sort()).toEqual(["collection", "deposit"]);
  });

  it("eventShiftId: shift.opened belongs to its own id", () => {
    expect(eventShiftId({ type: "shift.opened", payload: { id: "x" } })).toBe("x");
    expect(eventShiftId({ type: "sale.created", payload: { shift_id: "y" } })).toBe("y");
  });

  it("loadShiftSnapshot prefers the server running_totals only when nothing of the shift is unsynced", async () => {
    const accepted = {
      ...ev("sale.created", { payments: [{ method: "cash", amount: "1000.00" }] }),
      status: "accepted",
    };
    const rows = [accepted].map((e) => ({ ...e, fiscal: true, ofd_acked_at: null })) as never[];
    const server = {
      totals_by_method: {
        cash: "1000.00",
        card: "0.00",
        uzqr: "0.00",
        click: "0.00",
        payme: "0.00",
        uzum: "0.00",
        debt: "0.00",
      },
      sales_count: 1,
      voided_count: 0,
      returns_total: "0.00",
      cash_in: "0.00",
      cash_out: "0.00",
      expected_cash: "1500.00",
    };
    const snap = await loadShiftSnapshot(
      {
        events: async () => rows,
        history: async () => [],
        runningTotals: async () => server,
        isOnline: () => true,
      },
      { id: SHIFT, opening_cash: "500.00" },
    );
    expect(snap.unsynced).toBe(0);
    expect(snap.expectedCash).toBe("1500.00");
    expect(snap.fiscal).toEqual({ total: 1, acked: 0, unsent: 0, oldestUnsentAt: null });
    const offline = await loadShiftSnapshot(
      {
        events: async () => rows,
        history: async () => [],
        runningTotals: async () => server,
        isOnline: () => false,
      },
      { id: SHIFT, opening_cash: "500.00" },
    );
    expect(offline.server).toBeNull();
    expect(offline.expectedCash).toBe("1500.00");
  });
});

describe("helpers", () => {
  it("nextShiftNo is one above everything known", () => {
    expect(nextShiftNo(12, null, undefined)).toBe(13);
    expect(nextShiftNo(null, null)).toBe(1);
    expect(nextShiftNo(3, 7)).toBe(8);
  });

  it("limitCovers: undefined = no permission, null = unlimited (QT-PERM-05 boundary)", () => {
    expect(limitCovers("50000.0000", "50000.00")).toBe(true);
    expect(limitCovers("50000.0000", "50001.00")).toBe(false);
    expect(limitCovers(null, "99999999.00")).toBe(true);
    expect(limitCovers(undefined, "1.00")).toBe(false);
  });

  it("denominations Σ nominal × count and the variance sign (QT-M01-07)", () => {
    expect(denominationsTotal({ "200000": 2, "50000": 1, "1000": 3 })).toBe("453000.00");
    expect(denominationsTotal({})).toBe("0.00");
    expect(cashVariance("480000.00", "500000.00")).toBe("-20000.00");
    expect(cashVariance("500000.00", "500000.00")).toBe("0.00");
  });
});

const staff = (over: Partial<StaffRow> = {}): StaffRow => ({
  user_id: "u-cashier",
  full_name: "Dilnoza R.",
  role_codes: ["cashier"],
  branch_ids: [],
  active: true,
  must_change_pin: false,
  pin_local_hash: "x",
  permissions: [{ code: "sales.create", limit_value: null }],
  ...over,
});

type TestDeps = PosSessionDeps & { stored: StoredCashier | null; released: number };

function deps(over: Partial<PosSessionDeps> = {}): TestDeps {
  const box: TestDeps = {
    stored: null,
    released: 0,
    identity: async () => ({ deviceId: "d-1", tenantId: "t-1", branchId: "b-1", cashRegisterId: "cr-1" }),
    names: async () => ({ branchName: "Chilonzor-3", cashRegisterName: "Kassa 1" }),
    currentShift: async () => ({
      id: "s-1",
      cash_register_id: "cr-1",
      shift_no: 7,
      opened_at: "2026-10-17T03:00:00Z",
      opened_by: "u-cashier",
      status: "open" as const,
    }),
    staffRow: async () => staff(),
    staffCount: async () => 1,
    readCashier: () => box.stored,
    writeCashier: (c) => {
      box.stored = c;
    },
    releaseActor: async () => {
      box.released += 1;
    },
    ...over,
  };
  return box;
}

const CASHIER: PosCashier = {
  userId: "u-cashier",
  fullName: "Dilnoza R.",
  roleCodes: ["cashier"],
  permissions: ["sales.create"],
  verifiedAt: "2026-10-17T03:00:00Z",
  via: "local",
};

describe("pos-session model", () => {
  it("no identity → no_device; identity + no cashier → locked; sign-in persists, lock clears", async () => {
    const scope = fork();
    const d = deps({ identity: async () => null });
    await allSettled(configurePosSession, { scope, params: d });
    await allSettled(posSessionStarted, { scope });
    expect(scope.getState($posSessionStatus)).toBe("no_device");

    const scope2 = fork();
    const d2 = deps();
    await allSettled(configurePosSession, { scope: scope2, params: d2 });
    await allSettled(posSessionStarted, { scope: scope2 });
    expect(scope2.getState($posSessionStatus)).toBe("locked");
    expect(scope2.getState($posShift)?.shift_no).toBe(7);
    await allSettled(cashierSignedIn, { scope: scope2, params: CASHIER });
    expect(scope2.getState($posSessionStatus)).toBe("ready");
    expect(d2.stored?.userId).toBe("u-cashier");
    await allSettled(cashierLocked, { scope: scope2 });
    expect(scope2.getState($posCashier)).toBeNull();
    expect(d2.stored).toBeNull();
  });

  it("a reload keeps the tab's cashier; a blocked staff row locks the cashier out", async () => {
    const scope = fork();
    const d = deps();
    d.stored = { userId: "u-cashier", verifiedAt: "t", via: "local" };
    await allSettled(configurePosSession, { scope, params: d });
    await allSettled(posSessionStarted, { scope });
    expect(scope.getState($posSessionStatus)).toBe("ready");
    d.staffRow = async () => staff({ active: false });
    await allSettled(staffRefreshed, { scope });
    expect(scope.getState($posSessionStatus)).toBe("locked");
  });

  it("SYNC-10: the cashier disappears from the snapshot → locked", async () => {
    const scope = fork();
    const d = deps();
    d.stored = { userId: "u-cashier", verifiedAt: "t", via: "local" };
    await allSettled(configurePosSession, { scope, params: d });
    await allSettled(posSessionStarted, { scope });
    d.staffRow = async () => undefined;
    await allSettled(staffRefreshed, { scope });
    expect(scope.getState($posSessionStatus)).toBe("locked");
  });

  it("SYNC-10: an empty permission list means no permissions (never the old ones)", async () => {
    const scope = fork();
    const d = deps();
    await allSettled(configurePosSession, { scope, params: d });
    await allSettled(posSessionStarted, { scope });
    await allSettled(cashierSignedIn, {
      scope,
      params: { ...CASHIER, permissions: ["sales.create", "cash.withdraw"] },
    });
    d.staffRow = async () => staff({ permissions: [] });
    await allSettled(staffRefreshed, { scope });
    expect(scope.getState($posCashier)?.permissions).toEqual([]);
  });

  it("SEC-08: a hand-edited sessionStorage value with extra codes is ignored — permissions come from Dexie", async () => {
    const scope = fork();
    const d = deps();
    d.stored = {
      userId: "u-cashier",
      verifiedAt: "t",
      via: "local",
      ...{ permissions: ["cash.withdraw", "returns.approve"], roleCodes: ["owner"] },
    };
    await allSettled(configurePosSession, { scope, params: d });
    await allSettled(posSessionStarted, { scope });
    expect(scope.getState($posCashier)).toMatchObject({
      permissions: ["sales.create"],
      roleCodes: ["cashier"],
    });
    // only {userId, verifiedAt, via} is written back
    await allSettled(cashierSignedIn, { scope, params: CASHIER });
    expect(Object.keys(d.stored ?? {}).sort()).toEqual(["userId", "verifiedAt", "via"].sort());
  });

  it("SEC-05: lock and shift close release the server actor binding", async () => {
    const scope = fork();
    const d = deps();
    await allSettled(configurePosSession, { scope, params: d });
    await allSettled(cashierSignedIn, { scope, params: CASHIER });
    await allSettled(cashierLocked, { scope });
    await allSettled(shiftClosedLocally, { scope });
    expect(d.released).toBe(2);
  });

  it("SEC-07: the cached device is foreign when the online session is another device or tenant", () => {
    const device = { deviceId: "d-1", tenantId: "t-1" };
    expect(deviceForeign(null, device)).toBe(false);
    expect(deviceForeign({ tenant: { id: "t-1" }, device: { id: "d-1" } }, device)).toBe(false);
    expect(deviceForeign({ tenant: { id: "t-1" }, device: null }, device)).toBe(true);
    expect(deviceForeign({ tenant: { id: "t-2" }, device: { id: "d-1" } }, device)).toBe(true);
  });

  it("UX-03: a screen holds the POS keys (GlobalHotkeys reads $posKeysLocked)", async () => {
    const scope = fork();
    await allSettled(posKeysLocked, { scope, params: true });
    expect(scope.getState($posKeysLocked)).toBe(true);
    await allSettled(posKeysLocked, { scope, params: false });
    expect(scope.getState($posKeysLocked)).toBe(false);
  });
});
