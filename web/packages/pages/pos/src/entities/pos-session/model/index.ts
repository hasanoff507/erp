/**
 * POS session (contracts/pos-session.md): the device identity (erp-device), the PIN-verified cashier and
 * the open shift of this device. POS-01 produces it; every POS screen reads it (`posActorId()` is the
 * `actor_user_id` of outbox events, 18 §2.1). The cashier lives in sessionStorage — a reload of the tab
 * keeps it, closing the tab, «Bloklash» or logout drop it (14 §4.3 PIN = "who pressed").
 */
import { attach, combine, createEffect, createEvent, createStore, sample } from "effector";
import { useUnit } from "effector-react";

import { api } from "@shared/api";

import {
  deviceIdentity,
  deviceSettings,
  pullApplied,
  shift as localShift,
  staff,
  type DeviceIdentity,
  type LocalShift,
  type StaffRow,
} from "@shared/offline";
import { $activeShift } from "@shared/state/device";
import { $session } from "@shared/state/session";

export interface PosDevice extends DeviceIdentity {
  branchName: string | null;
  cashRegisterName: string | null;
}

export interface PosCashier {
  userId: string;
  fullName: string;
  roleCodes: string[];
  permissions: string[];
  verifiedAt: string;
  via: "online" | "local";
}

export type PosSessionStatus = "loading" | "no_device" | "locked" | "ready";

/** The open shift of this device (`@shared/offline` LocalShift + opening cash). */
export type PosShift = LocalShift & { opening_cash?: string };

/** What sessionStorage keeps (SYNC-10/SEC-08): no names, roles or permissions — those come from the staff snapshot. */
export interface StoredCashier {
  userId: string;
  verifiedAt: string;
  via: "online" | "local";
}

export interface PosSessionDeps {
  identity(): Promise<DeviceIdentity | null>;
  names(): Promise<{ branchName: string | null; cashRegisterName: string | null } | null>;
  currentShift(): Promise<PosShift | null>;
  staffRow(userId: string): Promise<StaffRow | undefined>;
  /** Rows of the pulled staff snapshot (0 = not pulled yet). */
  staffCount(): Promise<number>;
  readCashier(): StoredCashier | null;
  writeCashier(cashier: StoredCashier | null): void;
  /** `POST /auth/pin/release` — ends the server actor binding of this device session (SEC-05). */
  releaseActor(): Promise<void>;
}

export const CASHIER_STORAGE_KEY = "erp.pos.cashier";
export const DEVICE_NAMES_KEY = "pos.device_names";

function browserDeps(): PosSessionDeps {
  return {
    identity: () => deviceIdentity.get(),
    names: async () =>
      (await deviceSettings.get<{ branchName: string | null; cashRegisterName: string | null }>(
        DEVICE_NAMES_KEY,
      )) ?? null,
    currentShift: async () => await localShift.current(),
    staffRow: (userId) => staff.get(userId),
    staffCount: async () => (await staff.list()).length,
    releaseActor: async () => {
      // generated client function (operation auth_pin_release); absent until the API client is regenerated
      const release = (api.auth as unknown as Record<string, unknown>).pinRelease;
      if (typeof release === "function") await (release as () => Promise<unknown>)();
    },
    readCashier: () => {
      try {
        const raw = sessionStorage.getItem(CASHIER_STORAGE_KEY);
        const v = raw ? (JSON.parse(raw) as Partial<StoredCashier>) : null;
        return v && typeof v.userId === "string"
          ? {
              userId: v.userId,
              verifiedAt: String(v.verifiedAt ?? ""),
              via: v.via === "online" ? "online" : "local",
            }
          : null;
      } catch {
        return null;
      }
    },
    writeCashier: (cashier) => {
      try {
        if (cashier)
          sessionStorage.setItem(
            CASHIER_STORAGE_KEY,
            JSON.stringify({ userId: cashier.userId, verifiedAt: cashier.verifiedAt, via: cashier.via }),
          );
        else sessionStorage.removeItem(CASHIER_STORAGE_KEY);
      } catch {
        /* storage blocked — the cashier stays in memory only */
      }
    },
  };
}

