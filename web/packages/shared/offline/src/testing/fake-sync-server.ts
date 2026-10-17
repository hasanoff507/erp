/**
 * Test double of the `/sync/*` backend (contracts/sync-push.md, sync-pull.md) used by the unit tests:
 * dedupe by client_event_id (`duplicate` returns the stored result), per-event handler for rejections,
 * scripted request-level failures (network, 401, 403, 429, 5xx) and "lost answer" (server committed,
 * client never saw the response — the crash-between-push-and-ack case). Not exported from the package.
 */
import type { SyncTransport, TransportResult } from "../sync/transport.ts";
import { SyncHttpError } from "../sync/transport.ts";
import type {
  PushResultEntry,
  SyncEventEnvelope,
  SyncPullParams,
  SyncPullResponse,
  SyncPushRequest,
  SyncPushResponse,
} from "../types.ts";

export type ScriptedFailure =
  | { kind: "network" }
  | {
      kind: "http";
      status: number;
      code: string;
      retryAfterMs?: number;
      details?: { field: string; messageKey: string }[];
    }
  /** The server processes the request, but the answer is lost. */
  | { kind: "lost-answer" };

export class FakeSyncServer implements SyncTransport {
  /** Every client_event_id the server committed, in commit order (exactly-once check). */
  readonly committed: string[] = [];
  /** Every push request body received (including failed / lost ones). */
  readonly pushRequests: SyncPushRequest[] = [];
  readonly pullRequests: SyncPullParams[] = [];
  readonly stored = new Map<string, PushResultEntry>();
  pushFailures: ScriptedFailure[] = [];
  pullFailures: ScriptedFailure[] = [];
  /** Per-event decision; return a rejected entry to reject. */
  handler: (event: SyncEventEnvelope) => PushResultEntry | null = () => null;
  /** Pull pages served in order for the next pull calls (each call takes the next page). */
  pullPages: SyncPullResponse[] = [];
  sessionAlive = true;
  refreshCalls = 0;
  serverDate: number | null = null;
  private serial = 0;

  private fail(failure: ScriptedFailure | undefined): void {
    if (!failure || failure.kind === "lost-answer") return;
    if (failure.kind === "network") throw new SyncHttpError({ status: null, code: "NETWORK_ERROR" });
    throw new SyncHttpError({
      status: failure.status,
      code: failure.code,
      retryAfterMs: failure.retryAfterMs ?? null,
      details: failure.details ?? [],
    });
  }

  push(body: SyncPushRequest): Promise<TransportResult<SyncPushResponse>> {
    this.pushRequests.push(structuredClone(body));
    const failure = this.pushFailures.shift();
    this.fail(failure);
    const results: PushResultEntry[] = body.events.map((event) => {
      const previous = this.stored.get(event.client_event_id);
      if (previous) return { ...previous, status: "duplicate" };
      const decided = this.handler(event);
      if (decided && decided.status === "rejected") return decided;
      this.serial += 1;
      const entry: PushResultEntry = decided ?? {
        client_event_id: event.client_event_id,
        status: "accepted",
        server: { id: `srv-${this.serial}`, number: `K-${this.serial}` },
        error_code: null,
        message: null,
        retryable: false,
        warnings: [],
      };
      this.stored.set(event.client_event_id, entry);
      this.committed.push(event.client_event_id);
      return entry;
    });
    if (failure?.kind === "lost-answer") {
      return Promise.reject(new SyncHttpError({ status: null, code: "NETWORK_ERROR" }));
    }
    return Promise.resolve({ data: { results }, serverDate: this.serverDate });
  }

  pull(params: SyncPullParams): Promise<TransportResult<SyncPullResponse>> {
    this.pullRequests.push({ ...params });
    this.fail(this.pullFailures.shift());
    const page = this.pullPages.shift() ?? { cursor: params.cursor || "c0", has_more: false };
    return Promise.resolve({ data: page, serverDate: this.serverDate });
  }

  refreshSession(): Promise<boolean> {
    this.refreshCalls += 1;
    return Promise.resolve(this.sessionAlive);
  }
}

export function rejected(event: SyncEventEnvelope, code: string, retryable: boolean): PushResultEntry {
  return {
    client_event_id: event.client_event_id,
    status: "rejected",
    server: null,
    error_code: code,
    message: `errors.${code.toLowerCase()}`,
    retryable,
    warnings: [],
  };
}
