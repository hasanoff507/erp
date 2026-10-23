/** Small key/value helpers over `erp-pos.meta` (cursors, counters, trusted clock, sync timestamps). */
import type { Transaction } from "dexie";

import { posDb } from "../runtime.ts";

export const META = {
  seq: "outbox.seq",
  pullCursor: "pull.cursor",
  snapshotDone: "pull.snapshot_done",
  lastPullAt: "sync.last_pull_at",
  lastPushAt: "sync.last_push_at",
  maxSeenTime: "clock.max_seen_time",
  clockReset: "clock.last_reset",
  serverShift: "shift.server",
  deviceRevoked: "device.revoked",
  receiptSeq: (cashRegisterId: string, shiftId: string) => `receipt_seq:${cashRegisterId}:${shiftId}`,
} as const;

export async function getMeta<T>(key: string): Promise<T | undefined> {
  const row = await posDb().meta.get(key);
  return row?.value as T | undefined;
}

export async function setMeta(key: string, value: unknown): Promise<void> {
  await posDb().meta.put({ key, value });
}

/** Inside a running Dexie transaction that includes `meta`. */
export async function getMetaTx<T>(tx: Transaction, key: string): Promise<T | undefined> {
  const row = (await tx.table("meta").get(key)) as { value: unknown } | undefined;
  return row?.value as T | undefined;
}
