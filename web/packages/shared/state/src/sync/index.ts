/**
 * $syncState — POS sync indicator data (24 §2, §5; 16 §3; 06 §1.3): network state from `$isOnline`
 * plus the outbox/sync status published by @shared/offline (pending, rejected, oldest pending, last
 * push/pull, auth/revoke flags). No Dexie here — @shared/offline owns storage (lib ← offline ← state).
 * `$fiscalLadder` (48 h) is re-exported for the status bar.
 */
import { combine, createStore, sample } from "effector";

import {
  $fiscalLadder,
  INITIAL_SYNC_STATUS,
  syncRequested,
  syncStatusChanged,
  type FiscalLadder,
  type SyncStatus,
} from "@shared/offline";

import { $isOnline } from "../network/index.ts";

export interface SyncState extends SyncStatus {
  online: boolean;
}

export const $syncStatus = createStore<SyncStatus>(INITIAL_SYNC_STATUS).on(syncStatusChanged, (_, s) => s);

export const $syncState = combine($syncStatus, $isOnline, (status, online): SyncState => ({ ...status, online }));

/** Number of events that still have to reach the server (pending + rejected) — status chip badge. */
export const $unsyncedCount = $syncStatus.map((s) => s.pending + s.rejected);

// Network back (offline → online transition only, not every API answer) → sync now (16 §1).
sample({
  clock: $isOnline.updates,
  filter: (online) => online,
  fn: () => ({ push: true, pull: true }),
  target: syncRequested,
});

export { $fiscalLadder, syncRequested, type FiscalLadder, type SyncStatus };
