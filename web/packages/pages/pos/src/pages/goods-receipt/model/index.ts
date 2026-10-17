/**
 * POS-08 — Yetkazib beruvchidan tovar qabul qilish (07 POS-08; 19 §8). Online only (no outbox event): the
 * receipt is saved as a `draft` through `POST /goods-receipts` (or `PATCH` of the draft already saved for this
 * PO) — the accountant posts it in BO-04. Offline the scanned lines stay on screen; saving waits for internet.
 */
import { attach, combine, createEffect, createEvent, createStore, sample } from "effector";

import { api, toApiError } from "@shared/api";
import type { PoHeaderOut, PoOut, ReceiptIn, ReceiptOut } from "@shared/models";
import { catalog } from "@shared/offline";
import { $isOnline } from "@shared/state/network";

import { $posDevice } from "#/entities/pos-session/index.ts";
import { resolveScan, type ScanResult } from "#/features/wh-scan/index.ts";
import { tashkentDate } from "#/shared/lib/dates.ts";

import {
  applyDraft,
  applyScan,
  linesFromOrder,
  lineProblems,
  receiptBody,
  type DiscrepancyReason,
  type ReceiveLine,
} from "./lib.ts";

export * from "./lib.ts";

export interface GoodsReceiptDeps {
  online(): boolean;
  branchId(): string | null;
  openOrders(): Promise<PoHeaderOut[]>;
  order(id: string): Promise<PoOut>;
  draftFor(poId: string): Promise<ReceiptOut | null>;
  markedProducts(productIds: readonly string[]): Promise<Set<string>>;
  create(body: ReceiptIn): Promise<ReceiptOut>;
  update(id: string, body: ReceiptIn): Promise<ReceiptOut>;
  resolve(code: string): Promise<ScanResult>;
  now(): Date;
}

function defaultDeps(): GoodsReceiptDeps {
  return {
    online: () => $isOnline.getState(),
    branchId: () => $posDevice.getState()?.branchId ?? null,
    openOrders: async () => {
      const [sent, partial] = await Promise.all([
        api.purchasing.listPurchaseOrders({ status: "sent", limit: 100 }),
        api.purchasing.listPurchaseOrders({ status: "partially_received", limit: 100 }),
      ]);
      return [...sent.items, ...partial.items];
    },
    order: (id) => api.purchasing.getPurchaseOrder(id),
    draftFor: async (poId) => {
      const page = await api.purchasing.listGoodsReceipts({ po_id: poId, status: "draft", limit: 1 });
      const head = page.items[0];
      return head ? api.purchasing.getGoodsReceipt(head.id) : null;
    },
    markedProducts: async (ids) => {
      const out = new Set<string>();
      for (const id of ids) {
        const view = await catalog.get(id).catch(() => undefined);
        if (view?.product.is_marked) out.add(id);
      }
      return out;
    },
    create: (body) => api.purchasing.createGoodsReceipt(body),
    update: (id, body) => api.purchasing.updateGoodsReceipt(id, body),
    resolve: (code) => resolveScan(code),
    now: () => new Date(),
  };
}

const $deps = createStore<GoodsReceiptDeps | null>(null, { serialize: "ignore", skipVoid: false });
export const configureGoodsReceipt = createEvent<Partial<GoodsReceiptDeps>>();
$deps.on(configureGoodsReceipt, (prev, d) => ({ ...(prev ?? defaultDeps()), ...d }));
const deps = (d: GoodsReceiptDeps | null): GoodsReceiptDeps => d ?? defaultDeps();

export type ReceiptError =
  | { kind: "not_in_order"; name: string }
  | { kind: "unknown_barcode" | "check_digit"; code: string }
  | { kind: "marking_duplicate" }
  | { kind: "api"; code: string; params: Record<string, unknown> };

const toApiErrorOffline = () => Object.assign(new Error("offline"), { code: "NETWORK_ERROR" });

const apiError = (e: unknown): ReceiptError => {
  const err = toApiError(e);
  return { kind: "api", code: err.code, params: { ...err.params } };
};

