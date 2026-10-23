import { describe, expect, it } from "vitest";

import { hasPermissions, permissionPrefix } from "./index.ts";

describe("permission checks: exact codes behind the scope filter (06 §1.9, 14 §10)", () => {
  const granted = {
    permissions: ["reports.sales.view", "reports.finance.view", "sales.create", "debts.create"],
    scopes: ["reports", "sales"],
  };

  it("maps codes to module prefixes", () => {
    expect(permissionPrefix("debts.payment.accept")).toBe("debts");
    expect(permissionPrefix("onec")).toBe("onec");
  });

  it("requires the exact code", () => {
    expect(hasPermissions(granted, { permission: ["reports.sales.view", "reports.finance.view"] })).toBe(
      true,
    );
    expect(hasPermissions(granted, { permission: "sales.void" })).toBe(false);
    expect(hasPermissions(granted, { anyOf: ["prices.edit", "sales.create"] })).toBe(true);
    expect(hasPermissions(granted, { anyOf: ["prices.edit"] })).toBe(false);
    expect(hasPermissions(granted, {})).toBe(true);
  });

  it("a code outside the token scope is not granted on the client", () => {
    expect(hasPermissions(granted, { permission: "debts.create" })).toBe(false);
  });
});
