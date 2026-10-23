/**
 * WEB-12 (Bosqich 4) — `Ctrl+K` command palette (06 §1.9, 08 §9): screens (filtered by permission, given
 * by the layout), products (`GET /api/v1/products?search=`, `stock.view`) and counterparties
 * (`GET /api/v1/counterparties?search=`). The search runs 250 ms after typing stops, from 2 characters;
 * an answer for an older query is dropped.
 */
import { createEffect, createEvent, createStore, sample } from "effector";
import { debounce } from "patronum";

import { api, toApiError, type ApiError } from "@shared/api";
import type { CounterpartyOut, ProductOut } from "@shared/models";

export const SEARCH_DEBOUNCE_MS = 250;
export const MIN_QUERY = 2;
export const RESULT_LIMIT = 8;

export interface PaletteRights {
  products: boolean;
  counterparties: boolean;
}

export interface SearchRequest extends PaletteRights {
  query: string;
}

export interface SearchResult {
  products: ProductOut[];
  counterparties: CounterpartyOut[];
}

export const paletteOpened = createEvent<PaletteRights>();
export const paletteClosed = createEvent();
export const queryChanged = createEvent<string>();

export const searchFx = createEffect<SearchRequest, SearchResult, ApiError>(async (req) => {
  try {
    const [products, counterparties] = await Promise.all([
      req.products
        ? api.pricing.listProducts({ search: req.query, size: RESULT_LIMIT }).then((p) => p.items)
        : Promise.resolve([]),
      req.counterparties
        ? api.debts.listCounterparties({ search: req.query, size: RESULT_LIMIT }).then((p) => p.items)
        : Promise.resolve([]),
    ]);
    return { products, counterparties };
  } catch (e) {
    throw toApiError(e);
  }
});

export const $open = createStore(false)
  .on(paletteOpened, () => true)
  .on(paletteClosed, () => false);
export const $rights = createStore<PaletteRights>({ products: false, counterparties: false }).on(
  paletteOpened,
  (_, rights) => rights,
);
export const $query = createStore("")
  .on(queryChanged, (_, q) => q)
  .reset(paletteClosed);
export const $results = createStore<SearchResult>({ products: [], counterparties: [] }).reset(paletteClosed);
export const $searchError = createStore<ApiError | null>(null, { skipVoid: false });

/** The query worth sending to the server (trimmed, ≥ 2 characters). */
export function searchable(query: string): string | null {
  const q = query.trim();
  return q.length >= MIN_QUERY ? q.slice(0, 64) : null;
}

const settled = debounce({ source: queryChanged, timeout: SEARCH_DEBOUNCE_MS });
sample({
  clock: settled,
  source: { rights: $rights, open: $open },
  filter: ({ rights, open }, q) =>
    open && searchable(q) !== null && (rights.products || rights.counterparties),
  fn: ({ rights }, q): SearchRequest => ({ ...rights, query: searchable(q) ?? "" }),
  target: searchFx,
});
// A shorter query clears the server results at once.
sample({
  clock: queryChanged,
  filter: (q) => searchable(q) === null,
  fn: (): SearchResult => ({ products: [], counterparties: [] }),
  target: $results,
});
sample({
  clock: searchFx.done,
  source: $query,
  filter: (current, { params }) => searchable(current) === params.query,
  fn: (_, { result }) => result,
  target: $results,
});
$searchError.on(searchFx.failData, (_, e) => e).reset(searchFx, paletteClosed);
export const $searching = searchFx.pending;

/** Screens whose label contains every word of the query (case-insensitive); all for an empty query. */
export function filterScreens<T extends { label: string; keywords?: string }>(
  screens: readonly T[],
  query: string,
): T[] {
  const words = query.trim().toLowerCase().split(/\s+/).filter(Boolean);
  if (words.length === 0) return [...screens];
  return screens.filter((s) => {
    const text = `${s.label} ${s.keywords ?? ""}`.toLowerCase();
    return words.every((w) => text.includes(w));
  });
}

/** Product card route (19 §1, BO-05 sheet) and the counterparty in BO-06. */
export const productHref = (id: string) => `/app/catalog/products/${id}`;
export const counterpartyHref = (id: string) => `/app/debts?counterparty=${encodeURIComponent(id)}`;
