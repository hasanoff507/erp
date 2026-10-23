/**
 * Logout and device revocation — 16 §9, §12:
 * logout: (1) card_attempts not empty → blocked (`CARD_OUTCOME_UNKNOWN`); (2) unsynced outbox → the
 * caller must confirm after offering the export (`OUTBOX_NOT_EMPTY` otherwise); (3) `erp-pos` deleted,
 * `erp-device` kept (with seq / receipt_seq floors so counters stay monotonic for this device).
 * DEVICE_REVOKED: after the UI offered `outbox.export()`, both databases are deleted.
 * Re-login after a 401 or SUBSCRIPTION_RESTRICTED is NOT a logout — nothing is wiped there.
 */
import Dexie from "dexie";

import { META } from "../db/meta.ts";
import { deviceIdentity, readCounterFloors, writeCounterFloors } from "../device-settings.ts";
import { backgroundIdle } from "../lib/background.ts";
import { broadcast } from "../lib/broadcast.ts";
import { OfflineError } from "../lib/errors.ts";
import { OUTBOX_WRITER_LOCK, withLock } from "../lib/locks.ts";
import { summarize, unsyncedRows } from "../outbox/queries.ts";
import { stopSyncEngine, syncIdle } from "../sync/engine.ts";
import { resetSyncStatus } from "../sync/status.ts";
import { closeDatabases, posDb, rt } from "../runtime.ts";

export interface LogoutCheck {
  blocker: "card_attempts" | null;
  cardAttempts: number;
  pending: number;
  rejected: number;
}

export async function logoutCheck(): Promise<LogoutCheck> {
  const cardAttempts = await posDb().card_attempts.count();
  const summary = summarize(await unsyncedRows());
  return {
    blocker: cardAttempts > 0 ? "card_attempts" : null,
    cardAttempts,
    pending: summary.pending,
    rejected: summary.rejected,
  };
}

async function saveCounterFloors(): Promise<void> {
  const db = posDb();
  const floors = await readCounterFloors();
  const metaRows = await db.meta.toArray();
  for (const row of metaRows) {
    if (typeof row.value !== "number") continue;
    if (row.key === META.seq) floors.seq = Math.max(floors.seq, row.value);
    else if (row.key.startsWith("receipt_seq:")) {
      floors.receiptSeq[row.key] = Math.max(floors.receiptSeq[row.key] ?? 0, row.value);
    }
  }
  await writeCounterFloors(floors);
}

export async function logout(opts: { confirmUnsynced: boolean }): Promise<void> {
  await withLock(OUTBOX_WRITER_LOCK, async () => {
    const check = await logoutCheck();
    if (check.blocker === "card_attempts") {
      throw new OfflineError("CARD_OUTCOME_UNKNOWN", { card_attempts: check.cardAttempts });
    }
    if (check.pending + check.rejected > 0 && !opts.confirmUnsynced) {
      throw new OfflineError("OUTBOX_NOT_EMPTY", { pending: check.pending, rejected: check.rejected });
    }
    stopSyncEngine();
    await syncIdle();
    await backgroundIdle();
    await saveCounterFloors();
    closeDatabases();
    await Dexie.delete(rt().dbNames.pos);
    resetSyncStatus();
  });
  broadcast({ type: "wiped", scope: "pos" });
}

export type PosLogoutWipe =
  /** Not a POS device browser (no erp-device identity): nothing to wipe, log out normally. */
  | { kind: "not_device" }
  /** Unresolved card attempts (16 §2.1, §12) — refuse the logout. */
  | { kind: "blocked_card"; cardAttempts: number }
  /** Unsynced events and no confirmation yet — offer `outbox.export()`, then call again with true. */
  | { kind: "needs_confirm"; pending: number; rejected: number }
  /** erp-pos deleted (erp-device kept) — continue with the BFF logout. */
  | { kind: "wiped" };

/**
 * SEC-07: back-office logout / «Barcha seanslarni tugatish» on a POS device browser (an `erp-device`
 * identity exists) follows the POS logout rules (16 §12) — card attempts block, unsynced events need
 * a confirmation after the export offer — then deletes `erp-pos` so the next session never sees the
 * previous user's / tenant's cached data. Never throws for the expected outcomes: returns what happened.
 */
export async function wipePosForLogout(confirmUnsynced: boolean): Promise<PosLogoutWipe> {
  // a back-office-only browser must not get an empty erp-device database just by logging out
  if (!(await Dexie.exists(rt().dbNames.device))) return { kind: "not_device" };
  if (!(await deviceIdentity.get())) return { kind: "not_device" };
  const check = await logoutCheck();
  if (check.blocker === "card_attempts") return { kind: "blocked_card", cardAttempts: check.cardAttempts };
  if (check.pending + check.rejected > 0 && !confirmUnsynced) {
    return { kind: "needs_confirm", pending: check.pending, rejected: check.rejected };
  }
  await logout({ confirmUnsynced: true });
  return { kind: "wiped" };
}

/** DEVICE_REVOKED (16 §9): call only after the export was offered. Deletes both databases. */
export async function wipeAfterRevoke(): Promise<void> {
  await withLock(OUTBOX_WRITER_LOCK, async () => {
    stopSyncEngine();
    await syncIdle();
    await backgroundIdle();

    closeDatabases();
    await Dexie.delete(rt().dbNames.pos);
    await Dexie.delete(rt().dbNames.device);
    resetSyncStatus();
  });
  broadcast({ type: "wiped", scope: "all" });
}
