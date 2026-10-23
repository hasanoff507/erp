/**
 * POS-01 — Kassaga kirish / Smena ochish (07 POS-01; 14 §4.3, §7.2, §12; 16 §1, §9, §12; 18 §3.1).
 * Steps: device registration (no erp-device identity) → staff picker (permissions pull scope) → PIN
 * (online `POST /auth/pin/verify`, local PBKDF2 verifier when offline / server unavailable) → shift
 * (resume the open one, or `shift.opened` with the opening cash) or the warehouse menu (no `shift.open`).
 */
import { attach, combine, createEffect, createEvent, createStore, sample } from "effector";

import { ApiError, api, resetCsrfToken, toApiError } from "@shared/api";
import type { CashRegisterOut, PinVerifiedOut } from "@shared/models";
import { money, type Money } from "@shared/lib/money";
import {
  deviceIdentity,
  deviceSettings,
  enqueueEvent,
  outbox,
  pullApplied,
  shift as localShift,
  staff as staffRepo,
  storePinVerifier,
  syncNow,
  verifyLocalPin,
  type DeviceIdentity,
  type PinResult,
  type ServerShiftSnapshot,
  type StaffRow,
} from "@shared/offline";
import { $isOnline } from "@shared/state/network";
import { $session, sessionCheckRequested } from "@shared/state/session";

import {
  DEVICE_NAMES_KEY,
  cashierSignedIn,
  deviceRegistered,
  nextShiftNo,
  shiftOpenedLocally,
  uuidv7,
  type PosCashier,
  type PosDevice,
  type PosShift,
} from "#/entities/pos-session/index.ts";

export const LAST_SHIFT_NO_KEY = "pos.last_shift_no";
export const LAST_COUNTED_CASH_KEY = "pos.last_counted_cash";
/** erp-device: ids of the shifts this device closed (last 20) — survives the logout wipe (SYNC-01). */
export const CLOSED_SHIFTS_KEY = "pos.closed_shifts";

/** Permissions that make a user a POS user (07 POS-01: nobody else may sign in). */
export const POS_PERMISSIONS = [
  "sales.create",
  "shift.open",
  "shift.close",
  "returns.create",
  "purchases.receive",
  "transfer.create",
  "transfer.receive",
  "stock.count.create",
] as const;

export const hasPosRole = (permissions: readonly string[]): boolean =>
  POS_PERMISSIONS.some((p) => permissions.includes(p));

// ---- PIN ------------------------------------------------------------------------------------------

export type PinOutcome =
  | { ok: true; cashier: PosCashier }
  | { ok: false; reason: "invalid"; attemptsLeft: number | null }
  | { ok: false; reason: "locked"; lockedUntil: string | null; retryAfterS: number | null }
  | { ok: false; reason: "must_change" | "no_verifier" | "inactive" | "no_pos_role" | "refused" };

export interface PinDeps {
  isOnline(): boolean;
  onlineVerify(userId: string, pin: string): Promise<PinVerifiedOut>;
  storeVerifier(userId: string, hash: string): Promise<void>;
  localVerify(userId: string, pin: string): Promise<PinResult>;
  staffRow(userId: string): Promise<StaffRow | undefined>;
  now(): string;
}

function cashierFrom(
  row: StaffRow | undefined,
  out: PinVerifiedOut | null,
  via: "online" | "local",
  at: string,
) {
  const permissions = out ? [...out.permissions] : (row?.permissions.map((p) => p.code) ?? []);
  const cashier: PosCashier = {
    userId: out?.user_id ?? row?.user_id ?? "",
    fullName: out?.full_name ?? row?.full_name ?? "",
    roleCodes: out ? [...out.roles] : [...(row?.role_codes ?? [])],
    permissions,
    verifiedAt: out?.verified_at ?? at,
    via,
  };
  return cashier;
}

