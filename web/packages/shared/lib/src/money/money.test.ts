import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

import {
  InvalidMoneyError,
  addMoney,
  compareMoney,
  fromTiyin,
  lineTotal,
  money,
  subtractMoney,
  toTiyin,
  vatIncluded,
  type Money,
} from "./index.ts";

/**
 * ONE shared vector file for backend (pytest) and web (vitest) — 32 §3.3/§6.3, qaror #26.
 * Same file as backend/tests/unit/test_money.py: <repo>/shared/money-vectors.json.
 */
interface LineTotalCase {
  qty: string;
  unit_price: string;
  discount: string;
  expected: string;
}
interface VatCase {
  amount: string;
  rate: string;
  expected: string;
}
interface MoneyVectors {
  line_total: { cases: LineTotalCase[] };
  vat_from_gross: { cases: VatCase[] };
}

const VECTORS_URL = new URL("../../../../../../shared/money-vectors.json", import.meta.url);
const vectors = JSON.parse(readFileSync(VECTORS_URL, "utf-8")) as MoneyVectors;

describe("money — qaror #26 rounding (shared vectors)", () => {
  it("loads a non-empty shared vector file", () => {
    expect(vectors.line_total.cases.length).toBeGreaterThan(0);
    expect(vectors.vat_from_gross.cases.length).toBeGreaterThan(0);
  });

  it.each(vectors.line_total.cases)("line_total($qty × $unit_price − $discount) = $expected", (v) => {
    expect(lineTotal(v.qty, v.unit_price, money(v.discount))).toBe(v.expected);
  });

  it.each(vectors.vat_from_gross.cases)("vat_from_gross($amount @ $rate%) = $expected", (v) => {
    expect(vatIncluded(money(v.amount), v.rate)).toBe(v.expected);
  });

  it("23 §2.2 example: 10 kg × 12 000, VAT 12% included", () => {
    const total = lineTotal("10", "12000");
    const vat = vatIncluded(total, "12");
    expect([total, vat, subtractMoney(total, vat)]).toEqual(["120000.00", "12857.14", "107142.86"]);
  });
});

describe("money — string arithmetic", () => {
  it("normalises to 2 places with ROUND_HALF_UP", () => {
    expect(money("12000")).toBe("12000.00");
    expect(money("0.005")).toBe("0.01");
    expect(money("-0.005")).toBe("-0.01");
  });

  it("adds without float error", () => {
    expect(addMoney(money("0.10"), money("0.20"))).toBe("0.30");
    expect(addMoney()).toBe("0.00");
    expect(subtractMoney(money("100000.00"), money("69000.00"))).toBe("31000.00");
  });

  it("compares", () => {
    expect(compareMoney(money("10"), money("9.99"))).toBe(1);
    expect(compareMoney(money("10"), money("10.00"))).toBe(0);
  });

  it.each(["", " 1", "1e3", "1,5", "abc", "1.", ".5", "--1", "1.2.3", "NaN", "Infinity"])(
    "rejects %j",
    (bad) => {
      expect(() => money(bad)).toThrow(InvalidMoneyError);
    },
  );

  it("rejects non-strings at runtime", () => {
    expect(() => money(12 as unknown as string)).toThrow(InvalidMoneyError);
  });
});

describe("money — tiyin adapter boundary (24 §6.5)", () => {
  it("converts both ways", () => {
    expect(toTiyin("12000.00")).toBe(1_200_000);
    expect(toTiyin("0.01")).toBe(1);
    expect(fromTiyin(1_200_005)).toBe("12000.05");
    expect(fromTiyin(toTiyin("99000.00"))).toBe("99000.00" as Money);
  });

  it("refuses sub-tiyin precision", () => {
    expect(() => toTiyin("1.005")).toThrow(InvalidMoneyError);
  });
});
