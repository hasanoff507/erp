/**
 * Effector units published by @shared/offline (contract 7). @shared/state/sync builds `$syncState`
 * from `syncStatusChanged`; screens re-query on `pullApplied` / `outboxChanged`.
 */
import { createEvent } from "effector";

import type { PullScope } from "./types.ts";

export interface SyncStatus {
  pending: number;
  rejected: number;
  rejectedRetryable: number;
  oldestPendingAt: string | null;
  lastPushAt: string | null;
  lastPullAt: string | null;
  pushing: boolean;
  pulling: boolean;
  /** Last request-level error (catalog code, `NETWORK_ERROR`), cleared by the next success. */
  lastErrorCode: string | null;
  authRequired: boolean;
  deviceRevoked: boolean;
  subscriptionRestricted: boolean;
  snapshotDone: boolean;
  /** Device clock − server clock at the last contact (16 §8; warn when |skew| > 5 min). */
  clockSkewMs: number | null;
}

export const INITIAL_SYNC_STATUS: SyncStatus = {
  pending: 0,
  rejected: 0,
  rejectedRetryable: 0,
  oldestPendingAt: null,
  lastPushAt: null,
  lastPullAt: null,
  pushing: false,
  pulling: false,
  lastErrorCode: null,
  authRequired: false,
  deviceRevoked: false,
  subscriptionRestricted: false,
  snapshotDone: false,
  clockSkewMs: null,
};

export type QuotaLevel = "ok" | "warn80" | "critical95" | "unknown";

export interface QuotaState {
  usage: number | null;
  quota: number | null;
  ratio: number | null;
  level: QuotaLevel;
}

export const syncStatusChanged = createEvent<SyncStatus>();
/** On-demand sync (button, shift open, page mount — 16 §1). Empty payload = push + pull. */
export const syncRequested = createEvent<{ push?: boolean; pull?: boolean } | void>();
export const outboxChanged = createEvent();
export const pullApplied = createEvent<PullScope[]>();
export const deviceRevoked = createEvent();
/** 401 after the silent session probe failed — the POS shows the password re-login (16 §3.4). */
export const authRequired = createEvent();
export const subscriptionRestricted = createEvent();
export const quotaWarning = createEvent<QuotaState>();
