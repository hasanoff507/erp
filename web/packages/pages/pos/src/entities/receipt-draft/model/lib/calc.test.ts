import Decimal from "decimal.js";
import { describe, expect, it } from "vitest";

import type { DraftLine } from "../types/index.ts";
import {
  addQty,
  allocateDiscount,
  changeOf,
  effectiveDiscountPct,
  normalizePct,
  parseQty,
  price4,
  priceLines,
  stepQty,
  withinLimit,
} from "./calc.ts";

const line = (over: Partial<DraftLine>): DraftLine => ({
  id: "l1",
  productId: "p1",
  name: "Non",
  nameRu: null,
  unitCode: "dona",
  fractional: false,
  kind: "piece",
  qty: "1.000",
  price: "4000.0000",
  vatRate: "12.00",
  vatExemptionCode: null,
  mxik: null,
  barcode: null,
  markingCode: null,
  markingWarning: false,
  ...over,
});

describe("receipt arithmetic (18 §4.1, qaror #26)", () => {
  it("line total is whole so'm and VAT is inside the price (US-M10-01)", () => {
    const t = priceLines([line({ qty: "2.000", price: "4000.0000" })], null);
    expect(t.lines[0]?.total).toBe("8000.00");
    expect(t.lines[0]?.vat).toBe("857.14"); // 8000 × 12 / 112
    expect(t.total).toBe("8000.00");
    expect(t.vat).toEqual([{ rate: "12.00", amount: "857.14" }]);
  });

  it("weighed qty × price rounds half up to whole so'm (QT-M09-06)", () => {
    const t = priceLines(
      [line({ qty: "1.250", price: "95000.0000", fractional: true, kind: "weighed" })],
      null,
    );
    expect(t.lines[0]?.total).toBe("118750.00");
  });

  it("zero-rate lines produce no VAT row", () => {
    const t = priceLines([line({ vatRate: "0.00", vatExemptionCode: "X1" })], null);
    expect(t.vat).toEqual([]);
  });

  it("a receipt discount is spread by line gross, rest to the largest line (18 §4.4)", () => {
    const lines = [
      line({ id: "a", qty: "1.000", price: "10000.0000" }),
      line({ id: "b", qty: "1.000", price: "3333.0000" }),
      line({ id: "c", qty: "1.000", price: "3333.0000" }),
    ];
    const t = priceLines(lines, { pct: "10.00", approval: null });
    // Σ gross 16666 → D = round(1666.6) = 1667
    expect(t.discount).toBe("1667.00");
    expect(t.lines.map((l) => l.discount)).toEqual(["1001.00", "333.00", "333.00"]);
    expect(t.total).toBe("14999.00");
  });

  it("allocateDiscount gives the rounding rest to the largest weight (later on ties)", () => {
    const parts = allocateDiscount(new Decimal(10), [new Decimal(1), new Decimal(1), new Decimal(1)]);
    expect(parts.map((p) => p.toString())).toEqual(["3", "3", "4"]);
  });

  it("effective manual percent and limit check", () => {
    const t = priceLines([line({ price: "10000.0000" })], { pct: "5.00", approval: null });
    expect(effectiveDiscountPct(t)).toBe("5.00");
    expect(withinLimit("5.00", "5.0000")).toBe(true);
    expect(withinLimit("6.00", "5.0000")).toBe(false);
    expect(withinLimit("50.00", null)).toBe(true);
    expect(withinLimit("1.00", undefined)).toBe(false);
    expect(withinLimit("0.00", undefined)).toBe(true);
  });

  it("parses quantities per unit kind (07 POS-02 lines[].qty)", () => {
    expect(parseQty("2", false)).toBe("2.000");
    expect(parseQty("1,5", false)).toBeNull();
    expect(parseQty("1,25", true)).toBe("1.250");
    expect(parseQty("0", true)).toBeNull();
    expect(parseQty("100000", false)).toBeNull();
    expect(parseQty("1.2345", true)).toBeNull();
  });

  it("qty step never goes under 1, helpers keep decimal strings", () => {
    expect(stepQty("1.000", -1)).toBe("1.000");
    expect(stepQty("2.000", 1)).toBe("3.000");
    expect(addQty("1.000", "2.000")).toBe("3.000");
    expect(price4("8500")).toBe("8500.0000");
    expect(normalizePct("12,5")).toBe("12.50");
    expect(normalizePct("101")).toBeNull();
    expect(changeOf("100000.00", "69000.00" as never)).toBe("31000.00");
    expect(changeOf("1000.00", "69000.00" as never)).toBeNull();
  });
});
