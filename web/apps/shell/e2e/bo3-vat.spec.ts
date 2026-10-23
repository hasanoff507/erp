import { expect, test, type Page, type Route } from "@playwright/test";

/**
 * BO-07 «QQS ichki hisobi» (B3-SCR-BO-07, B3-EP-20#1/#2 web, US-M10-01) on the production build: the
 * «QQS va davlat hisoboti» sidebar item opens the BO-07 tab for `tax.vat.view`; KPI cards from
 * `GET /reports/vat-summary?period=` (a quarter = three monthly calls summed on the client); the
 * «QQS registri» from `GET /vat-moves` with kind / document filters. Backend stubbed per test.
 */
const session = {
  user: { id: "u-acc", full_name: "Gulnora Toshmatova", phone_masked: "+998 90 *** ** 67" },
  tenant: { id: "t-1", name: "Baraka do'koni" },
  branches: [{ id: "b-1", name: "Chilonzor-3" }],
  roles: ["accountant"],
  permissions: ["tax.vat.view", "accounting.post"],
  scope: ["tax", "accounting"],
  client_id: "web-bff",
  sub_status: "active",
  access_expires_at: 0,
};

function json(route: Route, status: number, body: unknown) {
  return route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
}

function summary(period: string) {
  return {
    period,
    regime: "vat",
    output_vat: "2210400.00",
    input_vat: "1500000.00",
    net_vat: "710400.00",
    pending_credit_red_invoices: 1,
    pending_credit_pct: "12.50",
    turnover_base: null,
    turnover_rate_pct: null,
    turnover_amount: null,
    tax_settlement_id: null,
  };
}

function move(id: string, period: string, patch: Record<string, unknown> = {}) {
  return {
    id,
    kind: "output",
    period,
    base_amount: "1000000.00",
    vat_amount: "120000.00",
    doc_type: "sales",
    doc_id: `d-${id}`,
    einvoice_id: null,
    created_at: `${period}-05T08:00:00Z`,
    ...patch,
  };
}

async function stubBackend(page: Page) {
  const summaryPeriods: string[] = [];
  const moveQueries: URLSearchParams[] = [];
  await page.route("**/auth/session", (route) => json(route, 200, session));
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    if (path === "/api/v1/auth/csrf") return json(route, 200, { csrf_token: "csrf-e2e" });
    if (path === "/api/v1/reports/vat-summary") {
      const period = url.searchParams.get("period") ?? "";
      summaryPeriods.push(period);
      return json(route, 200, summary(period));
    }
    if (path === "/api/v1/vat-moves") {
      moveQueries.push(url.searchParams);
      const period = url.searchParams.get("period") ?? "";
      const items =
        url.searchParams.get("doc_type") === "returns"
          ? [move("r1", period, { doc_type: "returns", base_amount: "-100000.00", vat_amount: "-12000.00" })]
          : [move("m1", period), move("m2", period, { kind: "input", doc_type: "goods_receipts" })];
      return json(route, 200, { items, next_cursor: null });
    }
    return json(route, 404, { error: { code: "NOT_FOUND", message_key: "errors.not_found", details: [] } });
  });
  return { summaryPeriods, moveQueries };
}

test("B3-SCR-BO-07: sidebar → QQS ichki hisobi; KPIs, red-invoice credit over 10%, register filters", async ({
  page,
}) => {
  const backend = await stubBackend(page);
  await page.goto("/app/accounting/journal");
  await page
    .getByRole("navigation", { name: "Asosiy menyu" })
    .getByRole("link", { name: "QQS va davlat hisoboti" })
    .click();
  await expect(page).toHaveURL(/\/app\/tax\/vat$/);
  await expect(
    page.getByRole("banner").getByRole("heading", { name: "QQS ichki hisob-kitobi" }),
  ).toBeVisible();

  await expect(page.getByText("QQS to'lovchi · 12%")).toBeVisible();
  await expect(page.getByText("Chiquvchi QQS (6410)")).toBeVisible();
  await expect(page.getByText("2 210 400,00 so'm")).toBeVisible();
  await expect(page.getByText("Byudjetga to'lanadi")).toBeVisible();
  await expect(page.getByText("710 400,00 so'm")).toBeVisible();
  const credit = page.getByRole("region", { name: "Kutilayotgan QQS krediti" });
  await expect(credit).toContainText("Qizil e-fakturalar: 1 ta");
  await expect(credit).toContainText("12,5%");
  await expect(
    page.getByText("Kutilayotgan QQS krediti ulushi 10% limitdan oshdi", { exact: false }),
  ).toBeVisible();
  expect(backend.summaryPeriods).toHaveLength(1);
  expect(backend.summaryPeriods[0]).toMatch(/^\d{4}-\d{2}$/);

  const register = page.getByRole("table", { name: "QQS registri" });
  await expect(register.getByRole("row")).toHaveCount(3);
  await expect(register.getByRole("row").nth(1)).toContainText("Sotuv");
  await expect(register.getByRole("row").nth(2)).toContainText("Kirim");
  await expect(page.getByRole("group", { name: "Ko'rsatilgan qatorlar jami" })).toContainText(
    "240 000,00 so'm",
  );

  // US-M10-01: returns reverse VAT — filter by document type.
  await page.getByRole("combobox", { name: "Hujjat" }).click();
  await page.getByRole("option", { name: "Qaytarish", exact: true }).click();
  await expect.poll(() => backend.moveQueries.at(-1)?.get("doc_type")).toBe("returns");
  await expect(register.getByRole("row").nth(1)).toContainText("−12 000,00");
});

test("BO-07: a quarter sums its three months (three summary calls)", async ({ page }) => {
  const backend = await stubBackend(page);
  await page.goto("/app/tax/vat");
  await expect(page.getByText("2 210 400,00 so'm")).toBeVisible();
  await page.getByRole("combobox", { name: "Davr" }).click();
  await page
    .getByRole("option", { name: /-chorak$/ })
    .first()
    .click();
  await expect(page.getByText("6 631 200,00 so'm")).toBeVisible();
  expect(backend.summaryPeriods).toHaveLength(4);
  await expect(page.getByText("Chorak uchun ulush hisoblanmaydi — oyni tanlang.")).toBeVisible();
});

test("BO-07: without tax.vat.view the screen is closed", async ({ page }) => {
  await page.route("**/auth/session", (route) =>
    json(route, 200, { ...session, permissions: ["tax.compare.review"], scope: ["tax"] }),
  );
  await page.route("**/api/v1/**", (route) =>
    json(route, 403, {
      error: { code: "PERMISSION_DENIED", message_key: "errors.permission_denied", details: [] },
    }),
  );
  await page.goto("/app/tax/vat");
  await expect(page.getByText("Sizda bu bo'limga kirish huquqi yo'q")).toBeVisible();
});
