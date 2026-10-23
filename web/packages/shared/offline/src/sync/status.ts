/** In-tab sync status (contract 7 `SyncStatus`), published through `syncStatusChanged`. */
import { INITIAL_SYNC_STATUS, syncStatusChanged, type SyncStatus } from "../events.ts";
import { runBackground } from "../lib/background.ts";
import { setCountersTrigger } from "../lib/triggers.ts";
import { summarize, unsyncedRows } from "../outbox/queries.ts";

let status: SyncStatus = { ...INITIAL_SYNC_STATUS };

export function getSyncStatus(): SyncStatus {
  return status;
}

export function patchSyncStatus(patch: Partial<SyncStatus>): void {
  const next = { ...status, ...patch };
  const changed = (Object.keys(next) as (keyof SyncStatus)[]).some((k) => next[k] !== status[k]);
  status = next;
  if (changed) syncStatusChanged(status);
}

/** Re-reads the outbox counters (cheap: only unsynced rows). */
export async function refreshOutboxCounters(): Promise<void> {
  const summary = summarize(await unsyncedRows());
  patchSyncStatus({
    pending: summary.pending,
    rejected: summary.rejected,
    rejectedRetryable: summary.rejectedRetryable,
    oldestPendingAt: summary.oldestPendingAt,
  });
}

export function resetSyncStatus(): void {
  status = { ...INITIAL_SYNC_STATUS };
}

// Every local outbox write (enqueue, manual retry) refreshes the counters at once — offline included
// (06 §1.3 «Offlayn · N chek»), without waiting for a push attempt.
// Coalesced: a burst of writes (2 h of offline sales replayed, bulk retries) costs one extra read.
let countersRunning = false;
let countersAgain = false;
setCountersTrigger(() => {
  if (countersRunning) {
    countersAgain = true;
    return;
  }
  countersRunning = true;
  runBackground(async () => {
    try {
      do {
        countersAgain = false;
        await refreshOutboxCounters();
      } while (countersAgain);
    } finally {
      countersRunning = false;
    }
  });
});
