/**
 * Storage limits and cleanup — 16 §10: accepted/duplicate outbox rows are kept 7 days after their
 * result, fiscal receipt events without `ofd_acked_at` and anything pending/rejected are never
 * deleted; the receipt history cache is a 90-day window; `navigator.storage.estimate()` → 80 % warn,
 * 95 % → the history cache is trimmed (never the outbox). `navigator.storage.persist()` at start.
 */
import { quotaWarning, type QuotaLevel, type QuotaState } from "../events.ts";
import { now, posDb, rt } from "../runtime.ts";

export const QUOTA_WARN_RATIO = 0.8;
export const QUOTA_CRITICAL_RATIO = 0.95;
/** History kept after a critical-quota trim (days). */
const CRITICAL_HISTORY_DAYS = 14;
const DAY_MS = 24 * 60 * 60 * 1000;

export interface RetentionResult {
  outboxDeleted: number;
  historyDeleted: number;
}

export async function runRetention(): Promise<RetentionResult> {
  const db = posDb();
  const cfg = rt();
  const outboxCutoff = new Date(now() - cfg.outboxRetentionMs).toISOString();
  const historyCutoff = new Date(now() - cfg.historyRetentionMs).toISOString();
  const outboxDeleted = await db.outbox
    .where("result_at")
    .below(outboxCutoff)
    .filter(
      (row) =>
        (row.status === "accepted" || row.status === "duplicate") &&
        row.unsynced === 0 &&
        (!row.fiscal || row.ofd_acked_at !== null),
    )
    .delete();
  const historyDeleted = await db.sales_history.where("created_at").below(historyCutoff).delete();
  return { outboxDeleted, historyDeleted };
}

interface StorageManagerLike {
  estimate?: () => Promise<{ usage?: number; quota?: number }>;
  persist?: () => Promise<boolean>;
  persisted?: () => Promise<boolean>;
}

function storageManager(): StorageManagerLike | null {
  if (typeof navigator === "undefined") return null;
  return (navigator as { storage?: StorageManagerLike }).storage ?? null;
}

export function quotaLevel(ratio: number | null): QuotaLevel {
  if (ratio === null) return "unknown";
  if (ratio >= QUOTA_CRITICAL_RATIO) return "critical95";
  if (ratio >= QUOTA_WARN_RATIO) return "warn80";
  return "ok";
}

/** Checks the quota; at 95 % trims the history cache to the last 14 days. Emits `quotaWarning`. */
export async function checkStorageQuota(
  estimate?: () => Promise<{ usage?: number; quota?: number }>,
): Promise<QuotaState> {
  const fn = estimate ?? storageManager()?.estimate?.bind(storageManager());
  if (!fn) return { usage: null, quota: null, ratio: null, level: "unknown" };
  const { usage, quota } = await fn();
  const ratio = usage !== undefined && quota !== undefined && quota > 0 ? usage / quota : null;
  const state: QuotaState = { usage: usage ?? null, quota: quota ?? null, ratio, level: quotaLevel(ratio) };
  if (state.level === "critical95") {
    const cutoff = new Date(now() - CRITICAL_HISTORY_DAYS * DAY_MS).toISOString();
    await posDb().sales_history.where("created_at").below(cutoff).delete();
  }
  if (state.level === "warn80" || state.level === "critical95") quotaWarning(state);
  return state;
}

/** 16 §10: ask the browser not to evict our data. */
export async function requestPersistentStorage(): Promise<boolean> {
  const manager = storageManager();
  if (!manager?.persist) return false;
  try {
    if (manager.persisted && (await manager.persisted())) return true;
    return await manager.persist();
  } catch {
    return false;
  }
}
