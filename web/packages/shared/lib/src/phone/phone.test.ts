import { describe, expect, it } from "vitest";

import { formatPhone, isCompleteNationalPhone, maskNationalPhone, toE164 } from "./index.ts";

describe("phone — +998 XX XXX XX XX", () => {
  it("masks progressively", () => {
    expect(maskNationalPhone("9")).toBe("9");
    expect(maskNationalPhone("901")).toBe("90 1");
    expect(maskNationalPhone("901234567")).toBe("90 123 45 67");
    expect(maskNationalPhone("90-123-45-67-89")).toBe("90 123 45 67");
  });

  it("drops a pasted country code", () => {
    expect(maskNationalPhone("+998 90 123 45 67")).toBe("90 123 45 67");
    expect(toE164("+998901234567")).toBe("+998901234567");
  });

  it("validates completeness and formats for display", () => {
    expect(isCompleteNationalPhone("90 123 45 6")).toBe(false);
    expect(isCompleteNationalPhone("90 123 45 67")).toBe(true);
    expect(formatPhone("+998901234567")).toBe("+998 90 123 45 67");
  });
});
