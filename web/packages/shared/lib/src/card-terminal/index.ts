/**
 * Bank card terminal client for the web POS (qaror #71; 21 §9.4, §16.1; 24 §6.5). Pure TS, no React and no
 * storage here — the Effector state machine lives in `@pages/pos` `features/card-payment`.
 */
import type { AgentClient } from "#/agent/index.ts";
import { getRuntimeConfig } from "#/runtime-config/index.ts";

import { createAgentCardTerminalClient } from "./agent-adapter.ts";
import { createFakeCardTerminalClient, type FakeCardTerminalClient } from "./fake.ts";
import type { CardTerminalClient } from "./port.ts";
import type { TerminalInfo, TerminalRef } from "./types.ts";

export * from "./types.ts";
export * from "./port.ts";
export * from "./mapping.ts";
export { createAgentCardTerminalClient, type AgentCardOptions } from "./agent-adapter.ts";
export {
  createFakeCardTerminalClient,
  fakeOutcomeFor,
  FAKE_RAW_MASK,
  FAKE_TID,
  type FakeCardTerminalClient,
  type FakeOutcome,
  type FakeOptions,
} from "./fake.ts";

export const terminalRef = (t: Pick<TerminalInfo, "id" | "local_id">): TerminalRef => ({
  card_terminal_id: t.id,
  local_id: t.local_id,
});

/** Default terminal of a register: `is_default`, else the only active one (18 §16a.1); several → caller asks. */
export function pickTerminal(terminals: readonly TerminalInfo[]): TerminalInfo | null {
  const active = terminals.filter((t) => (t.status ?? "active") === "active");
  return active.find((t) => t.is_default) ?? (active.length === 1 ? (active[0] ?? null) : null);
}

export interface ClientFactoryOptions {
  agent: Pick<AgentClient, "request">;
  /** One shared fake per page load (its journal must survive between calls). */
  fake?: FakeCardTerminalClient;
  /** Production guard: the fake adapter is refused unless the tenant is a demo one (24 §6.5). */
  allowFakeInProduction?: boolean;
}

let sharedFake: FakeCardTerminalClient | null = null;

/** `null` → the integrated path is unavailable for this terminal (`CARD_TERMINAL_UNREACHABLE`). */
export function createCardTerminalClient(
  terminal: Pick<TerminalInfo, "adapter">,
  options: ClientFactoryOptions,
): CardTerminalClient | null {
  if (terminal.adapter === "agent_ecr") return createAgentCardTerminalClient(options.agent);
  if (terminal.adapter === "fake") {
    if (getRuntimeConfig().environment === "production" && !options.allowFakeInProduction) return null;
    if (options.fake) return options.fake;
    sharedFake ??= createFakeCardTerminalClient();
    return sharedFake;
  }
  return null; // cloud (server adapter), android_intent, softpos — not in the web POS
}

export type { CardTerminalClient };
