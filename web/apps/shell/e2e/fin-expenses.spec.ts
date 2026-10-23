import { expect, test } from "@playwright/test";

import { Stub, apiError, json, type Body } from "./warehouse-stub.ts";

/**
 * BO-17 «Xarajatlar» (B4-SCR-BO-17; 20 #41–#51; US-M15-01, US-M15-02; QT-M15-02/-04/-05 web parts) on the
 * production build: the due recurring reminder → one-click «Tasdiqlash va yozish»; «Yangi xarajat» →
 * «Saqlash va o'tkazish» over the limit → 202 «Egasi tasdig'iga yuborildi»; a posted expense → «Bekor
 * qilish» with a reason; a new category. Backend stubbed (warehouse-stub router).
 */
const CATEGORIES = [
  {
    id: "c-rent",
    code: "rent",
    name: "Ijara",
    default_account: "9410",
    source_ref: null,
    is_system: true,
    archived_at: null,
    version: 1,
  },
  {
    id: "c-fix",
    code: null,
    name: "Ta'mirlash",
    default_account: "9430",
    source_ref: null,
    is_system: false,
    archived_at: null,
    version: 1,
  },
  {
    id: "c-tax",
    code: "tax",
    name: "Soliqlar",
    default_account: "6410",
    source_ref: null,
    is_system: true,
    archived_at: null,
    version: 1,
  },
];

function expense(id: string, patch: Body = {}): Body {
  return {
    id,
    number: "XR-01-2026-000005",
    branch_id: "b-1",
    doc_date: "2026-10-12",
    status: "posted",
    category_id: "c-rent",
    category_name: "Ijara",
    account: "9410",
    amount: "3000000.00",
    source: "bank",
    tax_type: null,
    cash_register_id: null,
    shift_id: null,
    attachment_id: null,
    recurring_rule_id: null,
    comment: "Do'kon binosi, oktabr",
    created_by: "u-1",
    created_at: "2026-10-12T05:00:00Z",
    posted_at: "2026-10-12T05:00:00Z",
    cancelled_at: null,
    cancel_reason: null,
    device_id: null,
    approval_request_id: null,
    approval_status: null,
    ...patch,
  };
}

const RULE = {
  id: "r-1",
  name: "Qo'riqlash xizmati",
  branch_id: "b-1",
  category_id: "c-fix",
  amount: "400000.00",
  period: "month",
  day_of_month: 16,
  source: "bank",
  cash_register_id: null,
  next_due_date: "2026-10-16",
  last_triggered_at: null,
  is_active: true,
  is_due: true,
  version: 1,
};

function stub() {
  const items: Body[] = [expense("e-1")];
  let rule: Body = { ...RULE };
  const s = new Stub(["expenses.create"])
    .on("GET", /^\/api\/v1\/expenses$/, ({ route }) =>
      json(route, 200, {
        items,
        next_cursor: null,
        totals: {
          posted: items.filter((e) => e.status === "posted").length ? "3000000.00" : "0.00",
          draft: items.some((e) => e.status === "draft") ? "1850000.00" : "0.00",
        },
      }),
    )
    .on("GET", /^\/api\/v1\/expense-categories$/, ({ route }) => json(route, 200, { items: CATEGORIES }))
    .on("GET", /^\/api\/v1\/recurring-expenses$/, ({ route }) =>
      json(route, 200, { items: [rule], total: 1, page: 1, size: 100 }),
    )
    .on("POST", /^\/api\/v1\/expenses$/, ({ route, body }) => {
      const created = expense("e-new", {
        number: null,
        status: "draft",
        category_id: body?.category_id,
        category_name: "Ta'mirlash",
        account: "9430",
        amount: body?.amount,
        comment: body?.comment ?? null,
        doc_date: body?.doc_date,
      });
      items.unshift(created);
      return json(route, 201, created);
    })
    .on("POST", /^\/api\/v1\/expenses\/([^/]+)\/post$/, ({ route, match }) => {
      const e = items.find((x) => x.id === match[1]);
      if (e) Object.assign(e, { approval_status: "pending", approval_request_id: "ar-1" });
      return json(route, 202, { id: match[1], status: "draft", approval_request_id: "ar-1" });
    })
    .on("POST", /^\/api\/v1\/expenses\/([^/]+)\/cancel$/, ({ route, match }) => {
      const e = items.find((x) => x.id === match[1]);
      if (e) Object.assign(e, { status: "cancelled", cancelled_at: "2026-10-17T06:00:00Z" });
      return json(route, 200, { id: match[1], status: "cancelled", cancelled_at: "2026-10-17T06:00:00Z" });
    })
    .on("POST", /^\/api\/v1\/recurring-expenses\/([^/]+)\/confirm$/, ({ route }) => {
      rule = { ...rule, is_due: false, next_due_date: "2026-11-16", version: 2 };
      items.unshift(
        expense("e-rule", {
          category_id: "c-fix",
          category_name: "Ta'mirlash",
          amount: "400000.00",
          recurring_rule_id: "r-1",
          comment: "Qo'riqlash",
        }),
      );
      return json(route, 201, { expense_id: "e-rule", status: "posted" });
    })
    .on("POST", /^\/api\/v1\/expense-categories$/, ({ route, body }) => {
      if (body?.name === "Ijara") return apiError(route, 422, "VALIDATION_ERROR", "errors.validation");
      const created = {
        id: "c-new",
        code: null,
        name: body?.name,
        default_account: body?.default_account,
        source_ref: null,
        is_system: false,
        archived_at: null,
        version: 1,
      };
      CATEGORIES.push(created as (typeof CATEGORIES)[number]);
      return json(route, 201, created);
    });
  return s;
}

