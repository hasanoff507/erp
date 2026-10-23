/** POS-15 (07; US-M16-02; QT-M01-06/-07): counting and the variance note rule. */
import { describe, expect, it } from "vitest";

import type { Money } from "@shared/lib/money";

import { countView, noteRequired } from "./index.ts";

describe("POS-15 cash count", () => {
  it("test_qt_m01_06: counted = expected → variance 0, no note needed", () => {
    const v = countView({}, "500000.00", "500000.00" as Money);
    expect(v).toMatchObject({ counted: "500000.00", variance: "0.00", varianceKind: "match" });
    expect(noteRequired(v)).toBe(false);
  });

  it("test_qt_m01_07: 480 000 counted vs 500 000 expected → −20 000 shortage, note required", () => {
    const v = countView({ "200000": 2, "50000": 1, "20000": 1, "10000": 1 }, "", "500000.00" as Money);
    expect(v.fromDenominations).toBe(true);
    expect(v.pieces).toBe(5);
    expect(v.counted).toBe("480000.00");
    expect(v.variance).toBe("-20000.00");
    expect(v.varianceKind).toBe("short");
    expect(noteRequired(v)).toBe(true);
  });

  it("over-count is «ortiqcha»; nothing typed → no counted value", () => {
    expect(countView({}, "510000.00", "500000.00" as Money).varianceKind).toBe("over");
    expect(countView({}, "", "500000.00" as Money).counted).toBeNull();
  });
});
