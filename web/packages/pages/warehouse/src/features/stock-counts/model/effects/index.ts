/** Inventarizatsiya effects — generated `api.stockCounts.*` (19 §14). */
import { api } from "@shared/api";

import { createProductSearch } from "#/entities/product/index.tsx";
import { apiFx } from "#/shared/lib/effect.ts";

import { toQuery } from "../lib/index.ts";
import type {
  CancelParams,
  Count,
  CountCreate,
  CountPage,
  CountPostOut,
  ListRequest,
  PostCountParams,
  RecordLinesParams,
} from "../types/index.ts";

export const listCountsFx = apiFx<ListRequest, CountPage>((req) =>
  api.stockCounts.listStockCounts(toQuery(req)),
);
export const getCountFx = apiFx<string, Count>((id) => api.stockCounts.getStockCount(id));
/** «Inventarizatsiya» (07 BO-03): `{warehouse_id, doc_date, responsible_user_id?}` — whole warehouse. */
export const createCountFx = apiFx<CountCreate, Count>((body) => api.stockCounts.createStockCount(body));
export const recordLinesFx = apiFx<RecordLinesParams, Count>(({ id, lines }) =>
  api.stockCounts.recordStockCountLines(id, { lines }),
);
/** «Sanashni yakunlash» — `counting → review`. */
export const submitCountFx = apiFx<string, Count>((id) => api.stockCounts.submitStockCount(id, {}));
/** «Farqni tasdiqlash» (`stock.count.post`). */
export const postCountFx = apiFx<PostCountParams, CountPostOut>(({ id, treatUncountedAsZero }) =>
  api.stockCounts.postStockCount(
    id,
    {},
    treatUncountedAsZero ? { treat_uncounted_as_zero: true } : undefined,
  ),
);
export const cancelCountFx = apiFx<CancelParams, Count>(({ id, reason }) =>
  api.stockCounts.cancelStockCount(id, { reason }),
);

/** Product search for an unexpected product found during the count. */
export const countProductSearch = createProductSearch();
