import { allSettled, fork, scopeBind } from "effector";
import { describe, expect, it } from "vitest";

import { ApiError } from "@shared/api";

import {
  $detail,
  $detailError,
  $form,
  $formError,
  $receipts,
  formClosed,
  formOpened,
  formTotals,
  getReceiptFx,
  lineIssue,
  newLine,
  linesFromOrder,
  linesFromReceipt,
  listReceiptsFx,
  loadOpenOrdersFx,
  loadOrderFx,
  postReceiptFx,
  receiptSelected,
  receiptsOpened,
  saveReceiptFx,
  toReceiptBody,
  type Order,
  type OrderWithProducts,
  type Receipt,
  type ReceiptLineDraft,
} from "./index.ts";

const card = (vat: string | null, marked = false, exemption: string | null = null) => ({
  vat_rate: vat,
  vat_exemption_code: exemption,
  is_marked: marked,
});

const order: Order = {
  id: "o-1",
  number: "Z-1",
  status: "sent",
  doc_date: "2026-10-14",
  branch_id: "b-1",
  warehouse_id: "w-1",
  supplier_id: "s-1",
  supplier: { id: "s-1", name: "Barakali Don", stir: null },
  comment: null,
  total: null,
  line_count: 2,
  created_by: "u-1",
  created_by_name: null,
  created_at: "",
  updated_at: "",
  sent_at: null,
  cancelled_at: null,
  cancel_reason: null,
  lines: [
    {
      id: "l1",
      line_no: 1,
      product_id: "p-1",
      product_name: "Guruch",
      unit_code: "kg",
      qty: "200.000",
      price: "15000.0000",
      amount: null,
    },
    {
      id: "l2",
      line_no: 2,
      product_id: "p-2",
      product_name: "Shakar",
      unit_code: "kg",
      qty: "10.000",
      price: "10400.0000",
      amount: null,
    },
  ],
  received_lines: [
    { product_id: "p-1", ordered_qty: "200.000", received_qty: "50.000" },
    { product_id: "p-2", ordered_qty: "10.000", received_qty: "10.000" },
  ],
};

function receipt(id: string, patch: Partial<Receipt> = {}): Receipt {
  return {
    id,
    number: null,
    status: "draft",
    doc_date: "2026-10-16",
    branch_id: "b-1",
    warehouse_id: "w-1",
    supplier_id: "s-1",
    supplier: { id: "s-1", name: "Barakali Don", stir: null },
    po_id: "o-1",
    kind: "purchase",
    source: "purchase_order",
    paid_immediately: false,
    einvoice_id: null,
    einvoice_risk_flag: null,
    ettn_ref: null,
    ettn_status: "none",
    poa_id: null,
    poa_number: null,
    comment: null,
    line_count: 1,
    net_total: "100.00",
    vat_total: "12.00",
    total: "112.00",
    created_by: "u-1",
    created_by_name: null,
    created_at: "",
    updated_at: "",
    posted_at: null,
    cancelled_at: null,
    cancel_reason: null,
    marking_acceptance: null,
    lines: [],
    ...patch,
  };
}

describe("Kirimlar model (19 §8, US-M07-02/03)", () => {
  it("a receipt from a PO opens with the order; save closes the sheet and selects the draft", async () => {
    const s = fork({
      handlers: [
        [listReceiptsFx, () => ({ items: [receipt("r-1")], next_cursor: null })],
        [loadOrderFx, () => ({ order, products: {} })],
        [loadOpenOrdersFx, () => []],
        [saveReceiptFx, () => receipt("r-2")],
        [getReceiptFx, (id: string) => receipt(id, { status: "posted", number: "M-1" })],
        [postReceiptFx, () => ({ ...receipt("r-2", { status: "posted" }), lots_created: [] })],
      ],
    });
    await allSettled(receiptsOpened, { scope: s });
    expect(s.getState($receipts)).toHaveLength(1);
    await allSettled(formOpened, { scope: s, params: { mode: "po", poId: "o-1" } });
    expect(s.getState($form)).toEqual({ mode: "po", order, products: {} });
    await allSettled(saveReceiptFx, { scope: s, params: { id: null, values: {} as never } });
    expect(s.getState($form)).toBeNull();
    expect(s.getState($detail)?.id).toBe("r-2");
    await allSettled(postReceiptFx, { scope: s, params: "r-2" });
    expect(s.getState($detail)?.status).toBe("posted");
    await allSettled(receiptSelected, { scope: s, params: null });
    expect(s.getState($detail)).toBeNull();
  });

  it("a PO answer that arrives after the sheet was closed is dropped (WEB-18)", async () => {
    let answer!: (v: OrderWithProducts) => void;
    const s = fork({
      handlers: [
        [loadOpenOrdersFx, () => []],
        [loadOrderFx, () => new Promise<OrderWithProducts>((res) => (answer = res))],
      ],
    });
    scopeBind(formOpened, { scope: s })({ mode: "po", poId: "o-1" });
    scopeBind(formClosed, { scope: s })();
    answer({ order, products: {} });
    await allSettled(s);
    expect(s.getState($form)).toBeNull();
    expect(s.getState($formError)).toBeNull();
  });

  it("an unreadable receipt shows an error; selecting again clears it (WEB-09)", async () => {
    let fail = true;
    const s = fork({
      handlers: [
        [
          getReceiptFx,
          (id: string) => {
            if (fail)
              throw new ApiError({ status: 500, code: "INTERNAL_ERROR", messageKey: "errors.internal" });
            return receipt(id);
          },
        ],
      ],
    });
    await allSettled(receiptSelected, { scope: s, params: "r-1" });
    expect(s.getState($detail)).toBeNull();
    expect(s.getState($detailError)?.code).toBe("INTERNAL_ERROR");
    fail = false;
    await allSettled(receiptSelected, { scope: s, params: "r-1" });
    expect(s.getState($detailError)).toBeNull();
    expect(s.getState($detail)?.id).toBe("r-1");
  });
});

