/**
 * BO-21 ③b «Boshlang'ich qoldiq» — qo'lda kiritish (07 `openingStockMethod`, 19 §16, US-M04-04):
 * product (search) · qty (> 0, 3 dp) · unit_cost (≥ 0, 4 dp — tannarx) · expiry_date? lines →
 * `POST /stock-openings` (draft, default branch warehouse) → `POST /stock-openings/{id}/post`
 * (lots + balance, Dt 2910/2920 / Kt 0000). Permission `stock.opening.manage` (the owner has it).
 *
 * If posting fails after the draft was created (e.g. 422 `validation.go_live_date_missing`), the draft id
 * is kept: «Saqlash» again with unchanged lines only re-posts it (no duplicate drafts). If the lines were
 * edited meanwhile, the stale draft is cancelled first (`POST /stock-openings/{id}/cancel`,
 * failure ignored — it stays a harmless draft) and a new one is created.
 */
import { combine, createEffect, createEvent, createStore, sample } from "effector";

import { api, toApiError, type ApiError } from "@shared/api";
import { i18next } from "@shared/i18n";
import { toDecimal } from "@shared/lib/money";
import type { OpeningOut, ProductListItem, WarehouseOut } from "@shared/models";

export interface OpeningProduct {
  id: string;
  name: string;
  unitCode: string;
}

export interface OpeningLineDraft {
  key: string;
  product: OpeningProduct;
  /** Decimal string from DecimalInput ("" = not entered). */
  qty: string;
  /** Unit cost decimal string from PriceInput ("" = not entered). */
  unitCost: string;
  /** `YYYY-MM-DD` or "". */
  expiryDate: string;
}

export type LineProblem = "qty" | "unitCost";

export interface SubmitParams {
  warehouseId: string;
  docDate: string;
  lines: OpeningLineDraft[];
  /** A draft created by a previous attempt with the same lines — post it instead of creating a new one. */
  draftId: string | null;
  /** A kept draft whose lines no longer match — cancelled before the new draft is created. */
  staleDraftId: string | null;
}

export interface StaleDraftCancel {
  id: string;
  reason: string;
  /** The submit to run once the cancel settles (whatever its outcome). */
  next: SubmitParams;
}

export const SEARCH_LIMIT = 10;
export const MAX_LINES = 5000;

// --- lib ---------------------------------------------------------------------------------------------

function decimalOrNull(value: string) {
  if (value.trim() === "") return null;
  try {
    return toDecimal(value);
  } catch {
    return null;
  }
}

/** qty > 0, unit_cost ≥ 0 (19 §16); `null` when the line is valid. */
export function lineProblem(line: Pick<OpeningLineDraft, "qty" | "unitCost">): LineProblem | null {
  const qty = decimalOrNull(line.qty);
  if (!qty || !qty.isPositive() || qty.isZero()) return "qty";
  const cost = decimalOrNull(line.unitCost);
  if (!cost || cost.isNegative()) return "unitCost";
  return null;
}

/** API body line: qty `^\d+\.\d{3}$`, unit_cost `^\d+\.\d{4}$` (OpeningLineIn). */
export function toLineIn(line: OpeningLineDraft) {
  return {
    product_id: line.product.id,
    qty: toDecimal(line.qty).toFixed(3),
    unit_cost: toDecimal(line.unitCost).toFixed(4),
    ...(line.expiryDate ? { expiry_date: line.expiryDate } : {}),
  };
}

/** Stable fingerprint of what would be sent (decides whether a kept draft may be re-posted). */
export function linesKey(lines: readonly OpeningLineDraft[]): string {
  return JSON.stringify(lines.map((l) => [l.product.id, l.qty, l.unitCost, l.expiryDate]));
}

/** The default branch's sales-floor warehouse first (`store`), else the first one. */
export function pickWarehouse(items: readonly WarehouseOut[]): WarehouseOut | null {
  return items.find((w) => w.type === "store") ?? items[0] ?? null;
}

export function toOpeningProduct(p: Pick<ProductListItem, "id" | "name" | "unit_code">): OpeningProduct {
  return { id: p.id, name: p.name, unitCode: p.unit_code };
}

// --- events ------------------------------------------------------------------------------------------

/** The manual form was opened — loads the warehouse. */
export const formOpened = createEvent<{ today: string }>();
export const searchChanged = createEvent<string>();
export const productPicked = createEvent<OpeningProduct>();
export const lineChanged = createEvent<{ key: string; patch: Partial<Omit<OpeningLineDraft, "key">> }>();
export const lineRemoved = createEvent<string>();
export const submitted = createEvent();
/** «Yana kiritish» after a posted document. */
export const formReset = createEvent();

// --- effects -----------------------------------------------------------------------------------------

function wrap<P, R>(fn: (params: P) => Promise<R>) {
  return createEffect<P, R, ApiError>(async (params) => {
    try {
      return await fn(params);
    } catch (e) {
      throw toApiError(e);
    }
  });
}

export const searchProductsFx = wrap<string, ProductListItem[]>(async (search) => {
  const page = await api.pricing.listProducts({ search, archived: false, page: 1, size: SEARCH_LIMIT });
  return page.items;
});

export const loadWarehouseFx = wrap<void, WarehouseOut | null>(async () => {
  const { items } = await api.branches.warehousesList();
  return pickWarehouse(items);
});

