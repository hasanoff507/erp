import { allSettled, fork } from "effector";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  $activeShift,
  $agentPolling,
  $agentStatus,
  agentCardTerminalOnline,
  agentPollingStarted,
  agentPollingStopped,
  agentProbeConfigured,
  type AgentStatus,
  agentStatusRefreshRequested,
  agentUnpaired,
  INITIAL_AGENT_STATUS,
} from "./index.ts";

const ONLINE: AgentStatus = {
  status: "online",
  version: "1.2.0",
  capabilities: {
    fiscal: { enabled: true, provider: "multikassa_local" },
    print: { enabled: true },
    card_terminal: { enabled: true },
  },
  fm_state: "ok",
  fiscal_devices: [{ local_id: "fm1", fm_state: "ok", pending_count: 0, oldest_unacked_at: null }],
  card_terminals: [
    { local_id: "t1", driver: "fake", tid: "1", status: "online" },
    { local_id: "t2", driver: "fake", tid: "2", status: "busy" },
  ],
  checked_at: "2026-10-16T10:00:00.000Z",
};

afterEach(() => {
  vi.useRealTimers();
});

describe("$agentStatus — 24 §6.4", () => {
  it("starts as not_installed; $activeShift placeholder untouched", () => {
    const scope = fork();
    expect(scope.getState($agentStatus)).toEqual(INITIAL_AGENT_STATUS);
    expect(scope.getState($activeShift)).toBeNull();
  });

  it("probe is injected; refresh stores the snapshot; 401 elsewhere → unpaired", async () => {
    const scope = fork();
    const probe = vi.fn(() => Promise.resolve(ONLINE));
    await allSettled(agentProbeConfigured, { scope, params: probe });
    expect(scope.getState($agentStatus)).toEqual(ONLINE);
    await allSettled(agentStatusRefreshRequested, { scope });
    expect(probe).toHaveBeenCalledTimes(2);
    await allSettled(agentUnpaired, { scope });
    expect(scope.getState($agentStatus).status).toBe("unpaired");
  });

  it("polls every 10 s with patronum/interval until stopped", async () => {
    vi.useFakeTimers();
    const scope = fork();
    let n = 0;
    const probe = vi.fn(() => {
      n += 1;
      return Promise.resolve({ ...ONLINE, checked_at: String(n) });
    });
    await allSettled(agentProbeConfigured, { scope, params: probe });
    const started = allSettled(agentPollingStarted, { scope });
    await vi.advanceTimersByTimeAsync(0);
    expect(scope.getState($agentPolling)).toBe(true);
    const before = probe.mock.calls.length;
    await vi.advanceTimersByTimeAsync(10_000);
    expect(probe.mock.calls.length).toBe(before + 1);
    await vi.advanceTimersByTimeAsync(20_000);
    expect(probe.mock.calls.length).toBe(before + 3);
    await allSettled(agentPollingStopped, { scope });
    await vi.advanceTimersByTimeAsync(30_000);
    await started;
    expect(probe.mock.calls.length).toBe(before + 3);
    expect(scope.getState($agentPolling)).toBe(false);
  });

  it("integrated card needs agent online + card_terminal capability + that terminal online (24 §6.5)", () => {
    expect(agentCardTerminalOnline(ONLINE, "t1")).toBe(true);
    expect(agentCardTerminalOnline(ONLINE, "t2")).toBe(false);
    expect(agentCardTerminalOnline({ ...ONLINE, status: "offline" }, "t1")).toBe(false);
    expect(
      agentCardTerminalOnline(
        { ...ONLINE, capabilities: { ...ONLINE.capabilities, card_terminal: { enabled: false } } },
        "t1",
      ),
    ).toBe(false);
  });
});
