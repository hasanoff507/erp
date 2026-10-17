import { expect, test } from "@playwright/test";

import { RepStub, alert, collectCspViolations, json, nb, salesRow, type Body } from "./rep-stub.ts";

/**
 * BO-02 Dashboard (B4-SCR-BO-02; US-M12-01, US-M14-01 / QT-M14-01, US-M15-03 / QT-M15-03, QT-M12-04) and
 * the topbar bell (WEB-12, 06 §1.9) on the production build: KPI cards from `GET /reports/dashboard`
 * (sales vs yesterday, receipts, receivables, stock, net profit), «Savdo — oxirgi 7 kun» (recharts,
 * `GET /reports/sales?group_by=day`), «Diqqat talab qiladi» with links, per-branch + total table over
 * «Barcha filiallar», the «faqat sinxronlangan ma'lumot» banner, the period switch, and the bell — the
 * same alerts, each a link. Strict CSP: no violation while the chart and popover render.
 */
const PERMISSIONS = [
  "reports.sales.view",
  "reports.finance.view",
  "stock.view",
  "debts.payment.accept",
  "ai.chat.use",
];

const ALERTS = [
  alert("pending_approvals", "info", 4, null, "/app/approvals"),
  alert("low_stock", "warning", 11, null, "/app/warehouse/stock?lowStockOnly=1"),
  alert("fiscal_unacked", "critical", 1, null, "/app/settings/branches"),
];

function dashboard(period: string): Body {
  return {
    period,
    date_from: "2026-10-17",
    date_to: "2026-10-17",
    branch_id: null,
    total_sales: "4250000.00",
    gross_sales: "4300000.00",
    returns_total: "50000.00",
    receipt_count: 86,
    avg_receipt: "50000.00",
    previous_total_sales: "3800000.00",
    net_profit: "910000.00",
    cash_on_hand: "2100000.00",
    by_branch: [
      {
        branch_id: "b-1",
        name: "Chilonzor-3",
        sales: "3000000.00",
        receipt_count: 60,
        avg_receipt: "50000.00",
        profit: "610000.00",
        cash_on_hand: "1500000.00",
        low_stock_count: 8,
      },
      {
        branch_id: "b-2",
        name: "Yunusobod-1",
        sales: "1250000.00",
        receipt_count: 26,
        avg_receipt: "48076.92",
        profit: "300000.00",
        cash_on_hand: "600000.00",
        low_stock_count: 3,
      },
    ],
    top_products: [
      { product_id: "p-1", name: "Non Bekhurmon", unit_code: "pcs", qty: "140.000" },
      { product_id: "p-2", name: "Sut Oltin 1 l", unit_code: "pcs", qty: "85.000" },
    ],
    receivables: { total: "12400000.00", debtors_count: 37, overdue_count: 5, overdue_amount: "2100000.00" },
    stock: { value: "185300000.00", positions: 412, low_stock_count: 11, expiring_lots: 2 },
    alerts: ALERTS,
    unsynced_devices: 2,
    data_complete: false,
  };
}

function stub() {
  const s = new RepStub(PERMISSIONS, "all");
  s.on("GET", /^\/api\/v1\/reports\/dashboard$/, ({ route, url }) =>
    json(route, 200, dashboard(url.searchParams.get("period") ?? "today")),
  ).on("GET", /^\/api\/v1\/reports\/sales$/, ({ route, url }) => {
    const to = url.searchParams.get("date_to") ?? "";
    return json(route, 200, {
      date_from: url.searchParams.get("date_from"),
      date_to: to,
      branch_id: null,
      group_by: "day",
      rows: [salesRow(to, "4250000.00", 86)],
      total: salesRow("total", "4250000.00", 86),
      unsynced_devices: 2,
      data_complete: false,
    });
  });
  return s;
}

