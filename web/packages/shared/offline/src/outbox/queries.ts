/**
 * Outbox reads and manual actions for POS-12 ("Sinxronlanmagan hujjatlar", 16 §3.4) and the export
 * offered before logout / after DEVICE_REVOKED (16 §9, §12). Rejected events are never deleted here.
 */
import Dexie from "dexie";

import { deviceIdentity } from "../device-settings.ts";
import { outboxChanged } from "../events.ts";
import { broadcast, onSyncMessage } from "../lib/broadcast.ts";
import { triggerCounters, triggerPush } from "../lib/triggers.ts";
import { nowIso, posDb } from "../runtime.ts";
import { stripCardData } from "../repos/card-attempts.ts";
import { closeBlockers } from "../sync/push.ts";
import type { CardAttempt, OutboxRow, OutboxStatus, PushResultEntry } from "../types.ts";

export interface OutboxSummary {
  pending: number;
  rejected: number;
  rejectedRetryable: number;
  /** Rejected with retryable=false — waiting for a manual fix / escalation (POS-12 «Eskalatsiya»). */
  escalated: number;
  /** created_at of the oldest event not yet accepted/duplicate. */
  oldestPendingAt: string | null;
}

export interface OutboxExport {
  device_id: string | null;
  exported_at: string;
  events: OutboxRow[];
  /** SYNC-12: local card attempts (16 §2.1) — PAN-free, keys from the card-data deny-list stripped. */
  card_attempts: CardAttempt[];
}

/** Every row that still has to reach the server (pending + rejected), in seq order. */
export function unsyncedRows(): Promise<OutboxRow[]> {
  return posDb().outbox.where("[unsynced+seq]").between([1, Dexie.minKey], [1, Dexie.maxKey]).toArray();
}

export function summarize(rows: readonly OutboxRow[]): OutboxSummary {
  let pending = 0;
  let rejected = 0;
  let rejectedRetryable = 0;
  let escalated = 0;
  let oldest: string | null = null;
  for (const row of rows) {
    if (row.status === "pending") pending += 1;
    if (row.status === "rejected") {
      rejected += 1;
      if (row.retryable) rejectedRetryable += 1;
      if (row.escalated === 1) escalated += 1;
    }
    if (oldest === null || row.created_at < oldest) oldest = row.created_at;
  }
  return { pending, rejected, rejectedRetryable, escalated, oldestPendingAt: oldest };
}

export function rowToResult(row: OutboxRow): PushResultEntry | null {
  if (row.status === "pending") return null;
  return {
    client_event_id: row.client_event_id,
    status: row.status,
    server: row.server,
    error_code: row.error_code,
    message: row.message,
    retryable: row.retryable ?? false,
    warnings: row.warnings,
  };
}

export const outbox = {
  async list(filter: { status?: OutboxStatus | OutboxStatus[]; limit?: number } = {}): Promise<OutboxRow[]> {
    const statuses =
      filter.status === undefined
        ? null
        : new Set(Array.isArray(filter.status) ? filter.status : [filter.status]);
    let collection = posDb().outbox.orderBy("seq");
    if (statuses) collection = collection.filter((row) => statuses.has(row.status));
    if (filter.limit !== undefined) collection = collection.limit(filter.limit);
    return collection.toArray();
  },

  get(clientEventId: string): Promise<OutboxRow | undefined> {
    return posDb().outbox.where("client_event_id").equals(clientEventId).first();
  },

  async summary(): Promise<OutboxSummary> {
    return summarize(await unsyncedRows());
  },

  /** POS-12 "Qayta urinish": a rejected event goes back to pending (next push sends it). */
  async retry(clientEventId: string): Promise<void> {
    const db = posDb();
    const changed = await db.outbox
      .where("client_event_id")
      .equals(clientEventId)
      .modify((row) => {
        if (row.status !== "rejected") return;
        row.status = "pending";
        row.next_attempt_at = 0;
        row.escalated = 0;
      });
    if (changed > 0) notifyOutboxChanged();
  },

  async retryAllRetryable(): Promise<number> {
    const changed = await posDb()
      .outbox.where("status")
      .equals("rejected")
      .modify((row) => {
        if (!row.retryable) return;
        row.status = "pending";
        row.next_attempt_at = 0;
        row.escalated = 0;
      });
    if (changed > 0) notifyOutboxChanged();
    return changed;
  },

  /** Everything in the outbox (synced rows of the last 7 days included) — the UI renders the file. */
  async export(): Promise<OutboxExport> {
    const identity = await deviceIdentity.get();
    return {
      device_id: identity?.deviceId ?? null,
      exported_at: nowIso(),
      events: await posDb().outbox.orderBy("seq").toArray(),
      card_attempts: (await posDb().card_attempts.toArray()).map((a) => stripCardData(a)),
    };
  },

  /**
   * ACC-01: `shift.closed` events held back because an earlier event of the same shift is not synced
   * yet (POS-07 / POS-12 «Smena yopilishi oldingi hujjatlarni kutmoqda»).
   */
  async heldShiftCloses(): Promise<
    { clientEventId: string; shiftId: string | null; waitingFor: string[] }[]
  > {
    const rows = await unsyncedRows();
    return rows
      .filter((r) => r.type === "shift.closed")
      .map((r) => ({
        clientEventId: r.client_event_id,
        shiftId: r.shift_id,
        waitingFor: closeBlockers(r, rows),
      }))
      .filter((r) => r.waitingFor.length > 0);
  },
};

function notifyOutboxChanged(): void {
  outboxChanged();
  triggerCounters();
  broadcast({ type: "outbox-changed" });
  triggerPush();
}

// ---- awaitEventResult --------------------------------------------------------------------------

type Waiter = (entry: PushResultEntry) => void;
const waiters = new Map<string, Set<Waiter>>();
let unsubscribe: (() => void) | null = null;

/** Called by the push engine (and by broadcasts from other tabs). */
export function resolveEventResults(results: readonly PushResultEntry[]): void {
  for (const entry of results) {
    const set = waiters.get(entry.client_event_id);
    if (!set) continue;
    waiters.delete(entry.client_event_id);
    for (const waiter of set) waiter(entry);
  }
}

function ensureSubscription(): void {
  unsubscribe ??= onSyncMessage((message) => {
    if (message.type === "event-results") resolveEventResults(message.results);
  });
}

/**
 * Resolves with the server result of one event, or `null` after `timeoutMs` (still pending — the sale
 * is safe in the outbox; the screen just stops waiting). A rejected-retryable result resolves too.
 */
export async function awaitEventResult(
  clientEventId: string,
  { timeoutMs }: { timeoutMs: number },
): Promise<PushResultEntry | null> {
  ensureSubscription();
  const row = await outbox.get(clientEventId);
  if (row) {
    const done = rowToResult(row);
    if (done) return done;
  }
  return new Promise<PushResultEntry | null>((resolve) => {
    const set = waiters.get(clientEventId) ?? new Set<Waiter>();
    waiters.set(clientEventId, set);
    const timer = setTimeout(() => {
      set.delete(waiter);
      if (set.size === 0) waiters.delete(clientEventId);
      resolve(null);
    }, timeoutMs);
    const waiter: Waiter = (entry) => {
      clearTimeout(timer);
      resolve(entry);
    };
    set.add(waiter);
  });
}

export function resetResultWaiters(): void {
  waiters.clear();
  unsubscribe?.();
  unsubscribe = null;
}
