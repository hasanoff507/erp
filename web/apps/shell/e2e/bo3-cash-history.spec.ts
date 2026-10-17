import { expect, test, type Page, type Route } from "@playwright/test";

/**
 * BO-09 «Hisobotlar markazi» → «Kassa / smena tarixi» (B3-SCR-BO-09, US-M16-03, QT-M16-04) on the
 * production build: the catalogue shows only permitted reports (the rest «Tez orada»); for the chosen
 * period every shift shows opening / cash sales / put in / taken out / expected / counted / variance;
 * a row opens the Z-report with the card split «integratsiyalangan / terminalsiz» and the shift's cash
 * movements (why, comment). Backend stubbed per test.
 */
const session = {
  user: { id: "u-owner", full_name: "Akmal Karimov", phone_masked: "+998 90 *** ** 67" },
  tenant: { id: "t-1", name: "Baraka do'koni" },
  branches: [{ id: "b-1", name: "Chilonzor-3" }],
  roles: ["owner"],
  permissions: ["reports.sales.view", "reports.finance.view", "tax.vat.view"],
  scope: ["reports", "tax"],
  client_id: "web-bff",
  sub_status: "active",
  access_expires_at: 0,
};

function json(route: Route, status: number, body: unknown) {
  return route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
}

const methods = {
  cash: "1450000.00",
  card: "820000.00",
  uzqr: "0.00",
  click: "0.00",
  payme: "0.00",
  uzum: "0.00",
  debt: "0.00",
};

const shift = {
  id: "sh-41",
  shift_no: 41,
  branch_id: "b-1",
  cash_register_id: "cr-1",
  device_id: "d-1",
  status: "closed",
  opening_cash: "200000.00",
  opened_by: "u-cashier",
  opened_at: "2026-10-16T03:00:00Z",
  closed_by: "u-cashier",
  closed_at: "2026-10-16T15:00:00Z",
  expected_cash: "1400000.00",
  counted_cash: "1395000.00",
  variance: "-5000.00",
  variance_note: "Qaytim xatosi",
  counted_card_total: "820000.00",
  comment: null,
  running_totals: null,
  z_report: {
    expected_cash: "1400000.00",
    counted_cash: "1395000.00",
    variance: "-5000.00",
    totals_by_method: methods,
    card_split: { integrated: "700000.00", manual: "120000.00" },
    card_settlements: [
      {
        card_terminal_id: "t-1",
        net_total: "700000.00",
        expected_total: "700000.00",
        variance: "0.00",
        status: "matched",
      },
    ],
    vat_total: "243000.00",
    discount_total: "15000.00",
    returns_total: "36000.00",
    sales_count: 87,
    returns_count: 2,
  },
};

const movement = (id: string, direction: string, reason: string, amount: string, comment: string | null) => ({
  id,
  number: `KH-${id}`,
  status: "posted",
  doc_date: "2026-10-16",
  branch_id: "b-1",
  cash_register_id: "cr-1",
  shift_id: "sh-41",
  direction,
  amount,
  reason,
  account: null,
  counterparty_id: null,
  employee_id: null,
  comment,
  created_by: "u-cashier",
  created_at: "2026-10-16T10:00:00Z",
  posted_at: "2026-10-16T10:00:00Z",
  cancelled_at: null,
  cancel_reason: null,
  device_id: "d-1",
});

