import { allSettled, fork } from "effector";
import { describe, expect, it } from "vitest";

import { INITIAL_SYNC_STATUS, syncRequested, syncStatusChanged } from "@shared/offline";

import { offlineDetected, onlineDetected } from "../network/index.ts";
import { $syncState, $unsyncedCount } from "./index.ts";

describe("$syncState (24 §5, 16 §3)", () => {
  it("combines the offline sync status with $isOnline", async () => {
    const scope = fork();
    await allSettled(syncStatusChanged, {
      scope,
      params: { ...INITIAL_SYNC_STATUS, pending: 3, rejected: 1, oldestPendingAt: "2026-10-14T04:00:00.000Z" },
    });
    await allSettled(offlineDetected, { scope });
    expect(scope.getState($syncState)).toMatchObject({ online: false, pending: 3, rejected: 1 });
    expect(scope.getState($unsyncedCount)).toBe(4);
  });

  it("requests a sync when the network comes back (offline → online only)", async () => {
    const scope = fork();
    const calls: unknown[] = [];
    const unwatch = syncRequested.watch((p) => calls.push(p));
    await allSettled(offlineDetected, { scope });
    await allSettled(onlineDetected, { scope });
    await allSettled(onlineDetected, { scope }); // already online: no second request
    expect(calls).toEqual([{ push: true, pull: true }]);
    unwatch.unsubscribe();
  });
});
