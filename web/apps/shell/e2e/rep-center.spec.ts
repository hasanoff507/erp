import { expect, test } from "@playwright/test";

import { RepStub, collectCspViolations, json, nb, salesRow, type Body } from "./rep-stub.ts";

/**
 * BO-09 «Hisobotlar markazi» (B4-SCR-BO-09) on the production build: the catalogue opens the Bosqich 4
 * reports, each with its filters (period, «Barcha filiallar» / one branch) — «Kunlik savdo» (QT-M12-01:
 * total, receipts, average per day + «Jami»; chart), «Kassirlar bo'yicha savdo», «Top tovarlar» (QT-M12-02:
 * by quantity, most / least sold), «Foyda va zarar» (QT-M15-03: net profit = revenue − COGS − expenses by
 * category), «Chegirmalar va marja» (QT-M03-03), «Ombor qoldig'i» (QT-M04-03: every branch + total) and
 * «Qarzdorlik muddati»; QT-M12-04 «faqat sinxronlangan ma'lumot».
 */
const PERMISSIONS = ["reports.sales.view", "reports.finance.view", "stock.view", "tax.vat.view"];

const pnl: Body = {
  period: null,
  date_from: "2026-10-01",
  date_to: "2026-10-17",
  branch_id: null,
  discount_posting: "gross_9050",
  revenue: "40000000.00",
  returns: "500000.00",
  discounts: "300000.00",
  net_revenue: "39200000.00",
  cogs: "28000000.00",
  gross_profit: "11200000.00",
  gross_margin_pct: "28.57",
  other_income: "100000.00",
  expenses_by_category: [
    { category_id: "ec-1", category: "Ijara", account: "9420", source: "expenses", amount: "4000000.00" },
    { category_id: null, category: null, account: "9430", source: "write_offs", amount: "250000.00" },
  ],
  expenses_total: "4250000.00",
  net_profit: "7050000.00",
  by_branch: [],
  unsynced_devices: 0,
  data_complete: true,
};

function stub() {
  const s = new RepStub(PERMISSIONS, "all");
  s.on("GET", /^\/api\/v1\/reports\/sales$/, ({ route, url }) => {
    const cashier = url.searchParams.get("group_by") === "cashier";
    const rows = cashier
      ? [salesRow("u-1", "2500000.00", 50, "Dilnoza"), salesRow("u-2", "1750000.00", 36, "Bekzod")]
      : [salesRow("2026-10-16", "3100000.00", 61), salesRow("2026-10-17", "1150000.00", 25)];
    return json(route, 200, {
      date_from: url.searchParams.get("date_from"),
      date_to: url.searchParams.get("date_to"),
      branch_id: url.searchParams.get("branch_id"),
      group_by: cashier ? "cashier" : "day",
      rows,
      total: salesRow("total", "4250000.00", 86),
      unsynced_devices: 1,
      data_complete: false,
    });
  })
    .on("GET", /^\/api\/v1\/reports\/top-products$/, ({ route, url }) => {
      const items = [
        {
          product_id: "p-1",
          name: "Non Bekhurmon",
          unit_code: "pcs",
          qty_sold: "140.000",
          revenue: "560000.00",
        },
        {
          product_id: "p-2",
          name: "Sut Oltin 1 l",
          unit_code: "pcs",
          qty_sold: "85.000",
          revenue: "1020000.00",
        },
      ];
      return json(route, 200, {
        date_from: "2026-10-01",
        date_to: "2026-10-17",
        branch_id: null,
        order: url.searchParams.get("order"),
        items: url.searchParams.get("order") === "bottom" ? [...items].reverse() : items,
        unsynced_devices: 0,
        data_complete: true,
      });
    })
    .on("GET", /^\/api\/v1\/reports\/profit-and-loss$/, ({ route }) => json(route, 200, pnl))
    .on("GET", /^\/api\/v1\/reports\/discounts$/, ({ route, url }) => {
      const row = {
        group_key: "2026-10-17",
        group_label: null,
        sales_total: "4250000.00",
        discount_total: "300000.00",
        discount_net: "267857.14",
        revenue_net: "3527000.00",
        cost: "2800000.00",
        margin: "727000.00",
        margin_without_discounts: "994857.14",
        margin_pct: "20.61",
        margin_pct_without_discounts: "26.22",
      };
      return json(route, 200, {
        date_from: "2026-10-01",
        date_to: "2026-10-17",
        branch_id: null,
        group_by: url.searchParams.get("group_by"),
        rows: [row],
        total: { ...row, group_key: "total" },
        unsynced_devices: 0,
        data_complete: true,
      });
    })
    .on("GET", /^\/api\/v1\/reports\/stock$/, ({ route }) =>
      json(route, 200, {
        branch_id: null,
        consolidated: true,
        items: [
          {
            product_id: "p-1",
            name: "Coca-Cola 1.5L",
            name_ru: null,
            unit_code: "pcs",
            category_id: "c-1",
            category_name: "Ichimliklar",
            barcode: "4780001234567",
            is_marked: false,
            is_weighed: false,
            min_stock: "20.000",
            qty: "32.000",
            value: "384000.00",
            avg_cost: "12000.0000",
            below_min: false,
            by_branch: [
              {
                branch_id: "b-1",
                branch_name: "Chilonzor-3",
                qty: "12.000",
                value: "144000.00",
                below_min: true,
              },
              {
                branch_id: "b-2",
                branch_name: "Yunusobod-1",
                qty: "20.000",
                value: "240000.00",
                below_min: false,
              },
            ],
          },
        ],
        branches: [
          { branch_id: "b-1", name: "Chilonzor-3", value: "144000.00", positions: 1, below_min_count: 1 },
          { branch_id: "b-2", name: "Yunusobod-1", value: "240000.00", positions: 1, below_min_count: 0 },
        ],
        total: { value: "384000.00", positions: 1, below_min_count: 1 },
      }),
    )
    .on("GET", /^\/api\/v1\/reports\/debts-aging$/, ({ route, url }) =>
      json(route, 200, {
        as_of: url.searchParams.get("as_of"),
        direction: url.searchParams.get("direction"),
        summary: {
          total: "1450000.00",
          count: 2,
          buckets: [
            { bucket: "0-30", count: 1, amount: "450000.00" },
            { bucket: "31-60", count: 0, amount: "0.00" },
            { bucket: "60+", count: 1, amount: "1000000.00" },
          ],
        },
        rows: [
          {
            counterparty_id: "c-1",
            name: "Aliyev Botir",
            phone: "+998901234567",
            balance: "1000000.00",
            credit_limit: null,
            due_date: null,
            overdue_since: "2026-08-01",
            days_overdue: 77,
            bucket: "60+",
            promise_date: null,
            open_docs: 2,
            limit_exceeded_offline: false,
            doubtful_flag: false,
            doubtful_flag_id: null,
            last_payment_amount: null,
            last_payment_date: null,
          },
        ],
      }),
    );
  return s;
}

