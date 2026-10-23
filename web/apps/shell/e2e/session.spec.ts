import { expect, test, type Page, type Route } from "@playwright/test";

/** Authenticated shell against a stubbed GET /auth/session (backend SessionInfo shape). */
const session = {
  user: { id: "u-1", full_name: "Akmal Karimov", phone_masked: "+998 90 *** ** 67" },
  tenant: { id: "t-1", name: "Baraka do'koni" },
  branches: [
    { id: "b-1", name: "Chilonzor-3" },
    { id: "b-2", name: "Yunusobod-1" },
  ],
  roles: ["owner"],
  // stock.view deliberately missing → «Qoldiq va ko'chirish» must not be in the sidebar (06 §1.9).
  permissions: ["reports.sales.view", "reports.finance.view", "ai.chat.use", "sales.create"],
  scope: ["reports", "ai", "sales", "stock"],
  client_id: "web-bff",
  sub_status: "active",
  access_expires_at: 0,
};

const envelope = (code: string, key: string) =>
  JSON.stringify({ error: { code, message_key: key, details: [], request_id: "e2e" } });

async function stubSession(page: Page, answer: () => { status: number; body: string }) {
  await page.route("**/auth/session", (route: Route) => {
    const { status, body } = answer();
    return route.fulfill({ status, contentType: "application/json", body });
  });
}

test("branch step after login, then the back-office shows real names", async ({ page }) => {
  await stubSession(page, () => ({ status: 200, body: JSON.stringify(session) }));
  await page.goto("/app/dashboard");

  // Several branches and none chosen → BO-01 branch step (07 `branchId`).
  await expect(page).toHaveURL(/\/login\?next=%2Fapp%2Fdashboard/);
  const step = page.getByRole("region", { name: "Filial tanlash" });
  await expect(step).toBeVisible();
  await step.getByLabel("Filial").selectOption({ label: "Yunusobod-1" });
  await step.getByRole("button", { name: "Davom etish" }).click();

  await expect(page).toHaveURL(/\/app\/dashboard$/);
  await expect(page.getByText("Xayrli kun, Akmal")).toBeVisible();
  const nav = page.getByRole("navigation", { name: "Asosiy menyu" });
  await expect(nav.getByText("Baraka do'koni")).toBeVisible();
  await expect(nav.getByText("Akmal Karimov")).toBeVisible();
  await expect(nav.getByText("Egasi")).toBeVisible();
  await expect(nav.getByRole("link", { name: "Dashboard" })).toBeVisible();
  await expect(nav.getByRole("link", { name: "Qoldiq va ko'chirish" })).toHaveCount(0);
  await expect(page.getByLabel("Filial")).toHaveValue("b-2");
  await expect(page.getByLabel("Filial").locator("option")).toHaveText([
    "Barcha filiallar",
    "Chilonzor-3",
    "Yunusobod-1",
  ]);
});

test("heartbeat: a later 401 sends the user back to /login (14 §16.1.4)", async ({ page }) => {
  await page.clock.install();
  let answer = { status: 200, body: JSON.stringify({ ...session, branches: [session.branches[0]] }) };
  await stubSession(page, () => answer);
  await page.goto("/app/dashboard");
  await expect(page.getByText("Xayrli kun, Akmal")).toBeVisible();

  answer = { status: 401, body: envelope("UNAUTHORIZED", "errors.unauthorized") };
  await page.clock.runFor(31_000);
  await expect(page).toHaveURL(/\/login\?next=%2Fapp%2Fdashboard/);
});

test("no active membership (403 PERMISSION_DENIED) is explained on /login", async ({ page }) => {
  await stubSession(page, () => ({
    status: 403,
    body: envelope("PERMISSION_DENIED", "errors.permission_denied"),
  }));
  await page.goto("/login");
  await expect(page.getByText("Bu do'konda faol a'zoligingiz yo'q.", { exact: false })).toBeVisible();
});
