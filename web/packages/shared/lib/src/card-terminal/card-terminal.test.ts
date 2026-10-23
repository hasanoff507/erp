import { describe, expect, it } from "vitest";

import { AgentError, createAgentClient } from "#/agent/index.ts";
import type { Money } from "#/money/index.ts";

import {
  CardTerminalError,
  createAgentCardTerminalClient,
  createFakeCardTerminalClient,
  fakeOutcomeFor,
  lookupBin,
  managerCardResult,
  newAttemptId,
  normalizeMask,
  pickTerminal,
  toCardResult,
  type CardPurchaseRequest,
  type CardTxResult,
} from "./index.ts";

const TERMINAL = { card_terminal_id: "t-1", local_id: "term-1" };

function req(amountTiyin: number, attemptId = newAttemptId()): CardPurchaseRequest {
  return {
    attempt_id: attemptId,
    terminal: TERMINAL,
    amount_tiyin: amountTiyin,
    currency: "UZS",
    cash_register_id: "cr-1",
    client_event_id: "ev-1",
  };
}

const instant = { delayMs: 0, sleep: () => Promise.resolve() };

describe("mapping — 24 §6.5 / 21 §9.4", () => {
  it("normalises the mask to 4+4 and keeps the BIN only in memory", () => {
    expect(normalizeMask("860031******1234")).toEqual({ mask: "8600********1234", bin: "860031" });
    expect(normalizeMask("8600****1234")).toEqual({ mask: "8600****1234", bin: null });
    expect(normalizeMask("8600123412341234")).toBeNull(); // a PAN is never a mask
  });

  it("card_type: terminal → BIN table (longest valid prefix) → unknown", async () => {
    const fake = createFakeCardTerminalClient(instant);
    const tx = await fake.purchase(req(1_200_000));
    const rules = [
      { bin_prefix: "8600", card_type: "personal" as const, valid_from: "2026-01-01" },
      { bin_prefix: "860031", card_type: "corporate" as const, valid_from: "2026-01-01" },
      { bin_prefix: "860031", card_type: "social" as const, valid_from: "2027-01-01" },
    ];
    expect(lookupBin("860031", rules, "2026-10-17")?.card_type).toBe("corporate");
    const opts = { cardTerminalId: "t-1", requestedAmount: "12000.00" as Money, resolvedBy: "auto" as const };
    const withRules = toCardResult(tx, { ...opts, binRules: rules, today: "2026-10-17" });
    expect([withRules.card_type, withRules.card_type_source]).toEqual(["corporate", "bin_table"]);
    expect(withRules.card_mask).toBe("8600********1234");
    expect(JSON.stringify(withRules)).not.toContain("860031");
    const noRules = toCardResult(tx, opts);
    expect([noRules.card_type, noRules.card_type_source]).toEqual(["unknown", "bin_table"]);
    const social = toCardResult(await fake.purchase(req(1_200_900)), opts);
    expect([social.card_type, social.card_type_source]).toEqual(["social", "terminal"]);
    expect(withRules.amount).toBe("12000.00");
  });

  it("status map: cancelled/error → declined with that code, timeout → unknown", async () => {
    const fake = createFakeCardTerminalClient(instant);
    const opts = { cardTerminalId: "t-1", requestedAmount: "12007.00" as Money, resolvedBy: "auto" as const };
    const cancelled = toCardResult(await fake.purchase(req(1_200_700)), opts);
    expect([cancelled.status, cancelled.decline_code]).toEqual(["declined", "cancelled"]);
    const timeout = toCardResult(await fake.purchase(req(1_200_200)), opts);
    expect(timeout.status).toBe("unknown");
    expect(timeout.amount).toBe("12007.00");
  });

  it("a manager resolution carries no card details", () => {
    const r = managerCardResult({
      attemptId: "a",
      cardTerminalId: "t",
      amount: "5.00" as Money,
      passed: false,
    });
    expect(r).toMatchObject({ status: "declined", decline_code: "not_found", rrn: null, card_mask: null });
    expect(r.resolved_by).toBe("manager");
  });

  it("attempt ids are UUIDv7", () => {
    const id = newAttemptId(Date.UTC(2026, 9, 17));
    expect(id).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
  });

  it("picks the default terminal, else the only active one", () => {
    const a = { id: "a", name: "A", adapter: "fake" as const, driver: "fake", local_id: null, tid: null };
    expect(pickTerminal([a, { ...a, id: "b", is_default: true }])?.id).toBe("b");
    expect(pickTerminal([a])?.id).toBe("a");
    expect(pickTerminal([a, { ...a, id: "c" }])).toBeNull();
    expect(pickTerminal([{ ...a, status: "disabled" }])).toBeNull();
  });
});

