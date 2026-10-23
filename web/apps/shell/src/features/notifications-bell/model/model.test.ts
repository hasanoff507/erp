import { allSettled, createEvent, fork, sample, scopeBind } from "effector";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { AlertOut } from "@shared/models";
import { $isOnline } from "@shared/state/network";
import { $activeBranchId, ALL_BRANCHES } from "@shared/state/session";

import {
  $alerts,
  ALERTS_POLL_MS,
  bellBadge,
  bellMounted,
  bellOpened,
  bellTone,
  bellUnmounted,
  branchParam,
  fetchAlertsFx,
} from "./index.ts";

const branchSwitched = createEvent<string>();
sample({ clock: branchSwitched, target: $activeBranchId });

const alert = (type: string, severity: AlertOut["severity"]): AlertOut => ({
  type,
  severity,
  message_key: `reports.alerts.${type}`,
  count: 2,
  amount: null,
  route: "/app/approvals",
});

describe("WEB-12 topbar bell (06 §1.9 — BO-02 alerts)", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("reads the topbar branch's alerts on mount, every 60 s, on open and on a branch change", async () => {
    const calls: (string | null)[] = [];
    const s = fork({
      values: [
        [$activeBranchId, ALL_BRANCHES],
        [$isOnline, true],
      ],
      handlers: [
        [
          fetchAlertsFx,
          (branchId: string | null) => {
            calls.push(branchId);
            return branchId === "b-2" ? [] : [alert("low_stock", "warning")];
          },
        ],
      ],
    });
    scopeBind(bellMounted, { scope: s })();
    await vi.advanceTimersByTimeAsync(0);
    expect(calls).toEqual([null]);
    expect(s.getState($alerts)?.map((a) => a.type)).toEqual(["low_stock"]);

    await vi.advanceTimersByTimeAsync(ALERTS_POLL_MS);
    expect(calls).toEqual([null, null]);

    scopeBind(bellOpened, { scope: s })();
    await vi.advanceTimersByTimeAsync(0);
    expect(calls).toHaveLength(3);

    scopeBind(branchSwitched, { scope: s })("b-2");
    await vi.advanceTimersByTimeAsync(0);
    expect(calls.at(-1)).toBe("b-2");
    expect(s.getState($alerts)).toEqual([]);

    scopeBind(bellUnmounted, { scope: s })();
    await vi.advanceTimersByTimeAsync(ALERTS_POLL_MS * 2);
    expect(calls).toHaveLength(4);
    expect(s.getState($alerts)).toBeNull();
  });

  it("an answer without alerts counts as none (never undefined in the store)", async () => {
    const s = fork({
      values: [[$isOnline, true]],
      handlers: [[fetchAlertsFx, () => undefined as unknown as AlertOut[]]],
    });
    scopeBind(bellMounted, { scope: s })();
    await vi.advanceTimersByTimeAsync(0);
    expect(s.getState($alerts)).toEqual([]);
    scopeBind(bellUnmounted, { scope: s })();
  });

  it("offline → no request", async () => {
    let calls = 0;
    const s = fork({
      values: [[$isOnline, false]],
      handlers: [[fetchAlertsFx, () => (calls++, [])]],
    });
    scopeBind(bellMounted, { scope: s })();
    await vi.advanceTimersByTimeAsync(0);
    expect(calls).toBe(0);
    scopeBind(bellUnmounted, { scope: s })();
    await allSettled(s);
  });
});

describe("bell lib", () => {
  it("badge text / tone, branch param", () => {
    expect(bellBadge(null)).toBeNull();
    expect(bellBadge([])).toBeNull();
    expect(bellBadge([alert("a", "info")])).toBe("1");
    expect(bellBadge(Array.from({ length: 12 }, (_, i) => alert(`a${i}`, "info")))).toBe("9+");
    expect(bellTone([alert("a", "info"), alert("b", "critical")])).toBe("destructive");
    expect(bellTone([alert("a", "info"), alert("b", "warning")])).toBe("warning");
    expect(branchParam(ALL_BRANCHES)).toBeNull();
    expect(branchParam(null)).toBeNull();
    expect(branchParam("b-1")).toBe("b-1");
  });
});
