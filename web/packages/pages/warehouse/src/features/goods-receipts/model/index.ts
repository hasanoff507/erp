/**
 * Kirimlar (19 §8, US-M07-02/03): list (holat, qidiruv), detail (qatorlar — miqdor, tannarx QQSsiz,
 * QQS, jami, yaroqlilik, nomuvofiqlik sababi, partiya), draft create — manual or from a sent purchase
 * order (`po_id`: supplier fixed, lines = ordered − received, `discrepancy_reason` required when the
 * quantity differs) —, draft edit (`PATCH` replaces the draft), «O'tkazish» (`purchases.post`, lots are
 * created), «Bekor qilish» (`{reason}`; 409 LOT_ALREADY_CONSUMED when a lot was used).
 */
import { combine, createEvent, createStore, merge, sample } from "effector";

import { api, type ApiError } from "@shared/api";
import type {
  ListGoodsReceiptsParams,
  PoHeaderOut,
  PoOut,
  ProductOut,
  ReceiptHeaderOut,
  ReceiptIn,
  ReceiptLineInDiscrepancyReason,
  ReceiptOut,
  ReceiptOutStatus,
  ReceiptPage,
  ReceiptPosted,
} from "@shared/models";

import { createProductSearch } from "#/entities/product/index.tsx";
import { productsCached } from "#/entities/refs/index.ts";
import { createSupplierSearch } from "#/entities/supplier/index.tsx";
import {
  compareQty,
  isDecimal,
  isPositive,
  lineValue,
  percentOf,
  price4,
  qty3,
  subtractQty,
  sumMoney,
  trimQty,
} from "#/shared/lib/decimal.ts";
import { apiFx, BULK_LIMIT, PAGE_LIMIT, readAllPages } from "#/shared/lib/effect.ts";

export type Receipt = ReceiptOut;
export type ReceiptRow = ReceiptHeaderOut;
export type ReceiptStatus = ReceiptOutStatus;
export type Order = PoOut;
export type LoadStatus = "idle" | "loading" | "error";
export type Discrepancy = NonNullable<ReceiptLineInDiscrepancyReason>;

export const RECEIPT_STATUSES: readonly ReceiptStatus[] = ["draft", "posted", "cancelled"];
export const DISCREPANCY_REASONS: readonly Discrepancy[] = [
  "short",
  "excess",
  "damaged",
  "wrong_item",
  "other",
];
export const VAT_RATES = ["12.00", "0.00"] as const;

export interface ReceiptFilters {
  search: string;
  status: ReceiptStatus | null;
}

export interface ReceiptLineDraft {
  key: string;
  productId: string;
  name: string;
  unitCode: string;
  isMarked: boolean;
  qty: string;
  /** Unit cost WITHOUT VAT, 4 dp (19 §8). */
  cost: string;
  vatRate: string;
  /** Soliq imtiyozi kodi of a 0% line (from the product card / the saved line); sent only at 0%. */
  vatExemptionCode: string | null;
  expiry: string;
  reason: Discrepancy | "";
  /** Marking codes, one per line (`is_marked`: exactly qty codes). */
  codes: string;
  /** From a purchase order: ordered − received (null for a manual receipt). */
  expected: string | null;
}

export interface ReceiptFormValues {
  supplierId: string;
  warehouseId: string;
  poId: string | null;
  docDate: string;
  paidImmediately: boolean;
  kind: "purchase" | "gratuitous";
  comment: string;
  lines: ReceiptLineDraft[];
}

/** VAT / marking facts of a product card a receipt line needs. */
export type ProductInfo = Pick<ProductOut, "vat_rate" | "vat_exemption_code" | "is_marked">;

/** A purchase order with the cards of its products (VAT, exemption, marking — WEB-01). */
export interface OrderWithProducts {
  order: Order;
  products: Record<string, ProductInfo>;
}

/** What the receipt sheet edits: a new manual receipt, one from a PO, or an existing draft. */
export type ReceiptFormSource =
  | { mode: "new" }
  | { mode: "po"; order: Order; products: Record<string, ProductInfo> }
  | { mode: "edit"; receipt: Receipt };

export type LineIssue = "qty" | "cost" | "reason" | "codes" | null;

// --- lib -------------------------------------------------------------------------------------------

export function isReceiptStatus(v: string | null): v is ReceiptStatus {
  return v !== null && (RECEIPT_STATUSES as readonly string[]).includes(v);
}

export function toQuery(f: ReceiptFilters, cursor: string | null): ListGoodsReceiptsParams {
  const search = f.search.trim();
  return {
    ...(search ? { search } : {}),
    ...(f.status ? { status: f.status } : {}),
    ...(cursor ? { cursor } : {}),
    limit: PAGE_LIMIT,
  };
}

