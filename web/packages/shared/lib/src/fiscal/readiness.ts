/**
 * Local-bridge readiness from `$agentStatus` (24 §6.4, 21 §16 «Fiskal modul ulanmagan»): the POS checks it
 * before a fiscal receipt is even built, and shows the POS-02/POS-03 banner from it.
 * - agent not `online` (not installed / no answer / token refused), fiscal capability off, the bound FM
 *   (`fiscal_local_device_id`) not reported by the agent, or its `fm_state` = `unknown` → `not_connected`;
 * - `locked` / `ack_overdue` / `memory_full` → `locked` (`FISCAL_DEVICE_LOCKED`, the FM will not sign);
 * - `ok` → `ready`.
 * Structural input — @shared/lib does not import @shared/state.
 */
export interface AgentFiscalState {
  status: "online" | "offline" | "not_installed" | "unpaired";
  capabilities: { fiscal: { enabled: boolean } };
  fiscal_devices: readonly { local_id: string; fm_state: string }[];
}

export type LocalFiscalReadiness =
  | { state: "ready"; fmState: "ok" }
  | { state: "locked"; fmState: string }
  | {
      state: "not_connected";
      reason: "agent_offline" | "agent_not_installed" | "agent_unpaired" | "capability_off" | "device_missing" | "fm_unknown";
    };

export const LOCKED_FM_STATES: ReadonlySet<string> = new Set(["locked", "ack_overdue", "memory_full"]);

export function localFiscalReadiness(agent: AgentFiscalState | null, localId: string): LocalFiscalReadiness {
  if (!agent || agent.status === "offline") return { state: "not_connected", reason: "agent_offline" };
  if (agent.status === "not_installed") return { state: "not_connected", reason: "agent_not_installed" };
  if (agent.status === "unpaired") return { state: "not_connected", reason: "agent_unpaired" };
  if (!agent.capabilities.fiscal.enabled) return { state: "not_connected", reason: "capability_off" };
  const device = agent.fiscal_devices.find((d) => d.local_id === localId);
  if (!device) return { state: "not_connected", reason: "device_missing" };
  if (LOCKED_FM_STATES.has(device.fm_state)) return { state: "locked", fmState: device.fm_state };
  if (device.fm_state !== "ok") return { state: "not_connected", reason: "fm_unknown" };
  return { state: "ready", fmState: "ok" };
}