export async function verifyCashierPin(deps: PinDeps, userId: string, pin: string): Promise<PinOutcome> {
  const row = await deps.staffRow(userId);
  if (deps.isOnline()) {
    try {
      const out = await deps.onlineVerify(userId, pin);
      if (out.pin_local_hash) await deps.storeVerifier(userId, out.pin_local_hash);
      const cashier = cashierFrom(row, out, "online", deps.now());
      return hasPosRole(cashier.permissions) ? { ok: true, cashier } : { ok: false, reason: "no_pos_role" };
    } catch (e) {
      const err = toApiError(e);
      if (err.code === "PIN_INVALID") {
        if (err.params.reason === "must_change_pin") return { ok: false, reason: "must_change" };
        return { ok: false, reason: "invalid", attemptsLeft: null };
      }
      if (err.code === "ACCOUNT_LOCKED") {
        const s = err.params.retry_after_s;
        return {
          ok: false,
          reason: "locked",
          lockedUntil: null,
          retryAfterS: typeof s === "number" ? s : null,
        };
      }
      // SEC-07: only "server not reachable / not able to answer" falls back to the local verifier —
      // network failure, RATE_LIMITED (Redis down, fail-closed) or a 5xx. A refusal (403 device_required,
      // PERMISSION_DENIED …) is final.
      const unreachable =
        err.code === "NETWORK_ERROR" ||
        err.code === "RATE_LIMITED" ||
        (err.status !== null && err.status >= 500);
      if (!unreachable) return { ok: false, reason: "refused" };
    }
  }
  const local = await deps.localVerify(userId, pin);
  if (local.ok) {
    if (local.mustChangePin) return { ok: false, reason: "must_change" };
    const cashier = cashierFrom(local.user, null, "local", deps.now());
    return hasPosRole(cashier.permissions) ? { ok: true, cashier } : { ok: false, reason: "no_pos_role" };
  }
  if (local.reason === "invalid") return { ok: false, reason: "invalid", attemptsLeft: local.attemptsLeft };
  if (local.reason === "locked")
    return { ok: false, reason: "locked", lockedUntil: local.lockedUntil, retryAfterS: null };
  if (local.reason === "no_verifier") return { ok: false, reason: "no_verifier" };
  return { ok: false, reason: "inactive" };
}

// ---- shift ----------------------------------------------------------------------------------------

export type ShiftPlan =
  | { kind: "resume"; shift: PosShift; adopt: boolean }
  | { kind: "open"; shiftNo: number; openingCash: Money }
  | { kind: "busy" }
  | { kind: "warehouse" };

/**
 * What POS-01 step ② does for this cashier: resume the local open shift, adopt the server's open shift
 * of THIS device (after a logout wipe), refuse when another device holds the register's shift
 * (SHIFT_ALREADY_OPEN), open a new one (`shift.open`) or go to the warehouse menu.
 */
export function planShift(input: {
  local: PosShift | null;
  server: ServerShiftSnapshot | null;
  deviceId: string;
  cashRegisterId: string | null;
  canOpen: boolean;
  lastShiftNo: number | null;
  lastCountedCash: string | null;
  /** Shifts this device already closed (local closed rows + `shift.closed` events) — SYNC-01. */
  closedLocally?: ReadonlySet<string>;
}): ShiftPlan {
  const { local, server } = input;
  if (!input.canOpen) return local ? { kind: "resume", shift: local, adopt: false } : { kind: "warehouse" };
  if (local) return { kind: "resume", shift: local, adopt: false };
  const serverOpen = server?.open_shift ?? null;
  // the pull snapshot lags behind our own `shift.closed`: a shift closed here is never re-adopted
  const open = serverOpen && input.closedLocally?.has(serverOpen.id) ? null : serverOpen;
  if (open && open.status === "open") {
    if (open.device_id !== input.deviceId) return { kind: "busy" };
    return {
      kind: "resume",
      adopt: true,
      shift: {
        id: open.id,
        cash_register_id: input.cashRegisterId ?? server?.cash_register_id ?? "",
        shift_no: open.shift_no,
        opened_at: open.opened_at,
        opened_by: open.opened_by,
        status: "open",
        client_event_id: null,
        opening_cash: open.opening_cash,
      },
    };
  }
  let opening = "0.00" as Money;
  try {
    if (input.lastCountedCash) opening = money(input.lastCountedCash);
  } catch {
    opening = "0.00" as Money;
  }
  return {
    kind: "open",
    shiftNo: nextShiftNo(server?.last_shift_no, input.lastShiftNo),
    openingCash: opening,
  };
}

