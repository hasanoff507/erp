import { sample } from "effector";

import { categoriesChanged, referenceRequested } from "#/entities/product/index.ts";

import {
  addBarcodeFx,
  archiveCategoryFx,
  archiveProductFx,
  createCategoryFx,
  createProductFx,
  deleteBarcodeFx,
  generateInternalBarcodeFx,
  getProductFx,
  listProductsFx,
  searchMxikFx,
  unarchiveProductFx,
  updateCategoryFx,
  updateProductFx,
} from "../effects/index.ts";
import {
  archivedChanged,
  categoryChanged,
  editorClosed,
  listRefreshRequested,
  mxikQueryChanged,
  pageChanged,
  pageMounted,
  productRequested,
  searchChanged,
} from "../events/index.ts";
import {
  $editing,
  $editingError,
  $filters,
  $listError,
  $listStatus,
  $mxikError,
  $mxikQuery,
  $mxikResults,
  $page,
  $products,
  $total,
} from "../stores/index.ts";

/** Below this the MXIK search is not sent (the classifier needs a meaningful fragment). */
export const MXIK_MIN_QUERY = 3;

// --- list ----------------------------------------------------------------------------------------
$filters
  .on(searchChanged, (f, search) => ({ ...f, search }))
  .on(categoryChanged, (f, categoryId) => ({ ...f, categoryId }))
  .on(archivedChanged, (f, archived) => ({ ...f, archived }));
$page.on(pageChanged, (_, page) => page).reset(searchChanged, categoryChanged, archivedChanged);

sample({ clock: pageMounted, target: referenceRequested });

sample({
  clock: [pageMounted, searchChanged, categoryChanged, archivedChanged, pageChanged, listRefreshRequested],
  source: { filters: $filters, page: $page },
  target: listProductsFx,
});

$products.on(listProductsFx.doneData, (_, res) => res.items);
$total.on(listProductsFx.doneData, (_, res) => res.total);
$listStatus
  .on(listProductsFx, () => "loading")
  .on(listProductsFx.done, () => "idle")
  .on(listProductsFx.fail, () => "error");
$listError.on(listProductsFx.failData, (_, e) => e).reset(listProductsFx);

// Any product write refreshes the current list page.
sample({
  clock: [
    createProductFx.done,
    updateProductFx.done,
    archiveProductFx.done,
    unarchiveProductFx.done,
    addBarcodeFx.done,
    deleteBarcodeFx.done,
    generateInternalBarcodeFx.done,
  ],
  target: listRefreshRequested,
});

// --- editor --------------------------------------------------------------------------------------
sample({ clock: productRequested, target: getProductFx });
$editing
  .on(
    [
      getProductFx.doneData,
      createProductFx.doneData,
      updateProductFx.doneData,
      archiveProductFx.doneData,
      unarchiveProductFx.doneData,
    ],
    (_, p) => p,
  )
  .reset(editorClosed);
$editingError.on(getProductFx.failData, (_, e) => e).reset(getProductFx, editorClosed);

// Barcode changes come back without the product: reload it (barcodes do not bump `version`).
sample({
  clock: [addBarcodeFx.done, deleteBarcodeFx.done, generateInternalBarcodeFx.done],
  source: $editing,
  filter: (p) => p !== null,
  fn: (p) => p?.id ?? "",
  target: getProductFx,
});

// --- MXIK search ---------------------------------------------------------------------------------
$mxikQuery.on(mxikQueryChanged, (_, q) => q).reset(editorClosed);
sample({ clock: mxikQueryChanged, filter: (q) => q.length >= MXIK_MIN_QUERY, target: searchMxikFx });
// Only the answer for the latest query is shown (a slow earlier search must not overwrite it).
sample({
  clock: searchMxikFx.done,
  source: $mxikQuery,
  filter: (query, { params }) => params === query,
  fn: (_, { result }) => result,
  target: $mxikResults,
});
$mxikResults
  .on(mxikQueryChanged, (current, q) => (q.length >= MXIK_MIN_QUERY ? current : []))
  .reset(editorClosed);
$mxikError.on(searchMxikFx.failData, (_, e) => e).reset(searchMxikFx, editorClosed);

// --- categories ----------------------------------------------------------------------------------
sample({
  clock: [createCategoryFx.done, updateCategoryFx.done, archiveCategoryFx.done],
  target: categoriesChanged,
});
