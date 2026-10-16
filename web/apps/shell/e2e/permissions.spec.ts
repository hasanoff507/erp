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
