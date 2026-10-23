import { describe, expect, it } from "vitest";

import { deviceSyncHealth, type SyncHealthInput } from "./index.ts";

const NOW = new Date("2026-10-17T12:00:00Z");
const hoursAgo = (h: number) => new Date(NOW.getTime() - h * 3_600_000).toISOString();

const device = (patch: Partial<SyncHealthInput> = {}): SyncHealthInput => ({
  kind: "web",
  revoked_at: null,
  last_sync_at: hoursAgo(1),
  last_seen_at: hoursAgo(0.1),
  outbox_pending_count: 0,
  outbox_oldest_pending_at: null,
  ...patch,
});

describe("deviceSyncHealth — BO-11 Qurilmalar (16 §6 ladder)", () => {
  it("is ok when synced recently with nothing old waiting", () => {
    expect(deviceSyncHealth(device(), NOW)).toBe("ok");
    expect(
      deviceSyncHealth(device({ outbox_pending_count: 3, outbox_oldest_pending_at: hoursAgo(2) }), NOW),
    ).toBe("ok");
  });

  it("warns from 24 h and is critical from 40 h of the oldest unsent event", () => {
    const pending = (h: number) => device({ outbox_pending_count: 2, outbox_oldest_pending_at: hoursAgo(h) });
    expect(deviceSyncHealth(pending(23.9), NOW)).toBe("ok");
    expect(deviceSyncHealth(pending(24), NOW)).toBe("warning");
    expect(deviceSyncHealth(pending(39.9), NOW)).toBe("warning");
    expect(deviceSyncHealth(pending(40), NOW)).toBe("critical");
  });

  it("warns when the device has not synced for 24 h", () => {
    expect(deviceSyncHealth(device({ last_sync_at: hoursAgo(30) }), NOW)).toBe("warning");
  });

  it("reports never-synced, and no signal for revoked devices and the shop agent", () => {
    expect(deviceSyncHealth(device({ last_sync_at: null }), NOW)).toBe("never");
    expect(deviceSyncHealth(device({ revoked_at: hoursAgo(1), last_sync_at: hoursAgo(99) }), NOW)).toBe(
      "none",
    );
    expect(deviceSyncHealth(device({ kind: "onec_agent", last_sync_at: null }), NOW)).toBe("none");
  });

  it("ignores a stale oldest timestamp when nothing is pending", () => {
    expect(
      deviceSyncHealth(device({ outbox_pending_count: 0, outbox_oldest_pending_at: hoursAgo(50) }), NOW),
    ).toBe("ok");
  });
});
