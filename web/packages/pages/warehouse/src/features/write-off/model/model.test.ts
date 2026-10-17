import { allSettled, fork } from "effector";
import { describe, expect, it } from "vitest";

import { ApiError } from "@shared/api";

import {
  $awaiting,
  $failedDraft,
  $lots,
  AUTO_LOT,
  isAwaitingApproval,
  lineError,
  lotsRequested,
  loadLotsFx,
  needsPromoRef,
  repostWriteOffFx,
  submitWriteOffFx,
  toBody,
  writeOffClosed,
  type StockLot,
  type SubmitResult,
  type WriteOff,
  type WriteOffForm,
  type WriteOffLineDraft,
} from "./index.ts";

const lot: StockLot = {
  id: "lot-1",
  product_id: "p-1",
  product_name: "Tuxum 10 dona",
  warehouse_id: "w-1",
  received_at: "2026-10-01T05:00:00Z",
  qty_in: "40.000",
  qty_left: "12.000",
  blocked_qty: "2.000",
  unit_cost: "13500.0000",
  expiry_date: "2026-10-20",
  receipt_line_id: "rl-1",
  source_doc_type: "goods_receipts",
  source_doc_id: "gr-1",
};

function line(patch: Partial<WriteOffLineDraft> = {}): WriteOffLineDraft {
  return {
    key: "k1",
    productId: "p-1",
    name: "Tuxum 10 dona",
    unitCode: "pcs",
    lotId: "lot-1",
    qty: "3.000",
    reason: "expired",
    giftKind: "other",
    ...patch,
  };
}

function doc(patch: Partial<WriteOff> = {}): WriteOff {
  return {
    id: "wo-1",
    number: null,
    status: "draft",
    doc_date: "2026-10-16",
    branch_id: "b-1",
    warehouse_id: "w-1",
    responsible_user_id: null,
    promo_order_ref: null,
    source_return_id: null,
    comment: null,
    line_count: 1,
    total_cost: "40500.00",
    approval_request_id: null,
    approval_status: null,
    created_by: "u-1",
    created_at: null,
    posted_at: null,
    cancelled_at: null,
    cancel_reason: null,
    lines: [],
    ...patch,
  };
}

const form = (lines: WriteOffLineDraft[], promo = ""): WriteOffForm => ({
  warehouseId: "w-1",
  docDate: "2026-10-16",
  lines,
  promoOrderRef: promo,
  responsibleUserId: null,
  comment: "",
});

describe("Hisobdan chiqarish model (19 §15, US-M04-06)", () => {
  it("200 posted → no approval state; 202 draft + approval_request_id → «Tasdiq kutilmoqda»", async () => {
    const results: SubmitResult[] = [
      { doc: doc({ status: "posted", number: "HC-1" }), postError: null },
      { doc: doc({ approval_request_id: "ar-1", approval_status: "pending" }), postError: null },
    ];
    const s = fork({ handlers: [[submitWriteOffFx, () => results.shift()]] });
    await allSettled(submitWriteOffFx, { scope: s, params: form([line()]) });
    expect(s.getState($awaiting)).toBeNull();
    await allSettled(submitWriteOffFx, { scope: s, params: form([line()]) });
    expect(s.getState($awaiting)?.approval_request_id).toBe("ar-1");
    await allSettled(writeOffClosed, { scope: s });
    expect(s.getState($awaiting)).toBeNull();
  });

  it("a refused post keeps the draft; «Qayta o'tkazish» clears it on success", async () => {
    const error = new ApiError({
      status: 422,
      code: "INSUFFICIENT_STOCK",
      messageKey: "errors.insufficient_stock",
    });
    const s = fork({
      handlers: [
        [submitWriteOffFx, () => ({ doc: doc(), postError: error })],
        [repostWriteOffFx, () => doc({ status: "posted", number: "HC-2" })],
      ],
    });
    await allSettled(submitWriteOffFx, { scope: s, params: form([line()]) });
    expect(s.getState($failedDraft)?.error.code).toBe("INSUFFICIENT_STOCK");
    await allSettled(repostWriteOffFx, { scope: s, params: "wo-1" });
    expect(s.getState($failedDraft)).toBeNull();
  });

  it("lots of a preset product are loaded by product", async () => {
    const s = fork({ handlers: [[loadLotsFx, () => [lot]]] });
    await allSettled(lotsRequested, { scope: s, params: { warehouseId: "w-1", productId: "p-1" } });
    expect(s.getState($lots)).toEqual({ "p-1": [lot] });
  });
});

describe("write-off lib", () => {
  it("qty must be positive and fit the lot (qty_left − blocked)", () => {
    expect(lineError(line(), [lot])).toBeNull();
    expect(lineError(line({ qty: "10.001" }), [lot])).toBe("overLot");
    expect(lineError(line({ qty: "0" }), [lot])).toBe("qty");
    expect(lineError(line({ lotId: AUTO_LOT, qty: "100" }), [lot])).toBeNull();
  });

  it("gift kind and promo order ref only where they belong", () => {
    const gift = line({ reason: "gift", giftKind: "promo_justified" });
    expect(needsPromoRef([gift])).toBe(true);
    expect(needsPromoRef([line({ reason: "gift" })])).toBe(false);
    expect(toBody(form([gift], " Buyruq 12 "))).toMatchObject({
      promo_order_ref: "Buyruq 12",
      lines: [
        { product_id: "p-1", lot_id: "lot-1", qty: "3.000", reason: "gift", gift_kind: "promo_justified" },
      ],
    });
    expect(toBody(form([line({ lotId: AUTO_LOT })])).lines[0]).toEqual({
      product_id: "p-1",
      lot_id: null,
      qty: "3.000",
      reason: "expired",
      gift_kind: null,
    });
    expect(isAwaitingApproval(doc({ approval_request_id: "x" }))).toBe(true);
    expect(isAwaitingApproval(doc({ status: "posted", approval_request_id: "x" }))).toBe(false);
  });
});
