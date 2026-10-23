import { createStore } from "effector";

import type { ApiError } from "@shared/api";

import type { ApprovalKind, ApprovalRequest, LoadStatus, QueueTab } from "../types/index.ts";

export const $today = createStore("1970-01-01");
/** Epoch ms of the last clock tick (time left until `expires_at`). */
export const $now = createStore(0);
export const $mounted = createStore(false);

export const $tab = createStore<QueueTab>("pending");
export const $kind = createStore<ApprovalKind | null>(null, { skipVoid: false });
export const $requests = createStore<ApprovalRequest[]>([]);
export const $cursor = createStore<string | null>(null, { skipVoid: false });
export const $status = createStore<LoadStatus>("idle");
export const $error = createStore<ApiError | null>(null, { skipVoid: false });
export const $loaded = createStore(false);

/**
 * Ids of the pending queue as last loaded on the «Kutilmoqda» tab — kept across tabs so the tab label
 * shows «Kutilmoqda (N)» everywhere (07 BO-16, UX-14); a local decision removes the id at once.
 */
export const $pendingIds = createStore<readonly string[] | null>(null, { skipVoid: false });
/** «Bugun hal qilinganlar» (approved / rejected today, newest first). */
export const $resolvedToday = createStore<ApprovalRequest[]>([]);

/** Requests with a decision in flight. */
export const $busy = createStore<readonly string[]>([]);
/** Last failed «Tasdiqlash» per request (PIN_INVALID, ACCOUNT_LOCKED, APPROVAL_INVALID…). */
export const $approveErrors = createStore<Readonly<Record<string, ApiError>>>({});
/** Last failed «Rad etish» per request. */
export const $rejectErrors = createStore<Readonly<Record<string, ApiError>>>({});
