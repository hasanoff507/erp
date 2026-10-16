/**
 * Catalog reference data shared by the catalog screens: units (19 §3, `GET /units`, global list)
 * and product categories (19 §2, `GET /product-categories`, page pagination — all pages loaded,
 * the list is small). `referenceRequested` reloads both; `categoriesChanged` reloads categories.
 */
import { createEffect, createEvent, createStore, sample } from "effector";

import { api, toApiError, type ApiError } from "@shared/api";
import type { CategoryOut, UnitOut } from "@shared/models";

export const referenceRequested = createEvent();
export const categoriesChanged = createEvent();

const CATEGORY_PAGE = 200;
const MAX_CATEGORY_PAGES = 25;

export const loadUnitsFx = createEffect<void, UnitOut[], ApiError>(async () => {
  try {
    return (await api.pricing.listUnits()).items;
  } catch (e) {
    throw toApiError(e);
  }
});

export const loadCategoriesFx = createEffect<void, CategoryOut[], ApiError>(async () => {
  try {
    const all: CategoryOut[] = [];
    for (let page = 1; page <= MAX_CATEGORY_PAGES; page += 1) {
      const res = await api.pricing.listProductCategories({ page, size: CATEGORY_PAGE });
      all.push(...res.items);
      if (all.length >= res.total || res.items.length === 0) break;
    }
    return all;
  } catch (e) {
    throw toApiError(e);
  }
});

export const $units = createStore<UnitOut[]>([]).on(loadUnitsFx.doneData, (_, units) => units);
/** Active (not archived) categories, by name. */
export const $categories = createStore<CategoryOut[]>([]).on(loadCategoriesFx.doneData, (_, list) =>
  list.filter((c) => c.archived_at === null).sort((a, b) => a.name.localeCompare(b.name)),
);
export const $categoryNames = $categories.map((list) => new Map(list.map((c) => [c.id, c.name])));
export const $referenceError = createStore<ApiError | null>(null, { skipVoid: false })
  .on([loadUnitsFx.failData, loadCategoriesFx.failData], (_, error) => error)
  .reset(referenceRequested);

sample({ clock: referenceRequested, target: [loadUnitsFx, loadCategoriesFx] });
sample({ clock: categoriesChanged, target: loadCategoriesFx });
