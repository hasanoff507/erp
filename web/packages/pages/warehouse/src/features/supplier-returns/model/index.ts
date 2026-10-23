/**
 * Yetkazib beruvchiga qaytarish (19 §12, US-M07-05): list, detail, draft from a POSTED receipt
 * (`purchases.return`: lines = receipt line + its lot + qty ≤ lot qty_left; header reason
 * `expired|damaged|excess|other`), «O'tkazish» (`purchases.post`; 409 DOC_INVALID_STATE
 * `reverse_sale_required` — 12 oydan keyin teskari realizatsiya), «Bekor qilish».
 */
import { combine, createEvent, createStore, merge, sample } from "effector";

import { api, type ApiError } from "@shared/api";
import type {
  ReceiptHeaderOut,
  ReceiptOut,
  ReturnHeaderOut,
  ReturnIn,
  ReturnInReason,
  ReturnOut,
  ReturnOutStatus,
  ReturnPage,
} from "@shared/models";

import { compareQty, isPositive, qty3 } from "#/shared/lib/decimal.ts";
import { apiFx, PAGE_LIMIT } from "#/shared/lib/effect.ts";
import { createSearch } from "#/shared/lib/search.ts";

export type SupplierReturn = ReturnOut;
export type ReturnRow = ReturnHeaderOut;
export type ReturnStatus = ReturnOutStatus;
export type ReturnReason = ReturnInReason;
export type Receipt = ReceiptOut;
export type LoadStatus = "idle" | "loading" | "error";

export const RETURN_STATUSES: readonly ReturnStatus[] = ["draft", "posted", "cancelled"];
export const RETURN_REASONS: readonly ReturnReason[] = ["expired", "damaged", "excess", "other"];

/** Typed return qty per receipt line ("" = not returned). */
export type ReturnDraft = Record<string, string>;

// --- lib -------------------------------------------------------------------------------------------

export function isReturnStatus(v: string | null): v is ReturnStatus {
  return v !== null && (RETURN_STATUSES as readonly string[]).includes(v);
}

/** Lines of a posted receipt that can still be returned (a lot with something left). */
export function returnableLines(r: Receipt): Receipt["lines"] {
  return r.lines.filter((l) => l.lot_id !== null && l.lot_qty_left !== null && isPositive(l.lot_qty_left));
}

export function returnLineError(qty: string, left: string): "range" | null {
  if (qty === "") return null;
  if (!isPositive(qty) || compareQty(qty, left) > 0) return "range";
  return null;
}

export function toReturnBody(
  r: Receipt,
  draft: ReturnDraft,
  reason: ReturnReason,
  docDate: string,
  comment: string,
): ReturnIn {
  return {
    receipt_id: r.id,
    doc_date: docDate,
    reason,
    comment: comment.trim() || null,
    lines: returnableLines(r)
      .filter((l) => isPositive(draft[l.id] ?? ""))
      .map((l) => ({ receipt_line_id: l.id, lot_id: l.lot_id ?? "", qty: qty3(draft[l.id] ?? "0") })),
  };
}

// --- events / effects ------------------------------------------------------------------------------

export const returnsOpened = createEvent();
export const statusChanged = createEvent<ReturnStatus | null>();
export const moreRequested = createEvent();
export const reloadRequested = createEvent();
export const returnSelected = createEvent<string | null>();
/** «Qaytarish» from a receipt (or the sheet's receipt choice). */
export const receiptChosen = createEvent<string>();
export const createOpened = createEvent();
export const createClosed = createEvent();
export const actionErrorDismissed = createEvent();

export const listReturnsFx = apiFx<{ status: ReturnStatus | null; cursor: string | null }, ReturnPage>(
  ({ status, cursor }) =>
    api.purchasing.listSupplierReturns({
      ...(status ? { status } : {}),
      ...(cursor ? { cursor } : {}),
      limit: PAGE_LIMIT,
    }),
);
export const getReturnFx = apiFx<string, SupplierReturn>((id) => api.purchasing.getSupplierReturn(id));
/** Number of posted receipts shown per search in the receipt picker. */
export const RECEIPT_SEARCH_LIMIT = 10;
export const searchPostedReceiptsFx = apiFx<string, ReceiptHeaderOut[]>(async (search) => {
  const page = await api.purchasing.listGoodsReceipts({
    status: "posted",
    ...(search.trim() ? { search: search.trim() } : {}),
    limit: RECEIPT_SEARCH_LIMIT,
  });
  return page.items;
});
/** «Kirim hujjati» picker of the create sheet (WEB-19): number / supplier search over posted receipts. */
export const receiptSearch = createSearch((query) => searchPostedReceiptsFx(query));
export const loadReceiptFx = apiFx<string, Receipt>((id) => api.purchasing.getGoodsReceipt(id));
export const createReturnFx = apiFx<ReturnIn, SupplierReturn>((body) =>
  api.purchasing.createSupplierReturn(body),
);
export const postReturnFx = apiFx<string, SupplierReturn>((id) => api.purchasing.postSupplierReturn(id, {}));
export const cancelReturnFx = apiFx<{ id: string; reason: string }, SupplierReturn>(({ id, reason }) =>
  api.purchasing.cancelSupplierReturn(id, { reason }),
);