test("B4-SCR-BO-17: due reminder → one click; new expense over the limit → 202; cancel with a reason", async ({
  page,
}) => {
  const s = stub();
  await s.install(page);
  await page.goto("/app/expenses");
  await expect(page.getByRole("banner").getByRole("heading", { name: "Xarajatlar" })).toBeVisible();

  // US-M15-02 / QT-M15-02: the reminder is never paid automatically — one click confirms it.
  const reminder = page.getByTestId("due-reminder");
  await expect(reminder).toContainText("Qo'riqlash xizmati to'lash vaqti — 400 000 so'm");
  await reminder.getByRole("button", { name: "Tasdiqlash va yozish" }).click();
  await expect.poll(() => s.writesTo(/\/recurring-expenses\/r-1\/confirm$/).length).toBe(1);
  await expect(page.getByTestId("expense-notice")).toHaveText("Xarajat o'tkazildi.");
  await expect(page.getByTestId("due-reminder")).toHaveCount(0);

  // US-M15-01 / QT-M15-05: the 10-second form — category → account shown, «Saqlash va o'tkazish».
  const form = page.getByRole("region", { name: "Yangi xarajat" });
  await form.getByTestId("expense-amount").fill("1850000");
  await form.getByRole("combobox", { name: "Toifa" }).click();
  await page.getByRole("option", { name: "Ta'mirlash" }).click();
  await expect(form).toContainText("Buxgalteriya hisobi: 9430 — Boshqa operatsion xarajatlar");
  await form.getByRole("textbox", { name: "Izoh" }).fill("Muzlatkich kompressori");
  await form.getByTestId("expense-save-post").click();
  await expect.poll(() => s.writesTo(/^\/api\/v1\/expenses$/).length).toBe(1);
  const created = s.writesTo(/^\/api\/v1\/expenses$/)[0];
  expect(created?.body).toMatchObject({
    category_id: "c-fix",
    amount: "1850000.00",
    source: "bank",
    branch_id: "b-1",
    comment: "Muzlatkich kompressori",
    tax_type: null,
  });
  expect(created?.idempotencyKey).toBeTruthy();
  await expect.poll(() => s.writesTo(/\/expenses\/e-new\/post$/).length).toBe(1);
  await expect(page.getByTestId("expense-notice")).toContainText("Egasi tasdig'iga yuborildi");
  const list = page.getByRole("table", { name: "Xarajatlar ro'yxati" });
  await expect(list.getByRole("row").filter({ hasText: "Muzlatkich kompressori" })).toContainText(
    "Tasdiq kutmoqda",
  );

  // QT-M15-04: cancel a posted expense — reason required (3–500).
  const posted = list.getByRole("row").filter({ hasText: "Do'kon binosi, oktabr" });
  await posted.getByRole("button", { name: "Qator amallari" }).click();
  await page.getByRole("menuitem", { name: "Bekor qilish" }).click();
  const dialog = page.getByRole("alertdialog", { name: "Xarajatni bekor qilish" });
  await dialog.getByTestId("cancel-reason").fill("ab");
  await dialog.getByRole("button", { name: "Bekor qilish" }).click();
  await expect(dialog).toContainText("Kamida 3 ta belgi kiriting");
  await dialog.getByTestId("cancel-reason").fill("Xato summa kiritilgan");
  await dialog.getByRole("button", { name: "Bekor qilish" }).click();
  await expect
    .poll(() => s.writesTo(/\/expenses\/e-1\/cancel$/)[0]?.body)
    .toEqual({
      reason: "Xato summa kiritilgan",
    });
  await expect(posted).toContainText("Bekor qilingan");
});

test("BO-17: a 6410 category asks for the tax type; categories tab adds a category", async ({ page }) => {
  const s = stub();
  await s.install(page);
  await page.goto("/app/expenses");
  const form = page.getByRole("region", { name: "Yangi xarajat" });
  await form.getByTestId("expense-amount").fill("36000");
  await form.getByRole("combobox", { name: "Toifa" }).click();
  await page.getByRole("option", { name: "Soliqlar" }).click();
  await form.getByTestId("expense-save-draft").click();
  await expect(form).toContainText("Bu maydonni to'ldirish shart");
  expect(s.writesTo(/^\/api\/v1\/expenses$/)).toHaveLength(0);
  await form.getByRole("combobox", { name: "Soliq turi" }).click();
  await page.getByRole("option", { name: "Aylanma solig'i" }).click();
  await form.getByTestId("expense-save-draft").click();
  await expect.poll(() => s.writesTo(/^\/api\/v1\/expenses$/)[0]?.body?.tax_type).toBe("turnover");
  expect(s.writesTo(/\/post$/)).toHaveLength(0);
  await expect(page.getByTestId("expense-notice")).toHaveText("Qoralama saqlandi.");

  await page.getByRole("tab", { name: "Toifalar" }).click();
  await page.getByRole("button", { name: "Yangi toifa" }).click();
  const dialog = page.getByRole("dialog", { name: "Yangi xarajat toifasi" });
  await dialog.getByTestId("category-name").fill("Internet va aloqa");
  await dialog.getByRole("button", { name: "Saqlash" }).click();
  await expect
    .poll(() => s.writesTo(/^\/api\/v1\/expense-categories$/)[0]?.body)
    .toEqual({
      name: "Internet va aloqa",
      default_account: "9410",
    });
  await expect(page.getByRole("table", { name: "Xarajat toifalari" })).toContainText("Internet va aloqa");
});

test("BO-17: without expenses.create the screen is closed", async ({ page }) => {
  const s = new Stub(["stock.view"]);
  await s.install(page);
  await page.goto("/app/expenses");
  await expect(page.getByText("Sizda bu bo'limga kirish huquqi yo'q")).toBeVisible();
});
