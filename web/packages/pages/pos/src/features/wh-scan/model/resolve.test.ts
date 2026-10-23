/* eslint-disable @typescript-eslint/require-await -- the fakes implement async ports */
import { describe, expect, it } from "vitest";

import type { BarcodeHit, ProductView } from "@shared/offline";

import { classifyCode, gtinOfMarkingCode, isMarkingCode } from "../lib/codes.ts";
import { addQty, decrementQty, qty3, sumQty, trimQty } from "../lib/qty.ts";
import { resolveScan, type ScanDeps } from "./resolve.ts";

const beef: ProductView = {
  product: {
    id: "p-beef",
    name: "Mol go'shti (kg)",
    name_ru: null,
    category_id: null,
    unit_code: "kg",
    code: "12345",
    is_weighed: true,
    tokens: [],
  },
  price: "95000.0000",
};
const cola: BarcodeHit = {
  product: {
    id: "p-cola",
    name: "Coca-Cola 1.5L",
    name_ru: "Кока-кола",
    category_id: null,
    unit_code: "pcs",
    tokens: [],
  },
  price: "12000.0000",
  barcode: {
    barcode: "4780000123454",
    product_id: "p-cola",
    kind: "ean",
    units_per_barcode: "1.000",
  } as never,
  unitsPerBarcode: "1.000",
};
const pack: BarcodeHit = { ...cola, unitsPerBarcode: "6.000" };
const milk: BarcodeHit = {
  ...cola,
  product: { ...cola.product, id: "p-milk", name: "Sut 2,5% 1 l", is_marked: true },
};

function deps(over: Partial<ScanDeps> = {}): ScanDeps {
  return {
    templates: async () => null,
    byBarcode: async (code) =>
      code === "4780000123454"
        ? cola
        : code === "4780000999990"
          ? pack
          : code === "4600000000015"
            ? milk
            : null,
    byItemCode: async (code) => (code === "12345" ? beef : null),
    ...over,
  };
}

const MARKING = "0104600000000015215abcDEF\u001d93xYz1";

describe("wh-scan resolver (24 §5.1, §6.3)", () => {
  it("weight label 22 → product with the label weight (QT-M01-22 numbers)", async () => {
    const r = await resolveScan("2212345012503", deps());
    expect(r).toMatchObject({
      kind: "product",
      item: { productId: "p-beef", qty: "1.250", isWeighed: true },
    });
  });

  it("amount label 21 → qty = amount ÷ current price", async () => {
    const r = await resolveScan("2112345118758", deps());
    expect(r).toMatchObject({ kind: "product", item: { productId: "p-beef", qty: "0.125" } });
  });

  it("wrong check digit of a weight label is rejected", async () => {
    expect(await resolveScan("2212345012504", deps())).toEqual({
      kind: "rejected",
      code: "2212345012504",
      reason: "check_digit",
    });
  });

  it("ordinary and pack barcodes; unknown code", async () => {
    expect(await resolveScan("4780000123454", deps())).toMatchObject({
      item: { productId: "p-cola", qty: "1.000" },
    });
    expect(await resolveScan("4780000999990", deps())).toMatchObject({ item: { qty: "6.000" } });
    expect(await resolveScan("  999  ", deps())).toEqual({ kind: "unknown", code: "999" });
    expect(await resolveScan("   ", deps())).toMatchObject({ kind: "rejected", reason: "empty" });
  });

  it("DataMatrix marking code → GTIN barcode → product, code kept with GS", async () => {
    const r = await resolveScan(MARKING, deps());
    expect(r).toMatchObject({
      kind: "product",
      item: { productId: "p-milk", isMarked: true, markingCode: MARKING },
    });
  });

  it("amount label without a price is rejected (no qty can be computed)", async () => {
    const r = await resolveScan(
      "2112345118758",
      deps({ byItemCode: async () => ({ ...beef, price: null }) }),
    );
    expect(r).toMatchObject({ kind: "rejected", reason: "no_price" });
  });
});

describe("codes + qty helpers", () => {
  it("classifies scanner input", () => {
    expect(classifyCode("4780000123454")).toBe("ean13");
    expect(classifyCode("4780000123455")).toBe("other");
    expect(classifyCode("96385074")).toBe("ean8");
    expect(classifyCode(MARKING)).toBe("datamatrix");
    expect(isMarkingCode("0104600000000015")).toBe(false);
    expect(gtinOfMarkingCode(MARKING)).toBe("4600000000015");
    expect(classifyCode("ABC-1")).toBe("other");
  });

  it("qty strings never go through numbers", () => {
    expect(qty3("12")).toBe("12.000");
    expect(qty3("x")).toBe("");
    expect(addQty("0.1", "0.2")).toBe("0.300");
    expect(sumQty(["1.250", "0.875"])).toBe("2.125");
    expect(decrementQty("0.500")).toBe("0.000");
    expect(decrementQty("3")).toBe("2.000");
    expect(trimQty("10.000")).toBe("10");
  });
});
