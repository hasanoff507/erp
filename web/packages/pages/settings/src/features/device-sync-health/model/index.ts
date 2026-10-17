/**
 * Sync health of a tenant device — BO-11 «Qurilmalar» (07, 16 §3.1, §6, §9).
 *
 * The server keeps per device `last_sync_at`, `last_seen_at` and the outbox report of the last push
 * (`outbox_pending_count`, `outbox_oldest_pending_at`). The owner needs one signal per row:
 *
 * - `critical` — an unsent event is 40 h old or older (the 48 h fiscal ladder turns red at 40 h, 16 §6);
 * - `warning`  — an unsent event is 24 h old or older, or the device has not synced for 24 h;
 * - `ok`       — synced within 24 h and nothing old is waiting;
 * - `never`    — never pushed (just registered);
 * - `none`     — revoked devices and Do'kon agenti (no outbox) carry no sync signal.
 */

export type SyncHealth = "ok" | "warning" | "critical" | "never" | "none";

export interface SyncHealthInput {
  kind: string;
  revoked_at: string | null;
  last_sync_at: string | null;
  last_seen_at: string | null;
  outbox_pending_count: number | null;
  outbox_oldest_pending_at: string | null;
}

const HOUR_MS = 3_600_000;
export const WARNING_AFTER_H = 24;
export const CRITICAL_AFTER_H = 40;

function hoursSince(iso: string, now: Date): number {
  return (now.getTime() - new Date(iso).getTime()) / HOUR_MS;
}

export function deviceSyncHealth(device: SyncHealthInput, now: Date = new Date()): SyncHealth {
  if (device.revoked_at !== null || device.kind === "onec_agent") return "none";
  const pending = device.outbox_pending_count ?? 0;
  if (pending > 0 && device.outbox_oldest_pending_at !== null) {
    const age = hoursSince(device.outbox_oldest_pending_at, now);
    if (age >= CRITICAL_AFTER_H) return "critical";
    if (age >= WARNING_AFTER_H) return "warning";
  }
  if (device.last_sync_at === null) return "never";
  return hoursSince(device.last_sync_at, now) >= WARNING_AFTER_H ? "warning" : "ok";
}