// --- stores ----------------------------------------------------------------------------------------

export const $filter = createStore<ReturnStatus | null>(null, { skipVoid: false });
export const $returns = createStore<ReturnRow[]>([]);
export const $cursor = createStore<string | null>(null, { skipVoid: false });
export const $status = createStore<LoadStatus>("idle");
export const $error = createStore<ApiError | null>(null, { skipVoid: false });
export const $selectedId = createStore<string | null>(null, { skipVoid: false });
export const $detail = createStore<SupplierReturn | null>(null, { skipVoid: false });
/** The selected return could not be read (WEB-09) — the sheet shows it with «Qayta urinish». */
export const $detailError = createStore<ApiError | null>(null, { skipVoid: false });
export const $actionError = createStore<ApiError | null>(null, { skipVoid: false });

export const $createOpen = createStore(false);
/** The receipt chosen in the create sheet (with lines, lots and lot balances). */
export const $receipt = createStore<Receipt | null>(null, { skipVoid: false });
export const $receiptError = createStore<ApiError | null>(null, { skipVoid: false });

export const $moreLoading = combine(listReturnsFx.pending, $status, (p, s) => p && s !== "loading");
export const $acting = combine(postReturnFx.pending, cancelReturnFx.pending, (a, b) => a || b);

// --- wiring ----------------------------------------------------------------------------------------

$filter.on(statusChanged, (_, s) => s);
sample({
  clock: [returnsOpened, statusChanged, reloadRequested],
  source: $filter,
  fn: (status) => ({ status, cursor: null }),
  target: listReturnsFx,
});
sample({
  clock: moreRequested,
  source: { status: $filter, cursor: $cursor, pending: listReturnsFx.pending },
  filter: ({ cursor, pending }) => cursor !== null && !pending,
  fn: ({ status, cursor }) => ({ status, cursor }),
  target: listReturnsFx,
});
const loaded = sample({
  clock: listReturnsFx.done,
  source: $filter,
  filter: (cur, { params }) => cur === params.status,
  fn: (_, payload) => payload,
});
$returns.on(loaded, (list, { params, result }) =>
  params.cursor ? [...list, ...result.items] : result.items,
);
$cursor.on(loaded, (_, { result }) => result.next_cursor);
$status
  .on(listReturnsFx, (s, { cursor }) => (cursor === null ? "loading" : s))
  .on(loaded, () => "idle")
  .on(listReturnsFx.fail, (s, { params }) => (params.cursor === null ? "error" : s));
$error.on(listReturnsFx.failData, (_, e) => e).reset(listReturnsFx);

$selectedId.on(returnSelected, (_, id) => id).on(createReturnFx.doneData, (_, r) => r.id);
sample({ clock: returnSelected, filter: (id): id is string => id !== null, target: getReturnFx });
const detailLoaded = sample({
  clock: getReturnFx.done,
  source: $selectedId,
  filter: (cur, { params }) => cur === params,
  fn: (_, { result }) => result,
});
const changed = merge([createReturnFx.doneData, postReturnFx.doneData, cancelReturnFx.doneData]);
$detail.on([detailLoaded, changed], (_, r) => r).reset(returnSelected);
sample({
  clock: getReturnFx.fail,
  source: $selectedId,
  filter: (cur, { params }) => cur === params,
  fn: (_, { error }) => error,
  target: $detailError,
});
$detailError.reset(getReturnFx, returnSelected);
sample({
  clock: [createReturnFx.done, postReturnFx.done, cancelReturnFx.done],
  fn: () => undefined,
  target: reloadRequested,
});
$actionError
  .on([postReturnFx.failData, cancelReturnFx.failData], (_, e) => e)
  .reset(actionErrorDismissed, returnSelected, postReturnFx, cancelReturnFx);

// Create sheet.
$createOpen.on([createOpened, receiptChosen], () => true).reset(createClosed, createReturnFx.done);
sample({ clock: [createOpened, createClosed], target: receiptSearch.reset });
sample({ clock: receiptChosen, target: loadReceiptFx });
$receipt.on(loadReceiptFx.doneData, (_, r) => r).reset(createClosed, createOpened, createReturnFx.done);
$receiptError.on(loadReceiptFx.failData, (_, e) => e).reset(loadReceiptFx, createClosed);
