/** BO-07 effects — generated `api.tax.getVatSummary` / `api.tax.listVatMoves` (20 #1, #2; `tax.vat.view`). */
import { createEffect } from "effector";

import { api, toApiError, type ApiError } from "@shared/api";

import { toMovesParams } from "../lib/index.ts";
import type { MovesRequest, VatMovePage, VatSummary } from "../types/index.ts";

function wrap<P, R>(fn: (params: P) => Promise<R>) {
  return createEffect<P, R, ApiError>(async (params) => {
    try {
      return await fn(params);
    } catch (e) {
      throw toApiError(e);
    }
  });
}

/** One `GET /reports/vat-summary?period=` per month of the period (a quarter = 3 calls). */
export const loadSummaryFx = wrap<{ period: string; months: readonly string[] }, VatSummary[]>(({ months }) =>
  Promise.all(months.map((period) => api.tax.getVatSummary({ period }))),
);

export const listMovesFx = wrap<MovesRequest, VatMovePage>((req) => api.tax.listVatMoves(toMovesParams(req)));