test("QT-M14-01 / QT-M15-03 / QT-M12-04: dashboard KPIs, chart, alerts, branches + total", async ({
  page,
}) => {
  const violations = collectCspViolations(page);
  const s = stub();
  await s.install(page);
  await page.goto("/app/dashboard");
  await expect(page.getByText("Xayrli kun, Akmal")).toBeVisible();

  const kpi = page.getByRole("group", { name: "Asosiy ko'rsatkichlar" });
  await expect(kpi).toContainText("Bugungi savdo");
  await expect(kpi).toContainText(nb("4 250 000 so'm"));
  await expect(kpi).toContainText("↑ 11,8% kecha bilan");
  await expect(kpi).toContainText("86");
  await expect(kpi).toContainText(nb("O'rtacha chek 50 000 so'm"));
  await expect(kpi).toContainText(nb("12 400 000 so'm"));
  await expect(kpi).toContainText("37 ta qarzdor · 5 ta muddati o'tgan");
  await expect(kpi).toContainText("11 ta tovar kam qolgan");
  // US-M15-03: «Sof foyda» = tushum − tannarx − xarajatlar; opens «Foyda va zarar».
  await expect(kpi.getByRole("link", { name: /Sof foyda/ })).toHaveAttribute(
    "href",
    "/app/reports?report=profit-and-loss",
  );
  await expect(kpi).toContainText(nb("910 000 so'm"));

  // QT-M12-04: some devices have not synced.
  await expect(page.getByText(/Faqat sinxronlangan ma'lumot: 2 ta qurilma/)).toBeVisible();

  // «Savdo — oxirgi 7 kun»: 7 day columns (recharts SVG); today (the only non-zero day) highlighted.
  const chart = page.getByTestId("bar-chart");
  await expect(chart.locator(".recharts-cartesian-axis-tick")).toHaveCount(7);
  await expect(chart.locator(".recharts-bar-rectangle .fill-primary")).toHaveCount(1);
  await expect(chart).toContainText("4,3");
  const sales = s.queriesOf("/api/v1/reports/sales")[0];
  expect(sales?.get("group_by")).toBe("day");
  expect(sales?.get("branch_id")).toBeNull();

  // «Diqqat talab qiladi»: most urgent first, each a link to its screen.
  const alerts = page.getByRole("list", { name: "Diqqat talab qiladi" }).first();
  await expect(alerts.getByRole("link").first()).toContainText("Fiskal cheklar tasdiqlanmagan");
  await expect(alerts.getByRole("link", { name: /Kam qolgan tovarlar/ })).toHaveAttribute(
    "href",
    "/app/warehouse/stock?lowStockOnly=1",
  );
  await expect(alerts).toContainText("11 ta tovar minimal darajadan kam qoldi");

  // QT-M14-01: each branch separately and the total.
  const branches = page.getByRole("table", { name: "Filiallar bo'yicha" });
  await expect(branches.getByRole("row").filter({ hasText: "Chilonzor-3" })).toContainText(
    nb("3 000 000 so'm"),
  );
  await expect(branches.getByRole("row").filter({ hasText: "Yunusobod-1" })).toContainText(
    nb("1 250 000 so'm"),
  );
  await expect(branches.getByRole("row").filter({ hasText: "Jami" })).toContainText(nb("4 250 000 so'm"));

  await expect(page.getByRole("list", { name: "Eng ko'p sotilgan" })).toContainText("Non Bekhurmon");

  // «Hafta» → period=week.
  await page.getByRole("group", { name: "Davr" }).getByRole("button", { name: "Hafta" }).click();
  await expect(kpi).toContainText("Haftalik savdo");
  expect(s.queriesOf("/api/v1/reports/dashboard").at(-1)?.get("period")).toBe("week");
  expect(violations).toEqual([]);
});

test("WEB-12 bell: alerts count, panel with links, follows a link", async ({ page }) => {
  const violations = collectCspViolations(page);
  const s = stub();
  await s.install(page);
  await page.goto("/app/reports");
  const bell = page.getByRole("button", { name: "Bildirishnomalar: 3 ta" });
  await expect(bell).toBeVisible();
  await expect(page.getByTestId("bell-badge")).toHaveText("3");
  await bell.click();
  const panel = page.getByRole("dialog", { name: "Bildirishnomalar" });
  await expect(panel.getByRole("link").first()).toContainText("Fiskal cheklar tasdiqlanmagan");
  await panel.getByRole("link", { name: /Tasdiqlash so'rovlari/ }).click();
  await expect(page).toHaveURL(/\/app\/approvals$/);
  await expect(panel).toHaveCount(0);
  expect(s.queriesOf("/api/v1/reports/dashboard")[0]?.get("period")).toBe("today");
  expect(violations).toEqual([]);
});

test("WEB-12 bell is hidden without reports.sales.view", async ({ page }) => {
  const s = new RepStub(["stock.view"], "b-1");
  await s.install(page);
  await page.goto("/app/catalog/products");
  await expect(
    page.getByRole("button", { name: "Menyuni ochish" }).or(page.getByRole("banner")),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: /^Bildirishnomalar/ })).toHaveCount(0);
  expect(s.queriesOf("/api/v1/reports/dashboard")).toHaveLength(0);
});
