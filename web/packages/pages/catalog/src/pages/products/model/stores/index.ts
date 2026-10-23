import { createStore } from "effector";

import type { ApiError } from "@shared/api";
import type { MxikItem } from "@shared/models";

import type { ListStatus, ProductFilters, ProductListItem, ProductOut } from "../types/index.ts";

export const $filters = createStore<ProductFilters>({ search: "", categoryId: null, archived: false });
export const $page = createStore(1);
/** Current page; each item carries `current_price` (19 §1 — branch → global, null = no price). */
export const $products = createStore<ProductListItem[]>([]);
export const $total = createStore(0);
export const $listStatus = createStore<ListStatus>("idle");
export const $listError = createStore<ApiError | null>(null, { skipVoid: false });

/** Product open in the editor Sheet (loaded by id), null for "new" or closed. */
export const $editing = createStore<ProductOut | null>(null, { skipVoid: false });
export const $editingError = createStore<ApiError | null>(null, { skipVoid: false });

export const $mxikQuery = createStore("");
export const $mxikResults = createStore<MxikItem[]>([]);
export const $mxikError = createStore<ApiError | null>(null, { skipVoid: false });