/** 18 §3.1 payload. */
export function shiftOpenedPayload(id: string, cashRegisterId: string, shiftNo: number, openingCash: string) {
  return {
    id,
    cash_register_id: cashRegisterId,
    shift_no: shiftNo,
    opening_cash: money(openingCash),
    comment: null,
  };
}

// ---- model ----------------------------------------------------------------------------------------

export type LoginStep =
  "loading" | "register" | "await_staff" | "staff" | "pin" | "shift" | "busy" | "warehouse" | "done";

export interface LoginDeps extends PinDeps {
  staff(): Promise<StaffRow[]>;
  identity(): Promise<DeviceIdentity | null>;
  setIdentity(
    v: DeviceIdentity,
    names: { branchName: string | null; cashRegisterName: string | null },
  ): Promise<void>;
  cashRegisters(branchId: string): Promise<CashRegisterOut[]>;
  registerDevice(cashRegisterId: string): Promise<{
    id: string;
    branch_id: string;
    branch_name: string;
    cash_register_id: string;
    cash_register_name: string;
  }>;
  afterRegister(): void;
  tenantId(): string | null;
  localShift(): Promise<PosShift | null>;
  serverShift(): Promise<ServerShiftSnapshot | null>;
  lastShiftNo(): Promise<number | null>;
  closedShiftIds(): Promise<Set<string>>;
  lastCountedCash(): Promise<string | null>;
  openShift(
    payload: ReturnType<typeof shiftOpenedPayload>,
    actorUserId: string,
  ): Promise<{ clientEventId: string; createdAt: string }>;
  saveShift(shift: PosShift): Promise<void>;
  rememberShiftNo(n: number): Promise<void>;
}

export const defaultLoginDeps: LoginDeps = {
  isOnline: () => $isOnline.getState(),
  onlineVerify: (userId, pin) => api.auth.pinVerify({ user_id: userId, pin }),
  storeVerifier: (userId, hash) => storePinVerifier(userId, hash),
  localVerify: (userId, pin) => verifyLocalPin(userId, pin),
  staffRow: (userId) => staffRepo.get(userId),
  now: () => new Date().toISOString(),
  staff: () => staffRepo.list(),
  identity: () => deviceIdentity.get(),
  setIdentity: async (v, names) => {
    await deviceIdentity.set(v);
    await deviceSettings.set(DEVICE_NAMES_KEY, names);
  },
  cashRegisters: async (branchId) => (await api.branches.cashRegistersList({ branch_id: branchId })).items,
  registerDevice: (cashRegisterId) =>
    api.auth.devicesRegister({ cash_register_id: cashRegisterId, app_version: "web-pos" }),
  afterRegister: () => {
    // 14 §7.2: the sid changed — the old CSRF token is dead; re-read the (now device-bound) session.
    resetCsrfToken();
    sessionCheckRequested();
    void syncNow().catch(() => undefined);
  },
  tenantId: () => $session.getState()?.tenant.id ?? null,
  localShift: async () => await localShift.current(),
  serverShift: () => localShift.server(),
  lastShiftNo: async () => (await deviceSettings.get<number>(LAST_SHIFT_NO_KEY)) ?? null,
  lastCountedCash: async () => (await deviceSettings.get<string>(LAST_COUNTED_CASH_KEY)) ?? null,
  closedShiftIds: async () => {
    // erp-device list (survives a logout wipe) ∪ local closed rows + unsynced `shift.closed` (@shared/offline)
    const ids = new Set((await deviceSettings.get<string[]>(CLOSED_SHIFTS_KEY)) ?? []);
    for (const id of await localShift.closedLocallyIds()) ids.add(id);
    for (const row of await outbox.list({ limit: 5000 })) {
      if (row.type === "shift.closed" && typeof row.payload.shift_id === "string")
        ids.add(row.payload.shift_id);
    }
    return ids;
  },
  openShift: async (payload, actorUserId) => {
    const r = await enqueueEvent("shift.opened", payload, { actorUserId });
    return { clientEventId: r.clientEventId, createdAt: r.createdAt };
  },
  saveShift: (s) => localShift.save(s),
  rememberShiftNo: (n) => deviceSettings.set(LAST_SHIFT_NO_KEY, n),
};