export function codesOf(text: string): string[] {
  return text
    .split("\n")
    .map((c) => c.replace(/\r$/, ""))
    .filter((c) => c.trim() !== "");
}

/** Quantity differs from what the order still expects → a reason is required (19 §8). */
export function needsReason(l: Pick<ReceiptLineDraft, "expected" | "qty">): boolean {
  return l.expected !== null && isDecimal(l.qty) && compareQty(l.qty, l.expected) !== 0;
}

export function lineIssue(l: ReceiptLineDraft): LineIssue {
  if (!isPositive(l.qty)) return "qty";
  if (!isDecimal(l.cost) || l.cost.startsWith("-")) return "cost";
  if (needsReason(l) && l.reason === "") return "reason";
  if (l.isMarked && compareQty(String(codesOf(l.codes).length), l.qty) !== 0) return "codes";
  return null;
}

/** Form totals (pre-submit): net = Σ ROUND(qty × cost, 2), VAT = Σ ROUND(net × rate / 100, 2). */
export function formTotals(lines: readonly ReceiptLineDraft[]): { net: string; vat: string; total: string } {
  const ok = lines.filter((l) => isPositive(l.qty) && isDecimal(l.cost));
  const nets = ok.map((l) => lineValue(l.qty, l.cost));
  const vats = ok.map((l, i) => percentOf(nets[i] ?? "0", l.vatRate));
  const net = sumMoney(nets);
  const vat = sumMoney(vats);
  return { net, vat, total: sumMoney([net, vat]) };
}

export function toReceiptBody(v: ReceiptFormValues): ReceiptIn {
  return {
    supplier_id: v.poId ? null : v.supplierId,
    warehouse_id: v.warehouseId,
    po_id: v.poId,
    doc_date: v.docDate,
    paid_immediately: v.kind === "gratuitous" ? false : v.paidImmediately,
    kind: v.kind,
    comment: v.comment.trim() || null,
    lines: v.lines.map((l) => ({
      product_id: l.productId,
      qty: qty3(l.qty),
      cost: price4(l.cost),
      vat_rate: l.vatRate,
      vat_exemption_code: l.vatRate === "0.00" ? l.vatExemptionCode : null,
      expiry_date: l.expiry || null,
      discrepancy_reason: l.reason === "" || (l.expected !== null && !needsReason(l)) ? null : l.reason,
      marking_codes: l.isMarked ? codesOf(l.codes) : null,
    })),
  };
}

let nextKey = 1;
const key = () => `r${(nextKey += 1)}`;

function vatOf(p: ProductInfo | undefined): string {
  return p?.vat_rate === "0.00" ? "0.00" : "12.00";
}

/**
 * PO → receipt lines: the remaining quantity (ordered − received) at the order price; VAT, exemption
 * and marking come from the product cards read with the order (`loadOrderFx`).
 */
export function linesFromOrder(
  order: Order,
  products: Readonly<Record<string, ProductInfo>>,
): ReceiptLineDraft[] {
  return order.lines.flatMap((l) => {
    const card = products[l.product_id];
    const received = order.received_lines.find((r) => r.product_id === l.product_id)?.received_qty ?? "0.000";
    const left = subtractQty(l.qty, received);
    if (compareQty(left, "0") <= 0) return [];
    return [
      {
        key: key(),
        productId: l.product_id,
        name: l.product_name ?? "—",
        unitCode: l.unit_code ?? "",
        isMarked: card?.is_marked ?? false,
        qty: trimQty(left),
        cost: l.price ? trimQty(l.price) : "",
        vatRate: vatOf(card),
        vatExemptionCode: card?.vat_exemption_code ?? null,
        expiry: "",
        reason: "" as const,
        codes: "",
        expected: left,
      },
    ];
  });
}

export function linesFromReceipt(r: Receipt): ReceiptLineDraft[] {
  return r.lines.map((l) => ({
    key: key(),
    productId: l.product_id,
    name: l.product_name ?? "—",
    unitCode: l.unit_code ?? "",
    isMarked: l.is_marked,
    qty: trimQty(l.qty),
    cost: trimQty(l.cost),
    vatRate: l.vat_rate,
    vatExemptionCode: l.vat_exemption_code,
    expiry: l.expiry_date ?? "",
    reason: l.discrepancy_reason ?? "",
    codes: l.marking_codes.join("\n"),
    expected: null,
  }));
}

export function newLine(p: {
  id: string;
  name: string;
  unit_code: string;
  is_marked: boolean;
  vat_rate: string | null;
  vat_exemption_code: string | null;
}): ReceiptLineDraft {
  return {
    key: key(),
    productId: p.id,
    name: p.name,
    unitCode: p.unit_code,
    isMarked: p.is_marked,
    qty: "",
    cost: "",
    vatRate: vatOf(p),
    vatExemptionCode: p.vat_exemption_code,
    expiry: "",
    reason: "",
    codes: "",
    expected: null,
  };
}

