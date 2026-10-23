import { combine, createStore } from "effector";

import type { ApiError } from "@shared/api";
import type { AgingRow, AgingSummary } from "@shared/models";
import { $activeBranchId, ALL_BRANCHES } from "@shared/state/session";

import type { DebtorTab, Direction } from "#/entities/debtor/index.ts";

import type { LoadStatus } from "../types/index.ts";

export const $mounted = createStore(false);
export const $today = createStore("1970-01-01");
export const $direction = createStore<Direction>("receivable");
export const $tab = createStore<DebtorTab>("all");
export const $search = createStore("");
export const $page = createStore(1);
export const $rows = createStore<AgingRow[]>([]);
export const $summary = createStore<AgingSummary | null>(null, { skipVoid: false });
export const $asOf = createStore<string | null>(null, { skipVoid: false });
export const $status = createStore<LoadStatus>("idle");
export const $error = createStore<ApiError | null>(null, { skipVoid: false });
export const $selectedId = createStore<string | null>(null, { skipVoid: false });
/** `?counterparty=` waiting for the first loaded list (then cleared). */
export const $pendingCounterparty = createStore<string | null>(null, { skipVoid: false });
/** Bumped after every (re)load — side blocks that read their own data follow it. */
export const $version = createStore(0);

/** The topbar branch (`null` = «Barcha filiallar» → the whole tenant). */
export const $branchId = combine($activeBranchId, (id) => (id && id !== ALL_BRANCHES ? id : null));
