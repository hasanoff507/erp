/* eslint-disable @typescript-eslint/require-await -- the fakes implement async ports */
import { allSettled, fork } from "effector";
import { describe, expect, it, vi } from "vitest";

import type { PoOut, ReceiptIn, ReceiptOut } from "@shared/models";

import type { ScanResult } from "#/features/wh-scan/index.ts";

import {
  $canSave,
  $error,
  $finished,
  $lines,
  $orders,
  $problems,
  applyScan,
  configureGoodsReceipt,
  goodsReceiptOpened,
  linesFromOrder,
  markingAdded,
  orderSelected,
  reasonChanged,
  receiptBody,
  saveRequested,
  scanned,
  type GoodsReceiptDeps,
} from "./index.ts";

const PO: PoOut = {
  id: "po-1", number: "X-01-2026-000005", status: "partially_received", doc_date: "2026-10-15", branch_id: "b-1",
  warehouse_id: "w-1", supplier_id: "s-1", supplier: { id: "s-1", name: "Coca-Cola Ichimliklar", stir: null },
  comment: null, total: null, line_count: 2, created_by: "u", created_by_name: null, created_at: "", updated_at: "",
  sent_at: null, cancelled_at: null, cancel_reason: null,
  lines: [
    { id: "pl-1", line_no: 1, product_id: "p-cola", product_name: "Coca-Cola 1.5L", unit_code: "pcs", qty: "24.000",
      price: "9000.0000", amount: null },
    { id: "pl-2", line_no: 2, product_id: "p-milk", product_name: "Sut 1 l", unit_code: "pcs", qty: "2.000",
      price: null, amount: null },
  ],
  received_lines: [{ product_id: "p-cola", ordered_qty: "24.000", received_qty: "20.000" }],
}; // prettier-ignore

const MARK1 = "0104600000000015215abc\u001d93x1";
const MARK2 = "0104600000000015215abd\u001d93x2";
const item = (productId: string, markingCode: string | null = null): ScanResult => ({
  kind: "product",
  item: { productId, name: productId, nameRu: null, unitCode: "pcs", isMarked: markingCode !== null,
    isWeighed: false, qty: "1.000", code: markingCode ?? "4780000123454", markingCode },
}); // prettier-ignore

function setup(over: Partial<GoodsReceiptDeps> = {}) {
  const create = vi.fn(
    async (body: ReceiptIn) =>
      ({ id: "gr-1", number: null, lines: [], marking_acceptance: null, body }) as unknown as ReceiptOut,
  );
  const deps: Partial<GoodsReceiptDeps> = {
    online: () => true,
    branchId: () => "b-1",
    openOrders: async () => [
      { ...PO, branch_id: "b-1" },
      { ...PO, id: "po-other", branch_id: "b-2" },
    ],
    order: async () => PO,
    draftFor: async () => null,
    markedProducts: async () => new Set(["p-milk"]),
    create,
    update: vi.fn(),
    resolve: async (code) =>
      code === "cola" ? item("p-cola") : code === MARK1 ? item("p-milk", MARK1) : code === MARK2 ? item("p-milk", MARK2)
        : code === "fanta" ? item("p-fanta") : { kind: "unknown", code }, // prettier-ignore
    now: () => new Date("2026-10-17T06:00:00Z"),
    ...over,
  };
  return { deps, create };
}

describe("POS-08 pure logic", () => {
  it("default received = what is still to come; first scan counts from zero", () => {
    const lines = linesFromOrder(PO, new Set(["p-milk"]));
    expect(lines.map((l) => [l.productId, l.remaining, l.received, l.isMarked])).toEqual([
      ["p-cola", "4.000", "4.000", false],
      ["p-milk", "2.000", "2.000", true],
    ]);
    const once = applyScan(lines, (item("p-cola") as Extract<ScanResult, { kind: "product" }>).item);
    expect(once.lines?.[0]).toMatchObject({ received: "1.000", scanned: true });
    expect(applyScan(lines, (item("p-x") as Extract<ScanResult, { kind: "product" }>).item)).toEqual({
      lines: null,
      error: "not_in_order",
    });
  });
});

