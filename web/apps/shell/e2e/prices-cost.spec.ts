import { expect, test, type Route } from "@playwright/test";

/**
 * BO-05 «Chakana narxlar» — «Tannarx» and «Ustama %» columns (07 BO-05, 19 §1 `current_cost` 4 dp,
 * `markup_pct` 2 dp; WEB-15) on the production build: whole so'm / comma-decimal percent (08 §8),
 * `null` → «—», a negative markup (below cost) is highlighted.
 */
const session = {
  user: { id: "u-1", full_name: "Akmal Karimov", phone_masked: "+998 90 *** ** 67" },
  tenant: { id: "t-1", name: "Baraka do'koni" },
  branches: [{ id: "b-1", name: "Chilonzor-3" }],
  roles: ["owner"],
  permissions: ["stock.view", "catalog.manage", "prices.edit", "prices.approve"],
  scope: ["stock", "catalog", "prices"],
  client_id: "web-bff",
  sub_status: "active",
  access_expires_at: 0,
};

function json(route: Route, status: number, body: unknown) {
  return route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
}

function product(id: string, name: string, cost: string | null, markup: string | null) {
  return {
    id,
    name,
    name_ru: null,
    category_id: null,
    unit_code: "pcs",
    mxik_code: null,
    package_code: null,
    vat_rate: "12.00",
    vat_exemption_code: null,
    is_marked: false,
    marking_group_code: null,
    is_weighed: false,
    min_stock: null,
    archived_at: null,
    version: 1,
    barcodes: [],
    current_price: "13500.0000",
    current_cost: cost,
    markup_pct: markup,
  };
}

test("BO-05: Tannarx / Ustama % from GET /products (null → «—»)", async ({ page }) => {
  await page.route("**/auth/session", (route) => json(route, 200, session));
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/v1/auth/csrf") return json(route, 200, { csrf_token: "csrf-e2e" });
    if (path === "/api/v1/units") return json(route, 200, { items: [{ code: "pcs", is_fractional: false }] });
    if (path === "/api/v1/product-categories")
      return json(route, 200, { items: [], total: 0, page: 1, size: 200 });
    if (path === "/api/v1/products") {
      const items = [
        product("p1", "Sut 2,5% 1 l", "10714.2857", "12.50"),
        product("p2", "Choy ko'k 100 g", null, null),
        product("p3", "Non", "14000.0000", "-13.85"),
      ];
      return json(route, 200, { items, total: items.length, page: 1, size: 20 });
    }
    if (/^\/api\/v1\/products\/p\d\/prices$/.test(path)) {
      return json(route, 200, {
        items: [
          {
            price: "13500.0000",
            valid_from: "2026-09-01T05:00:00Z",
            valid_to: null,
            set_by: null,
            set_by_name: null,
            price_change_doc_id: null,
            branch_id: null,
          },
        ],
        next_cursor: null,
      });
    }
    return json(route, 404, { error: { code: "NOT_FOUND", message_key: "errors.not_found", details: [] } });
  });

  await page.goto("/app/catalog/prices");
  const table = page.getByRole("table", { name: "Chakana narxlar" });
  await expect(table.getByRole("columnheader", { name: "Tannarx" })).toBeVisible();
  await expect(table.getByRole("columnheader", { name: "Ustama %" })).toBeVisible();

  const milk = table.getByRole("row").filter({ hasText: "Sut 2,5% 1 l" });
  await expect(milk.getByRole("cell").nth(1)).toHaveText("10 714");
  await expect(milk.getByRole("cell").nth(3)).toHaveText("12,5%");

  const tea = table.getByRole("row").filter({ hasText: "Choy ko'k 100 g" });
  await expect(tea.getByRole("cell").nth(1)).toHaveText("—");
  await expect(tea.getByRole("cell").nth(3)).toHaveText("—");

  const bread = table.getByRole("row").filter({ hasText: "Non" });
  await expect(bread.getByRole("cell").nth(3)).toHaveText("−13,85%");
  await expect(bread.getByRole("cell").nth(3).locator(".text-destructive-strong")).toBeVisible();
});