const $deps = createStore<PosSessionDeps | null>(null, { serialize: "ignore", skipVoid: false });
/** Tests (and nothing else) replace the collaborators. */
export const configurePosSession = createEvent<PosSessionDeps>();
$deps.on(configurePosSession, (_, d) => d);
const deps = (d: PosSessionDeps | null): PosSessionDeps => d ?? browserDeps();

// ---- events ---------------------------------------------------------------------------------------
export const posSessionStarted = createEvent();
export const deviceRegistered = createEvent<PosDevice>();
export const cashierSignedIn = createEvent<PosCashier>();
/** «Bloklash» / «Kassirni almashtirish» / logout: back to the staff picker. */
export const cashierLocked = createEvent();
export const shiftOpenedLocally = createEvent<PosShift>();
export const shiftClosedLocally = createEvent();
/** Staff snapshot pulled again — a blocked / removed cashier is locked out (16 §1 permissions). */
export const staffRefreshed = createEvent();

// ---- effects --------------------------------------------------------------------------------------
export const loadPosSessionFx = attach({
  source: $deps,
  effect: createEffect(async (d: PosSessionDeps | null) => {
    const api = deps(d);
    const identity = await api.identity();
    if (!identity) return { device: null, shift: null, cashier: null };
    const names = await api.names();
    const shift = await api.currentShift();
    const stored = api.readCashier();
    let cashier: PosCashier | null = null;
    if (stored) {
      // the staff snapshot is the authority (SYNC-10/SEC-08): names, roles and permissions are re-derived
      // from it; inactive / gone → PIN again. No snapshot yet → no cashier until it arrives (tab kept).
      const row = await api.staffRow(stored.userId);
      if (row?.active) cashier = withStaff({ ...stored, fullName: "", roleCodes: [], permissions: [] }, row);
      else if (row || (await api.staffCount()) > 0) api.writeCashier(null);
    }
    const device: PosDevice = {
      ...identity,
      branchName: names?.branchName ?? null,
      cashRegisterName: names?.cashRegisterName ?? null,
    };
    return { device, shift, cashier };
  }),
});

const persistCashierFx = attach({
  source: $deps,
  effect: createEffect(({ d, cashier }: { d: PosSessionDeps | null; cashier: StoredCashier | null }) =>
    deps(d).writeCashier(cashier),
  ),
  // SEC-08: only who / when / how is kept in the tab — never names, roles or permissions
  mapParams: (cashier: PosCashier | null, d) => ({
    d,
    cashier: cashier ? { userId: cashier.userId, verifiedAt: cashier.verifiedAt, via: cashier.via } : null,
  }),
});

/** The staff row always wins — an empty permission list means no permissions (SYNC-10). */
function withStaff(cashier: PosCashier, row: StaffRow): PosCashier {
  return {
    ...cashier,
    fullName: row.full_name || cashier.fullName,
    roleCodes: [...row.role_codes],
    permissions: row.permissions.map((p) => p.code),
  };
}

// ---- stores ---------------------------------------------------------------------------------------
export const $posLoaded = createStore(false)
  .on(loadPosSessionFx.finally, () => true)
  .on(deviceRegistered, () => true);
export const $posDevice = createStore<PosDevice | null>(null, { skipVoid: false })
  .on(loadPosSessionFx.doneData, (_, r) => r.device)
  .on(deviceRegistered, (_, d) => d);
export const $posCashier = createStore<PosCashier | null>(null, { skipVoid: false })
  .on(loadPosSessionFx.doneData, (_, r) => r.cashier)
  .on(cashierSignedIn, (_, c) => c)
  .reset(cashierLocked);
export const $posShift = createStore<PosShift | null>(null, { skipVoid: false })
  .on(loadPosSessionFx.doneData, (_, r) => r.shift)
  .on(shiftOpenedLocally, (_, s) => s)
  .reset(shiftClosedLocally);