describe("POS-08 model", () => {
  it("lists this branch's open orders; scans compare with the PO; reason + marking rules; draft POST", async () => {
    const { deps, create } = setup();
    const scope = fork();
    await allSettled(configureGoodsReceipt, { scope, params: deps });
    await allSettled(goodsReceiptOpened, { scope });
    expect(scope.getState($orders).map((o) => o.id)).toEqual(["po-1"]);
    await allSettled(orderSelected, { scope, params: "po-1" });

    await allSettled(scanned, { scope, params: "cola" });
    await allSettled(scanned, { scope, params: "cola" });
    await allSettled(scanned, { scope, params: "fanta" });
    expect(scope.getState($error)).toEqual({ kind: "not_in_order", name: "p-fanta" });
    expect(scope.getState($lines)[0]).toMatchObject({ received: "2.000" });
    expect(scope.getState($problems)["p-cola"]).toEqual(["reason_required"]);
    // marked line: 2 expected, no codes yet; no price → cost required
    expect(scope.getState($problems)["p-milk"]).toEqual(["cost_required", "marking_mismatch"]);
    expect(scope.getState($canSave)).toBe(false);

    await allSettled(reasonChanged, { scope, params: { productId: "p-cola", reason: "short" } });
    await allSettled(scanned, { scope, params: MARK1 });
    await allSettled(scanned, { scope, params: MARK1 });
    expect(scope.getState($error)).toEqual({ kind: "marking_duplicate" });
    await allSettled(markingAdded, { scope, params: { productId: "p-milk", code: MARK2 } });
    expect(scope.getState($lines)[1]).toMatchObject({ received: "2.000", markingCodes: [MARK1, MARK2] });
    expect(scope.getState($problems)["p-milk"]).toEqual(["cost_required"]);

    // cost of a PO line without a price
    const lines = scope.getState($lines);
    const body = receiptBody(PO, [lines[0]!, { ...lines[1]!, cost: "7000" }], "2026-10-17", " POA-12 ");
    expect(body).toEqual({
      supplier_id: "s-1",
      warehouse_id: "w-1",
      po_id: "po-1",
      doc_date: "2026-10-17",
      lines: [
        { product_id: "p-cola", qty: "2.000", discrepancy_reason: "short" },
        { product_id: "p-milk", qty: "2.000", cost: "7000", marking_codes: [MARK1, MARK2] },
      ],
      poa_number: "POA-12",
    });

    await allSettled(saveRequested, { scope, params: { finish: true } });
    expect(create).not.toHaveBeenCalled(); // cost still missing
  });

  it("finish saves a draft once (online only) and returns to the order list", async () => {
    const po = { ...PO, lines: [PO.lines[0]!], received_lines: [] };
    const { deps, create } = setup({ order: async () => po, markedProducts: async () => new Set() });
    const scope = fork();
    await allSettled(configureGoodsReceipt, { scope, params: deps });
    await allSettled(goodsReceiptOpened, { scope });
    await allSettled(orderSelected, { scope, params: "po-1" });
    expect(scope.getState($canSave)).toBe(true);
    await allSettled(saveRequested, { scope, params: { finish: true } });
    expect(create).toHaveBeenCalledTimes(1);
    expect(create.mock.calls[0]?.[0]).toMatchObject({
      po_id: "po-1",
      lines: [{ product_id: "p-cola", qty: "24.000" }],
    });
    expect(scope.getState($finished)?.id).toBe("gr-1");
    expect(scope.getState($lines)).toEqual([]);

    const offline = setup({
      online: () => false,
      order: async () => po,
      markedProducts: async () => new Set(),
    });
    const s2 = fork();
    await allSettled(configureGoodsReceipt, { scope: s2, params: offline.deps });
    await allSettled(orderSelected, { scope: s2, params: "po-1" });
    await allSettled(saveRequested, { scope: s2, params: { finish: true } });
    expect(offline.create).not.toHaveBeenCalled();
  });
});
