import { createStore } from "effector";

import type { ApiError } from "@shared/api";

import type { Dashboard, DashboardPeriod, LoadStatus, SalesReport } from "../types/index.ts";

export const $mounted = createStore(false);
export const $today = createStore("1970-01-01");
/** Default "Bugun" (07 BO-02). */
export const $period = createStore<DashboardPeriod>("today");

export const $dashboard = createStore<Dashboard | null>(null, { skipVoid: false });
export const $status = createStore<LoadStatus>("idle");
export const $error = createStore<ApiError | null>(null, { skipVoid: false });
/** When the figures were last read (07 offline: «Oxirgi yangilanish: N daqiqa oldin»). */
export const $loadedAt = createStore<string | null>(null, { skipVoid: false });

/** «Savdo — oxirgi 7 kun» (`GET /reports/sales?group_by=day`). */
export const $week = createStore<SalesReport | null>(null, { skipVoid: false });
export const $weekError = createStore<ApiError | null>(null, { skipVoid: false });
