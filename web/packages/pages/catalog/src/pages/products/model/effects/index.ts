/**
 * Catalog API effects (19 §1–§2) — generated `api.pricing.*` only; failures are ApiError.
 * Writes carry Idempotency-Key automatically (the axios instance); buttons are disabled while
 * pending, so a double click never sends twice.
 */
import { createEffect } from "effector";

import { api, toApiError, type ApiError } from "@shared/api";
import type {
  BarcodeCreate,
  BarcodeOut,
  CategoryCreate,
  CategoryOut,
  CategoryUpdate,
  InternalBarcodeOut,
  MxikItem,
  MxikLookupOut,
  ProductPage,
} from "@shared/models";

import { listParams } from "../lib/index.ts";
import type { ProductCreate, ProductFilters, ProductOut, UpdateProductParams } from "../types/index.ts";

function wrap<P, R>(fn: (params: P) => Promise<R>) {
  return createEffect<P, R, ApiError>(async (params) => {
    try {
      return await fn(params);
    } catch (e) {
      throw toApiError(e);
    }
  });
}

export const listProductsFx = wrap<{ filters: ProductFilters; page: number }, ProductPage>(
  ({ filters, page }) => api.pricing.listProducts(listParams(filters, page)),
);

export const getProductFx = wrap<string, ProductOut>((id) => api.pricing.getProduct(id));
export const createProductFx = wrap<ProductCreate, ProductOut>((body) => api.pricing.createProduct(body));
export const updateProductFx = wrap<UpdateProductParams, ProductOut>(({ id, body }) =>
  api.pricing.updateProduct(id, body),
);
export const archiveProductFx = wrap<string, ProductOut>((id) => api.pricing.archiveProduct(id, {}));
export const unarchiveProductFx = wrap<string, ProductOut>((id) => api.pricing.unarchiveProduct(id, {}));

export const addBarcodeFx = wrap<{ productId: string; body: BarcodeCreate }, BarcodeOut>(
  ({ productId, body }) => api.pricing.createProductBarcode(productId, body),
);
export const deleteBarcodeFx = wrap<{ productId: string; barcodeId: string }, void>(
  ({ productId, barcodeId }) => api.pricing.deleteProductBarcode(productId, barcodeId),
);
/** US-M09-05: EAN-13 `04…` from internal_barcode_seq (19 §1). */
export const generateInternalBarcodeFx = wrap<string, InternalBarcodeOut>((productId) =>
  api.pricing.generateInternalBarcode(productId, {}),
);

/** `GET /mxik-codes?query=` — tasnif.soliq.uz behind a cache; may take ~15 s during an outage. */
export const searchMxikFx = wrap<string, MxikItem[]>(
  async (query) => (await api.pricing.searchMxikCodes({ query, limit: 20 })).items,
);
/** `GET /mxik-codes/{code}` — verify a typed code (404 → not found; stale_cache → could not verify). */
export const lookupMxikFx = wrap<string, MxikLookupOut>((code) => api.pricing.getMxikCode(code));

export const createCategoryFx = wrap<CategoryCreate, CategoryOut>((body) =>
  api.pricing.createProductCategory(body),
);
export const updateCategoryFx = wrap<{ id: string; body: CategoryUpdate }, CategoryOut>(({ id, body }) =>
  api.pricing.updateProductCategory(id, body),
);
export const archiveCategoryFx = wrap<string, CategoryOut>((id) =>
  api.pricing.archiveProductCategory(id, {}),
);