// --- events / effects ------------------------------------------------------------------------------

export const receiptsOpened = createEvent();
export const searchChanged = createEvent<string>();
export const statusChanged = createEvent<ReceiptStatus | null>();
export const moreRequested = createEvent();
export const reloadRequested = createEvent();
export const receiptSelected = createEvent<string | null>();
/** Open the sheet: new / from a purchase order id / edit the selected draft. */
export const formOpened = createEvent<{ mode: "new" } | { mode: "po"; poId: string } | { mode: "edit" }>();
export const formClosed = createEvent();
export const actionErrorDismissed = createEvent();

export const listReceiptsFx = apiFx<{ filters: ReceiptFilters; cursor: string | null }, ReceiptPage>(
  ({ filters, cursor }) => api.purchasing.listGoodsReceipts(toQuery(filters, cursor)),
);
export const getReceiptFx = apiFx<string, Receipt>((id) => api.purchasing.getGoodsReceipt(id));
/**
 * The order and the cards of its products: VAT rate, exemption and marking are not on the order lines
 * and must not be guessed — an unreadable card fails the load (WEB-01).
 */
export const loadOrderFx = apiFx<string, OrderWithProducts>(async (id) => {
  const order = await api.purchasing.getPurchaseOrder(id);
  const ids = [...new Set(order.lines.map((l) => l.product_id))];
  const results = await Promise.allSettled(ids.map((pid) => api.pricing.getProduct(pid)));
  const products: Record<string, ProductOut> = {};
  for (const r of results) {
    if (r.status === "rejected") throw r.reason;
    products[r.value.id] = r.value;
  }
  return { order, products };
});
/** Orders a receipt may be created from (`sent`, `partially_received` — 19 §8 PURCHASE_ORDER_CLOSED). */
export const loadOpenOrdersFx = apiFx<void, PoHeaderOut[]>(async () => {
  const [sent, partial] = await Promise.all([
    readAllPages(
      (cursor) =>
        api.purchasing.listPurchaseOrders({
          status: "sent",
          ...(cursor ? { cursor } : {}),
          limit: BULK_LIMIT,
        }),
      3,
    ),
    readAllPages(
      (cursor) =>
        api.purchasing.listPurchaseOrders({
          status: "partially_received",
          ...(cursor ? { cursor } : {}),
          limit: BULK_LIMIT,
        }),
      3,
    ),
  ]);
  return [...sent.items, ...partial.items];
});
export const saveReceiptFx = apiFx<{ id: string | null; values: ReceiptFormValues }, Receipt>(
  ({ id, values }) =>
    id
      ? api.purchasing.updateGoodsReceipt(id, toReceiptBody(values))
      : api.purchasing.createGoodsReceipt(toReceiptBody(values)),
);
export const postReceiptFx = apiFx<string, ReceiptPosted>((id) => api.purchasing.postGoodsReceipt(id, {}));
export const cancelReceiptFx = apiFx<{ id: string; reason: string }, Receipt>(({ id, reason }) =>
  api.purchasing.cancelGoodsReceipt(id, { reason }),
);

export const receiptProductSearch = createProductSearch();
export const receiptSupplierSearch = createSupplierSearch();

// --- stores ----------------------------------------------------------------------------------------

export const $filters = createStore<ReceiptFilters>({ search: "", status: null });
export const $receipts = createStore<ReceiptRow[]>([]);
export const $cursor = createStore<string | null>(null, { skipVoid: false });
export const $status = createStore<LoadStatus>("idle");
export const $error = createStore<ApiError | null>(null, { skipVoid: false });
export const $selectedId = createStore<string | null>(null, { skipVoid: false });
export const $detail = createStore<Receipt | null>(null, { skipVoid: false });
/** The selected receipt could not be read (WEB-09) — the sheet shows it with «Qayta urinish». */
export const $detailError = createStore<ApiError | null>(null, { skipVoid: false });
export const $actionError = createStore<ApiError | null>(null, { skipVoid: false });
/** Receipt sheet: `null` closed; loading a PO keeps it `null` until the order arrives. */
export const $form = createStore<ReceiptFormSource | null>(null, { skipVoid: false });
export const $formError = createStore<ApiError | null>(null, { skipVoid: false });
export const $openOrders = createStore<PoHeaderOut[]>([]);
/** The purchase order the sheet waits for; a late answer for a closed / replaced request is dropped. */
export const $pendingPoId = createStore<string | null>(null, { skipVoid: false });

