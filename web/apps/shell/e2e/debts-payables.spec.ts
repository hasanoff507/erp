import { expect, test } from "@playwright/test";

import { Stub, json, type Body } from "./warehouse-stub.ts";

/**
 * BO-04 fifth tab «Men qarzdorman» (07 BO-04; US-M08-11, QT-M08-14 web half): the payable aging — whom, how much,
 * when (earliest due first) — the supplier's payable book, and «To'lash» → the supplier payment tab.
 */
const FORM_TITLE = "Yetkazib beruvchiga to'lov";
const PERMISSIONS = ["stock.view", "purchases.pay", "reports.finance.view"];

function row(id: string, name: string, balance: string, due: string | null): Body {
  return {
    counterparty_id: id,
    name,
    phone: null,
    balance,
    credit_limit: null,
    due_date: due,
    overdue_since: "2026-10-01",
    days_overdue: 0,
    bucket: "0-30",
    promise_date: null,
    open_docs: 1,
    limit_exceeded_offline: false,
    doubtful_flag: false,
    doubtful_flag_id: null,
    last_payment_amount: null,
    last_payment_date: null,
  };
}

test("QT-M08-14: «Men qarzdorman» — whom / how much / when, the book, «To'lash»", async ({ page }) => {
  const s = new Stub(PERMISSIONS);
  s.on("GET", /^\/api\/v1\/reports\/debts-aging$/, ({ route, url }) => {
    expect(url.searchParams.get("direction")).toBe("payable");
    return json(route, 200, {
      as_of: "2026-10-18",
      direction: "payable",
      summary: { total: "3000000.00", count: 2, buckets: [] },
      rows: [
        row("s-2", "«Sut Savdo» MChJ", "600000.00", null),
        row("s-1", "«Barakali Don» MChJ", "2400000.00", "2026-10-25"),
      ],
    });
  }).on("GET", /^\/api\/v1\/counterparties\/s-1\/debt-ledger$/, ({ route, url }) => {
    expect(url.searchParams.get("direction")).toBe("payable");
    return json(route, 200, {
      counterparty: {
        id: "s-1",
        name: "«Barakali Don» MChJ",
        phone: null,
        kind: "company",
        is_customer: false,
        is_supplier: true,
        credit_limit: null,
        receivable_balance: "0.00",
        payable_balance: "2400000.00",
        debt_due_date: null,
        doubtful_flag: null,
      },
      direction: "payable",
      balance: "2400000.00",
      entries: [
        {
          id: "e2",
          doc_type: "supplier_payments",
          doc_id: "sp-1",
          number: "TP-000004",
          doc_date: "2026-10-12",
          amount: "-600000.00",
          direction: "payable",
          kind: "payment",
          running_balance: "2400000.00",
          due_date: null,
          promise_date: null,
          comment: null,
          status: null,
          open_amount: null,
          created_by: null,
          created_by_name: null,
          paid_amount: "600000.00",
          products: [],
          allocations: [],
        },
        {
          id: "e1",
          doc_type: "goods_receipts",
          doc_id: "gr-1",
          number: "KR-000231",
          doc_date: "2026-10-10",
          amount: "3000000.00",
          direction: "payable",
          kind: "debt",
          running_balance: "3000000.00",
          due_date: "2026-10-25",
          promise_date: null,
          comment: null,
          status: "partially_paid",
          open_amount: "2400000.00",
          created_by: null,
          created_by_name: null,
          paid_amount: null,
          products: [],
          allocations: [],
        },
      ],
      next_cursor: null,
    });
  });
  // the supplier payment form (BO-04, w-finance) reads the supplier's open documents
  s.on("GET", /^\/api\/v1\/supplier-payments\/open-documents$/, ({ route }) =>
    json(route, 200, { supplier_id: "s-1", payable_balance: "2400000.00", advance_balance: "0.00", items: [] }),
  );
  await s.install(page);
  await page.goto("/app/purchases?tab=payables");
  const tab = page.getByTestId("payables-tab");
  await expect(tab.getByTestId("payables-total")).toHaveText(/3\s000\s000/);
  // «qachon to'lash»: the dated debt first
  await expect(tab.getByTestId("payable-name")).toHaveText(["«Barakali Don» MChJ", "«Sut Savdo» MChJ"]);
  await expect(tab.getByTestId("payable-due").first()).toContainText("25.10.2026");

  await tab.getByTestId("payable-name").first().click();
  const book = page.getByTestId("payable-ledger");
  await expect(book.getByTestId("payable-ledger-balance")).toHaveText(/2\s400\s000/);
  await expect(book.getByTestId("payable-ledger-row")).toHaveCount(2);
  await expect(book.getByTestId("payable-ledger-row").nth(1)).toContainText("Kirim KR-000231");
  await expect(book.getByTestId("payable-ledger-row").nth(1)).toContainText("qisman");
  await page.keyboard.press("Escape");
  await expect(book).toBeHidden();

  await tab.getByRole("button", { name: /Birinchisini to'lash/ }).click();
  // the «Yetkazib beruvchiga to'lov» tab opens with its «To'lov qayd etish» form for this supplier
  await expect(page.getByRole("dialog", { name: FORM_TITLE })).toBeVisible();
});
