import { describe, expect, it } from "vitest";

import { ean13CheckDigit } from "#/barcode/index.ts";
import { lineTotal } from "#/money/index.ts";

import {
  addWeightQty,
  amountLabelMismatch,
  DEFAULT_WEIGHT_BARCODE_TEMPLATES,
  parseWeightBarcode,
  type WeightBarcodeTemplate,
  weightLineQty,
} from "./index.ts";

describe("weight barcodes — QT-M09-06 / QT-M01-22 (24 §6.3, US-M09-06)", () => {
  it("test_qt_m09_06_weight_label_22_grams: PLU 12345, 1.250 kg × 95 000 = 118 750", () => {
    const parsed = parseWeightBarcode("2212345012503", DEFAULT_WEIGHT_BARCODE_TEMPLATES);
    expect(parsed).toEqual({ ok: true, kind: "WEIGHT", prefix: "22", productCode: "12345", qty: "1.250" });
    if (!parsed.ok) throw new Error("unreachable");
    const qty = weightLineQty(parsed, "95000.00");
    expect(qty).toBe("1.250");
    expect(lineTotal(qty ?? "", "95000.00")).toBe("118750.00");
  });

  it("test_qt_m01_22_amount_label_21: 11 875 so'm ÷ 95 000 = 0.125", () => {
    const parsed = parseWeightBarcode("2112345118758", null);
    expect(parsed).toEqual({
      ok: true,
      kind: "AMOUNT",
      prefix: "21",
      productCode: "12345",
      amount: "11875.00",
    });
    if (!parsed.ok) throw new Error("unreachable");
    expect(weightLineQty(parsed, "95000.00")).toBe("0.125");
    expect(amountLabelMismatch("11875.00", "0.125", "95000.00")).toBe(false);
    expect(amountLabelMismatch("11875.00", "0.125", "96000.00")).toBe(true);
  });

  it("test_qt_m01_22_wrong_check_digit_rejected", () => {
    expect(parseWeightBarcode("2212345012504", undefined)).toEqual({ ok: false, reason: "check_digit" });
  });

  it("non-weight codes are left to the ordinary barcode lookup", () => {
    expect(parseWeightBarcode("4780000123456", null)).toEqual({ ok: false, reason: "no_template" });
    expect(parseWeightBarcode("22123", null)).toEqual({ ok: false, reason: "not_ean13" });
    expect(parseWeightBarcode("22123450125a3", null)).toEqual({ ok: false, reason: "not_ean13" });
  });

  it("tenant templates: custom prefix, 4-digit PLU, disabled template ignored", () => {
    const templates: WeightBarcodeTemplate[] = [
      {
        prefixes: ["27", "28"],
        item_code_len: 4,
        value_len: 6,
        value_kind: "WEIGHT",
        decimals: 3,
        enabled: true,
      },
      { prefixes: ["22"], item_code_len: 5, value_len: 5, value_kind: "WEIGHT", decimals: 3, enabled: false },
    ];
    const payload = "28" + "0042" + "002500";
    const code = payload + ean13CheckDigit(payload);
    expect(parseWeightBarcode(code, templates)).toEqual({
      ok: true,
      kind: "WEIGHT",
      prefix: "28",
      productCode: "0042",
      qty: "2.500",
    });
    expect(parseWeightBarcode("2212345012503", templates)).toEqual({ ok: false, reason: "no_template" });
  });

  it("two labels of one product sum into one line; zero price gives no qty", () => {
    expect(addWeightQty("1.250", "0.875")).toBe("2.125");
    expect(weightLineQty({ kind: "AMOUNT", amount: "1000.00" }, "0.00")).toBeNull();
  });
});
