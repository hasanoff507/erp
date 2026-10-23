/**
 * Real collaborators of the card payment model: @shared/offline (card_attempts, settings, local PIN),
 * the Do'kon agenti client (@shared/lib/agent, token in erp-device), the generated REST client and
 * $agentStatus / $isOnline. Tests replace all of it through `configureCardPayment`.
 */
import { api } from "@shared/api";
import type { AgentClient } from "@shared/lib/agent";
import {
  createCardTerminalClient,
  type CardBinRule,
  type TerminalAdapter,
  type TerminalInfo,
} from "@shared/lib/card-terminal";
import {
  $fiscalLadder,
  cardAttempts,
  cardTerminals,
  settings,
  staff,
  verifyLocalPin,
} from "@shared/offline";
import { $agentStatus } from "@shared/state/device";
import { $isOnline } from "@shared/state/network";

import { posAgentClient } from "#/shared/lib/device-runtime.ts";

import type { CardPaymentDeps } from "../types/index.ts";

/** The POS's single Do'kon agenti client (token + `X-Device-Id`, 21 §16). */
export function cardAgentClient(): AgentClient {
  return posAgentClient();
}

const str = (v: unknown): string | null => (typeof v === "string" && v ? v : null);

export function toTerminalInfo(row: Record<string, unknown>): TerminalInfo {
  return {
    id: String(row.id),
    name: str(row.name) ?? "",
    adapter: (str(row.adapter) ?? "cloud") as TerminalAdapter,
    driver: str(row.driver) ?? "",
    local_id: str(row.local_id),
    tid: str(row.tid),
    host: str(row.host),
    is_default: row.is_default === true,
    status: str(row.status) ?? "active",
    capabilities: row.capabilities ?? {},
  };
}

function binRulesOf(raw: Record<string, unknown>): CardBinRule[] {
  const rows = raw.card_bin_rules;
  return Array.isArray(rows) ? (rows as CardBinRule[]) : [];
}

export function defaultCardPaymentDeps(): CardPaymentDeps {
  return {
    client: (terminal) => createCardTerminalClient(terminal, { agent: cardAgentClient() }),
    terminals: async (cashRegisterId) =>
      (await cardTerminals.forRegister(cashRegisterId)).map((r) => toTerminalInfo(r)),
    fallbackPolicy: async () => (await settings.get()).cardManualFallback,
    binRules: async () => binRulesOf((await settings.get()).raw),
    agent: () => {
      const s = $agentStatus.getState();
      return {
        status: s.status,
        cardTerminalEnabled: s.capabilities.card_terminal.enabled,
        terminals: s.card_terminals.map((t) => ({ local_id: t.local_id, status: t.status })),
      };
    },
    attempts: {
      put: (a) => cardAttempts.put(a),
      update: (id, patch) => cardAttempts.update(id, patch),
      remove: (id) => cardAttempts.remove(id),
      unresolved: async (id) => await cardAttempts.unresolved(id),
      list: async () => await cardAttempts.list(),
      get: async (id) => await cardAttempts.get(id),
    },
    recordTx: (body) =>
      api.cardTerminals.recordTransaction({
        ...body,
        result: body.result,
      }),
    isOnline: () => $isOnline.getState(),
    fiscalBlocked: () => $fiscalLadder.getState().level === "blocked48",
    verifyPin: async (userId, pin) => {
      const r = await verifyLocalPin(userId, pin);
      if (r.ok) return { ok: true };
      return {
        ok: false,
        reason: r.reason,
        ...(r.reason === "invalid" ? { attemptsLeft: r.attemptsLeft } : {}),
        ...(r.reason === "locked" ? { lockedUntil: r.lockedUntil } : {}),
      };
    },
    hasPermission: (userId, code) => staff.hasPermission(userId, code),
    approvers: async () =>
      (await staff.list())
        .filter((s) => s.active && s.permissions.some((p) => p.code === "card.manual_entry.approve"))
        .map((s) => ({ userId: s.user_id, name: s.full_name })),
    now: () => Date.now(),
    sleep: (ms) => new Promise((resolve) => setTimeout(resolve, ms)),
  };
}
