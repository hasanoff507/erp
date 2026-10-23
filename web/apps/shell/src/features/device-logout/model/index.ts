/**
 * SEC-07 — back-office «Chiqish» / «Barcha seanslarni tugatish» on a POS device browser (16 §12):
 * the POS logout rules apply before the BFF logout — unresolved card attempts refuse it, unsynced
 * events need a confirmation after the export offer — then `erp-pos` is deleted (`erp-device` kept)
 * and the POS cashier (sessionStorage `erp.pos.cashier`) is forgotten, so the next session never sees
 * the previous user's or tenant's cached data. A browser without a device identity logs out as before.
 */
import { createEffect, createEvent, createStore, sample } from "effector";

import { outbox, wipePosForLogout, type PosLogoutWipe } from "@shared/offline";
import { $session, logoutRequested, revokeAllSessionsRequested } from "@shared/state/session";

export type LogoutAction = "logout" | "revokeAll";

/** sessionStorage key of the PIN-verified POS cashier (POS-01, @pages/pos). */
export const POS_CASHIER_KEY = "erp.pos.cashier";

export type DeviceLogoutDialog =
  | { kind: "blocked_card"; cardAttempts: number }
  | { kind: "needs_confirm"; pending: number; rejected: number }
  /** The local check/wipe itself failed — the user stays signed in (nothing was deleted). */
  | { kind: "error" }
  | null;

/**
 * SEC-01 (web): a device-bound session (`session.device` set — the POS PC) may not revoke every session
 * or switch tenant (server: 403 reason=device_session) — the shell hides those actions.
 */
export const $deviceBoundSession = $session.map((s) => (s?.device ?? null) !== null);

export const deviceLogoutRequested = createEvent<LogoutAction>();
export const deviceLogoutConfirmed = createEvent();
export const deviceLogoutDismissed = createEvent();
export const deviceLogoutExportRequested = createEvent();

export const wipePosFx = createEffect<boolean, PosLogoutWipe>((confirmUnsynced) =>
  wipePosForLogout(confirmUnsynced),
);

export const clearCashierFx = createEffect(() => {
  try {
    sessionStorage.removeItem(POS_CASHIER_KEY);
  } catch {
    // storage unavailable — nothing cached there either
  }
});

/** Downloads the outbox (and card attempts) as JSON — the same export the POS logout offers. */
export const exportOutboxFx = createEffect(async () => {
  const data = await outbox.export();
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `erp-outbox-${data.device_id ?? "device"}-${data.exported_at.replace(/[:.]/g, "-")}.json`;
  a.click();
  URL.revokeObjectURL(url);
});

const proceedFx = createEffect((action: LogoutAction) => {
  if (action === "revokeAll") revokeAllSessionsRequested();
  else logoutRequested();
});

/** Requests that may proceed (device-bound sessions cannot revoke every session — SEC-01). */
const accepted = sample({
  clock: deviceLogoutRequested,
  source: $deviceBoundSession,
  filter: (deviceBound, action) => !(deviceBound && action === "revokeAll"),
  fn: (_, action) => action,
});

export const $logoutAction = createStore<LogoutAction | null>(null)
  .on(accepted, (_, action) => action)
  .reset(deviceLogoutDismissed);
export const $deviceLogoutDialog = createStore<DeviceLogoutDialog>(null)
  .on(wipePosFx.fail, () => ({ kind: "error" }))
  .reset(deviceLogoutDismissed, deviceLogoutRequested);
export const $deviceLogoutError = createStore(false)
  .on(wipePosFx.fail, () => true)
  .reset(deviceLogoutRequested, deviceLogoutDismissed, wipePosFx);
export const $exported = createStore(false)
  .on(exportOutboxFx.done, () => true)
  .reset(deviceLogoutRequested, deviceLogoutDismissed);
export const $deviceLogoutPending = wipePosFx.pending;

sample({ clock: accepted, fn: () => false, target: wipePosFx });
sample({ clock: deviceLogoutConfirmed, fn: () => true, target: wipePosFx });
sample({ clock: deviceLogoutExportRequested, target: exportOutboxFx });

sample({
  clock: wipePosFx.doneData,
  filter: (r) => r.kind === "blocked_card" || r.kind === "needs_confirm",
  fn: (r): DeviceLogoutDialog =>
    r.kind === "blocked_card"
      ? { kind: "blocked_card", cardAttempts: r.cardAttempts }
      : r.kind === "needs_confirm"
        ? { kind: "needs_confirm", pending: r.pending, rejected: r.rejected }
        : null,
  target: $deviceLogoutDialog,
});

const cleared = sample({
  clock: wipePosFx.doneData,
  filter: (r) => r.kind === "wiped" || r.kind === "not_device",
});
sample({ clock: cleared, filter: (r) => r.kind === "wiped", target: clearCashierFx });
sample({ clock: cleared, fn: () => null, target: $deviceLogoutDialog });
sample({
  clock: cleared,
  source: $logoutAction,
  filter: (action): action is LogoutAction => action !== null,
  target: proceedFx,
});
