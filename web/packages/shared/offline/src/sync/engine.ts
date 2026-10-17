/**
 * Sync engine scheduler — 16 §1 (pull every 60 s + on `online` + on demand), §3.1 (push right after
 * every enqueue, heartbeat push every 5 min, exponential backoff + jitter, Retry-After), §3.4
 * (401 → silent session probe → authRequired, outbox untouched; 403 DEVICE_REVOKED → stop), §11
 * (one pushing tab via Web Lock, other tabs informed by BroadcastChannel).
 */
import Dexie from "dexie";

import {
  authRequired,
  deviceRevoked,
  outboxChanged,
  pullApplied,
  subscriptionRestricted,
  syncRequested,
} from "../events.ts";
import { refreshFiscalLadder } from "../fiscal/ladder.ts";
import { runBackground } from "../lib/background.ts";
import { clockSkewMs } from "../lib/clock.ts";
import { broadcast, onSyncMessage } from "../lib/broadcast.ts";
import { SYNC_PUSH_LOCK, tryWithLock } from "../lib/locks.ts";
import { invalidateMemoryIndex } from "../lib/memory-index.ts";
import { setPushTrigger } from "../lib/triggers.ts";
import { META } from "../db/meta.ts";
import { runRetention } from "../lifecycle/retention.ts";
import { resolveEventResults } from "../outbox/queries.ts";
import { catalog } from "../repos/catalog.ts";
import { now, posDb, rt } from "../runtime.ts";
import { pullNow, type PullOutcome } from "./pull.ts";
import { pushNow, type PushOutcome } from "./push.ts";
import { getSyncStatus, patchSyncStatus, refreshOutboxCounters } from "./status.ts";

export const SYNC_PULL_LOCK = "erp-sync-pull";
const BACKOFF_BASE_MS = 1000;
const BACKOFF_MAX_MS = 60_000;
const RESTRICTED_RETRY_MS = 5 * 60_000;
const LADDER_REFRESH_MS = 60_000;
const RETENTION_MS = 60 * 60_000;
/** SYNC-11: retry delay when another tab holds `erp-sync-push`. */
export const LOCK_RETRY_MS = 1000;

/** Exponential backoff with jitter: 1 s, 2 s, 4 s … 60 s, each × [0.5, 1). */
export function backoffDelayMs(failures: number, random: () => number = Math.random): number {
  const base = Math.min(BACKOFF_MAX_MS, BACKOFF_BASE_MS * 2 ** Math.max(0, failures - 1));
  return Math.round(base * (0.5 + random() * 0.5));
}

interface EngineState {
  running: boolean;
  timers: ReturnType<typeof setInterval>[];
  pushTimer: ReturnType<typeof setTimeout> | null;
  pushTimerAt: number;
  pullTimer: ReturnType<typeof setTimeout> | null;
  pushFailures: number;
  pullFailures: number;
  pushInFlight: Promise<void> | null;
  pushAgain: boolean;
  pullInFlight: Promise<void> | null;
  cleanups: (() => void)[];
}

const engine: EngineState = {
  running: false,
  timers: [],
  pushTimer: null,
  pushTimerAt: 0,
  pullTimer: null,
  pushFailures: 0,
  pullFailures: 0,
  pushInFlight: null,
  pushAgain: false,
  pullInFlight: null,
  cleanups: [],
};

function browserOffline(): boolean {
  return typeof navigator !== "undefined" && (navigator as { onLine?: boolean }).onLine === false;
}

function schedulePush(delayMs: number): void {
  if (!engine.running) return;
  const at = now() + delayMs;
  if (engine.pushTimer !== null && engine.pushTimerAt <= at) return;
  if (engine.pushTimer !== null) clearTimeout(engine.pushTimer);
  engine.pushTimerAt = at;
  engine.pushTimer = setTimeout(() => {
    engine.pushTimer = null;
    runBackground(runPush);
  }, delayMs);
}

function schedulePull(delayMs: number): void {
  if (!engine.running) return;
  if (engine.pullTimer !== null) clearTimeout(engine.pullTimer);
  engine.pullTimer = setTimeout(() => {
    engine.pullTimer = null;
    runBackground(runPull);
  }, delayMs);
}

async function nextRetryableDueAt(): Promise<number | null> {
  const row = await posDb()
    .outbox.where("[unsynced+seq]")
    .between([1, Dexie.minKey], [1, Dexie.maxKey])
    .filter((r) => r.status === "rejected" && r.retryable === true)
    .toArray();
  let min: number | null = null;
  for (const r of row) if (min === null || r.next_attempt_at < min) min = r.next_attempt_at;
  return min;
}