export const $moreLoading = combine(listReceiptsFx.pending, $status, (p, s) => p && s !== "loading");
export const $acting = combine(postReceiptFx.pending, cancelReceiptFx.pending, (a, b) => a || b);

// --- wiring ----------------------------------------------------------------------------------------

$filters
  .on(searchChanged, (f, search) => ({ ...f, search }))
  .on(statusChanged, (f, status) => ({ ...f, status }));
sample({
  clock: [receiptsOpened, searchChanged, statusChanged, reloadRequested],
  source: $filters,
  fn: (filters) => ({ filters, cursor: null }),
  target: listReceiptsFx,
});
sample({
  clock: moreRequested,
  source: { filters: $filters, cursor: $cursor, pending: listReceiptsFx.pending },
  filter: ({ cursor, pending }) => cursor !== null && !pending,
  fn: ({ filters, cursor }) => ({ filters, cursor }),
  target: listReceiptsFx,
});
const loaded = sample({
  clock: listReceiptsFx.done,
  source: $filters,
  filter: (cur, { params }) => cur.search === params.filters.search && cur.status === params.filters.status,
  fn: (_, payload) => payload,
});
$receipts.on(loaded, (list, { params, result }) =>
  params.cursor ? [...list, ...result.items] : result.items,
);
$cursor.on(loaded, (_, { result }) => result.next_cursor);
$status
  .on(listReceiptsFx, (s, { cursor }) => (cursor === null ? "loading" : s))
  .on(loaded, () => "idle")
  .on(listReceiptsFx.fail, (s, { params }) => (params.cursor === null ? "error" : s));
$error.on(listReceiptsFx.failData, (_, e) => e).reset(listReceiptsFx);

// Detail.
$selectedId.on(receiptSelected, (_, id) => id).on(saveReceiptFx.doneData, (_, r) => r.id);
sample({ clock: receiptSelected, filter: (id): id is string => id !== null, target: getReceiptFx });
// The post answer is the receipt + created lots; it is re-read for the full card.
sample({ clock: postReceiptFx.done, fn: ({ params }) => params, target: getReceiptFx });
const detailLoaded = sample({
  clock: getReceiptFx.done,
  source: $selectedId,
  filter: (cur, { params }) => cur === params,
  fn: (_, { result }) => result,
});
const changed = merge([saveReceiptFx.doneData, cancelReceiptFx.doneData]);
$detail.on([detailLoaded, changed], (_, r) => r).reset(receiptSelected);
sample({
  clock: getReceiptFx.fail,
  source: $selectedId,
  filter: (cur, { params }) => cur === params,
  fn: (_, { error }) => error,
  target: $detailError,
});
$detailError.reset(getReceiptFx, receiptSelected);
sample({
  clock: [saveReceiptFx.done, postReceiptFx.done, cancelReceiptFx.done],
  fn: () => undefined,
  target: reloadRequested,
});
$actionError
  .on([postReceiptFx.failData, cancelReceiptFx.failData], (_, e) => e)
  .reset(actionErrorDismissed, receiptSelected, postReceiptFx, cancelReceiptFx);

// Form.
sample({
  clock: formOpened,
  filter: (o) => o.mode === "new",
  fn: (): ReceiptFormSource => ({ mode: "new" }),
  target: $form,
});
sample({
  clock: formOpened,
  source: $detail,
  filter: (d, o) => o.mode === "edit" && d !== null && d.status === "draft",
  fn: (d): ReceiptFormSource => ({ mode: "edit", receipt: d as Receipt }),
  target: $form,
});
sample({
  clock: formOpened,
  filter: (o) => o.mode === "po",
  fn: (o) => (o.mode === "po" ? o.poId : ""),
  target: loadOrderFx,
});
sample({ clock: formOpened, fn: () => undefined, target: loadOpenOrdersFx });
$pendingPoId
  .on(formOpened, (_, o) => (o.mode === "po" ? o.poId : null))
  .reset(formClosed, saveReceiptFx.done);
const orderLoaded = sample({
  clock: loadOrderFx.done,
  source: $pendingPoId,
  filter: (pending, { params }) => pending === params,
  fn: (_, { result }) => result,
});
sample({
  clock: orderLoaded,
  fn: ({ order, products }): ReceiptFormSource => ({ mode: "po", order, products }),
  target: $form,
});
sample({
  clock: orderLoaded,
  fn: ({ products }) => Object.values(products) as ProductOut[],
  target: productsCached,
});
$form.reset(formClosed, saveReceiptFx.done);
sample({
  clock: loadOrderFx.fail,
  source: $pendingPoId,
  filter: (pending, { params }) => pending === params,
  fn: (_, { error }) => error,
  target: $formError,
});
$formError.reset(formOpened, formClosed);
$openOrders.on(loadOpenOrdersFx.doneData, (_, list) => list);