async function stubBackend(page: Page) {
  const historyQueries: { register: string; from: string | null; to: string | null }[] = [];
  await page.route("**/auth/session", (route) => json(route, 200, session));
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    if (path === "/api/v1/auth/csrf") return json(route, 200, { csrf_token: "csrf-e2e" });
    if (path === "/api/v1/cash-registers") {
      return json(route, 200, {
        items: [
          {
            id: "cr-1",
            branch_id: "b-1",
            name: "Kassa 1",
            kind: "web",
            fiscal_module_id: null,
            txkm_contract_ref: null,
            fiscal_agent_id: null,
            fiscal_local_device_id: null,
            ofd_status: "active",
            fm_state: "ok",
            last_unacked_receipt_at: null,
            fm_receipts_pending: null,
            tax_registered_at: null,
            archived_at: null,
            version: 1,
          },
          {
            id: "cr-2",
            branch_id: "b-1",
            name: "Kassa 2",
            kind: "web",
            fiscal_module_id: null,
            txkm_contract_ref: null,
            fiscal_agent_id: null,
            fiscal_local_device_id: null,
            ofd_status: "active",
            fm_state: "ok",
            last_unacked_receipt_at: null,
            fm_receipts_pending: null,
            tax_registered_at: null,
            archived_at: null,
            version: 1,
          },
        ],
      });
    }
    const history = /^\/api\/v1\/cash-registers\/(cr-\d)\/cash-history$/.exec(path);
    if (history) {
      const register = history[1] ?? "";
      historyQueries.push({
        register,
        from: url.searchParams.get("date_from"),
        to: url.searchParams.get("date_to"),
      });
      if (register === "cr-2") return json(route, 200, { items: [] });
      return json(route, 200, {
        items: [
          {
            shift_id: "sh-41",
            shift_no: 41,
            status: "closed",
            opened_at: "2026-10-16T03:00:00Z",
            closed_at: "2026-10-16T15:00:00Z",
            opening_cash: "200000.00",
            cash_sales: "1450000.00",
            cash_in: "50000.00",
            cash_out: "300000.00",
            expected_cash: "1400000.00",
            counted_cash: "1395000.00",
            variance: "-5000.00",
            variance_note: "Qaytim xatosi",
            counted_card_total: "820000.00",
          },
          {
            shift_id: "sh-42",
            shift_no: 42,
            status: "open",
            opened_at: "2026-10-17T03:00:00Z",
            closed_at: null,
            opening_cash: "200000.00",
            cash_sales: "310000.00",
            cash_in: "0.00",
            cash_out: "0.00",
            expected_cash: "510000.00",
            counted_cash: null,
            variance: null,
            variance_note: null,
            counted_card_total: null,
          },
        ],
      });
    }
    if (path === "/api/v1/shifts/sh-41") return json(route, 200, shift);
    if (path === "/api/v1/cash-movements") {
      return json(route, 200, {
        items: [
          movement("1", "in", "deposit", "50000.00", "Mayda pul"),
          movement("2", "out", "collection", "300000.00", "Inkassator Bek"),
        ],
        next_cursor: null,
      });
    }
    return json(route, 404, { error: { code: "NOT_FOUND", message_key: "errors.not_found", details: [] } });
  });
  return { historyQueries };
}

test("QT-M16-04 «Kassa / smena tarixi»: per shift opening / sales / in / out / expected / counted / variance", async ({
  page,
}) => {
  const backend = await stubBackend(page);
  await page.goto("/app/reports");
  await expect(page.getByRole("banner").getByRole("heading", { name: "Hisobotlar markazi" })).toBeVisible();
  // Not yet built reports are visible but marked «Tez orada».
  await expect(page.getByText("Foyda va zarar")).toBeVisible();
  await expect(page.getByText("Tez orada").first()).toBeVisible();

  await page.getByRole("button", { name: /Kassa \/ smena tarixi/ }).click();
  await expect(page).toHaveURL(/report=cash-history/);
  const table = page.getByRole("table", { name: "Smenalar bo'yicha naqd pul" });
  const closed = table.getByRole("row").filter({ hasText: "№41" });
  for (const value of [
    "200 000",
    "1 450 000",
    "50 000",
    "300 000",
    "1 400 000",
    "1 395 000",
    "−5 000",
    "Qaytim xatosi",
    "820 000",
  ]) {
    await expect(closed).toContainText(value);
  }
  await expect(table.getByRole("row").filter({ hasText: "№42" })).toContainText("Ochiq");
  await expect(page.getByRole("group", { name: "Davr jami" })).toContainText("1 760 000 so'm");
  expect(backend.historyQueries[0]?.register).toBe("cr-1");
  expect(backend.historyQueries[0]?.from).toMatch(/^\d{4}-\d{2}-01$/);

  // The shift panel: Z-report, card split, settlement, cash movements «kim, nega».
  await closed.click();
  const panel = page.getByRole("region", { name: "Smena №41" });
  await expect(panel).toContainText("Karta (integratsiyalangan)");
  await expect(panel).toContainText("700 000 so'm");
  await expect(panel).toContainText("Karta (terminalsiz)");
  await expect(panel).toContainText("120 000 so'm");
  await expect(panel).toContainText("Mos");
  const movements = panel.getByRole("list", { name: "Kassa pul harakati" });
  await expect(movements).toContainText("Qo'yildi");
  await expect(movements).toContainText("Kassaga qo'yish");
  await expect(movements).toContainText("Mayda pul");
  await expect(movements).toContainText("Olindi");
  await expect(movements).toContainText("Inkassatsiya");

  // Quick period «Bugun» and another register reload the history.
  await page.getByRole("group", { name: "Davr" }).getByRole("button", { name: "Bugun" }).click();
  await expect.poll(() => backend.historyQueries.at(-1)?.from).toBe(backend.historyQueries.at(-1)?.to);
  await page.getByRole("combobox", { name: "Kassa" }).click();
  await page.getByRole("option", { name: "Kassa 2" }).click();
  await expect(page.getByText("Bu davrda smena yo'q")).toBeVisible();
  await expect(page.getByRole("region", { name: "Smena №41" })).toHaveCount(0);
});
