import { allSettled, fork } from "effector";
import { describe, expect, it } from "vitest";

import { loadCategoriesFx, loadUnitsFx, loadWarehousesFx } from "#/entities/refs/index.ts";
import {
  $form,
  listReceiptsFx,
  loadOpenOrdersFx,
  loadOrderFx,
} from "#/features/goods-receipts/model/index.ts";
import { listOrdersFx } from "#/features/purchase-orders/model/index.ts";
import { $createOpen, listReturnsFx, loadReceiptFx } from "#/features/supplier-returns/model/index.ts";

import {
  $draftReceipts,
  $orderSheetOpen,
  $tab,
  isPurchasesTab,
  loadDraftReceiptsFx,
  orderSheetToggled,
  pageMounted,
  receiptFromOrderRequested,
  returnFromReceiptRequested,
} from "./index.ts";

function scope(opened: string[]) {
  const empty = { items: [], next_cursor: null };
  return fork({
    handlers: [
      [loadWarehousesFx, () => []],
      [loadUnitsFx, () => []],
      [loadCategoriesFx, () => []],
      [loadDraftReceiptsFx, () => 2],
      [listOrdersFx, () => (opened.push("orders"), empty)],
      [listReceiptsFx, () => (opened.push("receipts"), empty)],
      [listReturnsFx, () => (opened.push("returns"), empty)],
      [loadOrderFx, (id: string) => ({ order: { id, lines: [], received_lines: [] }, products: {} })],
      [loadOpenOrdersFx, () => []],
      [loadReceiptFx, (id: string) => ({ id, lines: [] })],
    ],
  });
}

describe("BO-04 purchases page model", () => {
  it("mount opens the requested tab and reads the draft-receipt badge", async () => {
    const opened: string[] = [];
    const s = scope(opened);
    await allSettled(pageMounted, { scope: s, params: { tab: "receipts", canListStaff: false } });
    expect(s.getState($tab)).toBe("receipts");
    expect(opened).toEqual(["receipts"]);
    expect(s.getState($draftReceipts)).toBe(2);
  });

  it("«Kirim yaratish» → Kirimlar + sheet from the order; «Qaytarish» → Qaytarish + sheet", async () => {
    const opened: string[] = [];
    const s = scope(opened);
    await allSettled(receiptFromOrderRequested, { scope: s, params: "o-1" });
    expect(s.getState($tab)).toBe("receipts");
    expect(s.getState($form)).toMatchObject({ mode: "po", order: { id: "o-1" } });
    await allSettled(returnFromReceiptRequested, { scope: s, params: "r-1" });
    expect(s.getState($tab)).toBe("returns");
    expect(s.getState($createOpen)).toBe(true);
    expect(isPurchasesTab("suppliers")).toBe(true);
    // B4: «Yetkazib beruvchiga to'lov» is a tab now; «Men qarzdorman» is not (debts page).
    expect(isPurchasesTab("payments")).toBe(true);
    expect(isPurchasesTab("payable")).toBe(false);
  });

  it("the order sheet flag: opened by the page / a ?new=1 link, closed on a new visit", async () => {
    const s = scope([]);
    await allSettled(orderSheetToggled, { scope: s, params: true });
    expect(s.getState($orderSheetOpen)).toBe(true);
    await allSettled(pageMounted, { scope: s, params: { tab: "orders", canListStaff: false } });
    expect(s.getState($orderSheetOpen)).toBe(false);
  });
});