describe("receipts lib", () => {
  const info = { "p-1": card("12.00"), "p-2": card("12.00") };

  it("PO lines = remaining qty at the order price; a different qty needs a reason", () => {
    const lines = linesFromOrder(order, info);
    expect(lines).toHaveLength(1);
    expect(lines[0]).toMatchObject({ productId: "p-1", qty: "150", cost: "15000", expected: "150.000" });
    const short: ReceiptLineDraft = { ...lines[0]!, qty: "140" };
    expect(lineIssue(short)).toBe("reason");
    expect(lineIssue({ ...short, reason: "short" })).toBeNull();
    expect(lineIssue({ ...short, reason: "short", isMarked: true, codes: "a\nb" })).toBe("codes");
    const body = toReceiptBody({
      supplierId: "s-1",
      warehouseId: "w-1",
      poId: "o-1",
      docDate: "2026-10-16",
      paidImmediately: true,
      kind: "purchase",
      comment: "",
      lines: [{ ...short, reason: "short" }],
    });
    expect(body).toMatchObject({ supplier_id: null, po_id: "o-1", paid_immediately: true });
    expect(body.lines[0]).toEqual({
      product_id: "p-1",
      qty: "140.000",
      cost: "15000.0000",
      vat_rate: "12.00",
      vat_exemption_code: null,
      expiry_date: null,
      discrepancy_reason: "short",
      marking_codes: null,
    });
  });

  it("PO lines take VAT, exemption and marking from the product cards (WEB-01)", () => {
    const [line] = linesFromOrder(order, { "p-1": card("0.00", true, "10701001") });
    expect(line).toMatchObject({ isMarked: true, vatRate: "0.00", vatExemptionCode: "10701001" });
    // No card → the safe default (the load itself fails when a card is unreadable).
    expect(linesFromOrder(order, {})[0]).toMatchObject({
      isMarked: false,
      vatRate: "12.00",
      vatExemptionCode: null,
    });
  });

  it("the exemption code is sent only for a 0% line (WEB-23)", () => {
    const zero = newLine({
      id: "p-9",
      name: "Non",
      unit_code: "pcs",
      is_marked: false,
      vat_rate: "0.00",
      vat_exemption_code: "10701001",
    });
    expect(zero).toMatchObject({ vatRate: "0.00", vatExemptionCode: "10701001" });
    const saved = linesFromReceipt(
      receipt("r-1", {
        lines: [
          {
            id: "rl-1",
            line_no: 1,
            product_id: "p-9",
            product_name: "Non",
            unit_code: "pcs",
            qty: "2.000",
            cost: "3000.0000",
            vat_rate: "0.00",
            vat_exemption_code: "10701002",
            vat_amount: "0.00",
            net_amount: "6000.00",
            total_amount: "6000.00",
            expiry_date: null,
            discrepancy_reason: null,
            is_marked: false,
            marking_codes: [],
            lot_id: null,
            lot_qty_left: null,
            returned_qty: "0.000",
          },
        ],
      }),
    );
    expect(saved[0]?.vatExemptionCode).toBe("10701002");
    const body = (lines: ReceiptLineDraft[]) =>
      toReceiptBody({
        supplierId: "s-1",
        warehouseId: "w-1",
        poId: null,
        docDate: "2026-10-16",
        paidImmediately: false,
        kind: "purchase",
        comment: "",
        lines,
      }).lines;
    const filled = { ...zero, qty: "1", cost: "100" };
    expect(body([filled])[0]?.vat_exemption_code).toBe("10701001");
    expect(body([{ ...filled, vatRate: "12.00" }])[0]?.vat_exemption_code).toBeNull();
  });

  it("totals: net = Σ ROUND(qty × cost, 2), VAT 12% per line", () => {
    const line = { ...linesFromOrder(order, info)[0]!, qty: "3", cost: "333.3333" };
    expect(formTotals([line])).toEqual({ net: "1000.00", vat: "120.00", total: "1120.00" });
  });
});
