import { allSettled, fork } from "effector";
import { describe, expect, it } from "vitest";

import type { MxikItem, ProductOut, ProductPage } from "@shared/models";

import { loadCategoriesFx, loadUnitsFx } from "#/entities/product/index.ts";

import {
  $editing,
  $filters,
  $mxikResults,
  $page,
  $products,
  createProductFx,
  emptyProductForm,
  formToCreate,
  formToUpdate,
  getProductFx,
  listProductsFx,
  mxikQueryChanged,
  pageChanged,
  pageMounted,
  productToForm,
  searchChanged,
  searchMxikFx,
  type ProductFilters,
} from "./index.ts";

function product(patch: Partial<ProductOut> = {}): ProductOut {
  return {
    id: "p1",
    name: "Non",
    name_ru: "Хлеб",
    category_id: null,
    unit_code: "pcs",
    mxik_code: "10101001001000000",
    package_code: null,
    vat_rate: "12.00",
    vat_exemption_code: null,
    is_marked: false,
    marking_group_code: null,
    is_weighed: false,
    min_stock: null,
    archived_at: null,
    version: 3,
    barcodes: [],
    ...patch,
  };
}

const page = (items: ProductOut[]): ProductPage => ({
  items: items.map((p) => ({ ...p, current_price: null, current_cost: null, markup_pct: null })),
  total: items.length,
  page: 1,
  size: 25,
});

describe("products model (19 §1)", () => {
  it("search resets the page and reloads; writes refresh the list", async () => {
    const calls: { filters: ProductFilters; page: number }[] = [];
    const s = fork({
      handlers: [
        [loadUnitsFx, () => []],
        [loadCategoriesFx, () => []],
        [
          listProductsFx,
          (params: { filters: ProductFilters; page: number }) => {
            calls.push(params);
            return page([product()]);
          },
        ],
        [createProductFx, () => product({ id: "p2", name: "Sut" })],
      ],
    });
    await allSettled(pageMounted, { scope: s });
    await allSettled(pageChanged, { scope: s, params: 2 });
    await allSettled(searchChanged, { scope: s, params: "non" });
    expect(s.getState($page)).toBe(1);
    expect(s.getState($filters).search).toBe("non");
    expect(calls.map((c) => c.page)).toEqual([1, 2, 1]);

    await allSettled(createProductFx, { scope: s, params: formToCreate(emptyProductForm()) });
    expect(calls).toHaveLength(4);
    expect(s.getState($editing)?.id).toBe("p2");
    expect(s.getState($products)).toHaveLength(1);
  });

  it("MXIK search: < 3 chars is not sent, only the latest query's answer is shown", async () => {
    const sent: string[] = [];
    const item = (code: string): MxikItem => ({ code, name: `n${code}`, vat_hint: "12.00" });
    const s = fork({
      handlers: [
        [
          searchMxikFx,
          (q: string) => {
            sent.push(q);
            return [item(q)];
          },
        ],
        [getProductFx, () => product()],
      ],
    });
    await allSettled(mxikQueryChanged, { scope: s, params: "no" });
    expect(sent).toEqual([]);
    await allSettled(mxikQueryChanged, { scope: s, params: "non" });
    expect(s.getState($mxikResults).map((i) => i.code)).toEqual(["non"]);
  });
});

describe("product form mapping", () => {
  it("form ↔ API payload (VAT pair, empty → null, marking group only when marked)", () => {
    const values = { ...productToForm(product()), name_ru: " ", mxik_code: "", min_stock: "1.500" };
    expect(formToUpdate(values, 3)).toMatchObject({
      version: 3,
      name_ru: null,
      mxik_code: null,
      vat_rate: "12.00",
      vat_exemption_code: null,
      marking_group_code: null,
      min_stock: "1.500",
    });
    const exempt = formToCreate({
      ...emptyProductForm(),
      name: "Dori",
      vat_mode: "exempt",
      vat_exemption_code: "123",
      is_marked: true,
      marking_group_code: "medicines",
      barcode: "4780012340047",
    });
    expect(exempt).toMatchObject({
      vat_rate: null,
      vat_exemption_code: "123",
      marking_group_code: "medicines",
      barcode: "4780012340047",
    });
    expect(productToForm(product({ vat_rate: null, vat_exemption_code: "X" })).vat_mode).toBe("exempt");
    expect(productToForm(product({ vat_rate: "0.00" })).vat_mode).toBe("0.00");
  });
});
