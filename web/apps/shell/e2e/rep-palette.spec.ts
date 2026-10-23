import { expect, test } from "@playwright/test";

import { RepStub, collectCspViolations, json } from "./rep-stub.ts";

/**
 * WEB-12 `Ctrl+K` command palette (06 §1.9, 08 §9 — cmdk) on the production build: screens filtered by
 * permission, products (`GET /products?search=`) and counterparties (`GET /counterparties?search=`);
 * ↑ / ↓ / Enter navigate, Esc closes; the topbar search field opens it too. Strict CSP: no violation.
 */
const EMPTY_DASHBOARD = {
  period: "today",
  date_from: "2026-10-17",
  date_to: "2026-10-17",
  branch_id: "b-1",
  total_sales: "0.00",
  gross_sales: "0.00",
  returns_total: "0.00",
  receipt_count: 0,
  avg_receipt: "0.00",
  previous_total_sales: "0.00",
  net_profit: null,
  cash_on_hand: "0.00",
  by_branch: [],
  top_products: [],
  receivables: null,
  stock: null,
  alerts: [],
  unsynced_devices: 0,
  data_complete: true,
};

function stub(permissions: string[]) {
  const s = new RepStub(permissions, "b-1");
  s.on("GET", /^\/api\/v1\/products$/, ({ route, url }) =>
    json(route, 200, {
      items: (url.searchParams.get("search") ?? "").toLowerCase().startsWith("coc")
        ? [{ id: "p-1", name: "Coca-Cola 1.5L" }]
        : [],
      total: 1,
      page: 1,
      size: 8,
    }),
  )
    .on("GET", /^\/api\/v1\/counterparties$/, ({ route, url }) =>
      json(route, 200, {
        items: (url.searchParams.get("search") ?? "").toLowerCase().startsWith("ali")
          ? [{ id: "c-1", name: "Aliyev Botir", phone: "+998901234567", kind: "person" }]
          : [],
        total: 1,
        page: 1,
        size: 8,
      }),
    )
    .on("GET", /^\/api\/v1\/reports\/dashboard$/, ({ route }) => json(route, 200, EMPTY_DASHBOARD));
  return s;
}

test("WEB-12: Ctrl+K → screens, products, counterparties; Enter navigates", async ({ page }) => {
  const violations = collectCspViolations(page);
  const s = stub(["reports.sales.view", "reports.finance.view", "stock.view", "debts.payment.accept"]);
  await s.install(page);
  await page.goto("/app/reports");
  await expect(page.getByRole("banner").getByRole("heading", { name: "Hisobotlar markazi" })).toBeVisible();

  await page.keyboard.press("Control+K");
  const palette = page.getByRole("dialog", { name: "Tezkor qidiruv" });
  await expect(palette).toBeVisible();
  // Screens by permission: «Qoldiq va ko'chirish» (stock.view) yes, «Buxgalteriya» (accounting.post) no.
  await expect(palette.getByRole("option", { name: /Qoldiq va ko'chirish/ })).toBeVisible();
  await expect(palette.getByRole("option", { name: /Buxgalteriya/ })).toHaveCount(0);

  await page.keyboard.type("dash");
  await expect(palette.getByRole("option")).toHaveCount(1);
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/app\/dashboard$/);
  await expect(palette).toHaveCount(0);

  // The topbar search field opens it too; a product from the server search.
  await page.getByRole("button", { name: "Qidiruv" }).click();
  await page.keyboard.type("coca");
  const product = palette.getByRole("option", { name: /Coca-Cola 1\.5L/ });
  await expect(product).toBeVisible();
  expect(s.queriesOf("/api/v1/products").at(-1)?.get("search")).toBe("coca");
  await product.click();
  await expect(page).toHaveURL(/\/app\/catalog\/products\/p-1$/);

  // A counterparty → BO-06 (from a page without an open sheet).
  await page.goto("/app/reports");
  await expect(page.getByRole("banner").getByRole("heading", { name: "Hisobotlar markazi" })).toBeVisible();
  await page.keyboard.press("Control+K");
  await page.keyboard.type("ali");
  await palette.getByRole("option", { name: /Aliyev Botir/ }).click();
  await expect(page).toHaveURL(/\/app\/debts\?counterparty=c-1$/);

  // Esc closes.
  await page.keyboard.press("Control+K");
  await expect(palette).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(palette).toHaveCount(0);
  expect(violations).toEqual([]);
});

test("WEB-12: without stock.view / counterparty rights the palette searches nothing on the server", async ({
  page,
}) => {
  const s = stub(["reports.sales.view", "reports.finance.view"]);
  await s.install(page);
  await page.goto("/app/reports");
  await expect(page.getByRole("banner").getByRole("heading", { name: "Hisobotlar markazi" })).toBeVisible();
  await page.keyboard.press("Control+K");
  await page.keyboard.type("coca");
  await expect(page.getByText("Hech narsa topilmadi")).toBeVisible();
  expect(s.queriesOf("/api/v1/products")).toHaveLength(0);
  expect(s.queriesOf("/api/v1/counterparties")).toHaveLength(0);
});
