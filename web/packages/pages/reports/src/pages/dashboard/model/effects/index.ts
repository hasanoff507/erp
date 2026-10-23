/**
 * BO-02 effects — generated clients only: `api.reports.getDashboard` (20 #17: KPIs per branch + total,
 * top products, receivables, stock, alerts) and `api.reports.getSales` (20 #18, the 7-day chart).
 */
import { createEffect } from "effector";

import { api, toApiError, type ApiError } from "@shared/api";

import type { Dashboard, DashboardRequest, SalesReport, WeekRequest } from "../types/index.ts";

function wrap<P, R>(fn: (params: P) => Promise<R>) {
  return createEffect<P, R, ApiError>(async (params) => {
    try {
      return await fn(params);
    } catch (e) {
      throw toApiError(e);
    }
  });
}

export const loadDashboardFx = wrap<DashboardRequest, Dashboard>(({ period, branchId }) =>
  api.reports.getDashboard({ period, ...(branchId ? { branch_id: branchId } : {}) }),
);

export const loadWeekFx = wrap<WeekRequest, SalesReport>(({ branchId, from, to }) =>
  api.reports.getSales({
    group_by: "day",
    date_from: from,
    date_to: to,
    ...(branchId ? { branch_id: branchId } : {}),
  }),
);
