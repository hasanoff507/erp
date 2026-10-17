/**
 * `AgentEcrAdapter` — `http://127.0.0.1:47110/v1/card/*` through the b3-hw agent client (24 §6.5 table,
 * 21 §16.1). HTTP → state: 200 `CardTxResult` (declined is 200 too); 409 BUSY / OUTCOME_UNKNOWN; 422
 * AMOUNT_MISMATCH; 502 VOID_FAILED; 503 UNREACHABLE; 504 / client abort / dropped connection after the
 * purchase was sent → `timeout` result (`unknown`); 401/403 → AGENT_NOT_PAIRED. `202 {attempt_id}` → poll
 * `GET /v1/card/tx/{attempt_id}` every 2 s until the 125 s deadline.
 */
import type { AgentClient } from "#/agent/index.ts";
import { AgentError } from "#/agent/index.ts";

import { CardTerminalError, timeoutResult, type CardErrorCode, type CardTerminalClient } from "./port.ts";
import { CARD_TIMEOUTS, type AgentCardTerminal, type CardTxResult, type TerminalHealth } from "./types.ts";

type AgentLike = Pick<AgentClient, "request">;

const KNOWN: ReadonlySet<string> = new Set([
  "CARD_TERMINAL_UNREACHABLE",
  "CARD_TERMINAL_BUSY",
  "CARD_TERMINAL_TIMEOUT",
  "CARD_OUTCOME_UNKNOWN",
  "CARD_AMOUNT_MISMATCH",
  "CARD_VOID_FAILED",
]);

function toCardError(error: unknown): CardTerminalError {
  if (error instanceof CardTerminalError) return error;
  if (error instanceof AgentError) {
    if (error.kind === "unpaired") return new CardTerminalError("AGENT_NOT_PAIRED", { cause: error });
    if (error.kind === "http" && KNOWN.has(error.code)) {
      return new CardTerminalError(error.code as CardErrorCode, { cause: error });
    }
    if (error.kind === "http" && error.status === 504) {
      return new CardTerminalError("CARD_TERMINAL_TIMEOUT", { cause: error });
    }
  }
  return new CardTerminalError("CARD_TERMINAL_UNREACHABLE", { cause: error });
}

const isTxResult = (v: unknown): v is CardTxResult =>
  typeof v === "object" && v !== null && "status" in v && "attempt_id" in v;

export interface AgentCardOptions {
  sleep?: (ms: number) => Promise<void>;
  now?: () => number;
  pollIntervalMs?: number;
}

export function createAgentCardTerminalClient(
  agent: AgentLike,
  {
    sleep = (ms) => new Promise((r) => setTimeout(r, ms)),
    now = Date.now,
    pollIntervalMs = 2_000,
  }: AgentCardOptions = {},
): CardTerminalClient {
  async function call<T>(
    method: "GET" | "POST",
    path: string,
    body: unknown,
    timeoutMs: number,
    signal?: AbortSignal,
  ): Promise<T> {
    try {
      return await agent.request<T>(method, path, body, { timeoutMs, ...(signal ? { signal } : {}) });
    } catch (error) {
      throw toCardError(error);
    }
  }

  return {
    adapter: "agent_ecr",
    health: (terminal) =>
      call<TerminalHealth>(
        "GET",
        `/v1/card/health?local_id=${encodeURIComponent(terminal.local_id ?? "")}`,
        undefined,
        CARD_TIMEOUTS.health,
      ),

    async purchase(req, options = {}) {
      const deadline = now() + CARD_TIMEOUTS.agentLongPoll;
      let first: unknown;
      try {
        first = await agent.request<unknown>(
          "POST",
          "/v1/card/purchase",
          {
            attempt_id: req.attempt_id,
            local_id: req.terminal.local_id,
            amount_tiyin: req.amount_tiyin,
            currency: req.currency,
            cash_register_id: req.cash_register_id,
            client_event_id: req.client_event_id,
            ...(req.receipt_seq != null ? { receipt_seq: req.receipt_seq } : {}),
          },
          { timeoutMs: CARD_TIMEOUTS.agentLongPoll, ...(options.signal ? { signal: options.signal } : {}) },
        );
      } catch (error) {
        if (error instanceof AgentError) {
          // the request may have reached the terminal: never guess "not paid", never resend
          if (error.kind === "timeout" || error.kind === "aborted" || error.kind === "protocol") {
            return timeoutResult(req.attempt_id);
          }
          if (error.kind === "http" && (error.status === 504 || error.code === "CARD_TERMINAL_TIMEOUT")) {
            return timeoutResult(req.attempt_id);
          }
          if (error.kind === "unreachable") return timeoutResult(req.attempt_id);
        }
        throw toCardError(error);
      }
      if (isTxResult(first)) return first;
      // 202 {attempt_id}: the agent accepted it — poll its journal (safe, idempotent)
      while (now() < deadline) {
        await sleep(pollIntervalMs);
        try {
          const polled = await agent.request<CardTxResult>(
            "GET",
            `/v1/card/tx/${encodeURIComponent(req.attempt_id)}`,
            undefined,
            { timeoutMs: CARD_TIMEOUTS.status },
          );
          if (isTxResult(polled) && polled.status !== "unknown") return polled;
        } catch {
          // keep polling until the deadline; the outcome is then unknown
        }
      }
      return timeoutResult(req.attempt_id);
    },

    refund: (req) =>
      call<CardTxResult>(
        "POST",
        "/v1/card/refund",
        {
          attempt_id: req.attempt_id,
          local_id: req.terminal.local_id,
          amount_tiyin: req.amount_tiyin,
          original_rrn: req.original_rrn ?? null,
          original_attempt_id: req.original_attempt_id ?? null,
        },
        CARD_TIMEOUTS.refundVoid,
      ),

    void: (req) =>
      call<CardTxResult>(
        "POST",
        "/v1/card/void",
        {
          attempt_id: req.attempt_id,
          local_id: req.terminal.local_id,
          amount_tiyin: req.amount_tiyin,
          original_attempt_id: req.original_attempt_id,
        },
        CARD_TIMEOUTS.refundVoid,
      ),

    getStatus: (attemptId) =>
      call<CardTxResult>(
        "GET",
        `/v1/card/tx/${encodeURIComponent(attemptId)}`,
        undefined,
        CARD_TIMEOUTS.status,
      ),

    async getLastTransaction(_terminal, attemptId) {
      // no separate agent route (24 §6.5): the agent resolves it inside GET /v1/card/tx/{attempt_id}
      const tx = await call<CardTxResult>(
        "GET",
        `/v1/card/tx/${encodeURIComponent(attemptId)}`,
        undefined,
        CARD_TIMEOUTS.status,
      );
      return tx.attempt_id === attemptId ? tx : null;
    },

    async cancelPending(attemptId) {
      const res = await call<{ status: "cancelled" | "not_cancellable" }>(
        "POST",
        "/v1/card/cancel-pending",
        { attempt_id: attemptId },
        CARD_TIMEOUTS.cancelPending,
      );
      return res.status;
    },

    settlement: (terminal) =>
      call("POST", "/v1/card/settlement", { local_id: terminal.local_id }, CARD_TIMEOUTS.refundVoid),

    async listTerminals() {
      const res = await call<{ items: AgentCardTerminal[] }>(
        "GET",
        "/v1/card/terminals",
        undefined,
        CARD_TIMEOUTS.status,
      );
      return res.items;
    },
  };
}