function onRevoked(): void {
  patchSyncStatus({ deviceRevoked: true, pushing: false, pulling: false, lastErrorCode: "DEVICE_REVOKED" });
  deviceRevoked();
  stopTimers();
  // persisted: after a reload the POS stays locked until the wipe (16 §9)
  runBackground(() => posDb().meta.put({ key: META.deviceRevoked, value: true }));
}

function handleStopped(code: "DEVICE_REVOKED" | "AUTH_REQUIRED" | "SUBSCRIPTION_RESTRICTED"): void {
  if (code === "DEVICE_REVOKED") {
    onRevoked();
    broadcast({ type: "device-revoked" });
    return;
  }
  if (code === "AUTH_REQUIRED") {
    if (!getSyncStatus().authRequired) {
      patchSyncStatus({ authRequired: true, lastErrorCode: "UNAUTHORIZED" });
      authRequired();
    }
    return;
  }
  if (!getSyncStatus().subscriptionRestricted) {
    patchSyncStatus({ subscriptionRestricted: true, lastErrorCode: "SUBSCRIPTION_RESTRICTED" });
    subscriptionRestricted();
  }
  schedulePush(RESTRICTED_RETRY_MS);
}

async function afterPush(outcome: PushOutcome): Promise<void> {
  if (outcome.kind === "done") {
    engine.pushFailures = 0;
    const lastPushAt = ((await posDb().meta.get(META.lastPushAt))?.value as string | undefined) ?? null;
    patchSyncStatus({
      lastErrorCode: null,
      authRequired: false,
      subscriptionRestricted: false,
      lastPushAt,
      clockSkewMs: clockSkewMs(),
    });
    const due = await nextRetryableDueAt();
    if (due !== null && due < Number.MAX_SAFE_INTEGER) schedulePush(Math.max(0, due - now()));
    return;
  }
  if (outcome.kind === "retry") {
    engine.pushFailures += 1;
    patchSyncStatus({ lastErrorCode: outcome.code });
    schedulePush(outcome.retryAfterMs ?? backoffDelayMs(engine.pushFailures));
    return;
  }
  handleStopped(outcome.code);
}

/** One push run (coalesced in-tab; skipped when another tab holds the push lock). */
export function runPush(opts: { heartbeat?: boolean } = {}): Promise<void> {
  if (engine.pushInFlight) {
    engine.pushAgain = true;
    return engine.pushInFlight;
  }
  const status = getSyncStatus();
  if (status.deviceRevoked || browserOffline()) return Promise.resolve();
  engine.pushInFlight = (async () => {
    patchSyncStatus({ pushing: true });
    try {
      const result = await tryWithLock(SYNC_PUSH_LOCK, () => pushNow(opts));
      if (result.acquired) await afterPush(result.value);
      // SYNC-11: another tab holds the push lock — try again shortly instead of waiting for the heartbeat
      else schedulePush(LOCK_RETRY_MS);
    } catch (error) {
      engine.pushFailures += 1;
      patchSyncStatus({ lastErrorCode: "INTERNAL_ERROR" });
      schedulePush(backoffDelayMs(engine.pushFailures));
      console.error(error);
    } finally {
      patchSyncStatus({ pushing: false });
      engine.pushInFlight = null;
      if (engine.pushAgain) {
        engine.pushAgain = false;
        schedulePush(0);
      }
      await refreshOutboxCounters();
      await refreshFiscalLadder();
    }
  })();
  return engine.pushInFlight;
}

async function afterPull(outcome: PullOutcome): Promise<void> {
  if (outcome.kind === "done") {
    engine.pullFailures = 0;
    const lastPullAt = ((await posDb().meta.get(META.lastPullAt))?.value as string | undefined) ?? null;
    const snapshotDone = ((await posDb().meta.get(META.snapshotDone))?.value as boolean | undefined) ?? false;
    patchSyncStatus({ lastPullAt, snapshotDone, authRequired: false, clockSkewMs: clockSkewMs() });
    if (outcome.scopes.includes("catalog")) runBackground(() => catalog.warmUp());
    return;
  }
  if (outcome.kind === "retry") {
    engine.pullFailures += 1;
    patchSyncStatus({ lastErrorCode: outcome.code });
    schedulePull(outcome.retryAfterMs ?? backoffDelayMs(engine.pullFailures));
    return;
  }
  handleStopped(outcome.code);
}

