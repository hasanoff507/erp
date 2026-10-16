import { describe, expect, it } from "vitest";

import { firstAllowedNavItem, NAV_GROUPS, navItemForPath, requiresForPath } from "./nav-items.ts";

const access = (permissions: string[]) => ({
  permissions,
  scopes: [...new Set(permissions.map((code) => code.slice(0, code.indexOf("."))))],
});

describe("route permissions come from the sidebar definition (24 §2, 06 §1.9)", () => {
  it("maps a path to its sidebar item's requirement by longest prefix", () => {
    const dashboard = NAV_GROUPS[0]?.items[0];
    expect(requiresForPath("/app/dashboard")).toBe(dashboard?.requires);
    expect(requiresForPath("/app/dashboard/")).toEqual(dashboard?.requires);
    expect(requiresForPath("/app/warehouse/stock/123")).toEqual({ permission: "stock.view" });
    expect(requiresForPath("/app/tax/vat")).toEqual(navItemForPath("/app/tax/reconciliation")?.requires);
    expect(requiresForPath("/app/billing")).toEqual(navItemForPath("/app/settings/tenant")?.requires);
    expect(requiresForPath("/pos/sale")).toEqual({ permission: "sales.create" });
    expect(requiresForPath("/pos")).toEqual({ permission: "sales.create" });
  });

  it("does not match on a bare string prefix", () => {
    expect(navItemForPath("/app/dashboardx")).toBeNull();
    expect(navItemForPath("/position")).toBeNull();
  });

  it("paths without a sidebar item only need a session", () => {
    expect(requiresForPath("/app")).toEqual({});
    expect(requiresForPath("/app/unknown")).toEqual({});
  });

  it("the default route is the first permitted sidebar item", () => {
    const owner = access(["reports.sales.view", "reports.finance.view", "sales.create"]);
    expect(firstAllowedNavItem(owner)?.to).toBe("/app/dashboard");

    const cashier = access(["sales.create", "sales.return"]);
    expect(firstAllowedNavItem(cashier)?.to).toBe("/pos/login");

    const storekeeper = access(["stock.view", "purchases.receive"]);
    expect(firstAllowedNavItem(storekeeper)?.to).toBe("/app/warehouse/stock");

    // reports.sales.view alone is not enough for the dashboard (both codes) → «Hisobotlar».
    expect(firstAllowedNavItem(access(["reports.sales.view"]))?.to).toBe("/app/reports");

    expect(firstAllowedNavItem(access([]))).toBeNull();
    // A code outside the token scope is not granted.
    expect(firstAllowedNavItem({ permissions: ["stock.view"], scopes: [] })).toBeNull();
  });
});