const $deps = createStore<LoginDeps>(defaultLoginDeps, { serialize: "ignore" });
export const configureLogin = createEvent<LoginDeps>();
$deps.on(configureLogin, (_, d) => d);

export const loginOpened = createEvent<{ device: PosDevice | null; cashier: PosCashier | null }>();
export const staffPicked = createEvent<string>();
export const staffBack = createEvent();
export const pinSubmitted = createEvent<string>();
export const registerSubmitted = createEvent<string>();
export const registerBranchChanged = createEvent<string>();
export const openingCashChanged = createEvent<string>();
export const openShiftPressed = createEvent();
export const staffReloadRequested = createEvent();

export const $step = createStore<LoginStep>("loading");
export const $staff = createStore<StaffRow[]>([]);
export const $selectedUserId = createStore<string | null>(null, { skipVoid: false });
export const $pinError = createStore<Exclude<PinOutcome, { ok: true }> | null>(null, { skipVoid: false });
export const $cashier = createStore<PosCashier | null>(null, { skipVoid: false });
export const $device = createStore<PosDevice | null>(null, { skipVoid: false });
export const $shiftPlan = createStore<ShiftPlan | null>(null, { skipVoid: false });
export const $openingCash = createStore<string>("");
export const $registers = createStore<CashRegisterOut[]>([]);
export const $registerError = createStore<ApiError | null>(null, { skipVoid: false });
export const $openError = createStore<ApiError | null>(null, { skipVoid: false });

export const loadStaffFx = attach({ source: $deps, effect: (d) => d.staff() });

export const verifyPinFx = attach({
  source: { d: $deps, userId: $selectedUserId },
  effect: createEffect(({ d, userId, pin }: { d: LoginDeps; userId: string | null; pin: string }) =>
    userId
      ? verifyCashierPin(d, userId, pin)
      : Promise.resolve({ ok: false, reason: "inactive" } as PinOutcome),
  ),
  mapParams: (pin: string, src) => ({ ...src, pin }),
});

export const planShiftFx = attach({
  source: { d: $deps, device: $device },
  effect: createEffect(
    async ({ d, device, cashier }: { d: LoginDeps; device: PosDevice | null; cashier: PosCashier }) =>
      planShift({
        local: await d.localShift(),
        server: await d.serverShift(),
        deviceId: device?.deviceId ?? "",
        cashRegisterId: device?.cashRegisterId ?? null,
        canOpen: cashier.permissions.includes("shift.open"),
        lastShiftNo: await d.lastShiftNo(),
        lastCountedCash: await d.lastCountedCash(),
        closedLocally: await d.closedShiftIds(),
      }),
  ),
  mapParams: (cashier: PosCashier, src) => ({ ...src, cashier }),
});

export const adoptShiftFx = attach({
  source: $deps,
  effect: createEffect(async ({ d, shift }: { d: LoginDeps; shift: PosShift }) => {
    await d.saveShift(shift);
    await d.rememberShiftNo(shift.shift_no);
    return shift;
  }),
  mapParams: (shift: PosShift, d) => ({ d, shift }),
});

export const openShiftFx = attach({
  source: { d: $deps, plan: $shiftPlan, cash: $openingCash, cashier: $cashier, device: $device },
  effect: createEffect(
    async ({
      d,
      plan,
      cash,
      cashier,
      device,
    }: {
      d: LoginDeps;
      plan: ShiftPlan | null;
      cash: string;
      cashier: PosCashier | null;
      device: PosDevice | null;
    }): Promise<PosShift> => {
      if (plan?.kind !== "open" || !cashier || !device?.cashRegisterId) {
        throw new ApiError({ status: null, code: "VALIDATION_ERROR", messageKey: "errors.validation_error" });
      }
      const id = uuidv7();
      const payload = shiftOpenedPayload(id, device.cashRegisterId, plan.shiftNo, cash || "0");
      const r = await d.openShift(payload, cashier.userId);
      const shift: PosShift = {
        id,
        cash_register_id: device.cashRegisterId,
        shift_no: plan.shiftNo,
        opened_at: r.createdAt,
        opened_by: cashier.userId,
        status: "open",
        client_event_id: r.clientEventId,
        opening_cash: payload.opening_cash,
      };
      await d.saveShift(shift);
      await d.rememberShiftNo(plan.shiftNo);
      return shift;
    },
  ),
});

