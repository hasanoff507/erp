/**
 * Do'kon agenti local API client — 21 §16 / §16.1, 24 §6.4. `http://127.0.0.1:<port>/v1/*`, device-bound
 * local token (`Authorization: Bearer`), AbortController timeouts, error shape `{code, message_key, params?}`.
 * The token is stored by the caller (erp-device, never sent to the server) through `AgentTokenStore`.
 * Every authenticated call also carries `X-Device-Id: <devices.id>` — the agent accepts a token only with the
 * device it was paired with (21 §16 Himoya (c), .claude-scratch/b5/contracts/agent-local-api.md §1).
 * Contract: .claude-scratch/b3/contracts/hw-api.md §1.
 */
import { getRuntimeConfig } from "#/runtime-config/index.ts";

/** deviceSettings key of the local token (erp-device). */
export const AGENT_TOKEN_KEY = "agent.local_token";
export const AGENT_DEFAULT_TIMEOUT_MS = 10_000;
export const AGENT_STATUS_TIMEOUT_MS = 3_000;
export const AGENT_PRINT_TIMEOUT_MS = 15_000;
/** Header naming the POS device (`devices.id`) the local token was paired with (21 §16). */
export const AGENT_DEVICE_HEADER = "X-Device-Id";

export interface AgentTokenStore {
  get(): Promise<string | null>;
  set(token: string | null): Promise<void>;
}

export type AgentErrorKind = "unpaired" | "unreachable" | "timeout" | "aborted" | "http" | "protocol";

/** i18n keys of client-side agent states (namespace `pos`); HTTP errors carry the agent's `message_key`. */
export const LOCAL_KEY_PREFIX = "pos:equipment.agent.errors.";

export class AgentError extends Error {
  readonly kind: AgentErrorKind;
  readonly status: number | null;
  readonly code: string;
  readonly messageKey: string;
  readonly params: Record<string, unknown> | undefined;

  constructor(
    kind: AgentErrorKind,
    code: string,
    options: {
      status?: number | null;
      messageKey?: string;
      params?: Record<string, unknown>;
      cause?: unknown;
    } = {},
  ) {
    super(`${kind}: ${code}`, options.cause !== undefined ? { cause: options.cause } : undefined);
    this.name = "AgentError";
    this.kind = kind;
    this.code = code;
    this.status = options.status ?? null;
    this.messageKey = options.messageKey ?? `${LOCAL_KEY_PREFIX}${kind}`;
    this.params = options.params;
  }
}

export const isAgentUnpaired = (e: unknown): e is AgentError =>
  e instanceof AgentError && e.kind === "unpaired";

/** `GET /v1/status` (21 §16.1). */
export interface AgentStatusResponse {
  agent_version: string;
  capabilities: {
    fiscal?: { enabled: boolean; provider?: string | null };
    print?: { enabled: boolean };
    card_terminal?: { enabled: boolean };
  };
  fiscal_devices?: {
    local_id: string;
    fm_state: string;
    pending_count: number;
    oldest_unacked_at: string | null;
  }[];
  card_terminals?: {
    local_id: string;
    driver: string;
    tid: string | null;
    status: "online" | "busy" | "offline" | "error";
  }[];
}

export type AgentConnection = "online" | "offline" | "not_installed" | "unpaired";

/** What `$agentStatus` (@shared/state/device) stores — hw-api.md §2. */
export interface AgentStatusSnapshot {
  status: AgentConnection;
  version: string | null;
  capabilities: {
    fiscal: { enabled: boolean; provider: string | null };
    print: { enabled: boolean };
    card_terminal: { enabled: boolean };
  };
  fm_state: string | null;
  fiscal_devices: NonNullable<AgentStatusResponse["fiscal_devices"]>;
  card_terminals: NonNullable<AgentStatusResponse["card_terminals"]>;
  checked_at: string | null;
}

export const EMPTY_AGENT_CAPABILITIES: AgentStatusSnapshot["capabilities"] = Object.freeze({
  fiscal: { enabled: false, provider: null },
  print: { enabled: false },
  card_terminal: { enabled: false },
});

export function agentSnapshot(
  status: AgentConnection,
  response: AgentStatusResponse | null = null,
  checkedAt: string | null = new Date().toISOString(),
): AgentStatusSnapshot {
  const caps = response?.capabilities ?? {};
  const fiscalDevices = response?.fiscal_devices ?? [];
  return {
    status,
    version: response?.agent_version ?? null,
    capabilities: {
      fiscal: { enabled: caps.fiscal?.enabled === true, provider: caps.fiscal?.provider ?? null },
      print: { enabled: caps.print?.enabled === true },
      card_terminal: { enabled: caps.card_terminal?.enabled === true },
    },
    fm_state: fiscalDevices[0]?.fm_state ?? null,
    fiscal_devices: fiscalDevices,
    card_terminals: response?.card_terminals ?? [],
    checked_at: checkedAt,
  };
}

export interface AgentRequestOptions {
  timeoutMs?: number;
  signal?: AbortSignal;
  /** Send without the Bearer token (pairing). */
  anonymous?: boolean;
}

export interface AgentClientOptions {
  tokenStore: AgentTokenStore;
  /**
   * `devices.id` of this POS (`X-Device-Id`, 21 §16). Without it the agent answers 401 → `unpaired`;
   * re-pairing then binds the token to this device.
   */
  deviceId?: () => Promise<string | null> | string | null;
  port?: number;
  /** Override the whole origin (tests). Default `http://127.0.0.1:<port>`. */
  baseUrl?: string;
  fetch?: typeof fetch;
}

