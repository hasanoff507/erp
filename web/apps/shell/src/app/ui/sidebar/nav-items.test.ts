import { describe, expect, it } from "vitest";

import { hasPermissions } from "@shared/state/permissions";

import {
  firstAllowedNavItem,
  NAV_GROUPS,
  navItemForPath,
  navItemTarget,
  paletteSearchRights,
  requiresForPath,
} from "./nav-items.ts";

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

  it("«Tovarlar» opens the product catalogue without any price permission (06 §1.9)", () => {
    const products = navItemForPath("/app/catalog/products");
    expect(products?.key).toBe("products");
    // The card and the import screen belong to the same item; prices keep their own.
    expect(navItemForPath("/app/catalog/products/new")?.key).toBe("products");
    expect(navItemForPath("/app/catalog/products/import")?.key).toBe("products");
    expect(navItemForPath("/app/catalog/prices")?.key).toBe("catalogPrices");

    const visible = (permissions: string[]) =>
      NAV_GROUPS.flatMap((g) => g.items)
        .filter((item) => hasPermissions(access(permissions), item.requires))
        .map((item) => item.key);
    // Storekeeper (15 §2.2): catalog.manage + stock.view, no prices.* → «Tovarlar», not «Narxlar».
    const storekeeper = visible(["catalog.manage", "stock.view", "labels.print"]);
    expect(storekeeper).toContain("products");
    expect(storekeeper).not.toContain("catalogPrices");
    // The list needs stock.view (page + backend GET /products, 19 §1); catalog.manage alone is not enough.
    expect(visible(["catalog.manage"])).not.toContain("products");
    expect(visible(["stock.view"])).toContain("products"); // read-only list (GET /products)
    expect(visible(["sales.create"])).not.toContain("products");
    // The storekeeper still lands on stock — «Tovarlar» comes after it.
    expect(firstAllowedNavItem(access(["catalog.manage", "stock.view"]))?.to).toBe("/app/warehouse/stock");
    expect(firstAllowedNavItem(access(["catalog.manage"]))).toBeNull();
  });

  it("«Sozlamalar» opens the first Settings tab the user may open (06 §1.9 tabs)", () => {
    const settings = NAV_GROUPS.flatMap((g) => g.items).find((item) => item.key === "settings");
    if (!settings) throw new Error("settings item missing");
    const target = (permissions: string[]) => navItemTarget(settings, access(permissions));
    expect(target(["settings.tenant", "settings.users"])).toBe("/app/settings/tenant");
    expect(target(["settings.users"])).toBe("/app/settings/users");
    expect(target(["devices.revoke"])).toBe("/app/settings/users");
    expect(target(["cash_register.manage"])).toBe("/app/settings/branches");
    expect(target(["notifications.manage"])).toBe("/app/settings/telegram");
    expect(target(["billing.manage"])).toBe("/app/billing");
    expect(target(["onec.view"])).toBe("/app/settings/onec");
    // notifications.manage alone shows the item (Telegram tab).
    expect(hasPermissions(access(["notifications.manage"]), settings.requires)).toBe(true);
    expect(hasPermissions(access(["sales.create"]), settings.requires)).toBe(false);
    // Other items keep their route.
    const stock = navItemForPath("/app/warehouse/stock");
    if (stock) expect(navItemTarget(stock, access(["stock.view"]))).toBe("/app/warehouse/stock");
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

describe("Bosqich 3 back-office items (BO-07, BO-16)", () => {
  it("«QQS va davlat hisoboti» opens BO-07 for tax.vat.view, otherwise its own route", () => {
    const tax = NAV_GROUPS.flatMap((g) => g.items).find((i) => i.key === "taxReconciliation");
    expect(tax).toBeDefined();
    if (!tax) return;
    expect(navItemTarget(tax, access(["tax.vat.view"]))).toBe("/app/tax/vat");
    expect(navItemTarget(tax, access(["tax.compare.review"]))).toBe("/app/tax/reconciliation");
    expect(navItemForPath("/app/tax/vat")?.key).toBe("taxReconciliation");
  });

  it("«Tasdiqlash navbati» is shown for any approver code, card.manual_entry.approve included", () => {
    const approvals = navItemForPath("/app/approvals");
    expect(approvals?.key).toBe("approvals");
    if (!approvals) return;
    expect(hasPermissions(access(["card.manual_entry.approve"]), approvals.requires)).toBe(true);
    expect(hasPermissions(access(["cash.withdraw"]), approvals.requires)).toBe(true);
    expect(hasPermissions(access(["sales.create"]), approvals.requires)).toBe(false);
  });
});

describe("WEB-06: BO-06 rights — sidebar, route guard and Ctrl+K agree with the page guard", () => {
  it("test_web06_palette_hides_counterparties_without_debts_screen_right", () => {
    // the cashier taking debt payments has no BO-06 (debts-aging) right → no counterparty hits, no item
    const cashier = access(["sales.create", "debts.payment.accept"]);
    expect(paletteSearchRights(cashier).counterparties).toBe(false);
    expect(hasPermissions(cashier, requiresForPath("/app/debts"))).toBe(false);
    for (const right of ["reports.finance.view", "debts.approve"]) {
      const granted = access(["sales.create", right]);
      expect(paletteSearchRights(granted).counterparties).toBe(true);
      expect(hasPermissions(granted, requiresForPath("/app/debts"))).toBe(true);
    }
    // the BO-06 right alone does not read counterparties
    expect(paletteSearchRights(access(["reports.finance.view"]))).toEqual({
      products: false,
      counterparties: false,
    });
    expect(paletteSearchRights(access(["stock.view", "debts.approve"]))).toEqual({
      products: true,
      counterparties: true,
    });
  });
});
