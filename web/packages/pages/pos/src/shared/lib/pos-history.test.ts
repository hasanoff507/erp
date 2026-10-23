import { beforeEach, describe, expect, it } from "vitest";

import { posBackTarget, previousPosPath, recordPosPath, resetPosHistory } from "./pos-history.ts";

describe("POS back target (UX-09)", () => {
  beforeEach(() => resetPosHistory());

  it("returns to the screen the user came from", () => {
    recordPosPath("/pos/warehouse");
    recordPosPath("/pos/lookup");
    expect(posBackTarget("/pos/lookup", false)).toBe("/pos/warehouse");
    recordPosPath("/pos/sale");
    recordPosPath("/pos/sync");
    expect(previousPosPath("/pos/sync")).toBe("/pos/sale");
  });

  it("without history: seller → POS-02, storekeeper → hub", () => {
    recordPosPath("/pos/lookup");
    expect(posBackTarget("/pos/lookup", true)).toBe("/pos/sale");
    expect(posBackTarget("/pos/lookup", false)).toBe("/pos/warehouse");
  });
});