describe("FakeCardTerminalClient — deterministic table, idempotent attempt_id", () => {
  it("follows the so'm ending table", () => {
    expect(fakeOutcomeFor(1_200_000)).toBe("approved");
    expect(fakeOutcomeFor(1_200_100)).toBe("declined_51");
    expect(fakeOutcomeFor(1_200_300)).toBe("timeout_unresolved");
    expect(fakeOutcomeFor(1_200_500)).toBe("amount_mismatch");
  });

  it("same attempt_id → journalled result, terminal hit once; busy throws", async () => {
    const fake = createFakeCardTerminalClient(instant);
    const r = req(1_200_000);
    const first = await fake.purchase(r);
    expect((await fake.purchase(r)).rrn).toBe(first.rrn);
    expect(fake.calls.purchase).toBe(1);
    await expect(fake.purchase(req(1_200_400))).rejects.toMatchObject({ code: "CARD_TERMINAL_BUSY" });
  });

  it("timeout → status query; void of a 006 purchase fails; scenario override", async () => {
    const fake = createFakeCardTerminalClient(instant);
    const t = await fake.purchase(req(1_200_200));
    expect(t.status).toBe("timeout");
    expect((await fake.getStatus(t.attempt_id, TERMINAL)).status).toBe("approved");
    const u = await fake.purchase(req(1_200_300));
    expect((await fake.getStatus(u.attempt_id, TERMINAL)).status).toBe("unknown");
    expect(await fake.getLastTransaction(TERMINAL, u.attempt_id)).toBeNull();
    const p = await fake.purchase(req(1_200_600));
    const v = await fake.void({
      attempt_id: newAttemptId(),
      terminal: TERMINAL,
      amount_tiyin: 1_200_600,
      original_attempt_id: p.attempt_id,
    });
    expect(v.status).toBe("declined");
    fake.fakeCardScenario("declined_05");
    expect((await fake.purchase(req(1_200_000))).decline_code).toBe("05");
  });

  it("cancel-pending during the wait ends the purchase as cancelled", async () => {
    const fake = createFakeCardTerminalClient({ delayMs: 50 });
    const r = req(1_200_000);
    const pending = fake.purchase(r);
    await new Promise((res) => setTimeout(res, 5));
    expect(await fake.cancelPending(r.attempt_id)).toBe("cancelled");
    expect((await pending).status).toBe("cancelled");
  });
});

function agentWith(responder: (path: string, init: RequestInit) => Response | Promise<Response>) {
  const calls: string[] = [];
  const agent = createAgentClient({
    tokenStore: { get: () => Promise.resolve("tok"), set: () => Promise.resolve() },
    baseUrl: "http://127.0.0.1:47110",
    fetch: async (input, init) => {
      const url = input instanceof Request ? input.url : input.toString();
      const path = url.replace("http://127.0.0.1:47110", "");
      calls.push(`${init?.method ?? "GET"} ${path}`);
      return responder(path, init ?? {});
    },
  });
  return { agent, calls };
}

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

const approvedTx = (attemptId: string): CardTxResult => ({
  attempt_id: attemptId,
  kind: "purchase",
  status: "approved",
  amount_tiyin: 1_200_000,
  approval_code: "A1B2C3",
  rrn: "612345678901",
  stan: null,
  card_mask: "8600****1234",
  card_scheme: "uzcard",
  card_type: null,
  entry_mode: "chip",
  tid: "T1",
  mid: null,
  acquirer: null,
  tx_at: null,
  decline_code: null,
  decline_message: null,
});

