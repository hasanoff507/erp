/**
 * Push — 16 §3.1/§3.3/§3.4, 18 §2.6, contracts/sync-push.md. Events go in `seq` order, ≤ batch size,
 * always with `outbox_state` (the part of the outbox NOT in this request). Per result:
 * accepted/duplicate → done (kept 7 days, §10); rejected → stays in the outbox with error_code/message;
 * `retryable: true` → automatic retry with its own backoff and it never blocks later unrelated events,
 * `retryable: false` → waits for a manual retry/escalation (POS-12). Events without a result in the
 * answer simply stay pending. Request-level errors are classified for the engine (401/403/429/5xx…).
 */
import { META } from "../db/meta.ts";
import { deviceIdentity } from "../device-settings.ts";
import { outboxChanged } from "../events.ts";
import { broadcast } from "../lib/broadcast.ts";
import { observeServerTime } from "../lib/clock.ts";
import { resolveEventResults, unsyncedRows } from "../outbox/queries.ts";
import { now, nowIso, posDb, rt } from "../runtime.ts";
import type { OutboxRow, PushResultEntry, SyncPushRequest } from "../types.ts";
import { toSyncHttpError, type SyncHttpError } from "./transport.ts";

export type PushOutcome =
  | { kind: "done"; sent: number }
  | { kind: "retry"; code: string; retryAfterMs: number | null; error: SyncHttpError | null }
  | { kind: "stopped"; code: "DEVICE_REVOKED" | "AUTH_REQUIRED" | "SUBSCRIPTION_RESTRICTED" };

/** Backoff of one retryable rejected event: 5 s, 10 s, 20 s … capped at 30 min. */
export function rejectedRetryDelayMs(attempts: number): number {
  return Math.min(30 * 60 * 1000, 5000 * 2 ** Math.max(0, attempts - 1));
}

const NEVER = Number.MAX_SAFE_INTEGER;

/** Unsynced and still being worked on by the sync loop (not escalated to a manual decision). */
function isOpen(row: OutboxRow): boolean {
  return row.status === "pending" || (row.status === "rejected" && row.escalated !== 1);
}

/**
 * ACC-01: `shift.closed` is held while an earlier (lower seq) event of the same shift is still pending
 * or retryably rejected — the close must not overtake a cash document of that shift. Returns the
 * client_event_ids it waits for (empty = not held).
 */
export function closeBlockers(close: OutboxRow, unsynced: readonly OutboxRow[]): string[] {
  if (close.type !== "shift.closed" || close.shift_id === null) return [];
  return unsynced
    .filter((r) => r.seq < close.seq && r.shift_id === close.shift_id && isOpen(r))
    .map((r) => r.client_event_id);
}

function isDue(row: OutboxRow, nowMs: number): boolean {
  return (
    row.status === "pending" ||
    (row.status === "rejected" && row.retryable === true && row.next_attempt_at <= nowMs)
  );
}

function envelope(row: OutboxRow): SyncPushRequest["events"][number] {
  return {
    client_event_id: row.client_event_id,
    device_id: row.device_id,
    seq: row.seq,
    type: row.type,
    created_at: row.created_at,
    actor_user_id: row.actor_user_id,
    payload: row.payload,
  };
}

function fiscalAck(server: Record<string, unknown> | null | undefined): string | null {
  const fiscal = server?.fiscal;
  if (typeof fiscal !== "object" || fiscal === null) return null;
  const acked = (fiscal as { ofd_acked_at?: unknown }).ofd_acked_at;
  return typeof acked === "string" ? acked : null;
}