/**
 * SEC-07: the cached POS data (erp-pos) belongs to the device identity; it is used only while the online
 * BFF session is the same device + tenant. Unknown session (offline cold start) is trusted.
 */
export function deviceForeign(
  session: { tenant: { id: string }; device?: { id: string } | null } | null,
  device: Pick<PosDevice, "deviceId" | "tenantId"> | null,
): boolean {
  if (!session || !device) return false;
  return session.device?.id !== device.deviceId || session.tenant.id !== device.tenantId;
}

export const $posDeviceForeign = combine($session, $posDevice, (session, device) =>
  deviceForeign(session, device),
);

export const $posSessionStatus = combine(
  $posLoaded,
  $posDevice,
  $posCashier,
  $posDeviceForeign,
  (loaded, device, cashier, foreign): PosSessionStatus => {
    if (!loaded) return "loading";
    if (!device) return "no_device";
    // another session's device: no cashier, POS-01 shows the "foreign device" state
    if (foreign) return "locked";
    return cashier ? "ready" : "locked";
  },
);

// ---- wiring ---------------------------------------------------------------------------------------
sample({ clock: posSessionStarted, target: loadPosSessionFx });
sample({ clock: cashierSignedIn, target: persistCashierFx });
sample({ clock: cashierLocked, fn: () => null, target: persistCashierFx });

/** SEC-05: lock / cashier switch / logout / shift close end the server actor binding (best effort, online). */
export const releaseActorFx = attach({
  source: $deps,
  effect: createEffect(async (d: PosSessionDeps | null) => {
    try {
      await deps(d).releaseActor();
    } catch {
      /* offline / already gone — the binding expires on its own; the next verify replaces it */
    }
  }),
});
sample({ clock: [cashierLocked, shiftClosedLocally], target: releaseActorFx });

const recheckCashierFx = attach({
  source: { d: $deps, cashier: $posCashier },
  effect: createEffect(async ({ d, cashier }: { d: PosSessionDeps | null; cashier: PosCashier | null }) => {
    if (!cashier) return { cashier: null, lock: false };
    const api = deps(d);
    const row = await api.staffRow(cashier.userId);
    // removed from the snapshot or blocked → locked out (SYNC-10)
    if (!row) return (await api.staffCount()) > 0 ? { cashier: null, lock: true } : { cashier, lock: false };
    if (!row.active) return { cashier: null, lock: true };
    return { cashier: withStaff(cashier, row), lock: false };
  }),
});
sample({ clock: staffRefreshed, target: recheckCashierFx });
sample({
  clock: pullApplied,
  filter: (scopes) => scopes.includes("permissions"),
  fn: () => undefined,
  target: staffRefreshed,
});
sample({ clock: recheckCashierFx.doneData, filter: (r) => r.lock, target: cashierLocked });
sample({
  clock: recheckCashierFx.doneData,
  filter: (r): r is { cashier: PosCashier; lock: false } => !r.lock && r.cashier !== null,
  fn: (r) => r.cashier,
  target: $posCashier,
});

// The status bar shift chip (@shared/state/device, 24 §2).
sample({
  clock: $posShift,
  fn: (s) => (s ? { id: s.id, number: s.shift_no, openedAt: s.opened_at } : null),
  target: $activeShift,
});

/** `actor_user_id` of the next outbox event (null — nobody signed in). */
export const posActorId = (): string | null => $posCashier.getState()?.userId ?? null;

export const cashierCan = (cashier: PosCashier | null, code: string): boolean =>
  cashier !== null && cashier.permissions.includes(code);

/** The CASHIER's permission (staff snapshot / `/auth/pin/verify`), not the browser session owner's. */
export function usePosPermission(code: string): boolean {
  const cashier = useUnit($posCashier);
  return cashierCan(cashier, code);
}

/**
 * UX-03: a screen holds the POS keys while the terminal may take money (POS-05 card refund) — Esc, back and
 * the global F-keys (GlobalHotkeys reads this store) do nothing until it is released.
 */
export const posKeysLocked = createEvent<boolean>();
export const $posKeysLocked = createStore(false).on(posKeysLocked, (_, v) => v);
