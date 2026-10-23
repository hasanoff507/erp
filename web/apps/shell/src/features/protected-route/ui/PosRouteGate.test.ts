import { describe, expect, it } from "vitest";

import { isOfflineSessionCheck, offlinePosTarget } from "./PosRouteGate.tsx";

describe("PosRouteGate offline rule (B3-DoD-01)", () => {
  it("only a network failure of the first session check opens the POS from local state", () => {
    expect(isOfflineSessionCheck("unknown", { code: "NETWORK_ERROR" })).toBe(true);
    expect(isOfflineSessionCheck("unknown", { code: "INTERNAL_ERROR" })).toBe(false);
    expect(isOfflineSessionCheck("unknown", null)).toBe(false);
    expect(isOfflineSessionCheck("anonymous", { code: "NETWORK_ERROR" })).toBe(false);
    expect(isOfflineSessionCheck("authenticated", null)).toBe(false);
  });
});

describe("offline cold start (UX-05)", () => {
  it("a registered device without a cashier opens POS-01, other screens redirect there", () => {
    expect(offlinePosTarget("/pos/login", false)).toBeNull();
    expect(offlinePosTarget("/pos/settings/devices", false)).toBeNull();
    expect(offlinePosTarget("/pos", false)).toBe("/pos/login");
    expect(offlinePosTarget("/pos/sale", false)).toBe("/pos/login");
    expect(offlinePosTarget("/pos/sale", true)).toBeNull();
  });
});
