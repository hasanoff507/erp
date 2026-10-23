import { describe, expect, it, vi } from "vitest";

import { AgentError, type AgentTokenStore, createAgentClient } from "./index.ts";

function memoryStore(initial: string | null = null): AgentTokenStore & { value: string | null } {
  const store = {
    value: initial,
    get: () => Promise.resolve(store.value),
    set: (t: string | null) => {
      store.value = t;
      return Promise.resolve();
    },
  };
  return store;
}

const json = (status: number, body: unknown) =>
  new Response(body === undefined ? "" : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });

const STATUS = {
  agent_version: "1.2.0",
  capabilities: {
    fiscal: { enabled: true, provider: "multikassa_local" },
    print: { enabled: true },
    card_terminal: { enabled: true },
  },
  fiscal_devices: [{ local_id: "fm1", fm_state: "ok", pending_count: 0, oldest_unacked_at: null }],
  card_terminals: [{ local_id: "t1", driver: "fake", tid: "12345678", status: "online" }],
};

describe("agentClient (21 §16, 24 §6.4)", () => {
  it("sends the Bearer token to 127.0.0.1:<port>/v1/* and parses JSON", async () => {
    const fetch = vi.fn((_url: RequestInfo | URL, _init?: RequestInit) => Promise.resolve(json(200, STATUS)));
    const client = createAgentClient({ tokenStore: memoryStore("tok"), port: 47110, fetch });
    await expect(client.status()).resolves.toEqual(STATUS);
    const [url, init] = fetch.mock.calls[0] ?? [];
    expect(url).toBe("http://127.0.0.1:47110/v1/status");
    expect((init?.headers as Record<string, string>).Authorization).toBe("Bearer tok");
  });

  it("pair: POST /v1/pair {code, device_id} without a token, stores local_token", async () => {
    const store = memoryStore(null);
    const fetch = vi.fn((_url: RequestInfo | URL, _init?: RequestInit) =>
      Promise.resolve(json(200, { local_token: "L1", expires_at: null })),
    );
    const client = createAgentClient({ tokenStore: store, baseUrl: "http://127.0.0.1:1", fetch });
    await client.pair("123456", "dev-1");
    const init = fetch.mock.calls[0]?.[1];
    expect(init?.method).toBe("POST");
    expect(JSON.parse(init?.body as string)).toEqual({ code: "123456", device_id: "dev-1" });
    expect((init?.headers as Record<string, string>).Authorization).toBeUndefined();
    expect(store.value).toBe("L1");
    await client.unpair();
    expect(store.value).toBeNull();
  });

  it("401/403 and a missing token → unpaired; error body → typed http error", async () => {
    const client401 = createAgentClient({
      tokenStore: memoryStore("x"),
      fetch: () => Promise.resolve(json(401, undefined)),
    });
    await expect(client401.status()).rejects.toMatchObject({ kind: "unpaired", status: 401 });
    const noToken = createAgentClient({ tokenStore: memoryStore(null), fetch: vi.fn() });
    await expect(noToken.request("GET", "/v1/card/terminals")).rejects.toMatchObject({
      kind: "unpaired",
      code: "AGENT_NOT_PAIRED",
    });
    const busy = createAgentClient({
      tokenStore: memoryStore("x"),
      fetch: () =>
        Promise.resolve(
          json(409, {
            code: "CARD_TERMINAL_BUSY",
            message_key: "errors.CARD_TERMINAL_BUSY",
            params: { local_id: "t1" },
          }),
        ),
    });
    const error = await busy.request("POST", "/v1/card/purchase", {}).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(AgentError);
    expect(error).toMatchObject({
      kind: "http",
      status: 409,
      code: "CARD_TERMINAL_BUSY",
      messageKey: "errors.CARD_TERMINAL_BUSY",
      params: { local_id: "t1" },
    });
  });

  it("timeout via AbortController; network failure → unreachable", async () => {
    vi.useFakeTimers();
    try {
      const hanging = createAgentClient({
        tokenStore: memoryStore("x"),
        fetch: (_u, init) =>
          new Promise((_resolve, reject) => {
            init?.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
          }),
      });
      const pending = hanging
        .request("GET", "/v1/card/tx/a1", undefined, { timeoutMs: 10_000 })
        .catch((e: unknown) => e);
      await vi.advanceTimersByTimeAsync(10_000);
      await expect(pending).resolves.toMatchObject({ kind: "timeout", code: "AGENT_TIMEOUT" });
    } finally {
      vi.useRealTimers();
    }
    const down = createAgentClient({
      tokenStore: memoryStore("x"),
      fetch: () => Promise.reject(new TypeError("Failed to fetch")),
    });
    await expect(down.status()).rejects.toMatchObject({
      kind: "unreachable",
      messageKey: "pos:equipment.agent.errors.unreachable",
    });
  });

  it("printRaw sends base64 bytes with the encoding", async () => {
    const fetch = vi.fn((_u: RequestInfo | URL, _i?: RequestInit) =>
      Promise.resolve(json(200, { status: "sent" })),
    );
    const client = createAgentClient({ tokenStore: memoryStore("x"), fetch });
    await client.printRaw({
      printerLocalId: "192.168.1.50:9100",
      data: Uint8Array.from([0x1b, 0x40]),
      encoding: "cp866",
    });
    expect(JSON.parse(fetch.mock.calls[0]?.[1]?.body as string)).toEqual({
      printer_local_id: "192.168.1.50:9100",
      data_base64: "G0A=",
      encoding: "cp866",
    });
  });

  it("probe → online / unpaired / not_installed / offline", async () => {
    const online = await createAgentClient({
      tokenStore: memoryStore("x"),
      fetch: () => Promise.resolve(json(200, STATUS)),
    }).probe();
    expect(online).toMatchObject({
      status: "online",
      version: "1.2.0",
      fm_state: "ok",
      capabilities: {
        fiscal: { enabled: true, provider: "multikassa_local" },
        print: { enabled: true },
        card_terminal: { enabled: true },
      },
      card_terminals: [{ local_id: "t1", status: "online" }],
    });
    const unpaired = await createAgentClient({
      tokenStore: memoryStore(null),
      fetch: () => Promise.resolve(json(401, undefined)),
    }).probe();
    expect(unpaired.status).toBe("unpaired");
    const revoked = await createAgentClient({
      tokenStore: memoryStore("x"),
      fetch: () => Promise.resolve(json(403, undefined)),
    }).probe();
    expect(revoked.status).toBe("unpaired");
    const fail = () => Promise.reject(new TypeError("Failed to fetch"));
    expect((await createAgentClient({ tokenStore: memoryStore(null), fetch: fail }).probe()).status).toBe(
      "not_installed",
    );
    const offline = await createAgentClient({ tokenStore: memoryStore("x"), fetch: fail }).probe();
    expect(offline).toMatchObject({ status: "offline", version: null, card_terminals: [] });
  });
});
