/**
 * POS device context — 24 §2 ($activeShift) and §6.4 ($agentStatus). Bosqich 0 placeholders:
 * shift opening is POS-01 (Bosqich 3), the shop agent client arrives in Bosqich 5.
 */
import { createStore } from "effector";

export type AgentConnection = "online" | "offline" | "not_installed" | "unpaired";

export interface AgentStatus {
  status: AgentConnection;
  version: string | null;
}

export interface ActiveShift {
  id: string;
  number: number;
  openedAt: string;
}

export const $activeShift = createStore<ActiveShift | null>(null);
export const $agentStatus = createStore<AgentStatus>({ status: "not_installed", version: null });
