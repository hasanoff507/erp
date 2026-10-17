import { combine, sample } from "effector";

import { isPositiveAmount, referenceRequested } from "#/entities/product/index.ts";

import { listProductsFx, loadHistoryFx, loadPricesFx, saveNameRuFx, savePricesFx } from "../effects/index.ts";
import {
  categoryChanged,
  draftChanged,
  draftsReset,
  effectiveFromChanged,
  historyMoreRequested,
  listRefreshRequested,
  pageChanged,
  pageMounted,
  productSelected,
  resultDismissed,
  saveRequested,
  scopeChanged,
  searchChanged,
} from "../events/index.ts";
import { applyDraft, collectChanges, todayIso, validFromOf } from "../lib/index.ts";
import {
  $drafts,
  $effectiveFrom,
  $filters,
  $history,
  $historyCursor,
  $historyError,
  $listError,
  $listStatus,
  $page,
  $prices,
  $products,
  $saveError,
  $saveResult,
  $scope,
  $selectedId,
  $total,
} from "../stores/index.ts";
import { ALL_BRANCHES_SCOPE } from "../types/index.ts";

/**
 * Edited rows that differ from the current price (07 BO-05 «N ta o'zgarish») — every draft, not only the
 * visible page: paging, search and category filters keep the drafts (one document per save).
 */
export const $changes = combine($prices, $drafts, collectChanges);
export const $selectedProduct = combine(
  $products,
  $selectedId,
  (list, id) => list.find((p) => p.id === id) ?? null,
);

// --- list ----------------------------------------------------------------------------------------
$filters
  .on(searchChanged, (f, search) => ({ ...f, search }))
  .on(categoryChanged, (f, categoryId) => ({ ...f, categoryId }));
$page.on(pageChanged, (_, page) => page).reset(searchChanged, categoryChanged);

sample({ clock: pageMounted, target: referenceRequested });
$effectiveFrom.on(pageMounted, () => todayIso()).on(effectiveFromChanged, (_, d) => d);

sample({
  clock: [pageMounted, searchChanged, categoryChanged, pageChanged, listRefreshRequested],
  source: { filters: $filters, page: $page },
  target: listProductsFx,
});
$products
  .on(listProductsFx.doneData, (_, res) => res.items)
  // PATCH answers ProductOut (no current_price / current_cost / markup_pct): merge into the list row.
  .on(saveNameRuFx.doneData, (list, updated) =>
    list.map((p) => (p.id === updated.id ? { ...p, ...updated } : p)),
  );
$total.on(listProductsFx.doneData, (_, res) => res.total);
$listStatus
  .on(listProductsFx, () => "loading")
  .on(listProductsFx.done, () => "idle")
  .on(listProductsFx.fail, () => "error");
$listError.on(listProductsFx.failData, (_, e) => e).reset(listProductsFx);

// Prices of the visible rows: after each list load, scope change and successful posting.
sample({
  clock: [listProductsFx.doneData.map(() => undefined), scopeChanged, savePricesFx.done.map(() => undefined)],
  source: { products: $products, scope: $scope },
  fn: ({ products, scope }) => ({ productIds: products.map((p) => p.id), scope }),
  target: loadPricesFx,
});
$prices.on(loadPricesFx.doneData, (current, loaded) => ({ ...current, ...loaded }));
$scope.on(scopeChanged, (_, s) => s);

// --- drafts --------------------------------------------------------------------------------------
// The scope (global / branch price) changes the base price of every row — drafts are dropped; the page
// asks for confirmation first when there are unsaved edits.
sample({
  clock: draftChanged,
  source: { drafts: $drafts, products: $products, prices: $prices },
  fn: ({ drafts, products, prices }, edit) => applyDraft(drafts, edit, products, prices),
  target: $drafts,
});
$drafts.reset(draftsReset, scopeChanged);

// --- history panel -------------------------------------------------------------------------------
$selectedId.on(productSelected, (_, id) => id);
// The first row is selected by default so the panel is never empty.
sample({
  clock: listProductsFx.doneData,
  source: $selectedId,
  filter: (selected, res) => res.items.length > 0 && !res.items.some((p) => p.id === selected),
  fn: (_, res) => res.items[0]?.id ?? "",
  target: productSelected,
});
sample({
  clock: [productSelected, scopeChanged, savePricesFx.done],
  source: { productId: $selectedId, scope: $scope },
  filter: (s) => s.productId !== null,
  fn: ({ productId, scope }) => ({ productId: productId ?? "", scope, cursor: null }),
  target: loadHistoryFx,
});
sample({
  clock: historyMoreRequested,
  source: { productId: $selectedId, scope: $scope, cursor: $historyCursor },
  filter: (s) => s.productId !== null && s.cursor !== null,
  fn: ({ productId, scope, cursor }) => ({ productId: productId ?? "", scope, cursor }),
  target: loadHistoryFx,
});
$history
  .on(loadHistoryFx.done, (items, { params, result }) =>
    params.cursor ? [...items, ...result.items] : result.items,
  )
  .reset(productSelected);
$historyCursor.on(loadHistoryFx.doneData, (_, res) => res.next_cursor).reset(productSelected);
$historyError.on(loadHistoryFx.failData, (_, e) => e).reset(loadHistoryFx);

// --- save ----------------------------------------------------------------------------------------
sample({
  clock: saveRequested,
  source: { changes: $changes, effectiveFrom: $effectiveFrom, scope: $scope },
  filter: ({ changes }) => changes.length > 0 && changes.every((c) => isPositiveAmount(c.newPrice)),
  fn: ({ changes, effectiveFrom, scope }) => {
    const today = todayIso();
    return {
      docDate: today,
      validFrom: validFromOf(effectiveFrom, today),
      branchId: scope === ALL_BRANCHES_SCOPE ? null : scope,
      lines: changes.map((c) => ({ productId: c.product.id, newPrice: c.newPrice })),
    };
  },
  target: savePricesFx,
});
$saveResult.on(savePricesFx.doneData, (_, doc) => doc).reset(resultDismissed, savePricesFx);
$saveError.on(savePricesFx.failData, (_, e) => e).reset(savePricesFx, resultDismissed, draftsReset);
// Posted or sent for approval: the edits are done either way (pending prices do not apply yet).
sample({ clock: savePricesFx.done, target: draftsReset });