test("QT-M12-01 / QT-M12-02 / QT-M12-04: daily and cashier sales, top products", async ({ page }) => {
  const violations = collectCspViolations(page);
  const s = stub();
  await s.install(page);
  await page.goto("/app/reports");
  await page.getByRole("button", { name: /Kunlik savdo/ }).click();
  await expect(page).toHaveURL(/report=daily-sales/);

  const kpi = page.getByRole("group", { name: "Hisobot ko'rsatkichlari" });
  await expect(kpi).toContainText(nb("4 250 000 so'm"));
  await expect(kpi).toContainText("86");
  await expect(page.getByText(/Faqat sinxronlangan ma'lumot: 1 ta qurilma/)).toBeVisible();
  const table = page.getByRole("table", { name: "Kunlik savdo" });
  await expect(table.getByRole("row").filter({ hasText: "16.10.2026" })).toContainText(nb("3 100 000"));
  await expect(table.getByRole("row").filter({ hasText: "Jami" })).toContainText(nb("4 250 000"));
  await expect(page.getByTestId("bar-chart")).toBeVisible();
  // The recharts chart renders without a CSP violation (checked before the Radix Select below: its
  // viewport <style> is a separate @shared/ui matter — see the w-reports report).
  expect(violations).toEqual([]);
  const first = s.queriesOf("/api/v1/reports/sales")[0];
  expect(first?.get("group_by")).toBe("day");
  expect(first?.get("date_from")).toMatch(/^\d{4}-\d{2}-01$/);
  expect(first?.get("branch_id")).toBeNull();

  // One branch → branch_id; «Bugun» → one day.
  await page.getByRole("main").getByRole("combobox", { name: "Filial" }).click();
  await page.getByRole("option", { name: "Yunusobod-1" }).click();
  await expect.poll(() => s.queriesOf("/api/v1/reports/sales").at(-1)?.get("branch_id")).toBe("b-2");
  await page.getByRole("group", { name: "Davr" }).getByRole("button", { name: "Bugun" }).click();
  await expect
    .poll(() => {
      const q = s.queriesOf("/api/v1/reports/sales").at(-1);
      return q?.get("date_from") === q?.get("date_to");
    })
    .toBe(true);

  // «Kassirlar bo'yicha savdo».
  await page.getByRole("button", { name: "Hisobotlar" }).click();
  await page.getByRole("button", { name: /Kassirlar bo'yicha savdo/ }).click();
  await expect(page.getByRole("table", { name: "Kassirlar bo'yicha savdo" })).toContainText("Dilnoza");
  expect(s.queriesOf("/api/v1/reports/sales").at(-1)?.get("group_by")).toBe("cashier");

  // QT-M12-02: by quantity, most sold first; «Eng kam sotilgan» → order=bottom.
  await page.getByRole("button", { name: "Hisobotlar" }).click();
  await page.getByRole("button", { name: /Top tovarlar/ }).click();
  const top = page.getByRole("table", { name: "Top tovarlar" });
  await expect(top.getByRole("row").nth(1)).toContainText("Non Bekhurmon");
  await expect(top.getByRole("row").nth(1)).toContainText("140");
  await page.getByRole("button", { name: "Eng kam sotilgan" }).click();
  await expect(top.getByRole("row").nth(1)).toContainText("Sut Oltin 1 l");
  expect(s.queriesOf("/api/v1/reports/top-products").at(-1)?.get("order")).toBe("bottom");
});

test("QT-M15-03 / QT-M03-03: profit and loss by category; discounts and lost margin", async ({ page }) => {
  const s = stub();
  await s.install(page);
  await page.goto("/app/reports?report=profit-and-loss");
  const statement = page.getByRole("definition").first().locator("..").locator("..");
  await expect(statement).toContainText("Sof tushum");
  const pnlBox = page.locator("dl", { hasText: "Sotilgan tovar tannarxi" });
  await expect(pnlBox).toContainText(nb("39 200 000 so'm"));
  await expect(pnlBox).toContainText(nb("28 000 000 so'm"));
  await expect(pnlBox).toContainText("Ijara");
  await expect(pnlBox).toContainText("Hisobdan chiqarilgan tovarlar");
  await expect(pnlBox).toContainText(nb("4 250 000 so'm"));
  await expect(page.getByRole("group", { name: "Hisobot ko'rsatkichlari" })).toContainText(
    nb("7 050 000 so'm"),
  );
  await expect(page.getByRole("group", { name: "Hisobot ko'rsatkichlari" })).toContainText(
    "Yalpi marja 28,57%",
  );

  await page.getByRole("button", { name: "Hisobotlar" }).click();
  await page.getByRole("button", { name: /Chegirmalar va marja/ }).click();
  const kpi = page.getByRole("group", { name: "Hisobot ko'rsatkichlari" });
  await expect(kpi).toContainText(nb("300 000 so'm"));
  // Lost margin = margin without discounts − margin = 994 857,14 − 727 000 → 267 857.
  await expect(kpi).toContainText(nb("267 857 so'm"));
  await page.getByRole("button", { name: "Tovar" }).click();
  expect(s.queriesOf("/api/v1/reports/discounts").at(-1)?.get("group_by")).toBe("product");
});

test("QT-M04-03: «Ombor qoldig'i» over every branch — per branch and total; debts aging", async ({
  page,
}) => {
  const s = stub();
  await s.install(page);
  await page.goto("/app/reports?report=stock");
  const byBranch = page.getByRole("table", { name: "Filiallar bo'yicha qoldiq" });
  await expect(byBranch.getByRole("row").filter({ hasText: "Chilonzor-3" })).toContainText(nb("144 000"));
  await expect(byBranch.getByRole("row").filter({ hasText: "Jami" })).toContainText(nb("384 000"));
  const items = page.getByRole("table", { name: "Tovarlar qoldig'i" });
  const cola = items.getByRole("row").filter({ hasText: "Coca-Cola 1.5L" });
  await expect(cola).toContainText("Ichimliklar");
  await expect(cola).toContainText("12");
  await expect(cola).toContainText("20");
  await expect(cola).toContainText("32");
  expect(s.queriesOf("/api/v1/reports/stock")[0]?.get("branch_id")).toBeNull();

  await page.getByRole("button", { name: "Hisobotlar" }).click();
  await page.getByRole("button", { name: /Qarzdorlik muddati/ }).click();
  await expect(page.getByRole("table", { name: "Qarzdorlik muddati" })).toContainText("Aliyev Botir");
  await expect(page.getByRole("table", { name: "Qarzdorlik muddati" })).toContainText("77");
  await page.getByRole("button", { name: "Men qarzdorman" }).click();
  expect(s.queriesOf("/api/v1/reports/debts-aging").at(-1)?.get("direction")).toBe("payable");
});