// ---- events ---------------------------------------------------------------------------------------
export const goodsReceiptOpened = createEvent();
export const orderSelected = createEvent<string | null>();
export const scanned = createEvent<string>();
export const receivedChanged = createEvent<{ productId: string; qty: string }>();
export const reasonChanged = createEvent<{ productId: string; reason: DiscrepancyReason | null }>();
export const costChanged = createEvent<{ productId: string; cost: string }>();
export const markingAdded = createEvent<{ productId: string; code: string }>();
export const markingRemoved = createEvent<{ productId: string; code: string }>();
export const poaChanged = createEvent<string>();
export const saveRequested = createEvent<{ finish: boolean }>();
export const errorDismissed = createEvent();

// ---- effects --------------------------------------------------------------------------------------
export const loadOrdersFx = attach({
  source: $deps,
  effect: createEffect(async (d: GoodsReceiptDeps | null) => {
    const x = deps(d);
    if (!x.online()) return null;
    const branch = x.branchId();
    return (await x.openOrders()).filter((o) => !branch || o.branch_id === branch);
  }),
});

export const loadOrderFx = attach({
  source: $deps,
  mapParams: (id: string, d) => ({ id, d }),
  effect: createEffect(async ({ id, d }: { id: string; d: GoodsReceiptDeps | null }) => {
    const x = deps(d);
    const order = await x.order(id);
    const marked = await x.markedProducts(order.lines.map((l) => l.product_id));
    const draft = await x.draftFor(id);
    const base = linesFromOrder(order, marked);
    return { order, draft, lines: draft ? applyDraft(base, draft) : base };
  }),
});

export const scanFx = attach({
  source: $deps,
  mapParams: (code: string, d) => ({ code, d }),
  effect: createEffect(async ({ code, d }: { code: string; d: GoodsReceiptDeps | null }) =>
    deps(d).resolve(code),
  ),
});

export const saveFx = attach({
  source: $deps,
  mapParams: (
    input: { order: PoOut; lines: ReceiveLine[]; poa: string; draftId: string | null; finish: boolean },
    d,
  ) => ({
    input,
    d,
  }),
  effect: createEffect(
    async ({
      input,
      d,
    }: {
      input: { order: PoOut; lines: ReceiveLine[]; poa: string; draftId: string | null; finish: boolean };
      d: GoodsReceiptDeps | null;
    }) => {
      const x = deps(d);
      if (!x.online()) throw toApiErrorOffline();
      const body = receiptBody(input.order, input.lines, tashkentDate(x.now()), input.poa);
      const receipt = input.draftId ? await x.update(input.draftId, body) : await x.create(body);
      return { receipt, finish: input.finish };
    },
  ),
});

// ---- stores ---------------------------------------------------------------------------------------
export const $orders = createStore<PoHeaderOut[]>([]).on(loadOrdersFx.doneData, (list, r) => r ?? list);
export const $ordersLoaded = createStore(false).on(loadOrdersFx.done, () => true);
export const $order = createStore<PoOut | null>(null, { skipVoid: false })
  .on(loadOrderFx.doneData, (_, r) => r.order)
  .reset(orderSelected);
export const $draftId = createStore<string | null>(null, { skipVoid: false })
  .on(loadOrderFx.doneData, (_, r) => r.draft?.id ?? null)
  .on(saveFx.doneData, (_, r) => (r.finish ? null : r.receipt.id))
  .reset(orderSelected);
export const $draftLoaded = createStore(false)
  .on(loadOrderFx.doneData, (_, r) => r.draft !== null)
  .reset(orderSelected);
export const $poa = createStore("")
  .on(poaChanged, (_, v) => v.slice(0, 64))
  .on(loadOrderFx.doneData, (_, r) => r.draft?.poa_number ?? "")
  .reset(orderSelected);

const patchLine = (lines: ReceiveLine[], productId: string, f: (l: ReceiveLine) => ReceiveLine) =>
  lines.map((l) => (l.productId === productId ? f(l) : l));

export const $lines = createStore<ReceiveLine[]>([])
  .on(loadOrderFx.doneData, (_, r) => r.lines)
  .on(receivedChanged, (lines, { productId, qty }) =>
    patchLine(lines, productId, (l) => ({ ...l, received: qty, scanned: true })),
  )
  .on(reasonChanged, (lines, { productId, reason }) => patchLine(lines, productId, (l) => ({ ...l, reason })))
  .on(costChanged, (lines, { productId, cost }) => patchLine(lines, productId, (l) => ({ ...l, cost })))
  .on(markingRemoved, (lines, { productId, code }) =>
    patchLine(lines, productId, (l) => ({ ...l, markingCodes: l.markingCodes.filter((c) => c !== code) })),
  )
  .reset(orderSelected);

