/**
 * Do'kon agenti (store agent) read model for the back office — 33 §10.3 W-01/W-02, 34 §14.2 `capabilities`.
 * The generated client types W-01/W-02 as loose objects, so the JSON is normalised here (unknown fields
 * dropped, wrong types → safe defaults). Used by BO-14 «Do'kon agentlari» and the BO-12 bindings
 * (fiscal agent of a cash register, `agent_ecr` card terminal).
 */
import { createEffect, createEvent, createStore, sample } from "effector";

import { api, toApiError, type ApiError } from "@shared/api";

/** 34 §14.2 capability families of B5 (`onec` is Bosqich 7, kept only to show the badge). */
export const CAPABILITY_FAMILIES = ["fiscal", "print", "card_terminal", "scale", "onec"] as const;
export type CapabilityFamily = (typeof CAPABILITY_FAMILIES)[number];

export interface AgentDevice {
  local_id: string;
  name: string | null;
  model: string | null;
  host: string | null;
  port: number | null;
  status: string | null;
  driver: string | null;
  tid: string | null;
  transport: string | null;
}

export interface AgentCapability {
  enabled: boolean;
  version: number;
  provider: string | null;
  devices: AgentDevice[];
}

export type AgentStatus = "active" | "revoked";

export interface StoreAgent {
  id: string;
  device_id: string;
  name: string;
  pc_name: string;
  os_version: string | null;
  agent_version: string | null;
  status: AgentStatus;
  online: boolean;
  last_hello_at: string | null;
  last_poll_at: string | null;
  paired_by_name: string | null;
  paired_at: string | null;
  update_channel: string | null;
  update_available: string | null;
  capabilities: Partial<Record<CapabilityFamily, AgentCapability>>;
  revoked_at: string | null;
  revoke_reason: string | null;
  version: number;
}

type Raw = Record<string, unknown>;

const isObject = (v: unknown): v is Raw => typeof v === "object" && v !== null && !Array.isArray(v);
const str = (v: unknown): string | null => (typeof v === "string" ? v : null);
const int = (v: unknown): number | null => (typeof v === "number" && Number.isInteger(v) ? v : null);

function toDevice(raw: unknown): AgentDevice | null {
  if (!isObject(raw)) return null;
  const localId = str(raw.local_id);
  if (!localId) return null;
  return {
    local_id: localId,
    name: str(raw.name),
    model: str(raw.model),
    host: str(raw.host),
    port: int(raw.port),
    status: str(raw.status),
    driver: str(raw.driver),
    tid: str(raw.tid),
    transport: str(raw.transport),
  };
}

function toCapabilities(raw: unknown): StoreAgent["capabilities"] {
  const out: StoreAgent["capabilities"] = {};
  if (!isObject(raw)) return out;
  for (const family of CAPABILITY_FAMILIES) {
    const entry = raw[family];
    if (!isObject(entry)) continue;
    out[family] = {
      enabled: entry.enabled === true,
      version: int(entry.version) ?? 0,
      provider: str(entry.provider),
      devices: Array.isArray(entry.devices)
        ? entry.devices.map(toDevice).filter((d): d is AgentDevice => d !== null)
        : [],
    };
  }
  return out;
}

/** W-01/W-02 JSON → {@link StoreAgent}; `null` when the id is missing. */
export function toAgent(raw: unknown): StoreAgent | null {
  if (!isObject(raw)) return null;
  const id = str(raw.id);
  if (!id) return null;
  return {
    id,
    device_id: str(raw.device_id) ?? "",
    name: str(raw.name) ?? str(raw.pc_name) ?? "—",
    pc_name: str(raw.pc_name) ?? "—",
    os_version: str(raw.os_version),
    agent_version: str(raw.agent_version),
    status: raw.status === "revoked" ? "revoked" : "active",
    online: raw.online === true,
    last_hello_at: str(raw.last_hello_at),
    last_poll_at: str(raw.last_poll_at),
    paired_by_name: str(raw.paired_by_name),
    paired_at: str(raw.paired_at),
    update_channel: str(raw.update_channel),
    update_available: str(raw.update_available),
    capabilities: toCapabilities(raw.capabilities),
    revoked_at: str(raw.revoked_at),
    revoke_reason: str(raw.revoke_reason),
    version: int(raw.version) ?? 0,
  };
}

/** W-01 page → agents (malformed rows dropped). */
export function toAgentList(raw: unknown): StoreAgent[] {
  if (!isObject(raw) || !Array.isArray(raw.items)) return [];
  return raw.items.map(toAgent).filter((a): a is StoreAgent => a !== null);
}

/** Enabled families of an agent, in display order. */
export function enabledFamilies(agent: Pick<StoreAgent, "capabilities">): CapabilityFamily[] {
  return CAPABILITY_FAMILIES.filter((f) => agent.capabilities[f]?.enabled === true);
}

/** Devices of an enabled family (`[]` when disabled — the server refuses such a binding). */
export function devicesOf(agent: Pick<StoreAgent, "capabilities">, family: CapabilityFamily): AgentDevice[] {
  const cap = agent.capabilities[family];
  return cap?.enabled ? cap.devices : [];
}

/** Active agents that can serve `family` (BO-12 «Fiskal agent» / `agent_ecr` terminal pickers). */
export function agentsFor(agents: readonly StoreAgent[], family: CapabilityFamily): StoreAgent[] {
  return agents.filter((a) => a.status === "active" && a.capabilities[family]?.enabled === true);
}

/** Device label for selects: «name (local_id)» or the id alone. */
export function deviceLabel(d: Pick<AgentDevice, "local_id" | "name" | "model">): string {
  const title = d.name ?? d.model;
  return title ? `${title} (${d.local_id})` : d.local_id;
}

// --- W-01 list store -----------------------------------------------------------------------------------

/** Load (or reload) the tenant's agents — callers fire it only with `onec.view`. */
export const agentsRequested = createEvent();

export const fetchAgentsFx = createEffect<void, StoreAgent[], ApiError>(async () => {
  try {
    return toAgentList(await api.onec.listAgents({ page: 1, size: 200 }));
  } catch (e) {
    throw toApiError(e);
  }
});

export const $agents = createStore<StoreAgent[]>([]);
export const $agentsError = createStore<ApiError | null>(null, { skipVoid: false });
export const $agentsLoaded = createStore(false);

sample({ clock: agentsRequested, target: fetchAgentsFx });
$agents.on(fetchAgentsFx.doneData, (_, list) => list);
$agentsLoaded.on(fetchAgentsFx.done, () => true);
$agentsError.on(fetchAgentsFx.failData, (_, e) => e).reset(fetchAgentsFx.done);

/** Replace / add one agent after W-02/W-04/W-05 answers. */
export const agentUpdated = createEvent<StoreAgent>();
$agents.on(agentUpdated, (list, agent) =>
  list.some((a) => a.id === agent.id) ? list.map((a) => (a.id === agent.id ? agent : a)) : [agent, ...list],
);

/** Agent name by id (or `null` when unknown — e.g. without `onec.view`). */
export function agentName(agents: readonly StoreAgent[], id: string | null | undefined): string | null {
  if (!id) return null;
  return agents.find((a) => a.id === id)?.name ?? null;
}
