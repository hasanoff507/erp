import { describe, expect, it } from "vitest";

import type { PriceHistoryItem } from "@shared/models";

import { barcodeIssue, isMxikFormat } from "./codes.ts";
import {
  changePct,
  currentPriceOf,
  exceedsLimit,
  isPositiveAmount,
  priceAuthorOf,
  samePrice,
  scheduledPriceOf,
  toPrice4,
} from "./price.ts";

const item = (price: string, from: string, to: string | null): PriceHistoryItem => ({
  price,
  valid_from: from,
  valid_to: to,
  set_by: null,
  set_by_name: null,
  price_change_doc_id: null,
  branch_id: null,
});

describe("price helpers (19 §4, US-M09-01)", () => {
  // Newest first, like GET /products/{id}/prices.
  const history = [
    item("21000.0000", "2026-11-01T00:00:00Z", null),
    item("19000.0000", "2026-10-10T00:00:00Z", "2026-11-01T00:00:00Z"),
    item("18000.0000", "2026-09-01T00:00:00Z", "2026-10-10T00:00:00Z"),
  ];
  const now = new Date("2026-10-17T09:00:00Z");

  it("current = the entry in force now; scheduled = the nearest future one", () => {
    expect(currentPriceOf(history, now)?.price).toBe("19000.0000");
    expect(scheduledPriceOf(history, now)?.price).toBe("21000.0000");
    expect(currentPriceOf([], now)).toBeNull();
    expect(currentPriceOf(history, new Date("2026-12-01T00:00:00Z"))?.price).toBe("21000.0000");
  });

  it("change percent and the 10% limit use decimal strings", () => {
    expect(changePct("21000.0000", "23500.00")).toBe("11.9");
    expect(changePct("18000", "18000")).toBe("0.0");
    expect(changePct("20000", "18000.00")).toBe("-10.0");
    expect(changePct(null, "100.00")).toBeNull();
    expect(changePct("0.00", "100.00")).toBeNull();
    expect(exceedsLimit("11.9")).toBe(true);
    expect(exceedsLimit("-10.0")).toBe(false);
    expect(exceedsLimit("-10.1")).toBe(true);
    expect(exceedsLimit(null)).toBe(false);
  });

  it("API price has 4 places; equality ignores the scale; > 0 check", () => {
    expect(toPrice4("19000.00")).toBe("19000.0000");
    expect(samePrice("19000.00", "19000.0000")).toBe(true);
    expect(isPositiveAmount("0.00")).toBe(false);
    expect(isPositiveAmount("")).toBe(false);
    expect(isPositiveAmount("1.00")).toBe(true);
  });
});

describe("barcode / MXIK checks (19 §1)", () => {
  it("EAN check digit, allowed characters", () => {
    expect(barcodeIssue("4780012340047")).toBeNull();
    expect(barcodeIssue("4780012340048")).toBe("validation.barcode_check_digit");
    expect(barcodeIssue("ABC-123")).toBeNull();
    expect(barcodeIssue("bad code")).toBe("validation.barcode_format");
    expect(barcodeIssue("  ")).toBe("validation.required");
  });

  it("MXIK is exactly 17 digits", () => {
    expect(isMxikFormat("10101001001000000")).toBe(true);
    expect(isMxikFormat("1010100100100000")).toBe(false);
    expect(isMxikFormat("1010100100100000A")).toBe(false);
  });
});

describe("priceAuthorOf (19 §4 set_by_name)", () => {
  const by = (set_by: string | null, set_by_name: string | null) => ({ set_by, set_by_name });

  it("names the user who set the price", () => {
    expect(priceAuthorOf(by("u-2", "Dilshod Toshev"), "u-1")).toEqual({
      kind: "user",
      name: "Dilshod Toshev",
    });
  });

  it("says «you» for the viewer's own change", () => {
    expect(priceAuthorOf(by("u-1", "Akmal Karimov"), "u-1")).toEqual({ kind: "you" });
  });

  it("falls back to «staff» when the name is hidden (left the tenant) and «system» without an author", () => {
    expect(priceAuthorOf(by("u-9", null), "u-1")).toEqual({ kind: "staff" });
    expect(priceAuthorOf(by("u-9", "  "), null)).toEqual({ kind: "staff" });
    expect(priceAuthorOf(by(null, null), "u-1")).toEqual({ kind: "system" });
  });
});
