/**
 * BO-04 page model: tabs «Xaridnomalar» / «Kirimlar» (badge — kirim qoralamalari, o'tkazish kutilmoqda)
 * / «Yetkazib beruvchiga to'lov» (B4) / «Qaytarish» / «Yetkazib beruvchilar»; cross-tab flows «Kirim
 * yaratish» (PO → receipt sheet) and «Qaytarish» (posted receipt → return sheet). sample() only (24 §2).
 */
import { createEvent, createStore, sample } from "effector";

import { api } from "@shared/api";

import { refsRequested } from "#/entities/refs/index.ts";
import { ordersOpened } from "#/features/purchase-orders/index.ts";
import {
  cancelReceiptFx,
  postReceiptFx,
  receiptFormOpened,
  receiptsOpened,
  saveReceiptFx,
} from "#/features/goods-receipts/index.ts";
import { payablesOpened } from "#/features/payables/index.ts";
import { paymentsOpened } from "#/features/supplier-payments/index.ts";
import { returnFromReceipt, returnsOpened } from "#/features/supplier-returns/index.ts";
import { suppliersOpened } from "#/features/suppliers/index.ts";
import { apiFx, BULK_LIMIT, readAllPages } from "#/shared/lib/effect.ts";

export type PurchasesTab = "orders" | "receipts" | "payments" | "returns" | "payables" | "suppliers";
export const PURCHASES_TABS: readonly PurchasesTab[] = [
  "orders",
  "receipts",
  "payments",
  "returns",
  // B4 (w-debts): «Men qarzdorman» — 07 BO-04 fifth tab
  "payables",
  "suppliers",
];

export function isPurchasesTab(v: string | null): v is PurchasesTab {
  return v !== null && (PURCHASES_TABS as readonly string[]).includes(v);
}

export const pageMounted = createEvent<{ tab: PurchasesTab; canListStaff: boolean }>();
export const tabChanged = createEvent<PurchasesTab>();
/** «Kirim yaratish» on a sent purchase order. */
export const receiptFromOrderRequested = createEvent<string>();
/** «Qaytarish» on a posted receipt. */
export const returnFromReceiptRequested = createEvent<string>();

/** «Kirimlar» badge: drafts waiting for «O'tkazish» (`purchases.post`). */
export const loadDraftReceiptsFx = apiFx<void, number>(async () => {
  const { items } = await readAllPages(
    (cursor) =>
      api.purchasing.listGoodsReceipts({ status: "draft", ...(cursor ? { cursor } : {}), limit: BULK_LIMIT }),
    5,
  );
  return items.length;
});

/** «Xaridnoma» create sheet (page button, or a one-shot `?new=1` link — WEB-20). */
export const orderSheetToggled = createEvent<boolean>();

export const $tab = createStore<PurchasesTab>("orders");
export const $orderSheetOpen = createStore(false)
  .on(orderSheetToggled, (_, open) => open)
  .reset(pageMounted);
export const $draftReceipts = createStore<number | null>(null, { skipVoid: false });

sample({ clock: pageMounted, fn: ({ canListStaff }) => ({ canListStaff }), target: refsRequested });
sample({ clock: pageMounted, fn: ({ tab }) => tab, target: tabChanged });
sample({
  clock: [pageMounted, saveReceiptFx.done, postReceiptFx.done, cancelReceiptFx.done],
  fn: () => undefined,
  target: loadDraftReceiptsFx,
});
$draftReceipts.on(loadDraftReceiptsFx.doneData, (_, n) => n);

$tab.on(tabChanged, (_, tab) => tab);
sample({ clock: tabChanged, filter: (t) => t === "orders", fn: () => undefined, target: ordersOpened });
sample({ clock: tabChanged, filter: (t) => t === "receipts", fn: () => undefined, target: receiptsOpened });
sample({ clock: tabChanged, filter: (t) => t === "returns", fn: () => undefined, target: returnsOpened });
sample({ clock: tabChanged, filter: (t) => t === "payments", fn: () => undefined, target: paymentsOpened });
sample({ clock: tabChanged, filter: (t) => t === "suppliers", fn: () => undefined, target: suppliersOpened });
sample({ clock: tabChanged, filter: (t) => t === "payables", fn: () => undefined, target: payablesOpened });

sample({ clock: receiptFromOrderRequested, fn: () => "receipts" as const, target: tabChanged });
sample({
  clock: receiptFromOrderRequested,
  fn: (poId) => ({ mode: "po" as const, poId }),
  target: receiptFormOpened,
});
sample({ clock: returnFromReceiptRequested, fn: () => "returns" as const, target: tabChanged });
sample({ clock: returnFromReceiptRequested, target: returnFromReceipt });