export const $problems = $lines.map((lines) =>
  Object.fromEntries(lines.map((l) => [l.productId, lineProblems(l)])),
);
export const $canSave = combine(
  $lines,
  $problems,
  (lines, problems) =>
    lines.some((l) => l.received && !/^0*(\.0*)?$/.test(l.received)) &&
    Object.values(problems).every((p) => p.length === 0),
);
export const $saved = createStore<ReceiptOut | null>(null, { skipVoid: false })
  .on(saveFx.doneData, (_, r) => r.receipt)
  .reset(orderSelected);
export const $finished = createStore<ReceiptOut | null>(null, { skipVoid: false })
  .on(saveFx.doneData, (_, r) => (r.finish ? r.receipt : null))
  .reset(goodsReceiptOpened);
export const $error = createStore<ReceiptError | null>(null, { skipVoid: false })
  .on([loadOrdersFx.failData, loadOrderFx.failData, saveFx.failData], (_, e) => apiError(e))
  .reset(errorDismissed, orderSelected);
export const $saving = saveFx.pending;
export const $loading = combine(loadOrdersFx.pending, loadOrderFx.pending, (a, b) => a || b);

// ---- wiring ---------------------------------------------------------------------------------------
sample({ clock: goodsReceiptOpened, target: loadOrdersFx });
sample({ clock: $isOnline, filter: (online) => online, fn: () => undefined, target: loadOrdersFx });
sample({ clock: orderSelected, filter: (id): id is string => id !== null, target: loadOrderFx });
sample({ clock: scanned, source: $order, filter: (o) => o !== null, fn: (_, code) => code, target: scanFx });

const scanApplied = sample({
  clock: scanFx.doneData,
  source: $lines,
  fn: (lines, r) => ({ lines, r }),
});
$lines.on(scanApplied, (lines, { r }) => {
  if (r.kind !== "product") return lines;
  const out = applyScan(lines, r.item);
  return out.lines ?? lines;
});
$error.on(scanApplied, (e, { lines, r }) => {
  if (r.kind === "unknown") return { kind: "unknown_barcode", code: r.code };
  if (r.kind === "rejected") return r.reason === "check_digit" ? { kind: "check_digit", code: r.code } : e;
  const out = applyScan(lines, r.item);
  if (out.error === "not_in_order") return { kind: "not_in_order", name: r.item.name };
  if (out.error === "marking_duplicate") return { kind: "marking_duplicate" };
  return null;
});

// manual DataMatrix entry after failed scans (07 POS-08) — one code = one unit
$lines.on(markingAdded, (lines, { productId, code }) =>
  patchLine(lines, productId, (l) =>
    l.markingCodes.includes(code) || !code.trim()
      ? l
      : applyScan([l], {
          productId, name: l.name, nameRu: null, unitCode: l.unitCode ?? "", isMarked: true, isWeighed: false,
          qty: "1.000", code, markingCode: code,
        }).lines?.[0] ?? l,
  ),
); // prettier-ignore
sample({
  clock: markingAdded,
  source: $lines,
  filter: (lines, { productId, code }) =>
    lines.some((l) => l.productId === productId && l.markingCodes.includes(code)),
  fn: (): ReceiptError => ({ kind: "marking_duplicate" }),
  target: $error,
});

sample({
  clock: saveRequested,
  source: { order: $order, lines: $lines, poa: $poa, draftId: $draftId, ok: $canSave },
  filter: ({ order, ok }) => order !== null && ok,
  fn: ({ order, lines, poa, draftId }, { finish }) => ({
    order: order as PoOut,
    lines,
    poa,
    draftId,
    finish,
  }),
  target: saveFx,
});
// finished → back to the order list (the PO list changes: partially received / closed)
sample({ clock: saveFx.doneData, filter: (r) => r.finish, fn: () => null, target: orderSelected });
sample({ clock: saveFx.doneData, filter: (r) => r.finish, fn: () => undefined, target: loadOrdersFx });