export const loadRegistersFx = attach({
  source: $deps,
  effect: createEffect(({ d, branchId }: { d: LoginDeps; branchId: string }) => d.cashRegisters(branchId)),
  mapParams: (branchId: string, d) => ({ d, branchId }),
});

export const registerFx = attach({
  source: $deps,
  effect: createEffect(async ({ d, cashRegisterId }: { d: LoginDeps; cashRegisterId: string }) => {
    const out = await d.registerDevice(cashRegisterId);
    d.afterRegister();
    const tenantId = d.tenantId() ?? "";
    const identity: DeviceIdentity = {
      deviceId: out.id,
      tenantId,
      branchId: out.branch_id,
      cashRegisterId: out.cash_register_id,
    };
    const names = { branchName: out.branch_name, cashRegisterName: out.cash_register_name };
    await d.setIdentity(identity, names);
    return { ...identity, ...names } satisfies PosDevice;
  }),
  mapParams: (cashRegisterId: string, d) => ({ d, cashRegisterId }),
});

/**
 * The browser already carries a device-bound session (`GET /auth/session` → `device`) but erp-device has no
 * identity (first POS start after a BO-11 registration in another tab): adopt it, no new registration.
 */
export const adoptSessionDeviceFx = attach({
  source: $deps,
  effect: createEffect(
    async ({
      d,
      device,
      branchName,
    }: {
      d: LoginDeps;
      device: { id: string; branch_id: string | null; cash_register_id: string | null };
      branchName: string | null;
    }): Promise<PosDevice | null> => {
      const tenantId = d.tenantId();
      if (!tenantId || !device.branch_id) return null;
      const identity: DeviceIdentity = {
        deviceId: device.id,
        tenantId,
        branchId: device.branch_id,
        cashRegisterId: device.cash_register_id,
      };
      const names = { branchName, cashRegisterName: null };
      await d.setIdentity(identity, names);
      d.afterRegister();
      return { ...identity, ...names };
    },
  ),
  mapParams: (
    p: {
      device: { id: string; branch_id: string | null; cash_register_id: string | null };
      branchName: string | null;
    },
    d,
  ) => ({ d, ...p }),
});

// ---- wiring ---------------------------------------------------------------------------------------
sample({
  clock: adoptSessionDeviceFx.doneData,
  filter: (dev): dev is PosDevice => dev !== null,
  target: [deviceRegistered, loadStaffFx],
});
$device.on(adoptSessionDeviceFx.doneData, (prev, dev) => dev ?? prev);
sample({
  clock: adoptSessionDeviceFx.doneData,
  filter: (dev) => dev !== null,
  fn: (): LoginStep => "await_staff",
  target: $step,
});
$device.on(loginOpened, (_, p) => p.device).on(registerFx.doneData, (_, d) => d);
$cashier
  .on(loginOpened, (_, p) => p.cashier)
  .on(verifyPinFx.doneData, (prev, r) => (r.ok ? r.cashier : prev));

sample({
  clock: loginOpened,
  fn: ({ device, cashier }): LoginStep => (!device ? "register" : cashier ? "shift" : "loading"),
  target: $step,
});
sample({
  clock: loginOpened,
  filter: ({ device, cashier }) => device !== null && cashier === null,
  target: loadStaffFx,
});
sample({
  clock: loginOpened,
  filter: (p) => p.device !== null && p.cashier !== null,
  fn: (p) => p.cashier as PosCashier,
  target: planShiftFx,
});

