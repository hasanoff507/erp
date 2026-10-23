import { describe, expect, it } from "vitest";

import { formatMoney, formatPercent, formatQty } from "./index.ts";

const NBSP = " ";

describe("formatMoney — 08 §8", () => {
  it("whole so'm with NBSP grouping and Latin suffix", () => {
    expect(formatMoney("1240000.00")).toBe(`1${NBSP}240${NBSP}000 so'm`);
    expect(formatMoney("99000")).toBe(`99${NBSP}000 so'm`);
    expect(formatMoney("0")).toBe("0 so'm");
  });

  it("rounds ROUND_HALF_UP for display only", () => {
    expect(formatMoney("1240000.50")).toBe(`1${NBSP}240${NBSP}001 so'm`);
    expect(formatMoney("1240000.49")).toBe(`1${NBSP}240${NBSP}000 so'm`);
    expect(formatMoney("-0.4")).toBe("0 so'm");
  });

  it("uses the minus sign U+2212, never parentheses", () => {
    expect(formatMoney("-1240000")).toBe(`−1${NBSP}240${NBSP}000 so'm`);
  });

  it("precision 2 for fiscal/VAT views uses comma decimals", () => {
    expect(formatMoney("94500", { precision: 2 })).toBe(`94${NBSP}500,00 so'm`);
    expect(formatMoney("7392.857", { precision: 2 })).toBe(`7${NBSP}392,86 so'm`);
  });

  it("can omit the currency suffix", () => {
    expect(formatMoney("17640000", { withCurrency: false })).toBe(`17${NBSP}640${NBSP}000`);
  });

  it("never accepts JS numbers or garbage", () => {
    expect(() => formatMoney("1e6")).toThrow();
    expect(() => formatMoney(1000 as unknown as string)).toThrow();
  });
});

describe("formatQty / formatPercent — 08 §8", () => {
  it("piece units are whole, weight units have 3 decimals", () => {
    expect(formatQty("184", "integer")).toBe("184");
    expect(formatQty("1.25", "fractional")).toBe("1,250");
    expect(formatQty("58.4", "fractional")).toBe("58,400");
  });

  it("percent with comma", () => {
    expect(formatPercent("12.50")).toBe("12,5%");
    expect(formatPercent("12.00")).toBe("12%");
  });
});
