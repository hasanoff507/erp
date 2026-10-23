/**
 * POS device context — 24 §2 ($activeShift) and §6.4 ($agentStatus).
 *
 * `$agentStatus` — Do'kon agenti state polled every 10 s with patronum/interval (`GET /v1/status`).
 * The probe itself lives in `@shared/lib/agent` (`agentClient.probe()`); the POS app injects it with
 * `agentProbeConfigured` — @shared/state does not depend on @shared/lib. Contract: hw-api.md §2.
 */
import { attach, createEvent, createStore, sample } from "effector";
import { interval } from "patronum";

export type AgentConnection = "online" | "offline" | "not_installed" | "unpaired";

export interface AgentCapabilities {
  fiscal: { enabled: boolean; provider: string | null };
  print: { enabled: boolean };
  card_terminal: { enabled: boolean };
}

export interface AgentFiscalDevice {
  local_id: string;
  fm_state: string;
  pending_count: number;
  oldest_unacked_at: string | null;
}

export interface AgentCardTerminal {
  local_id: string;
  driver: string;
  tid: string | null;
  status: "online" | "busy" | "offline" | "error";
}

export interface AgentStatus {
  status: AgentConnection;
  version: string | null;
  capabilities: AgentCapabilities;
  fm_state: string | null;
  fiscal_devices: AgentFiscalDevice[];
  card_terminals: AgentCardTerminal[];
  /** ISO time of the last probe; null — never probed. */
  checked_at: string | null;
}

export interface ActiveShift {
  id: string;
  number: number;
  openedAt: string;
}

export const AGENT_POLL_INTERVAL_MS = 10_000;

export const INITIAL_AGENT_STATUS: AgentStatus = Object.freeze({
  status: "not_installed",
  version: null,
  capabilities: {
    fiscal: { enabled: false, provider: null },
    print: { enabled: false },
    card_terminal: { enabled: false },
  },
  fm_state: null,
  fiscal_devices: [],
  card_terminals: [],
  checked_at: null,
});

export type AgentProbe = () => Promise<AgentStatus>;

export const $activeShift = createStore<ActiveShift | null>(null);

/** Inject `() => agentClient.probe()` once (POS app). */
export const agentProbeConfigured = createEvent<AgentProbe>();
export const agentPollingStarted = createEvent();
export const agentPollingStopped = createEvent();
/** Probe now (POS-16 «Aloqani tekshirish», after pairing, after a printer/card error). */
export const agentStatusRefreshRequested = createEvent();
/** A local API call answered 401/403 (b3-card, printer) — POS-16 re-pairing without waiting for the poll. */
export const agentUnpaired = createEvent();

const $agentProbe = createStore<AgentProbe | null>(null, { serialize: "ignore" }).on(
  agentProbeConfigured,
  (_, probe) => probe,
);

const probeAgentFx = attach({
  source: $agentProbe,
  effect: async (probe): Promise<AgentStatus | null> => (probe ? probe() : null),
});

export const $agentStatus = createStore<AgentStatus>(INITIAL_AGENT_STATUS)
  .on(probeAgentFx.doneData, (state, next) => next ?? state)
  .on(agentUnpaired, (state) => ({ ...state, status: "unpaired" }));

/** True while the polling loop runs. */
export const $agentPolling = createStore(false)
  .on(agentPollingStarted, () => true)
  .on(agentPollingStopped, () => false);

const { tick } = interval({
  timeout: AGENT_POLL_INTERVAL_MS,
  start: agentPollingStarted,
  stop: agentPollingStopped,
  leading: true,
});

sample({ clock: [tick, agentStatusRefreshRequested, agentProbeConfigured], target: probeAgentFx });

/** Integrated card availability rule of 24 §6.5 for one terminal `local_id`. */
export function agentCardTerminalOnline(status: AgentStatus, localId: string): boolean {
  return (
    status.status === "online" &&
    status.capabilities.card_terminal.enabled &&
    status.card_terminals.some((t) => t.local_id === localId && t.status === "online")
  );
}
