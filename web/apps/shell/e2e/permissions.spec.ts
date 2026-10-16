import { expect, test, type Page } from "@playwright/test";

/**
 * Route-level permissions (24 §2, 06 §1.9): a screen hidden from the sidebar cannot be opened by URL
 * (NoPermissionState), and `/` lands on the first screen the user may open. GET /auth/session is
 * stubbed per role (backend SessionInfo shape; a single branch → no branch step).
 */
function sessionFor(role: string, permissions: string[]) {
  return {
    user: { id: "u-2", full_name: "Dilshod Toshev", phone_masked: "+998 91 *** ** 12" },
    tenant: { id: "t-1", name: "Baraka do'koni" },
    branches: [{ id: "b-1", name: "Chilonzor-3" }],
    roles: [role],
    permissions,
    scope: [...new Set(permissions.map((code) => code.split(".")[0]))],
    client_id: "web-bff",
    sub_status: "active",
    access_expires_at: 0,
  };
}

async function signInAs(page: Page, role: string, permissions: string[]) {
  const body = JSON.stringify(sessionFor(role, permissions));
  await page.route("**/auth/session", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body }),
  );
}

const NO_PERMISSION = "Sizda bu bo'limga kirish huquqi yo'q";

test("storekeeper: /app/dashboard by URL shows NoPermissionState; / lands on stock", async ({ page }) => {
  await signInAs(page, "storekeeper", ["stock.view", "purchases.receive", "labels.print"]);

  await page.goto("/app/dashboard");
  await expect(page).toHaveURL(/\/app\/dashboard$/);
  await expect(page.getByText(NO_PERMISSION)).toBeVisible();
  await expect(page.getByText("Xayrli kun", { exact: false })).toHaveCount(0);
  // The layout stays: the sidebar offers only what the user may open.
  const nav = page.getByRole("navigation", { name: "Asosiy menyu" });
  await expect(nav.getByRole("link", { name: "Qoldiq va ko'chirish" })).toBeVisible();
  await expect(nav.getByRole("link", { name: "Dashboard" })).toHaveCount(0);

  // A sub-path of a forbidden item is forbidden too (prefix match).
  await page.goto("/app/reports/sales");
  await expect(page.getByText(NO_PERMISSION)).toBeVisible();

  await page.goto("/");
  await expect(page).toHaveURL(/\/app\/warehouse\/stock$/);
  await expect(page.getByText(NO_PERMISSION)).toHaveCount(0);

  await page.goto("/app");
  await expect(page).toHaveURL(/\/app\/warehouse\/stock$/);
});

test("storekeeper with catalog.manage but no price rights reaches «Tovarlar» from the sidebar (06 §1.9)", async ({
  page,
}) => {
  await signInAs(page, "storekeeper", ["stock.view", "catalog.manage", "labels.print"]);
  await page.route("**/api/v1/**", (route) => {
    const path = new URL(route.request().url()).pathname;
    const body =
      path === "/api/v1/products" || path === "/api/v1/product-categories"
        ? { items: [], total: 0, page: 1, size: 25 }
        : { items: [] };
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
  });

  await page.goto("/app/warehouse/stock");
  const nav = page.getByRole("navigation", { name: "Asosiy menyu" });
  await expect(nav.getByRole("link", { name: "Tovarlar va narxlar" })).toHaveCount(0);
  await nav.getByRole("link", { name: "Tovarlar", exact: true }).click();
  await expect(page).toHaveURL(/\/app\/catalog\/products$/);
  await expect(page.getByRole("heading", { level: 1, name: "Tovarlar" })).toBeVisible();
  await expect(page.getByText(NO_PERMISSION)).toHaveCount(0);
  await expect(nav.getByRole("link", { name: "Tovarlar", exact: true })).toHaveAttribute(
    "aria-current",
    "page",
  );
});

test("«Tovarlar» needs stock.view — catalog.manage alone neither shows nor opens it (19 §1)", async ({
  page,
}) => {
  await signInAs(page, "custom", ["catalog.manage", "labels.print"]);
  await page.route("**/api/v1/**", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ items: [] }) }),
  );
  await page.goto("/app/catalog/products");
  await expect(page.getByText(NO_PERMISSION)).toBeVisible();
  const nav = page.getByRole("navigation", { name: "Asosiy menyu" });
  await expect(nav.getByRole("link", { name: "Tovarlar", exact: true })).toHaveCount(0);
});

test("«Sozlamalar» links to the first Settings tab the user may open", async ({ page }) => {
  await signInAs(page, "admin", ["settings.users", "notifications.manage"]);
  await page.route("**/api/v1/**", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ items: [] }) }),
  );
  await page.goto("/app/settings/users");
  const nav = page.getByRole("navigation", { name: "Asosiy menyu" });
  await expect(nav.getByRole("link", { name: "Sozlamalar" })).toHaveAttribute("href", "/app/settings/users");
});

test("cashier: / opens the web POS; back-office screens are refused", async ({ page }) => {
  await signInAs(page, "cashier", ["sales.create"]);

  await page.goto("/");
  await expect(page).toHaveURL(/\/pos\/login$/);
  await expect(page.getByText(NO_PERMISSION)).toHaveCount(0);

  await page.goto("/app/settings/tenant");
  await expect(page.getByText(NO_PERMISSION)).toBeVisible();
});

test("accountant without sales.create cannot open /pos by URL", async ({ page }) => {
  await signInAs(page, "accountant", ["reports.sales.view", "reports.finance.view"]);

  await page.goto("/pos/sale");
  await expect(page.getByText(NO_PERMISSION)).toBeVisible();

  await page.goto("/");
  await expect(page).toHaveURL(/\/app\/dashboard$/);
  await expect(page.getByText("Xayrli kun, Dilshod")).toBeVisible();
});

test("no screen at all → NoPermissionState instead of a redirect loop", async ({ page }) => {
  await signInAs(page, "cashier", []);
  await page.goto("/");
  await expect(page.getByText(NO_PERMISSION)).toBeVisible();
  await expect(page).toHaveURL(/localhost:4173\/$/);
});