export interface AgentClient {
  readonly baseUrl: string;
  request<T>(method: "GET" | "POST", path: string, body?: unknown, options?: AgentRequestOptions): Promise<T>;
  status(options?: AgentRequestOptions): Promise<AgentStatusResponse>;
  pair(code: string, deviceId: string): Promise<void>;
  unpair(): Promise<void>;
  printRaw(input: { printerLocalId: string; data: Uint8Array; encoding: "cp866" | "raster" }): Promise<void>;
  /** One status probe → snapshot for `$agentStatus` (never throws). */
  probe(): Promise<AgentStatusSnapshot>;
}

function toBase64(bytes: Uint8Array): string {
  let binary = "";
  for (let i = 0; i < bytes.length; i += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  }
  return btoa(binary);
}

const isRecord = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null;

export function createAgentClient(options: AgentClientOptions): AgentClient {
  const doFetch = options.fetch ?? ((input: RequestInfo | URL, init?: RequestInit) => fetch(input, init));
  const baseUrl = options.baseUrl ?? `http://127.0.0.1:${options.port ?? getRuntimeConfig().agentPort}`;

  async function request<T>(
    method: "GET" | "POST",
    path: string,
    body?: unknown,
    { timeoutMs = AGENT_DEFAULT_TIMEOUT_MS, signal, anonymous = false }: AgentRequestOptions = {},
  ): Promise<T> {
    const headers: Record<string, string> = { Accept: "application/json" };
    if (!anonymous) {
      const token = await options.tokenStore.get();
      if (!token) throw new AgentError("unpaired", "AGENT_NOT_PAIRED");
      headers.Authorization = `Bearer ${token}`;
      const deviceId = await options.deviceId?.();
      if (deviceId) headers[AGENT_DEVICE_HEADER] = deviceId;
    }
    if (body !== undefined) headers["Content-Type"] = "application/json";

    const controller = new AbortController();
    let timedOut = false;
    const timer = setTimeout(() => {
      timedOut = true;
      controller.abort();
    }, timeoutMs);
    const onAbort = () => controller.abort();
    signal?.addEventListener("abort", onAbort, { once: true });
    if (signal?.aborted) controller.abort();

    let response: Response;
    try {
      const init: RequestInit & { targetAddressSpace?: string } = {
        method,
        headers,
        signal: controller.signal,
        // Chrome Local Network Access (24 §6.4): loopback request from the https PWA.
        targetAddressSpace: "loopback",
        ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
      };
      response = await doFetch(`${baseUrl}${path}`, init);
    } catch (cause) {
      if (timedOut) throw new AgentError("timeout", "AGENT_TIMEOUT", { cause });
      if (signal?.aborted) throw new AgentError("aborted", "AGENT_ABORTED", { cause });
      throw new AgentError("unreachable", "AGENT_UNREACHABLE", { cause });
    } finally {
      clearTimeout(timer);
      signal?.removeEventListener("abort", onAbort);
    }

    let payload: unknown = null;
    const text = await response.text();
    if (text) {
      try {
        payload = JSON.parse(text);
      } catch (cause) {
        if (response.ok)
          throw new AgentError("protocol", "AGENT_PROTOCOL_ERROR", { status: response.status, cause });
      }
    }
    if (response.status === 401 || response.status === 403) {
      throw new AgentError("unpaired", "AGENT_NOT_PAIRED", { status: response.status });
    }
    if (!response.ok) {
      const code = isRecord(payload) && typeof payload.code === "string" ? payload.code : "AGENT_HTTP_ERROR";
      const messageKey =
        isRecord(payload) && typeof payload.message_key === "string" ? payload.message_key : `errors.${code}`;
      const params = isRecord(payload) && isRecord(payload.params) ? payload.params : undefined;
      throw new AgentError("http", code, {
        status: response.status,
        messageKey,
        ...(params ? { params } : {}),
      });
    }
    return payload as T;
  }

  const client: AgentClient = {
    baseUrl,
    request,
    status: (opts) =>
      request<AgentStatusResponse>("GET", "/v1/status", undefined, {
        timeoutMs: AGENT_STATUS_TIMEOUT_MS,
        ...opts,
      }),
    async pair(code, deviceId) {
      const result = await request<{ local_token?: unknown }>(
        "POST",
        "/v1/pair",
        { code, device_id: deviceId },
        { anonymous: true },
      );
      if (!isRecord(result) || typeof result.local_token !== "string" || !result.local_token) {
        throw new AgentError("protocol", "AGENT_PROTOCOL_ERROR");
      }
      await options.tokenStore.set(result.local_token);
    },
    unpair: () => options.tokenStore.set(null),
    async printRaw({ printerLocalId, data, encoding }) {
      await request(
        "POST",
        "/v1/print/raw",
        { printer_local_id: printerLocalId, data_base64: toBase64(data), encoding },
        {
          timeoutMs: AGENT_PRINT_TIMEOUT_MS,
        },
      );
    },
    async probe() {
      const hasToken = Boolean(await options.tokenStore.get());
      try {
        if (!hasToken) {
          // Agent answers 401 without a token → installed but not paired; network error → not installed.
          await request("GET", "/v1/status", undefined, {
            timeoutMs: AGENT_STATUS_TIMEOUT_MS,
            anonymous: true,
          });
          return agentSnapshot("unpaired");
        }
        return agentSnapshot("online", await client.status());
      } catch (error) {
        if (error instanceof AgentError && error.kind === "unpaired") return agentSnapshot("unpaired");
        if (error instanceof AgentError && (error.kind === "http" || error.kind === "protocol")) {
          return agentSnapshot(hasToken ? "offline" : "unpaired");
        }
        return agentSnapshot(hasToken ? "offline" : "not_installed");
      }
    },
  };
  return client;
}
