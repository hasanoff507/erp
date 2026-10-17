/* eslint-disable @typescript-eslint/require-await -- in-memory fakes of async collaborators */
/**
 * POS-01 (07; 14 §4.3/§7.2/§12; 18 §3.1; US-M01-04; B3-T17 client): PIN verification online → local
 * fallback, lockout and must_change_pin; the shift plan (resume / adopt / busy / open / warehouse); the
 * staff picker → PIN → `shift.opened` flow and the device registration (CSRF refresh after the sid change).
 */
import { allSettled, fork } from "effector";
import { describe, expect, it } from "vitest";

import { ApiError } from "@shared/api";
import type { PinVerifiedOut } from "@shared/models";
import type { PinResult, StaffRow } from "@shared/offline";

import { $posCashier, $posShift, configurePosSession } from "#/entities/pos-session/index.ts";

import {
  $pinError,
  $shiftPlan,
  $step,
  configureLogin,
  loginOpened,
  openShiftPressed,
  pinSubmitted,
  planShift,
  registerSubmitted,
  shiftOpenedPayload,
  staffPicked,
  verifyCashierPin,
  type LoginDeps,
  type PinDeps,
} from "./index.ts";

const row = (over: Partial<StaffRow> = {}): StaffRow => ({
  user_id: "u-1",
  full_name: "Dilnoza R.",
  role_codes: ["cashier"],
  branch_ids: [],
  active: true,
  must_change_pin: false,
  pin_local_hash: "pbkdf2_sha256$1000$AAECAwQFBgcICQoLDA0ODw==$IkDqKiJ1SjxGEDVu+OTXrPJa8qw9LRGGbel6i3gSxSw=",
  permissions: [
    { code: "sales.create", limit_value: null },
    { code: "shift.open", limit_value: null },
  ],
  ...over,
});

const verified: PinVerifiedOut = {
  user_id: "u-1",
  full_name: "Dilnoza R.",
  roles: ["cashier"],
  permissions: ["sales.create", "shift.open", "shift.close"],
  verified_at: "2026-10-17T03:00:00Z",
  pin_local_hash: "pbkdf2_sha256$600000$new$hash=",
};

function pinDeps(over: Partial<PinDeps> & { local?: PinResult } = {}): PinDeps & { stored: string[] } {
  const stored: string[] = [];
  return {
    stored,
    isOnline: () => true,
    onlineVerify: async () => verified,
    storeVerifier: async (_u, h) => void stored.push(h),
    localVerify: async () => over.local ?? { ok: true, user: row(), mustChangePin: false },
    staffRow: async () => row(),
    now: () => "2026-10-17T03:00:00Z",
    ...over,
  };
}

const apiError = (code: string, params: Record<string, unknown> = {}, status = 400) =>
  new ApiError({ status, code, messageKey: `errors.${code.toLowerCase()}`, params });