sample({ clock: [staffReloadRequested, registerFx.done], target: loadStaffFx });
sample({
  clock: pullApplied,
  source: $step,
  filter: (s) => s === "await_staff" || s === "staff",
  target: loadStaffFx,
});
$staff.on(loadStaffFx.doneData, (_, rows) =>
  rows.filter(
    (r) => r.active && r.permissions.some((p) => (POS_PERMISSIONS as readonly string[]).includes(p.code)),
  ),
);
sample({
  clock: loadStaffFx.doneData,
  source: $step,
  filter: (step) => step === "loading" || step === "await_staff" || step === "register" || step === "staff",
  fn: (_, rows): LoginStep =>
    rows.some(
      (r) => r.active && r.permissions.some((p) => (POS_PERMISSIONS as readonly string[]).includes(p.code)),
    )
      ? "staff"
      : "await_staff",
  target: $step,
});
sample({
  clock: loadStaffFx.fail,
  source: $step,
  filter: (s) => s === "loading",
  fn: () => "await_staff" as const,
  target: $step,
});

$selectedUserId.on(staffPicked, (_, id) => id).reset(staffBack);
$pinError.reset([staffPicked, staffBack, verifyPinFx.done.filter({ fn: ({ result }) => result.ok })]);
sample({ clock: staffPicked, fn: (): LoginStep => "pin", target: $step });
sample({ clock: staffBack, fn: (): LoginStep => "staff", target: $step });
sample({ clock: pinSubmitted, target: verifyPinFx });
sample({
  clock: verifyPinFx.doneData,
  filter: (r): r is Exclude<PinOutcome, { ok: true }> => !r.ok,
  target: $pinError,
});
const signedIn = sample({
  clock: verifyPinFx.doneData,
  filter: (r) => r.ok,
  fn: (r) => (r as Extract<PinOutcome, { ok: true }>).cashier,
});
sample({ clock: signedIn, target: [cashierSignedIn, planShiftFx] });

$shiftPlan.on(planShiftFx.doneData, (_, p) => p);
$openingCash
  .on(planShiftFx.doneData, (prev, p) => (p.kind === "open" ? p.openingCash : prev))
  .on(openingCashChanged, (_, v) => v);
sample({
  clock: planShiftFx.doneData,
  fn: (p): LoginStep =>
    p.kind === "open" ? "shift" : p.kind === "busy" ? "busy" : p.kind === "warehouse" ? "warehouse" : "done",
  target: $step,
});
sample({
  clock: planShiftFx.doneData,
  filter: (p) => p.kind === "resume" && p.adopt,
  fn: (p) => (p as Extract<ShiftPlan, { kind: "resume" }>).shift,
  target: adoptShiftFx,
});
sample({
  clock: planShiftFx.doneData,
  filter: (p) => p.kind === "resume" && !p.adopt,
  fn: (p) => (p as Extract<ShiftPlan, { kind: "resume" }>).shift,
  target: shiftOpenedLocally,
});
sample({ clock: adoptShiftFx.doneData, target: shiftOpenedLocally });

sample({ clock: openShiftPressed, source: openShiftFx.pending, filter: (p) => !p, target: openShiftFx });
$openError.on(openShiftFx.failData, (_, e) => toApiError(e)).reset([openShiftPressed, openShiftFx.done]);
sample({ clock: openShiftFx.doneData, target: shiftOpenedLocally });
sample({ clock: openShiftFx.done, fn: (): LoginStep => "done", target: $step });

sample({ clock: registerBranchChanged, target: loadRegistersFx });
$registers
  .on(loadRegistersFx.doneData, (_, rows) => rows.filter((r) => !r.archived_at))
  .reset(registerBranchChanged);
sample({ clock: registerSubmitted, target: registerFx });
$registerError.on(registerFx.failData, (_, e) => toApiError(e)).reset([registerSubmitted, registerFx.done]);
sample({ clock: registerFx.doneData, target: deviceRegistered });
sample({ clock: registerFx.done, fn: (): LoginStep => "await_staff", target: $step });

export const $selectedStaff = combine(
  $staff,
  $selectedUserId,
  (rows, id) => rows.find((r) => r.user_id === id) ?? null,
);