/** Creates the draft (unless a kept one is re-posted) and posts it. A failed post keeps the draft id. */
export const createDraftFx = wrap<SubmitParams, OpeningOut>(({ warehouseId, docDate, lines }) =>
  api.inventory.createStockOpening({
    warehouse_id: warehouseId,
    doc_date: docDate,
    lines: lines.map(toLineIn),
  }),
);
export const postDraftFx = wrap<string, OpeningOut>((id) => api.inventory.postStockOpening(id, {}));
/** Cancels a kept draft whose lines were edited; the caller ignores a failure (the draft is never posted). */
export const cancelStaleDraftFx = wrap<StaleDraftCancel, OpeningOut>(({ id, reason }) =>
  api.inventory.cancelStockOpening(id, { reason }),
);

// --- stores ------------------------------------------------------------------------------------------

let nextKey = 0;

export const $today = createStore("1970-01-01");
export const $search = createStore("");
export const $results = createStore<ProductListItem[]>([]);
export const $lines = createStore<OpeningLineDraft[]>([]);
export const $warehouse = createStore<WarehouseOut | null>(null, { skipVoid: false });
export const $warehouseError = createStore<ApiError | null>(null, { skipVoid: false });
export const $draft = createStore<{ id: string; key: string } | null>(null, { skipVoid: false });
export const $submitError = createStore<ApiError | null>(null, { skipVoid: false });
export const $posted = createStore<OpeningOut | null>(null, { skipVoid: false });
export const $submitting = combine(
  createDraftFx.pending,
  postDraftFx.pending,
  cancelStaleDraftFx.pending,
  (a, b, c) => a || b || c,
);

export const $problems = $lines.map((lines) =>
  Object.fromEntries(lines.map((l) => [l.key, lineProblem(l)] as const)),
);
export const $canSubmit = combine(
  $lines,
  $warehouse,
  $submitting,
  (lines, warehouse, submitting) =>
    !submitting &&
    warehouse !== null &&
    lines.length > 0 &&
    lines.length <= MAX_LINES &&
    lines.every((l) => lineProblem(l) === null),
);

// --- connections ---------------------------------------------------------------------------------

$today.on(formOpened, (_, { today }) => today);
sample({
  clock: formOpened,
  source: $warehouse,
  filter: (warehouse) => warehouse === null,
  fn: () => undefined,
  target: loadWarehouseFx,
});
$warehouse.on(loadWarehouseFx.doneData, (_, w) => w);
$warehouseError.on(loadWarehouseFx.failData, (_, e) => e).reset(loadWarehouseFx);

$search.on(searchChanged, (_, s) => s);
sample({
  clock: searchChanged,
  filter: (s) => s.trim().length >= 2,
  fn: (s) => s.trim(),
  target: searchProductsFx,
});
// Only the answer for the current query is shown.
sample({
  clock: searchProductsFx.done,
  source: $search,
  filter: (search, { params }) => search.trim() === params,
  fn: (_, { result }) => result,
  target: $results,
});
sample({ clock: searchChanged, filter: (s) => s.trim().length < 2, fn: () => [], target: $results });

$lines
  .on(productPicked, (lines, product) => [
    ...lines,
    { key: `l${(nextKey += 1)}`, product, qty: "", unitCost: "", expiryDate: "" },
  ])
  .on(lineChanged, (lines, { key, patch }) => lines.map((l) => (l.key === key ? { ...l, ...patch } : l)))
  .on(lineRemoved, (lines, key) => lines.filter((l) => l.key !== key))
  .reset(formReset);
$search.reset(productPicked, formReset);
$results.reset(productPicked, formReset);

// Submit: re-post a kept draft when the lines did not change, otherwise create a new one.
const submitAccepted = sample({
  clock: submitted,
  source: { lines: $lines, warehouse: $warehouse, today: $today, draft: $draft, ok: $canSubmit },
  filter: ({ ok }) => ok,
  fn: ({ lines, warehouse, today, draft }): SubmitParams => {
    const same = draft !== null && draft.key === linesKey(lines);
    return {
      warehouseId: warehouse?.id ?? "",
      docDate: today,
      lines,
      draftId: same ? draft.id : null,
      staleDraftId: draft !== null && !same ? draft.id : null,
    };
  },
});
sample({
  clock: submitAccepted,
  filter: (p) => p.draftId === null && p.staleDraftId === null,
  target: createDraftFx,
});
// Edited lines after a failed post: cancel the stale draft first, then create the new one whatever the outcome.
sample({
  clock: submitAccepted,
  filter: (p) => p.draftId === null && p.staleDraftId !== null,
  fn: (p): StaleDraftCancel => ({
    id: p.staleDraftId ?? "",
    reason: i18next.t("onboarding:openingStock.manual.replacedDraft"),
    next: { ...p, staleDraftId: null },
  }),
  target: cancelStaleDraftFx,
});
$draft.reset(cancelStaleDraftFx);
sample({ clock: cancelStaleDraftFx.finally, fn: ({ params }) => params.next, target: createDraftFx });
sample({
  clock: submitAccepted,
  filter: (p) => p.draftId !== null,
  fn: (p) => p.draftId ?? "",
  target: postDraftFx,
});
sample({
  clock: createDraftFx.done,
  fn: ({ params, result }) => ({ id: result.id, key: linesKey(params.lines) }),
  target: $draft,
});
sample({ clock: createDraftFx.doneData, fn: (doc) => doc.id, target: postDraftFx });

$posted.on(postDraftFx.doneData, (_, doc) => doc).reset(formReset);
$draft.reset(postDraftFx.done, formReset);
$lines.reset(postDraftFx.done);
$submitError
  .on([createDraftFx.failData, postDraftFx.failData], (_, e) => e)
  .reset(submitted, formReset, lineChanged, productPicked, lineRemoved);
