import { expect, test } from "@playwright/test";

import { Stub, apiError, json, type Body } from "./warehouse-stub.ts";

/**
 * BO-06 «Qarzdorlar» (07, 18 §12, 20 #21; US-M08-03/04/06/07/09/10, QT-M08-09/18) on the production build:
 * aging cards + tabs → the paper-book ledger → bank payment (≤ debt, `method:"bank"`, create → post) →
 * «Boshlang'ich qarz» for a new customer (name + phone) → Owner «Qarzni kechish» (create → post).
 */
const PERMISSIONS = [
  "reports.finance.view",
  "reports.sales.view",
  "debts.payment.accept",
  "debts.limit.manage",
  "debts.forgive",
  "stock.opening.manage",
];

function localDay(offset = 0): string {
  const d = new Date(Date.now() + offset * 86_400_000);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

const TODAY = localDay();

function row(id: string, name: string, patch: Body = {}): Body {
  return {
    counterparty_id: id,
    name,
    phone: "+998901234567",
    balance: "450000.00",
    credit_limit: "1000000.00",
    due_date: null,
    overdue_since: "2026-10-01",
    days_overdue: 15,
    bucket: "0-30",
    promise_date: null,
    open_docs: 2,
    limit_exceeded_offline: false,
    doubtful_flag: false,
    doubtful_flag_id: null,
    last_payment_amount: "150000.00",
    last_payment_date: "2026-10-02",
    ...patch,
  };
}

const ROWS = [
  row("c-1", "Aliyev Botir", { promise_date: TODAY }),
  row("c-2", "Karimova Malika", {
    phone: "+998977654321",
    balance: "1240000.00",
    bucket: "60+",
    days_overdue: 64,
    due_date: "2026-08-10",
  }),
  row("c-3", "Rahimov Jasur", {
    balance: "950000.00",
    credit_limit: "900000.00",
    limit_exceeded_offline: true,
  }),
];

function aging(rows: Body[]): Body {
  return {
    as_of: TODAY,
    direction: "receivable",
    summary: {
      total: "2640000.00",
      count: rows.length,
      buckets: [
        { bucket: "0-30", count: 2, amount: "1400000.00" },
        { bucket: "60+", count: 1, amount: "1240000.00" },
      ],
    },
    rows,
  };
}

const LEDGER: Body = {
  counterparty: {
    id: "c-1",
    name: "Aliyev Botir",
    phone: "+998901234567",
    kind: "person",
    is_customer: true,
    is_supplier: false,
    credit_limit: "1000000.00",
    receivable_balance: "450000.00",
    payable_balance: "0.00",
    debt_due_date: TODAY,
    doubtful_flag: null,
  },
  direction: "receivable",
  balance: "450000.00",
  entries: [
    {
      id: "e3",
      doc_type: "debt_payments",
      doc_id: "pay-1",
      number: "QT-01-2026-000012",
      doc_date: "2026-10-08",
      amount: "-100000.00",
      direction: "receivable",
      kind: "payment",
      running_balance: "450000.00",
      due_date: null,
      promise_date: null,
      comment: null,
      status: null,
      open_amount: null,
      created_by: "u-2",
      created_by_name: "Dilnoza Rahimova",
      paid_amount: "100000.00",
      products: [],
      allocations: [
        { target_doc_type: "sales", target_doc_id: "s-1", target_number: "S-000301", amount: "100000.00" },
      ],
    },
    {
      id: "e2",
      doc_type: "sales",
      doc_id: "s-2",
      number: "S-000355",
      doc_date: "2026-10-05",
      amount: "370000.00",
      direction: "receivable",
      kind: "debt",
      running_balance: "550000.00",
      due_date: "2026-10-20",
      promise_date: "2026-10-20",
      comment: null,
      status: "open",
      open_amount: "370000.00",
      created_by: "u-2",
      created_by_name: "Dilnoza Rahimova",
      paid_amount: null,
      products: [
        { product_id: "p1", name: "Non", name_ru: "Хлеб", qty: "2.000", line_total: "8000.00" },
        { product_id: "p2", name: "Sut", name_ru: null, qty: "1.000", line_total: "13500.00" },
      ],
      allocations: [],
    },
    {
      id: "e1",
      doc_type: "sales",
      doc_id: "s-1",
      number: "S-000301",
      doc_date: "2026-10-01",
      amount: "180000.00",
      direction: "receivable",
      kind: "debt",
      running_balance: "180000.00",
      due_date: null,
      promise_date: null,
      comment: "Oylikdan keyin",
      status: "partially_paid",
      open_amount: "80000.00",
      created_by: "u-2",
      created_by_name: "Dilnoza Rahimova",
      paid_amount: null,
      products: [{ product_id: "p3", name: "Guruch", name_ru: null, qty: "5.000", line_total: "180000.00" }],
      allocations: [],
    },
  ],
  next_cursor: null,
};

const doc = (id: string, status: string, patch: Body = {}): Body => ({
  id,
  number: status === "posted" ? `N-${id}` : null,
  status,
  doc_date: TODAY,
  branch_id: "b-1",
  counterparty_id: "c-1",
  counterparty_name: "Aliyev Botir",
  amount: "150000.00",
  comment: null,
  created_by: "u-1",
  created_at: "2026-10-16T08:00:00Z",
  posted_at: null,
  cancelled_at: null,
  cancelled_by: null,
  cancel_reason: null,
  ...patch,
});

test("BO-06: aging → ledger → bank payment → opening → write-off", async ({ page }) => {
  const s = new Stub(PERMISSIONS);
  let agingCalls = 0;
  s.on("GET", /^\/api\/v1\/reports\/debts-aging$/, ({ route, url }) => {
    agingCalls += 1;
    expect(url.searchParams.get("direction")).toBe("receivable");
    expect(url.searchParams.get("branch_id")).toBe("b-1");
    return json(route, 200, aging(ROWS));
  })
    .on("GET", /^\/api\/v1\/counterparties\/c-1\/debt-ledger$/, ({ route }) => json(route, 200, LEDGER))
    .on("POST", /^\/api\/v1\/debt-payments$/, ({ route, body }) =>
      body?.amount === "999999.00"
        ? apiError(route, 422, "VALIDATION_ERROR", "errors.debt_payment_exceeds_balance", {
            balance: "450000.00",
            requested: "999999.00",
          })
        : json(route, 201, doc("pay-9", "draft", { method: "bank" })),
    )
    .on("POST", /^\/api\/v1\/debt-payments\/pay-9\/post$/, ({ route }) =>
      json(route, 200, doc("pay-9", "posted", { method: "bank" })),
    )
    .on("POST", /^\/api\/v1\/debt-openings$/, ({ route }) => json(route, 201, doc("op-1", "draft")))
    .on("POST", /^\/api\/v1\/debt-openings\/op-1\/post$/, ({ route }) =>
      json(route, 200, doc("op-1", "posted")),
    )
    .on("POST", /^\/api\/v1\/debt-writeoffs$/, ({ route }) => json(route, 201, doc("wo-1", "draft")))
    .on("POST", /^\/api\/v1\/debt-writeoffs\/wo-1\/post$/, ({ route }) =>
      json(route, 200, doc("wo-1", "posted")),
    );
  // the topbar bell (reports.sales.view) reads the dashboard alerts
  s.on("GET", /^\/api\/v1\/reports\/dashboard$/, ({ route }) => json(route, 200, { alerts: [] }));
  await s.install(page);
  await page.goto("/app/debts");
  await expect(page.getByRole("banner").getByRole("heading", { name: "Qarzdorlar" })).toBeVisible();

  // US-M08-10: total + aging groups; tabs with counts (60+ is a reminder list only)
  await expect(page.getByTestId("kpi-total")).toContainText(/2\s640\s000/);
  await expect(page.getByTestId("bucket-60+")).toContainText(/1\s240\s000/);
  await expect(page.getByTestId("debtor-name")).toHaveCount(3);
  await page.getByTestId("tab-due").click(); // US-M08-09: promise today / overdue
  await expect(page.getByTestId("debtor-name")).toHaveText(["Aliyev Botir", "Karimova Malika"]);
  await page.getByTestId("tab-aged").click();
  await expect(page.getByTestId("debtor-name")).toHaveText(["Karimova Malika"]);
  await expect(page.getByText(/Tizim hech kimni avtomatik shubhali deb belgilamaydi/)).toBeVisible();
  await page.getByTestId("tab-over_limit").click();
  await expect(page.getByTestId("debtor-name")).toHaveText(["Rahimov Jasur"]);
  await expect(page.getByText("oshgan (offline)")).toBeVisible();
  await page.getByTestId("tab-all").click();
  await page.getByRole("searchbox", { name: /Mijoz qidirish/ }).fill("aliyev");
  await expect(page.getByTestId("debtor-name")).toHaveText(["Aliyev Botir"]);

  // US-M08-06 / QT-M08-09: the paper book — date, goods, who wrote it, running balance, status
  await page.getByTestId("debtor-name").first().click();
  await expect(page.getByTestId("panel-name")).toContainText("Aliyev Botir");
  await page.getByTestId("open-ledger").click();
  const ledger = page.getByTestId("ledger-sheet");
  await expect(ledger.getByTestId("ledger-row")).toHaveCount(3);
  await expect(ledger.getByTestId("ledger-row").nth(1)).toContainText("Non, Sut");
  await expect(ledger.getByTestId("ledger-row").nth(1)).toContainText("Yozdi: Dilnoza Rahimova");
  await expect(ledger.getByTestId("ledger-status")).toHaveText(["ochiq", "qisman"]);
  await expect(ledger.getByTestId("ledger-allocations")).toContainText("S-000301");
  await expect(ledger.getByTestId("ledger-running").first()).toHaveText(/450\s000/);
  await page.keyboard.press("Escape");
  await expect(ledger).toBeHidden();

  // US-M08-04: bank payment ≤ debt (qaror #45 — the client refuses more), create → post, list re-read
  const pay = page.getByTestId("bank-payment");
  await pay.getByTestId("bank-amount").fill("500000");
  await pay.getByTestId("bank-submit").click();
  await expect(pay.getByText("To'lov joriy qarzdan oshmasligi kerak")).toBeVisible();
  expect(s.writesTo(/\/debt-payments/)).toHaveLength(0);
  await pay.getByTestId("bank-amount").fill("150000");
  const before = agingCalls;
  await pay.getByTestId("bank-submit").click();
  await expect(page.getByText("Bank to'lovi qabul qilindi").first()).toBeVisible();
  const create = s.writesTo(/^\/api\/v1\/debt-payments$/)[0];
  expect(create?.body).toEqual({
    counterparty_id: "c-1",
    branch_id: "b-1",
    amount: "150000.00",
    method: "bank",
    doc_date: TODAY,
    promise_date: null,
    comment: null,
  });
  expect(create?.idempotencyKey).toBeTruthy();
  expect(s.writesTo(/\/debt-payments\/pay-9\/post$/)).toHaveLength(1);
  await expect.poll(() => agingCalls).toBeGreaterThan(before);

  // US-M08-07: «Boshlang'ich qarz» — a paper-book customer by name + phone
  await page.getByTestId("new-opening").click();
  const opening = page.getByTestId("opening-dialog");
  await opening.getByTestId("opening-name").fill("Tursunova Nigora");
  await opening.getByTestId("opening-phone").fill("915550730");
  await opening.getByTestId("opening-amount").fill("320000");
  await opening.getByTestId("opening-submit").click();
  await expect(page.getByText("Boshlang'ich qarz yozildi").first()).toBeVisible();
  expect(s.writesTo(/^\/api\/v1\/debt-openings$/)[0]?.body).toMatchObject({
    counterparty: { name: "Tursunova Nigora", phone: "+998915550730", kind: "person" },
    amount: "320000.00",
    direction: "receivable",
    branch_id: "b-1",
  });
  expect(s.writesTo(/\/debt-openings\/op-1\/post$/)).toHaveLength(1);

  // Owner: «Qarzni kechish» — reason required, «Bu amal provodka yaratadi», create → post
  await page.getByTestId("panel-writeoff").click();
  const wo = page.getByTestId("writeoff-dialog");
  await expect(wo.getByText(/Bu amal provodka yaratadi/)).toBeVisible();
  await wo.getByTestId("writeoff-amount").fill("100000");
  await wo.getByTestId("writeoff-submit").click();
  await expect(wo.getByText("Bu maydonni to'ldirish shart").first()).toBeVisible();
  await wo.getByTestId("writeoff-reason").fill("Vafot etgan");
  await wo.getByTestId("writeoff-submit").click();
  await expect(page.getByText("Qarz kechildi").first()).toBeVisible();
  expect(s.writesTo(/^\/api\/v1\/debt-writeoffs$/)[0]?.body).toMatchObject({
    counterparty_id: "c-1",
    amount: "100000.00",
    reason: "Vafot etgan",
    account_choice: "9430",
  });
  expect(s.writesTo(/\/debt-writeoffs\/wo-1\/post$/)).toHaveLength(1);
});

test("BO-06: without reports.finance.view / debts.approve the screen is closed", async ({ page }) => {
  const s = new Stub(["debts.payment.accept"]);
  // the topbar bell (reports.sales.view) reads the dashboard alerts
  s.on("GET", /^\/api\/v1\/reports\/dashboard$/, ({ route }) => json(route, 200, { alerts: [] }));
  await s.install(page);
  await page.goto("/app/debts");
  await expect(page.getByText("Sizda bu bo'limga kirish huquqi yo'q")).toBeVisible();
});
