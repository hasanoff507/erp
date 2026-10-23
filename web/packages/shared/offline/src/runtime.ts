/**
 * Module-level runtime of @shared/offline: options, clock, lazily opened databases.
 * `configureOffline()` is called once by the POS app layer (tests call it with a fake clock and
 * unique database names). Everything else reads through `rt()`.
 */
import { DeviceDb, PosDb } from "./db/schema.ts";
import type { SyncTransport } from "./sync/transport.ts";

export const DEFAULT_DB_NAMES = { pos: "erp-pos", device: "erp-device" } as const;

export interface OfflineOptions {
  transport?: SyncTransport;
  /** Wall clock in ms (fake clock in tests). */
  now?: () => number;
  dbNames?: { pos: string; device: string };
  /** 16 §3.1 — default 100 events per push (qaror #54). */
  pushBatchSize?: number;
  /** 16 §1 — default 60 s delta pull. */
  pullIntervalMs?: number;
  /** 16 §3.1 — default 5 min empty push carrying outbox_state. */
  heartbeatPushMs?: number;
  /** 16 §1 — default 500 rows per pull page. */
  pageSize?: number;
  /** 16 §10 — default 7 days. */
  outboxRetentionMs?: number;
  /** 16 §10 — default 90 days. */
  historyRetentionMs?: number;
}

interface Runtime {
  transport: SyncTransport | null;
  now: () => number;
  dbNames: { pos: string; device: string };
  pushBatchSize: number;
  pullIntervalMs: number;
  heartbeatPushMs: number;
  pageSize: number;
  outboxRetentionMs: number;
  historyRetentionMs: number;
  pos: PosDb | null;
  device: DeviceDb | null;
}

const DAY_MS = 24 * 60 * 60 * 1000;

const defaults = (): Runtime => ({
  transport: null,
  now: () => Date.now(),
  dbNames: { ...DEFAULT_DB_NAMES },
  pushBatchSize: 100,
  pullIntervalMs: 60_000,
  heartbeatPushMs: 300_000,
  pageSize: 500,
  outboxRetentionMs: 7 * DAY_MS,
  historyRetentionMs: 90 * DAY_MS,
  pos: null,
  device: null,
});

let state: Runtime = defaults();

export function configureOffline(options: OfflineOptions = {}): void {
  const namesChanged =
    options.dbNames !== undefined &&
    (options.dbNames.pos !== state.dbNames.pos || options.dbNames.device !== state.dbNames.device);
  if (namesChanged) closeDatabases();
  state = {
    ...state,
    transport: options.transport ?? state.transport,
    now: options.now ?? state.now,
    dbNames: options.dbNames ?? state.dbNames,
    pushBatchSize: options.pushBatchSize ?? state.pushBatchSize,
    pullIntervalMs: options.pullIntervalMs ?? state.pullIntervalMs,
    heartbeatPushMs: options.heartbeatPushMs ?? state.heartbeatPushMs,
    pageSize: options.pageSize ?? state.pageSize,
    outboxRetentionMs: options.outboxRetentionMs ?? state.outboxRetentionMs,
    historyRetentionMs: options.historyRetentionMs ?? state.historyRetentionMs,
  };
}

export function rt(): Readonly<Runtime> {
  return state;
}

export function now(): number {
  return state.now();
}

export function nowIso(): string {
  return new Date(state.now()).toISOString();
}

export function posDb(): PosDb {
  state.pos ??= new PosDb(state.dbNames.pos);
  return state.pos;
}

export function deviceDb(): DeviceDb {
  state.device ??= new DeviceDb(state.dbNames.device);
  return state.device;
}

export function closeDatabases(): void {
  state.pos?.close();
  state.device?.close();
  state.pos = null;
  state.device = null;
}

/** Tests: drop every option and close the databases. */
export function resetOfflineRuntime(): void {
  closeDatabases();
  state = defaults();
}
