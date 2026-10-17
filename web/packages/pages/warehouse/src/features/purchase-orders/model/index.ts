/**
 * Xaridnomalar (19 §10, US-M07-01): list (qidiruv — raqam / yetkazib beruvchi, holat), detail
 * (qatorlar, jami, `received_lines` — buyurtma / qabul qilingan), create / edit (`draft`/`sent`, `lines`
 * replace all), «Yuborish» (`draft → sent`, raqam Z-…), «Bekor qilish» (`{reason}`).
 */
import { combine, createEvent, createStore, merge, sample } from "effector";

import { api, toApiError, type ApiError } from "@shared/api";
import type {
  DebtBalanceOut,
  ListPurchaseOrdersParams,
  PoCreate,
  PoHeaderOut,
  PoOut,
  PoOutStatus,
  PoPage,
} from "@shared/models";

import { createProductSearch } from "#/entities/product/index.tsx";
import { createSupplierSearch } from "#/entities/supplier/index.tsx";
import {
  isDecimal,
  isPositive,
  lineValue,
  price4,
  qty3,
  subtractQty,
  sumMoney,
  trimQty,
} from "#/shared/lib/decimal.ts";
import { apiFx, PAGE_LIMIT } from "#/shared/lib/effect.ts";

export type Order = PoOut;
export type OrderRow = PoHeaderOut;
export type OrderStatus = PoOutStatus;
export type LoadStatus = "idle" | "loading" | "error";

export const ORDER_STATUSES: readonly OrderStatus[] = [
  "draft",
  "sent",
  "partially_received",
  "closed",
  "cancelled",
];

export interface OrderFilters {
  search: string;
  status: OrderStatus | null;
}

export interface OrderLineDraft {
  key: string;
  productId: string;
  name: string;
  unitCode: string;
  qty: string;
  /** Expected price (4 dp, optional — 19 §10). */
  price: string;
}

export interface SaveOrderParams {
  /** `null` → `POST`, else `PATCH` (draft / sent). */
  id: string | null;
  body: PoCreate;
  /** «Saqlash va yuborish» — `POST /purchase-orders/{id}/send` after saving a draft. */
  send: boolean;
}

export interface SaveOrderResult {
  /** The saved order — sent when the send step succeeded, else the saved draft. */
  order: Order;
  /** The draft was saved but «Yuborish» was refused (409 …) — the draft is kept and selected. */
  sendError: ApiError | null;
}

// --- lib -------------------------------------------------------------------------------------------

export function isOrderStatus(value: string | null): value is OrderStatus {
  return value !== null && (ORDER_STATUSES as readonly string[]).includes(value);
}

export function toQuery(f: OrderFilters, cursor: string | null): ListPurchaseOrdersParams {
  const search = f.search.trim();
  return {
    ...(search ? { search } : {}),
    ...(f.status ? { status: f.status } : {}),
    ...(cursor ? { cursor } : {}),
    limit: PAGE_LIMIT,
  };
}

/** Price is optional (19 §10), but a given one must be > 0 (WEB-15: «0» is an error). */
export function lineError(l: OrderLineDraft): "qty" | "price" | null {
  if (!isPositive(l.qty)) return "qty";
  if (l.price !== "" && !isPositive(l.price)) return "price";
  return null;
}

export function toOrderBody(input: {
  supplierId: string;
  warehouseId: string;
  docDate: string;
  lines: readonly OrderLineDraft[];
  comment: string;
}): PoCreate {
  return {
    supplier_id: input.supplierId,
    warehouse_id: input.warehouseId,
    doc_date: input.docDate,
    lines: input.lines.map((l) => ({
      product_id: l.productId,
      qty: qty3(l.qty),
      price: l.price === "" ? null : price4(l.price),
    })),
    comment: input.comment.trim() || null,
  };
}

/** Σ qty × price of priced lines — the form total (pre-submit, decimal.js). */
export function formTotal(lines: readonly OrderLineDraft[]): string {
  return sumMoney(
    lines.filter((l) => isPositive(l.qty) && isDecimal(l.price)).map((l) => lineValue(l.qty, l.price)),
  );
}

export function draftLinesOf(order: Order): OrderLineDraft[] {
  return order.lines.map((l) => ({
    key: l.id,
    productId: l.product_id,
    name: l.product_name ?? "—",
    unitCode: l.unit_code ?? "",
    qty: trimQty(l.qty),
    price: l.price ? trimQty(l.price) : "",
  }));
}

/** What is still expected per product: ordered − received (≥ 0). */
export function remainingByProduct(order: Pick<Order, "received_lines">): Record<string, string> {
  const out: Record<string, string> = {};
  for (const r of order.received_lines) {
    const left = subtractQty(r.ordered_qty, r.received_qty);
    out[r.product_id] = left.startsWith("-") ? "0.000" : left;
  }
  return out;
}

export function canEdit(o: Pick<Order, "status">): boolean {
  return o.status === "draft" || o.status === "sent";
}
export function canCancel(o: Pick<Order, "status">): boolean {
  return o.status === "draft" || o.status === "sent" || o.status === "partially_received";
}
/** A goods receipt may be created from a sent / partially received order (19 §8 `po_id`). */
export function canReceive(o: Pick<Order, "status">): boolean {
  return o.status === "sent" || o.status === "partially_received";
}

// --- events / effects ------------------------------------------------------------------------------

export const ordersOpened = createEvent();
export const searchChanged = createEvent<string>();
export const statusChanged = createEvent<OrderStatus | null>();
export const moreRequested = createEvent();
export const reloadRequested = createEvent();
export const orderSelected = createEvent<string | null>();
export const actionErrorDismissed = createEvent();

