import { createStore } from "effector";

import type { ApiError } from "@shared/api";

import type { LoadStatus, Transfer, TransferStatus } from "../types/index.ts";

export const $filter = createStore<TransferStatus | null>(null, { skipVoid: false });
export const $transfers = createStore<Transfer[]>([]);
export const $cursor = createStore<string | null>(null, { skipVoid: false });
export const $status = createStore<LoadStatus>("idle");
export const $error = createStore<ApiError | null>(null, { skipVoid: false });
export const $loaded = createStore(false);

export const $selectedId = createStore<string | null>(null, { skipVoid: false });
/** A transfer opened from outside the list (`transferShown`), kept up to date by the actions. */
export const $pinned = createStore<Transfer | null>(null, { skipVoid: false });
/** Last refused action (409 ETTN_REQUIRED / DOC_INVALID_STATE, 422 NEGATIVE_STOCK_NOT_ALLOWED…). */
export const $actionError = createStore<ApiError | null>(null, { skipVoid: false });
/** Cancelled with `warnings:["ETTN_CANCEL_IN_OPERATOR"]` — cancel the e-TTN in the operator cabinet. */
export const $notice = createStore<"ettn_cancel_in_operator" | null>(null, { skipVoid: false });
/** product_id → balance in the source warehouse (create sheet). */
export const $available = createStore<Record<string, string>>({});
