import { allSettled, fork } from "effector";
import { describe, expect, it } from "vitest";

import {
  $debt,
  $detail,
  $orders,
  canCancel,
  canReceive,
  formTotal,
  getOrderFx,
  lineError,
  getSupplierDebtFx,
  listOrdersFx,
  orderSelected,
  ordersOpened,
  remainingByProduct,
  saveOrderFx,
  statusChanged,
  toOrderBody,
  toQuery,
  type Order,
  type SaveOrderParams,
} from "./index.ts";

function order(id: string, patch: Partial<Order> = {}): Order {
  return {
    id,
    number: null,
    status: "draft",
    doc_date: "2026-10-14",
    branch_id: "b-1",
    warehouse_id: "w-1",
    supplier_id: "s-1",
    supplier: { id: "s-1", name: "Barakali Don", stir: "305112847" },
    comment: null,
    total: "3000000.00",
    line_count: 1,
    created_by: "u-1",
    created_by_name: "Akmal K.",
    created_at: "2026-10-14T05:00:00Z",
    updated_at: "2026-10-14T05:00:00Z",
    sent_at: null,
    cancelled_at: null,
    cancel_reason: null,
    lines: [
      {
        id: "l-1",
        line_no: 1,
        product_id: "p-1",
        product_name: "Guruch",
        unit_code: "kg",
        qty: "200.000",
        price: "15000.0000",
        amount: "3000000.00",
      },
    ],
    received_lines: [{ product_id: "p-1", ordered_qty: "200.000", received_qty: "150.000" }],
    ...patch,
  };
}

describe("Xaridnomalar model (19 §10, US-M07-01)", () => {
  it("list by status; select reads the order and the supplier debt; save+send updates the row", async () => {
    const saves: SaveOrderParams[] = [];
    const s = fork({
      handlers: [
        [listOrdersFx, () => ({ items: [order("o-1")], next_cursor: null })],
        [getOrderFx, (id: string) => order(id)],
        [getSupplierDebtFx, () => ({ payable: "2400000.00", receivable: "0.00" })],
        [
          saveOrderFx,
          (p: SaveOrderParams) => {
            saves.push(p);
            return { order: order("o-1", { status: "sent", number: "Z-01-2026-000231" }), sendError: null };
          },
        ],
      ],
    });
    await allSettled(ordersOpened, { scope: s });
    await allSettled(statusChanged, { scope: s, params: "sent" });
    await allSettled(orderSelected, { scope: s, params: "o-1" });
    expect(s.getState($detail)?.id).toBe("o-1");
    expect(s.getState($debt)?.payable).toBe("2400000.00");
    await allSettled(saveOrderFx, {
      scope: s,
      params: {
        id: "o-1",
        send: true,
        body: toOrderBody({
          supplierId: "s-1",
          warehouseId: "w-1",
          docDate: "2026-10-14",
          lines: [],
          comment: "",
        }),
      },
    });
    expect(saves[0]?.send).toBe(true);
    expect(s.getState($orders)[0]?.number).toBe("Z-01-2026-000231");
    expect(s.getState($detail)?.status).toBe("sent");
  });
});

describe("purchase orders lib", () => {
  it("body, totals and state rules", () => {
    const lines = [
      { key: "a", productId: "p-1", name: "A", unitCode: "kg", qty: "1.5", price: "1000.3333" },
      { key: "b", productId: "p-2", name: "B", unitCode: "pcs", qty: "2", price: "" },
    ];
    expect(
      toOrderBody({ supplierId: "s", warehouseId: "w", docDate: "2026-10-14", lines, comment: " " }),
    ).toEqual({
      supplier_id: "s",
      warehouse_id: "w",
      doc_date: "2026-10-14",
      comment: null,
      lines: [
        { product_id: "p-1", qty: "1.500", price: "1000.3333" },
        { product_id: "p-2", qty: "2.000", price: null },
      ],
    });
    expect(formTotal(lines)).toBe("1500.50");
    expect(remainingByProduct(order("x"))).toEqual({ "p-1": "50.000" });
    expect(canReceive({ status: "draft" })).toBe(false);
    expect(canReceive({ status: "partially_received" })).toBe(true);
    expect(canCancel({ status: "closed" })).toBe(false);
    expect(toQuery({ search: " Z-1 ", status: null }, null)).toEqual({ search: "Z-1", limit: 50 });
  });

  it("price is optional, but a given one must be > 0 (WEB-15)", () => {
    const l = { key: "a", productId: "p-1", name: "A", unitCode: "kg", qty: "1", price: "" };
    expect(lineError(l)).toBeNull();
    expect(lineError({ ...l, price: "0" })).toBe("price");
    expect(lineError({ ...l, price: "0.0000" })).toBe("price");
    expect(lineError({ ...l, price: "-5" })).toBe("price");
    expect(lineError({ ...l, price: "0.0001" })).toBeNull();
  });
});
