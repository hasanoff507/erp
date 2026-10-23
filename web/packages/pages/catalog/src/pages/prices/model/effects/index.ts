/**
 * BO-05 effects (19 §1, §4) — generated `api.pricing.*`.
 * Saving is two calls (07 BO-05 «SAQLASH»): `POST /price-changes` (draft) → `POST /price-changes/{id}/post`
 * → `posted` (200) or `pending_approval` (202, APPROVAL_REQUIRED → BO-16).
 */
import { createEffect } from "effector";

import { api, toApiError, type ApiError } from "@shared/api";
import type { PriceHistory, ProductPage } from "@shared/models";

import { toPrice4 } from "#/entities/product/index.ts";

import { productPriceOf } from "../lib/index.ts";
import {
  ALL_BRANCHES_SCOPE,
  HISTORY_PAGE_SIZE,
  PRICES_PAGE_SIZE,
  type PriceChangeOut,
  type PriceFilters,
  type PriceScope,
  type ProductOut,
  type ProductPrice,
  type SavePricesParams,
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

export const listProductsFx = wrap<{ filters: PriceFilters; page: number }, ProductPage>(
  ({ filters, page }) =>
    api.pricing.listProducts({
      search: filters.search || undefined,
      category_id: filters.categoryId ?? undefined,
      archived: false,
      page,
      size: PRICES_PAGE_SIZE,
    }),
);

/** Current/scheduled price of each listed product (no bulk endpoint in 19 §4 — one history call per row). */
export const loadPricesFx = wrap<{ productIds: string[]; scope: PriceScope }, Record<string, ProductPrice>>(
  async ({ productIds, scope }) => {
    const branchId = scope === ALL_BRANCHES_SCOPE ? null : scope;
    const entries = await Promise.all(
      productIds.map(async (id) => {
        const [global, branch] = await Promise.all([
          api.pricing.listProductPrices(id, { limit: 10 }),
          branchId
            ? api.pricing.listProductPrices(id, { branch_id: branchId, limit: 10 })
            : Promise.resolve(null),
        ]);
        return [id, productPriceOf(global.items, branch?.items ?? null)] as const;
      }),
    );
    return Object.fromEntries(entries);
  },
);

export const loadHistoryFx = wrap<
  { productId: string; scope: PriceScope; cursor: string | null },
  PriceHistory
>(({ productId, scope, cursor }) =>
  api.pricing.listProductPrices(productId, {
    branch_id: scope === ALL_BRANCHES_SCOPE ? undefined : scope,
    cursor: cursor ?? undefined,
    limit: HISTORY_PAGE_SIZE,
  }),
);

export const savePricesFx = wrap<SavePricesParams, PriceChangeOut>(
  async ({ docDate, validFrom, branchId, lines }) => {
    const draft = await api.pricing.createPriceChange({
      doc_date: docDate,
      lines: lines.map((l) => ({
        product_id: l.productId,
        new_price: toPrice4(l.newPrice),
        valid_from: validFrom,
        branch_id: branchId,
      })),
    });
    return api.pricing.postPriceChange(draft.id, {});
  },
);

/** `nameRu` (qaror #29) — `PATCH /products/{id}` with `version`, permission `catalog.manage`. */
export const saveNameRuFx = wrap<{ product: ProductOut; nameRu: string }, ProductOut>(({ product, nameRu }) =>
  api.pricing.updateProduct(product.id, {
    version: product.version,
    name_ru: nameRu.trim() === "" ? null : nameRu.trim(),
  }),
);