export const listOrdersFx = apiFx<{ filters: OrderFilters; cursor: string | null }, PoPage>(
  ({ filters, cursor }) => api.purchasing.listPurchaseOrders(toQuery(filters, cursor)),
);
export const getOrderFx = apiFx<string, Order>((id) => api.purchasing.getPurchaseOrder(id));
/**
 * Save (`POST` / `PATCH`) and, for «Saqlash va yuborish», send. Only the save step can fail the effect:
 * a refused send keeps the saved draft (WEB-07) and is returned as `sendError` — no second create.
 */
export const saveOrderFx = apiFx<SaveOrderParams, SaveOrderResult>(async ({ id, body, send }) => {
  const saved = id
    ? await api.purchasing.updatePurchaseOrder(id, body)
    : await api.purchasing.createPurchaseOrder(body);
  if (!send || saved.status !== "draft") return { order: saved, sendError: null };
  try {
    return { order: await api.purchasing.sendPurchaseOrder(saved.id, {}), sendError: null };
  } catch (e) {
    return { order: saved, sendError: toApiError(e) };
  }
});
export const sendOrderFx = apiFx<string, Order>((id) => api.purchasing.sendPurchaseOrder(id, {}));
export const cancelOrderFx = apiFx<{ id: string; reason: string }, Order>(({ id, reason }) =>
  api.purchasing.cancelPurchaseOrder(id, { reason }),
);
export const getSupplierDebtFx = apiFx<string, DebtBalanceOut>((id) =>
  api.debts.getCounterpartyDebtBalance(id),
);

export const orderProductSearch = createProductSearch();
export const orderSupplierSearch = createSupplierSearch();

// --- stores ----------------------------------------------------------------------------------------

export const $filters = createStore<OrderFilters>({ search: "", status: null });
export const $orders = createStore<OrderRow[]>([]);
export const $cursor = createStore<string | null>(null, { skipVoid: false });
export const $status = createStore<LoadStatus>("idle");
export const $error = createStore<ApiError | null>(null, { skipVoid: false });
export const $selectedId = createStore<string | null>(null, { skipVoid: false });
export const $detail = createStore<Order | null>(null, { skipVoid: false });
export const $detailError = createStore<ApiError | null>(null, { skipVoid: false });
export const $debt = createStore<DebtBalanceOut | null>(null, { skipVoid: false });
export const $actionError = createStore<ApiError | null>(null, { skipVoid: false });

export const $moreLoading = combine(listOrdersFx.pending, $status, (p, s) => p && s !== "loading");
export const $acting = combine(sendOrderFx.pending, cancelOrderFx.pending, (a, b) => a || b);

// --- wiring ----------------------------------------------------------------------------------------

$filters
  .on(searchChanged, (f, search) => ({ ...f, search }))
  .on(statusChanged, (f, status) => ({ ...f, status }));
sample({
  clock: [ordersOpened, searchChanged, statusChanged, reloadRequested],
  source: $filters,
  fn: (filters) => ({ filters, cursor: null }),
  target: listOrdersFx,
});
sample({
  clock: moreRequested,
  source: { filters: $filters, cursor: $cursor, pending: listOrdersFx.pending },
  filter: ({ cursor, pending }) => cursor !== null && !pending,
  fn: ({ filters, cursor }) => ({ filters, cursor }),
  target: listOrdersFx,
});
const loaded = sample({
  clock: listOrdersFx.done,
  source: $filters,
  filter: (cur, { params }) => cur.search === params.filters.search && cur.status === params.filters.status,
  fn: (_, payload) => payload,
});
$orders.on(loaded, (list, { params, result }) => (params.cursor ? [...list, ...result.items] : result.items));
$cursor.on(loaded, (_, { result }) => result.next_cursor);
$status
  .on(listOrdersFx, (s, { cursor }) => (cursor === null ? "loading" : s))
  .on(loaded, () => "idle")
  .on(listOrdersFx.fail, (s, { params }) => (params.cursor === null ? "error" : s));
$error.on(listOrdersFx.failData, (_, e) => e).reset(listOrdersFx);

const savedOrder = saveOrderFx.doneData.map((r) => r.order);
const changed = merge([savedOrder, sendOrderFx.doneData, cancelOrderFx.doneData]);
$selectedId.on(orderSelected, (_, id) => id).on(savedOrder, (_, o) => o.id);
sample({ clock: orderSelected, filter: (id): id is string => id !== null, target: getOrderFx });
const detailLoaded = sample({
  clock: getOrderFx.done,
  source: $selectedId,
  filter: (cur, { params }) => cur === params,
  fn: (_, { result }) => result,
});
$detail.on([detailLoaded, changed], (_, o) => o).reset(orderSelected);
$detailError.on(getOrderFx.failData, (_, e) => e).reset(getOrderFx, orderSelected);
sample({
  clock: $detail.updates,
  filter: (o) => o !== null,
  fn: (o) => o?.supplier_id ?? "",
  target: getSupplierDebtFx,
});
$debt.on(getSupplierDebtFx.doneData, (_, d) => d).reset(orderSelected);

// List rows follow the changed document.
$orders.on(changed, (list, o) => {
  const { lines: _l, received_lines: _r, ...header } = o;
  return list.some((x) => x.id === o.id) ? list.map((x) => (x.id === o.id ? header : x)) : [header, ...list];
});
$actionError
  .on([sendOrderFx.failData, cancelOrderFx.failData], (_, e) => e)
  // Saved but not sent: the draft is selected with the refusal shown (WEB-07).
  .on(saveOrderFx.doneData, (e, r) => r.sendError ?? e)
  .reset(actionErrorDismissed, orderSelected, sendOrderFx, cancelOrderFx, saveOrderFx);
