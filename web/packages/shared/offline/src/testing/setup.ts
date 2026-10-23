/**
 * Per-test isolation: fresh database names, fake clock, fake server, a registered device identity.
 * IndexedDB itself comes from fake-indexeddb (vitest setupFiles).
 */
import { closeSyncChannel } from "../lib/broadcast.ts";
import { resetClockCache } from "../lib/clock.ts";
import { deviceIdentity } from "../device-settings.ts";
import { resetResultWaiters } from "../outbox/queries.ts";
import { configureOffline, resetOfflineRuntime } from "../runtime.ts";
import { stopSyncEngine, syncIdle } from "../sync/engine.ts";
import { backgroundIdle } from "../lib/background.ts";
import { resetSyncStatus } from "../sync/status.ts";
import type { DeviceIdentity } from "../types.ts";
import { FakeSyncServer } from "./fake-sync-server.ts";

export const DEVICE: DeviceIdentity = {
  deviceId: "018f2c2e-11aa-7b00-9c3d-aa11bb22cc33",
  tenantId: "018f2c2e-0000-7000-8000-000000000001",
  branchId: "018f2c2e-0000-7000-8000-0000000000b1",
  cashRegisterId: "018f2c2e-0000-7000-8000-0000000000c1",
};
export const SHIFT_ID = "018f2c2e-0000-7000-8000-0000000000s1";
export const CASHIER = "018f2c2e-0000-7000-8000-00000000a001";

export interface TestEnv {
  server: FakeSyncServer;
  clock: { now: number; advance(ms: number): void };
  names: { pos: string; device: string };
}

let counter = 0;

export async function setupOffline(opts: { register?: boolean; startMs?: number } = {}): Promise<TestEnv> {
  counter += 1;
  const names = { pos: `t-pos-${counter}-${Math.random()}`, device: `t-dev-${counter}-${Math.random()}` };
  const clock = {
    now: opts.startMs ?? Date.parse("2026-10-14T04:00:00.000Z"),
    advance(ms: number) {
      clock.now += ms;
    },
  };
  const server = new FakeSyncServer();
  resetOfflineRuntime();
  resetClockCache();
  resetSyncStatus();
  configureOffline({ dbNames: names, now: () => clock.now, transport: server });
  if (opts.register !== false) await deviceIdentity.set(DEVICE);
  return { server, clock, names };
}

export async function teardownOffline(): Promise<void> {
  stopSyncEngine();
  await syncIdle();
  await backgroundIdle();
  resetResultWaiters();
  closeSyncChannel();
  resetOfflineRuntime();
}