export function runPull(): Promise<void> {
  if (engine.pullInFlight) return engine.pullInFlight;
  if (getSyncStatus().deviceRevoked || browserOffline()) return Promise.resolve();
  engine.pullInFlight = (async () => {
    patchSyncStatus({ pulling: true });
    try {
      const result = await tryWithLock(SYNC_PULL_LOCK, () => pullNow());
      if (result.acquired) await afterPull(result.value);
    } catch (error) {
      engine.pullFailures += 1;
      patchSyncStatus({ lastErrorCode: "INTERNAL_ERROR" });
      schedulePull(backoffDelayMs(engine.pullFailures));
      console.error(error);
    } finally {
      patchSyncStatus({ pulling: false });
      engine.pullInFlight = null;
      await refreshFiscalLadder();
    }
  })();
  return engine.pullInFlight;
}

/** On demand / `online`: clears the auth pause and runs push then pull now. */
export async function syncNow(what: { push?: boolean; pull?: boolean } = {}): Promise<void> {
  engine.pushFailures = 0;
  engine.pullFailures = 0;
  if (getSyncStatus().authRequired) patchSyncStatus({ authRequired: false });
  const doPush = what.push ?? true;
  const doPull = what.pull ?? true;
  if (doPush) await runPush();
  if (doPull) await runPull();
}

function stopTimers(): void {
  for (const t of engine.timers) clearInterval(t);
  engine.timers = [];
  if (engine.pushTimer !== null) clearTimeout(engine.pushTimer);
  if (engine.pullTimer !== null) clearTimeout(engine.pullTimer);
  engine.pushTimer = null;
  engine.pullTimer = null;
}

export function startSyncEngine(): void {
  if (engine.running) return;
  engine.running = true;
  setPushTrigger(() => schedulePush(0));

  const cfg = rt();
  engine.timers.push(
    setInterval(() => runBackground(runPull), cfg.pullIntervalMs),
    setInterval(() => runBackground(() => runPush({ heartbeat: true })), cfg.heartbeatPushMs),
    setInterval(() => runBackground(refreshFiscalLadder), LADDER_REFRESH_MS),
    setInterval(() => runBackground(runRetention), RETENTION_MS),
  );

  if (typeof window !== "undefined" && typeof window.addEventListener === "function") {
    const onOnline = () => runBackground(syncNow);
    window.addEventListener("online", onOnline);
    engine.cleanups.push(() => window.removeEventListener("online", onOnline));
  }

  engine.cleanups.push(
    onSyncMessage((message) => {
      switch (message.type) {
        case "outbox-changed":
          outboxChanged();
          runBackground(refreshOutboxCounters);
          schedulePush(0); // SYNC-11: this tab may be the one able to push
          break;
        case "event-results":
          resolveEventResults(message.results);
          outboxChanged();
          runBackground(refreshOutboxCounters);
          runBackground(refreshFiscalLadder);
          break;
        case "pull-applied":
          if (message.scopes.includes("catalog")) invalidateMemoryIndex("catalog");
          if (message.scopes.includes("customers")) invalidateMemoryIndex("customers");
          pullApplied(message.scopes);
          runBackground(refreshFiscalLadder);
          break;
        case "device-revoked":
          onRevoked();
          break;
        case "wiped":
          stopSyncEngine();
          break;
      }
    }),
  );

  const unwatch = syncRequested.watch((what) => runBackground(() => syncNow(what ?? {})));
  engine.cleanups.push(() => unwatch.unsubscribe());

  runBackground(async () => {
    const revoked = (await posDb().meta.get(META.deviceRevoked))?.value === true;
    if (revoked) {
      onRevoked();
      return;
    }
    await refreshOutboxCounters();
    await refreshFiscalLadder();
    await syncNow();
  });
}

export function stopSyncEngine(): void {
  engine.running = false;
  stopTimers();
  for (const cleanup of engine.cleanups) cleanup();
  engine.cleanups = [];
  setPushTrigger(() => undefined);
}

/** Waits for the in-flight push/pull of this tab (tests, logout). */
export async function syncIdle(): Promise<void> {
  await Promise.all([engine.pushInFlight, engine.pullInFlight]);
}

/** When the next scheduled push fires (engine clock, ms) — null = none scheduled. For status/tests. */
export function nextPushAt(): number | null {
  return engine.pushTimer === null ? null : engine.pushTimerAt;
}