describe("AgentEcrAdapter — HTTP → state (24 §6.5), purchase never retried", () => {
  it("200 → result; the body has no card data fields beyond the result", async () => {
    const r = req(1_200_000);
    let sent: unknown;
    const { agent, calls } = agentWith((_p, init) => {
      sent = JSON.parse(init.body as string);
      return json(200, approvedTx(r.attempt_id));
    });
    const client = createAgentCardTerminalClient(agent);
    expect((await client.purchase(r)).status).toBe("approved");
    expect(calls).toEqual(["POST /v1/card/purchase"]);
    expect(sent).toEqual({
      attempt_id: r.attempt_id,
      local_id: "term-1",
      amount_tiyin: 1_200_000,
      currency: "UZS",
      cash_register_id: "cr-1",
      client_event_id: "ev-1",
    });
  });

  it("504 / dropped connection → timeout result (unknown), exactly one purchase call", async () => {
    const r = req(1_200_000);
    const gateway = agentWith(() =>
      json(504, { code: "CARD_TERMINAL_TIMEOUT", message_key: "errors.card_terminal_timeout" }),
    );
    expect((await createAgentCardTerminalClient(gateway.agent).purchase(r)).status).toBe("timeout");
    expect(gateway.calls).toHaveLength(1);
    const dropped = agentWith(() => {
      throw new TypeError("network");
    });
    expect((await createAgentCardTerminalClient(dropped.agent).purchase(r)).status).toBe("timeout");
    expect(dropped.calls).toHaveLength(1);
  });

  it("409 busy / outcome unknown, 503 unreachable, 401 unpaired → typed errors", async () => {
    const cases: [number, string, string][] = [
      [409, "CARD_TERMINAL_BUSY", "CARD_TERMINAL_BUSY"],
      [409, "CARD_OUTCOME_UNKNOWN", "CARD_OUTCOME_UNKNOWN"],
      [503, "CARD_TERMINAL_UNREACHABLE", "CARD_TERMINAL_UNREACHABLE"],
      [401, "X", "AGENT_NOT_PAIRED"],
    ];
    for (const [status, code, expected] of cases) {
      const { agent } = agentWith(() => json(status, { code, message_key: `errors.${code.toLowerCase()}` }));
      const error = await createAgentCardTerminalClient(agent)
        .purchase(req(100))
        .catch((e: unknown) => e);
      expect(error).toBeInstanceOf(CardTerminalError);
      expect((error as CardTerminalError).code).toBe(expected);
    }
  });

  it("202 {attempt_id} → polls GET /v1/card/tx/{id} every 2 s", async () => {
    const r = req(1_200_000);
    let polls = 0;
    const { agent, calls } = agentWith((path) => {
      if (path === "/v1/card/purchase") return json(202, { attempt_id: r.attempt_id });
      polls += 1;
      return polls < 2
        ? json(200, { ...approvedTx(r.attempt_id), status: "unknown" })
        : json(200, approvedTx(r.attempt_id));
    });
    let clock = 0;
    const client = createAgentCardTerminalClient(agent, {
      sleep: (ms) => {
        clock += ms;
        return Promise.resolve();
      },
      now: () => clock,
    });
    expect((await client.purchase(r)).status).toBe("approved");
    expect(calls.filter((c) => c.startsWith("GET /v1/card/tx/"))).toHaveLength(2);
    expect(clock).toBe(4_000);
  });

  it("health uses local_id, cancel-pending and list map to the agent routes", async () => {
    const { agent, calls } = agentWith((path) => {
      if (path.startsWith("/v1/card/health"))
        return json(200, { status: "online", tid: "T1", last_tx_at: null });
      if (path === "/v1/card/cancel-pending") return json(200, { status: "cancelled" });
      return json(200, {
        items: [
          { local_id: "term-1", driver: "rahmat_lan", host: "192.168.1.5", tid: "T1", status: "online" },
        ],
      });
    });
    const client = createAgentCardTerminalClient(agent);
    expect((await client.health(TERMINAL)).status).toBe("online");
    expect(await client.cancelPending("a-1")).toBe("cancelled");
    expect((await client.listTerminals())[0]?.local_id).toBe("term-1");
    expect(calls).toEqual([
      "GET /v1/card/health?local_id=term-1",
      "POST /v1/card/cancel-pending",
      "GET /v1/card/terminals",
    ]);
  });

  it("unknown agent errors never become a decline", async () => {
    const { agent } = agentWith(() => json(500, { code: "WEIRD" }));
    const e = await createAgentCardTerminalClient(agent)
      .health(TERMINAL)
      .catch((x: unknown) => x);
    expect((e as CardTerminalError).code).toBe("CARD_TERMINAL_UNREACHABLE");
    expect(new AgentError("http", "X")).toBeInstanceOf(Error);
  });
});
