/**
 * Pull — 16 §1 (snapshot + deltas), §3.2, contracts/sync-pull.md. One cursor (`scope=all`), which the
 * server keeps per stream; first run = from-scratch snapshot (delta tables cleared in the first page's
 * transaction), then pages until `has_more=false`. A rejected cursor (422 field `cursor`) drops it and
 * re-snapshots once. Server time feeds the trusted clock; the `device` block refreshes the identity.
 */
import { META } from "../db/meta.ts";
import { deviceIdentity } from "../device-settings.ts";
import { pullApplied } from "../events.ts";
import { broadcast } from "../lib/broadcast.ts";
import { observeServerTime } from "../lib/clock.ts";
import { invalidateMemoryIndex } from "../lib/memory-index.ts";
import { nowIso, posDb, rt } from "../runtime.ts";
import type { PullScope, SyncPullResponse } from "../types.ts";
import { applyPullPage, DELTA_TABLES, POS_TABLES_FOR_PULL } from "./apply.ts";
import { toSyncHttpError, type SyncHttpError } from "./transport.ts";

export type PullOutcome =
  | { kind: "done"; pages: number; scopes: PullScope[] }
  | { kind: "retry"; code: string; retryAfterMs: number | null; error: SyncHttpError | null }
  | { kind: "stopped"; code: "DEVICE_REVOKED" | "AUTH_REQUIRED" | "SUBSCRIPTION_RESTRICTED" };

const MAX_PAGES_PER_RUN = 1000;

function isCursorRejected(error: SyncHttpError): boolean {
  return error.status === 422 && error.details.some((d) => d.field === "cursor");
}

async function applyPage(page: SyncPullResponse, fromScratch: boolean): Promise<PullScope[]> {
  const db = posDb();
  return db.transaction(
    "rw",
    [...POS_TABLES_FOR_PULL].map((name) => db.table(name)),
    async () => {
      if (fromScratch) {
        for (const name of DELTA_TABLES) await db.table(name).clear();
        // local "sold offline" marking codes stay until the server row replaces them
      }
      const scopes = await applyPullPage(db, page);
      if (!page.has_more) {
        await db.meta.put({ key: META.lastPullAt, value: nowIso() });
        await db.meta.put({ key: META.snapshotDone, value: true });
      }
      return scopes;
    },
  );
}

export async function pullNow(): Promise<PullOutcome> {
  const transport = rt().transport;
  const identity = await deviceIdentity.get();
  if (!transport || !identity) return { kind: "done", pages: 0, scopes: [] };

  const touched = new Set<PullScope>();
  let cursor = ((await posDb().meta.get(META.pullCursor))?.value as string | undefined) ?? "";
  let fromScratch = cursor === "";
  let cursorReset = false;
  let sessionProbed = false;
  let pages = 0;

  while (pages < MAX_PAGES_PER_RUN) {
    let page: SyncPullResponse;
    try {
      const response = await transport.pull({ scope: "all", cursor, page_size: rt().pageSize });
      page = response.data;
      if (response.serverDate !== null) await observeServerTime(response.serverDate);
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
      if (isCursorRejected(error) && !cursorReset) {
        cursorReset = true;
        cursor = "";
        fromScratch = true;
        continue;
      }
      return {
        kind: "retry",
        code: error.status === null ? "NETWORK_ERROR" : error.code,
        retryAfterMs: error.retryAfterMs,
        error,
      };
    }

    if (typeof page.server_time === "string") {
      const ms = Date.parse(page.server_time);
      if (!Number.isNaN(ms)) await observeServerTime(ms);
    }
    const scratch = fromScratch;
    const scopes = await applyPage(page, fromScratch);
    for (const s of scopes) touched.add(s);
    if (scratch || scopes.includes("catalog")) invalidateMemoryIndex("catalog");
    if (scratch || scopes.includes("customers")) invalidateMemoryIndex("customers");
    fromScratch = false;
    pages += 1;

    const device = page.device;
    if (
      device &&
      (device.branch_id !== identity.branchId || device.cash_register_id !== identity.cashRegisterId)
    ) {
      await deviceIdentity.set({
        ...identity,
        branchId: device.branch_id,
        cashRegisterId: device.cash_register_id,
      });
    }
    cursor = page.cursor;
    if (!page.has_more) break;
  }

  const scopes = [...touched];
  if (scopes.length > 0) {
    pullApplied(scopes);
    broadcast({ type: "pull-applied", scopes });
  }
  return { kind: "done", pages, scopes };
}