describe("verifyCashierPin (14 §4.3, §12, device-auth.md §2)", () => {
  it("online success stores the fresh PBKDF2 verifier and uses the server's permissions", async () => {
    const d = pinDeps();
    const r = await verifyCashierPin(d, "u-1", "1234");
    expect(r).toMatchObject({
      ok: true,
      cashier: { userId: "u-1", via: "online", permissions: verified.permissions },
    });
    expect(d.stored).toEqual([verified.pin_local_hash]);
  });

  it("server PIN_INVALID / must_change_pin / ACCOUNT_LOCKED are final (no local fallback)", async () => {
    let local = 0;
    const base = {
      localVerify: async (): Promise<PinResult> => (local++, { ok: true, user: row(), mustChangePin: false }),
    };
    expect(
      await verifyCashierPin(
        pinDeps({ ...base, onlineVerify: () => Promise.reject(apiError("PIN_INVALID")) }),
        "u-1",
        "0000",
      ),
    ).toEqual({
      ok: false,
      reason: "invalid",
      attemptsLeft: null,
    });
    expect(
      await verifyCashierPin(
        pinDeps({
          ...base,
          onlineVerify: () => Promise.reject(apiError("PIN_INVALID", { reason: "must_change_pin" })),
        }),
        "u-1",
        "0000",
      ),
    ).toEqual({ ok: false, reason: "must_change" });
    expect(
      await verifyCashierPin(
        pinDeps({
          ...base,
          onlineVerify: () => Promise.reject(apiError("ACCOUNT_LOCKED", { retry_after_s: 300 }, 423)),
        }),
        "u-1",
        "0000",
      ),
    ).toEqual({ ok: false, reason: "locked", lockedUntil: null, retryAfterS: 300 });
    expect(local).toBe(0);
  });

  it("SEC-07: a server refusal (403 device_required) is final — no local fallback", async () => {
    let local = 0;
    const r = await verifyCashierPin(
      pinDeps({
        onlineVerify: () => Promise.reject(apiError("PERMISSION_DENIED", { reason: "device_required" }, 403)),
        localVerify: async () => (local++, { ok: true, user: row(), mustChangePin: false }),
      }),
      "u-1",
      "1234",
    );
    expect(r).toEqual({ ok: false, reason: "refused" });
    expect(local).toBe(0);
    const five = await verifyCashierPin(
      pinDeps({ onlineVerify: () => Promise.reject(apiError("INTERNAL_ERROR", {}, 503)) }),
      "u-1",
      "1234",
    );
    expect(five).toMatchObject({ ok: true, cashier: { via: "local" } });
  });

  it("RATE_LIMITED (Redis down, fail-closed) or a network error → the local verifier", async () => {
    const r = await verifyCashierPin(
      pinDeps({ onlineVerify: () => Promise.reject(apiError("RATE_LIMITED", {}, 429)) }),
      "u-1",
      "1234",
    );
    expect(r).toMatchObject({ ok: true, cashier: { via: "local" } });
  });

  it("offline: local result mapping — wrong PIN with attempts left, lockout, no verifier, must change", async () => {
    const off = (local: PinResult) =>
      verifyCashierPin(pinDeps({ isOnline: () => false, local }), "u-1", "9999");
    expect(await off({ ok: false, reason: "invalid", attemptsLeft: 3 })).toEqual({
      ok: false,
      reason: "invalid",
      attemptsLeft: 3,
    });
    expect(await off({ ok: false, reason: "locked", lockedUntil: "2026-10-17T03:05:00Z" })).toEqual({
      ok: false,
      reason: "locked",
      lockedUntil: "2026-10-17T03:05:00Z",
      retryAfterS: null,
    });
    expect(await off({ ok: false, reason: "no_verifier" })).toEqual({ ok: false, reason: "no_verifier" });
    expect(await off({ ok: true, user: row(), mustChangePin: true })).toEqual({
      ok: false,
      reason: "must_change",
    });
  });

  it("a user without any POS permission cannot sign in (07 POS-01)", async () => {
    const r = await verifyCashierPin(
      pinDeps({ onlineVerify: async () => ({ ...verified, permissions: ["reports.sales.view"] }) }),
      "u-1",
      "1234",
    );
    expect(r).toEqual({ ok: false, reason: "no_pos_role" });
  });
});

describe("planShift (07 POS-01 step ②, 18 §3.1)", () => {
  const base = {
    deviceId: "d-1",
    cashRegisterId: "cr-1",
    canOpen: true,
    lastShiftNo: 5,
    lastCountedCash: "480000.00",
  };
  const local = {
    id: "s-l",
    cash_register_id: "cr-1",
    shift_no: 6,
    opened_at: "x",
    opened_by: "u",
    status: "open" as const,
  };

  it("resumes the local open shift", () => {
    expect(planShift({ ...base, local, server: null })).toEqual({
      kind: "resume",
      shift: local,
      adopt: false,
    });
  });

  it("adopts the server's open shift of THIS device; another device's shift blocks (SHIFT_ALREADY_OPEN)", () => {
    const open = {
      id: "s-9",
      shift_no: 9,
      status: "open",
      device_id: "d-1",
      opened_by: "u",
      opened_at: "t",
      opening_cash: "0.00",
    };
    expect(
      planShift({
        ...base,
        local: null,
        server: { cash_register_id: "cr-1", open_shift: open, last_shift_no: 9 },
      }),
    ).toMatchObject({
      kind: "resume",
      adopt: true,
      shift: { id: "s-9", shift_no: 9 },
    });
    expect(
      planShift({
        ...base,
        local: null,
        server: { cash_register_id: "cr-1", open_shift: { ...open, device_id: "d-2" }, last_shift_no: 9 },
      }),
    ).toEqual({ kind: "busy" });
  });

  it("new shift: number above server and device, opening cash = last counted cash", () => {
    expect(
      planShift({
        ...base,
        local: null,
        server: { cash_register_id: "cr-1", open_shift: null, last_shift_no: 12 },
      }),
    ).toEqual({
      kind: "open",
      shiftNo: 13,
      openingCash: "480000.00",
    });
  });

  it("SYNC-01: a server open_shift this device already closed is not re-adopted → new shift, number + 1", () => {
    const open = {
      id: "s-9",
      shift_no: 9,
      status: "open",
      device_id: "d-1",
      opened_by: "u",
      opened_at: "t",
      opening_cash: "0.00",
    };
    expect(
      planShift({
        ...base,
        local: null,
        lastShiftNo: 9,
        server: { cash_register_id: "cr-1", open_shift: open, last_shift_no: 9 },
        closedLocally: new Set(["s-9"]),
      }),
    ).toEqual({ kind: "open", shiftNo: 10, openingCash: "480000.00" });
  });

  it("no shift.open (storekeeper) → warehouse menu", () => {
    expect(planShift({ ...base, canOpen: false, local: null, server: null })).toEqual({ kind: "warehouse" });
  });

  it("shift.opened payload is exactly 18 §3.1", () => {
    expect(shiftOpenedPayload("id-1", "cr-1", 13, "500000")).toEqual({
      id: "id-1",
      cash_register_id: "cr-1",
      shift_no: 13,
      opening_cash: "500000.00",
      comment: null,
    });
  });
});

