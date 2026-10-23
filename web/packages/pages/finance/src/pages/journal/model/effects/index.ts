/**
 * BO-08 effects — generated `api.accounting.listLedgerEntries` (20 #9), `api.inventory.*RecostJob*`
 * (19 §18); names of products (`GET /products/{id}`) and warehouses (`GET /warehouses`) for the queue.
 */
import { createEffect } from "effector";

import { api, toApiError, type ApiError } from "@shared/api";

import { toQuery } from "../lib/index.ts";
import {
  RECOST_PAGE_SIZE,
  type EntriesRequest,
  type LedgerEntryPage,
  type RecostJob,
  type RecostJobPage,
  type RecostRequest,
} from "../types/index.ts";

function wrap<P, R>(fn: (params: P) => Promise<R>) {
  return createEffect<P, R, ApiError>(async (params) => {
    try {
      return await fn(params);
    } catch (e) {
      throw toApiError(e);
    }
  });
}

export const listEntriesFx = wrap<EntriesRequest, LedgerEntryPage>(({ filters, cursor }) =>
  api.accounting.listLedgerEntries(toQuery(filters, cursor)),
);

export const listRecostFx = wrap<RecostRequest, RecostJobPage>(({ status, cursor }) =>
  api.inventory.listRecostJobs({
    ...(status ? { status } : {}),
    ...(cursor ? { cursor } : {}),
    limit: RECOST_PAGE_SIZE,
  }),
);

/** `POST /recost-jobs/{id}/retry` (`accounting.post`, Idempotency-Key from the client) → the job, queued. */
export const retryRecostFx = wrap<string, RecostJob>((id) => api.inventory.retryRecostJob(id, {}));

/** Names of the given products; an unreadable product (deleted, no access) is simply left out. */
export const loadProductNamesFx = wrap<string[], Record<string, string>>(async (ids) => {
  const results = await Promise.allSettled(ids.map((id) => api.pricing.getProduct(id)));
  const names: Record<string, string> = {};
  for (const r of results) {
    if (r.status === "fulfilled") names[r.value.id] = r.value.name;
  }
  return names;
});

export const loadWarehousesFx = wrap<void, Record<string, string>>(async () => {
  const { items } = await api.branches.warehousesList();
  return Object.fromEntries(items.map((w) => [w.id, w.name]));
});
