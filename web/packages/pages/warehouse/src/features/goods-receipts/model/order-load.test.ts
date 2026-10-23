/** WEB-01: the receipt sheet reads the order AND its product cards (real `loadOrderFx`, API mocked). */
import { allSettled, fork } from "effector";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type * as ApiModule from "@shared/api";

import type { PoOut, ProductOut } from "@shared/models";

const { getPurchaseOrder, getProduct } = vi.hoisted(() => ({
  getPurchaseOrder: vi.fn<(id: string) => Promise<PoOut>>(),
  getProduct: vi.fn<(id: string) => Promise<ProductOut>>(),
}));

vi.mock("@shared/api", async (importOriginal) => {
  const actual = await importOriginal<typeof ApiModule>();
  return {
    ...actual,
    api: {
      ...actual.api,
      purchasing: { ...actual.api.purchasing, getPurchaseOrder },
      pricing: { ...actual.api.pricing, getProduct },
    },
  };
});

const { $products } = await import("#/entities/refs/index.ts");
const { $form, $formError, formOpened, linesFromOrder, loadOpenOrdersFx } = await import("./index.ts");

const order: PoOut = {
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
  line_count: 1,
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
      product_name: "Dori",
      unit_code: "pcs",
      qty: "10.000",
      price: "5000.0000",
      amount: null,
    },
  ],
  received_lines: [],
};

const product: ProductOut = {
  id: "p-1",
  name: "Dori",
  name_ru: null,
  category_id: null,
  unit_code: "pcs",
  mxik_code: null,
  package_code: null,
  vat_rate: "0.00",
  vat_exemption_code: "10701001",
  is_marked: true,
  marking_group_code: "pharma",
  is_weighed: false,
  min_stock: null,
  archived_at: null,
  version: 1,
  barcodes: [],
};

describe("receipt from a purchase order (WEB-01)", () => {
  beforeEach(() => {
    getPurchaseOrder.mockReset().mockResolvedValue(order);
    getProduct.mockReset();
  });

  it("a 0%-VAT marked product with an empty product cache → marked, 0.00 lines", async () => {
    getProduct.mockResolvedValue(product);
    const s = fork({ handlers: [[loadOpenOrdersFx, () => []]] });
    expect(s.getState($products)).toEqual({});
    await allSettled(formOpened, { scope: s, params: { mode: "po", poId: "o-1" } });
    const form = s.getState($form);
    expect(form?.mode).toBe("po");
    if (form?.mode !== "po") return;
    expect(linesFromOrder(form.order, form.products)[0]).toMatchObject({
      productId: "p-1",
      isMarked: true,
      vatRate: "0.00",
      vatExemptionCode: "10701001",
    });
    expect(getProduct).toHaveBeenCalledTimes(1);
    // The cards go to the shared cache too.
    expect(s.getState($products)["p-1"]?.is_marked).toBe(true);
  });

  it("an unreadable card fails the load instead of guessing", async () => {
    getProduct.mockRejectedValue(new Error("gone"));
    const s = fork({ handlers: [[loadOpenOrdersFx, () => []]] });
    await allSettled(formOpened, { scope: s, params: { mode: "po", poId: "o-1" } });
    expect(s.getState($form)).toBeNull();
    expect(s.getState($formError)).not.toBeNull();
  });
});