type TestLoginDeps = LoginDeps & { opened: unknown[]; registered: number; identities: unknown[] };

function loginDeps(): TestLoginDeps {
  const box: TestLoginDeps = {
    ...pinDeps(),
    opened: [],
    registered: 0,
    identities: [],
    staff: async () => [
      row(),
      row({
        user_id: "u-x",
        full_name: "Accountant",
        permissions: [{ code: "reports.sales.view", limit_value: null }],
      }),
    ],
    identity: async () => null,
    setIdentity: async (v) => void box.identities.push(v),
    cashRegisters: async () => [],
    registerDevice: async (id) => ({
      id: "d-new",
      branch_id: "b-1",
      branch_name: "Chilonzor-3",
      cash_register_id: id,
      cash_register_name: "Kassa 1",
    }),
    afterRegister: () => {
      box.registered += 1;
    },
    tenantId: () => "t-1",
    localShift: async () => null,
    serverShift: async () => ({ cash_register_id: "cr-1", open_shift: null, last_shift_no: 213 }),
    lastShiftNo: async () => null,
    lastCountedCash: async () => "200000.00",
    closedShiftIds: async () => new Set<string>(),
    openShift: async (payload) => {
      box.opened.push(payload);
      return { clientEventId: "ce-1", createdAt: "2026-10-17T03:00:00Z" };
    },
    saveShift: async () => undefined,
    rememberShiftNo: async () => undefined,
  };
  return box;
}

const DEVICE = {
  deviceId: "d-1",
  tenantId: "t-1",
  branchId: "b-1",
  cashRegisterId: "cr-1",
  branchName: "Chilonzor-3",
  cashRegisterName: "Kassa 1",
};

describe("POS-01 model flow", () => {
  it("staff picker → PIN → shift step → shift.opened → done (non-POS staff hidden)", async () => {
    const scope = fork();
    const d = loginDeps();
    await allSettled(configurePosSession, {
      scope,
      params: {
        identity: async () => null,
        names: async () => null,
        currentShift: async () => null,
        staffRow: async () => row(),
        staffCount: async () => 1,
        readCashier: () => null,
        writeCashier: () => undefined,
        releaseActor: async () => undefined,
      },
    });
    await allSettled(configureLogin, { scope, params: d });
    await allSettled(loginOpened, { scope, params: { device: DEVICE, cashier: null } });
    expect(scope.getState($step)).toBe("staff");
    await allSettled(staffPicked, { scope, params: "u-1" });
    expect(scope.getState($step)).toBe("pin");
    await allSettled(pinSubmitted, { scope, params: "1234" });
    expect(scope.getState($posCashier)?.userId).toBe("u-1");
    expect(scope.getState($step)).toBe("shift");
    expect(scope.getState($shiftPlan)).toEqual({ kind: "open", shiftNo: 214, openingCash: "200000.00" });
    await allSettled(openShiftPressed, { scope });
    expect(d.opened).toEqual([
      {
        id: expect.any(String) as string,
        cash_register_id: "cr-1",
        shift_no: 214,
        opening_cash: "200000.00",
        comment: null,
      },
    ]);
    expect(scope.getState($posShift)?.shift_no).toBe(214);
    expect(scope.getState($step)).toBe("done");
  });

  it("wrong PIN shows the error and keeps the PIN step", async () => {
    const scope = fork();
    const d = { ...loginDeps(), onlineVerify: () => Promise.reject(apiError("PIN_INVALID")) };
    await allSettled(configureLogin, { scope, params: d });
    await allSettled(loginOpened, { scope, params: { device: DEVICE, cashier: null } });
    await allSettled(staffPicked, { scope, params: "u-1" });
    await allSettled(pinSubmitted, { scope, params: "0000" });
    expect(scope.getState($pinError)).toEqual({ ok: false, reason: "invalid", attemptsLeft: null });
    expect(scope.getState($step)).toBe("pin");
  });

  it("device registration sets the identity and refreshes CSRF/session (B3-T17)", async () => {
    const scope = fork();
    const d = loginDeps();
    await allSettled(configureLogin, { scope, params: d });
    await allSettled(loginOpened, { scope, params: { device: null, cashier: null } });
    expect(scope.getState($step)).toBe("register");
    await allSettled(registerSubmitted, { scope, params: "cr-7" });
    expect(d.identities).toEqual([
      { deviceId: "d-new", tenantId: "t-1", branchId: "b-1", cashRegisterId: "cr-7" },
    ]);
    expect(d.registered).toBe(1);
    expect(scope.getState($step)).toBe("staff");
  });
});