async function applyResults(results: readonly PushResultEntry[]): Promise<void> {
  const db = posDb();
  const at = nowIso();
  const nowMs = now();
  await db.transaction("rw", db.outbox, async () => {
    for (const entry of results) {
      const row = await db.outbox.where("client_event_id").equals(entry.client_event_id).first();
      if (!row) continue;
      row.attempts += 1;
      row.last_attempt_at = at;
      row.message = entry.message ?? null;
      row.warnings = entry.warnings ?? [];
      if (entry.status === "accepted" || entry.status === "duplicate") {
        row.status = entry.status;
        row.server = entry.server ?? null;
        row.error_code = null;
        row.retryable = null;
        row.result_at = at;
        row.unsynced = 0;
        row.next_attempt_at = NEVER;
        row.escalated = 0;
        const acked = fiscalAck(entry.server);
        if (acked && row.fiscal) row.ofd_acked_at = acked;
        // a manual retry accepted later counts again until its OFD ack (16 §6)
        row.fiscal_unacked = row.fiscal && row.ofd_acked_at === null ? 1 : 0;
      } else {
        row.status = "rejected";
        row.server = null;
        row.error_code = entry.error_code ?? "INTERNAL_ERROR";
        row.retryable = entry.retryable === true;
        row.result_at = at;
        row.unsynced = 1;
        row.next_attempt_at = row.retryable ? nowMs + rejectedRetryDelayMs(row.attempts) : NEVER;
        row.escalated = row.retryable ? 0 : 1;
        // F-1 (SYNC-02): a non-retryable rejection without an FM-signed fiscal_result never produced a
        // receipt (D3: server-side fiscalization) — it leaves the 48 h timer; FM-signed ones keep counting.
        if (!row.retryable && row.fiscal && (row.payload.fiscal_result ?? null) === null)
          row.fiscal_unacked = 0;
      }
      await db.outbox.put(row);
    }
  });
}

/**
 * One push run: sends every due event (several batches if needed). `heartbeat` sends an empty
 * request when nothing is due (outbox_state report, 16 §3.1).
 */
export async function pushNow({ heartbeat = false }: { heartbeat?: boolean } = {}): Promise<PushOutcome> {
  const transport = rt().transport;
  const identity = await deviceIdentity.get();
  if (!transport || !identity) return { kind: "done", sent: 0 };

  const attempted = new Set<string>();
  let sent = 0;
  let sessionProbed = false;
  let sendEmpty = heartbeat;

  for (;;) {
    const all = await unsyncedRows();
    const nowMs = now();
    const batch = all
      .filter(
        (row) =>
          !attempted.has(row.client_event_id) && isDue(row, nowMs) && closeBlockers(row, all).length === 0,
      )
      .slice(0, rt().pushBatchSize);
    if (batch.length === 0 && !sendEmpty) return { kind: "done", sent };

    const inBatch = new Set(batch.map((r) => r.client_event_id));
    const rest = all.filter((r) => !inBatch.has(r.client_event_id));
    let oldest: string | null = null;
    for (const r of rest) if (oldest === null || r.created_at < oldest) oldest = r.created_at;
    const body: SyncPushRequest = {
      device_id: identity.deviceId,
      events: batch.map(envelope),
      outbox_state: { pending_count: rest.length, oldest_pending_created_at: rest.length ? oldest : null },
    };

    let results: PushResultEntry[];
    try {
      const response = await transport.push(body);
      if (response.serverDate !== null) await observeServerTime(response.serverDate);
      results = Array.isArray(response.data.results) ? response.data.results : [];
    } catch (raw) {
      const error = toSyncHttpError(raw);
      if (error.status === 401) {
        if (!sessionProbed) {
          sessionProbed = true;
          if (await transport.refreshSession()) continue;
        }
        return { kind: "stopped", code: "AUTH_REQUIRED" };
      }
      if (error.status === 403 && error.code === "DEVICE_REVOKED")
        return { kind: "stopped", code: "DEVICE_REVOKED" };
      if (error.status === 403 && error.code === "SUBSCRIPTION_RESTRICTED") {
        return { kind: "stopped", code: "SUBSCRIPTION_RESTRICTED" };
      }
      return {
        kind: "retry",
        code: error.status === null ? "NETWORK_ERROR" : error.code,
        retryAfterMs: error.retryAfterMs,
        error,
      };
    }

    for (const row of batch) attempted.add(row.client_event_id);
    sendEmpty = false;
    await posDb().meta.put({ key: META.lastPushAt, value: nowIso() });
    if (results.length > 0) {
      await applyResults(results);
      resolveEventResults(results);
      broadcast({ type: "event-results", results });
      outboxChanged();
    }
    sent += batch.length;
    if (batch.length === 0) return { kind: "done", sent };
  }
}
