import { expect, test } from "@playwright/test";

import { Stub, apiError, json, product, type Body } from "./warehouse-stub.ts";

/**
 * BO-03 «Qoldiq» (07, 19 §7, US-M04-01…03, US-M04-06) on the production build: KPI cards, the
 * low-stock / expiry banner, balance rows (Kam qoldi / Yetarli / ⚠ manfiy / Muddati N kunda), search,
 * «Faqat kam qoldiq» (`low_stock=true`), «Muddati 7 kunda tugaydi» (lots view) and «Hisobdan chiqarish»
 * (19 §15) — posted (200) and over the limit (202 → «Tasdiq kutilmoqda»).
 */
const NBSP = " ";
const nb = (text: string) => text.replace(/ /g, NBSP);

function isoIn(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() + days);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function balance(id: string, name: string, patch: Body = {}): Body {
  return {
    product_id: id,
    product_name: name,
    warehouse_id: "w-1",
    qty: "85.000",
    value: "952000.00",
    avg_cost: "11200.0000",
    min_stock: "30.000",
    is_low: false,
    is_negative: false,
    updated_at: "2026-10-16T09:32:00Z",
    ...patch,
  };
}

const ROWS = [
  balance("p1", "Choy ko'k 100 g", {
    qty: "8.000",
    min_stock: "12.000",
    value: "140000.00",
    avg_cost: "17500.0000",
    is_low: true,
  }),
  balance("p2", "Sut 2,5% 1 l"),
  balance("p3", "Shakar", {
    qty: "-2.000",
    min_stock: null,
    value: "-20800.00",
    avg_cost: null,
    is_negative: true,
  }),
];

const LOT = {
  id: "lot-1",
  product_id: "p2",
  product_name: "Sut 2,5% 1 l",
  warehouse_id: "w-1",
  received_at: "2026-10-01T05:00:00Z",
  qty_in: "40.000",
  qty_left: "12.000",
  blocked_qty: "0.000",
  unit_cost: "11200.0000",
  expiry_date: isoIn(3),
  receipt_line_id: "rl-1",
  source_doc_type: "goods_receipts",
  source_doc_id: "gr-1",
};

const PERMISSIONS = [
  "stock.view",
  "stock.writeoff",
  "transfer.create",
  "stock.count.create",
  "purchases.create",
];

function stub(postStatus: 200 | 202 = 200) {
  const s = new Stub(PERMISSIONS, [
    product("p1", "Choy ko'k 100 g"),
    product("p2", "Sut 2,5% 1 l"),
    product("p3", "Shakar", { unit_code: "kg" }),
  ]);
  s.on("GET", /^\/api\/v1\/stock-balances$/, ({ route, url }) => {
    const search = (url.searchParams.get("search") ?? "").toLowerCase();
    const low = url.searchParams.get("low_stock") === "true";
    const items = ROWS.filter(
      (r) => String(r.product_name).toLowerCase().includes(search) && (!low || r.is_low),
    );
    return json(route, 200, { items, next_cursor: null });
  })
    .on("GET", /^\/api\/v1\/stock-lots$/, ({ route }) =>
      json(route, 200, { items: [LOT], next_cursor: null }),
    )
    .on("POST", /^\/api\/v1\/write-offs$/, ({ route, body }) =>
      json(route, 201, writeOff("draft", body ?? {})),
    )
    .on("POST", /^\/api\/v1\/write-offs\/wo-1\/post$/, ({ route }) =>
      postStatus === 200
        ? json(route, 200, writeOff("posted", {}, { number: "HC-01-2026-000012" }))
        : json(
            route,
            202,
            writeOff("draft", {}, { approval_request_id: "ar-1", approval_status: "pending" }),
          ),
    );
  return s;
}

function writeOff(status: string, body: Body, patch: Body = {}): Body {
  return {
    id: "wo-1",
    number: null,
    status,
    doc_date: body.doc_date ?? "2026-10-16",
    branch_id: "b-1",
    warehouse_id: "w-1",
    responsible_user_id: null,
    promo_order_ref: null,
    source_return_id: null,
    comment: null,
    line_count: 1,
    total_cost: "22400.00",
    approval_request_id: null,
    approval_status: null,
    created_by: "u-1",
    created_at: null,
    posted_at: null,
    cancelled_at: null,
    cancel_reason: null,
    lines: [],
    ...patch,
  };
}

test("BO-03: KPI, banner, balance rows with statuses, search and «Faqat kam qoldiq»", async ({ page }) => {
  const s = stub();
  await s.install(page);
  await page.goto("/app/warehouse/stock");
  await expect(page.getByRole("banner").getByRole("heading", { name: "Ombor qoldig'i" })).toBeVisible();

  const kpi = page.getByRole("group", { name: "Ombor ko'rsatkichlari" });
  await expect(kpi).toContainText("Ombor qiymati (Chilonzor-3)");
  await expect(kpi).toContainText(nb("1 071 200"));
  await expect(kpi).toContainText("3 pozitsiya");
  await expect(page.getByText("1 ta tovar minimal darajadan kam qoldi")).toBeVisible();

  const table = page.getByRole("table", { name: "Qoldiq" });
  const choy = table.getByRole("row").filter({ hasText: "Choy ko'k 100 g" });
  await expect(choy).toContainText("Kam qoldi");
  await expect(choy).toContainText("Bakaleya");
  const sut = table.getByRole("row").filter({ hasText: "Sut 2,5% 1 l" });
  await expect(sut).toContainText("Yetarli");
  await expect(sut).toContainText("Muddati 3 kunda");
  await expect(sut).toContainText(nb("952 000"));
  await expect(table.getByRole("row").filter({ hasText: "Shakar" })).toContainText("⚠ manfiy");
  await expect(page.getByRole("group", { name: "Sahifadagi jami" })).toContainText(nb("1 071 200 so'm"));
  // The branch's warehouse is asked for explicitly.
  expect(s.queries.find((q) => q.path === "/api/v1/stock-balances")?.query.get("warehouse_id")).toBe("w-1");

  await page.getByRole("searchbox", { name: "Qidirish" }).fill("Sut");
  await expect(table.getByRole("row")).toHaveCount(2);
  expect(
    s.queries
      .filter((q) => q.path === "/api/v1/stock-balances")
      .at(-1)
      ?.query.get("search"),
  ).toBe("Sut");
  await page.getByRole("searchbox", { name: "Qidirish" }).fill("");
  await page.getByRole("searchbox", { name: "Qidirish" }).press("Enter");

  await page.getByRole("switch", { name: "Faqat kam qoldiq" }).click();
  await expect(table.getByRole("row")).toHaveCount(2);
  await expect(table.getByRole("row").nth(1)).toContainText("Choy ko'k 100 g");
  expect(
    s.queries
      .filter((q) => q.path === "/api/v1/stock-balances")
      .at(-1)
      ?.query.get("low_stock"),
  ).toBe("true");

  // «Muddati 7 kunda tugaydi» → lots view.
  await page.getByRole("switch", { name: "Muddati 7 kunda tugaydi" }).click();
  const lots = page.getByRole("table", { name: "Muddati yaqin partiyalar" });
  await expect(lots.getByRole("row").nth(1)).toContainText("Sut 2,5% 1 l");
  await expect(lots.getByRole("row").nth(1)).toContainText("Muddati 3 kunda");
  expect(
    s.queries
      .filter((q) => q.path === "/api/v1/stock-lots")
      .at(-1)
      ?.query.get("expiring_within_days"),
  ).toBe("7");
});

test("BO-03: «Hisobdan chiqarish» from an expiring lot → POST /write-offs → /post (200)", async ({
  page,
}) => {
  const s = stub(200);
  await s.install(page);
  await page.goto("/app/warehouse/stock");
  await page.getByRole("switch", { name: "Muddati 7 kunda tugaydi" }).click();
  await page.getByRole("button", { name: "Hisobdan chiqarish — Sut 2,5% 1 l" }).click();

  const sheet = page.getByRole("dialog", { name: "Hisobdan chiqarish" });
  await expect(sheet.getByRole("combobox", { name: "Partiya" })).toContainText("qoldiq 12");
  await sheet.getByLabel("Miqdor").fill("2");
  await sheet.getByRole("button", { name: "Hisobdan chiqarish" }).click();
  await expect(page.getByText("Hisobdan chiqarildi HC-01-2026-000012", { exact: true })).toBeVisible();

  const create = s.writesTo(/^\/api\/v1\/write-offs$/)[0];
  expect(create?.body).toMatchObject({
    warehouse_id: "w-1",
    lines: [{ product_id: "p2", lot_id: "lot-1", qty: "2.000", reason: "expired", gift_kind: null }],
    responsible_user_id: null,
  });
  expect(create?.idempotencyKey).toBeTruthy();
  expect(create?.csrf).toBe("csrf-e2e");
  expect(s.writesTo(/\/write-offs\/wo-1\/post$/)).toHaveLength(1);
});

test("BO-03: a write-off over the limit (202) waits for approval; gift needs the promo order", async ({
  page,
}) => {
  const s = stub(202);
  await s.install(page);
  await page.goto("/app/warehouse/stock");
  await page.getByRole("button", { name: "Hisobdan chiqarish" }).first().click();
  const sheet = page.getByRole("dialog", { name: "Hisobdan chiqarish" });
  await sheet.getByRole("button", { name: "Tovar qo'shish" }).click();
  await page.getByRole("searchbox", { name: "Tovar qidirish" }).fill("Choy");
  await page.getByRole("button", { name: /Choy ko'k 100 g/ }).click();
  await sheet.getByLabel("Miqdor").fill("1");
  await sheet.getByRole("combobox", { name: "Sabab" }).click();
  await page.getByRole("option", { name: "Sovg'a / aksiya" }).click();
  await sheet.getByRole("combobox", { name: "Sovg'a turi" }).click();
  await page.getByRole("option", { name: "Aksiya (buyruq asosida)" }).click();
  await sheet.getByRole("button", { name: "Hisobdan chiqarish" }).click();
  await expect(sheet.getByText("Majburiy maydon").or(sheet.getByRole("alert")).first()).toBeVisible();
  expect(s.writesTo(/^\/api\/v1\/write-offs$/)).toHaveLength(0);

  await sheet.getByLabel("Aksiya buyrug'i").fill("Buyruq 12, 01.10.2026");
  await sheet.getByRole("button", { name: "Hisobdan chiqarish" }).click();
  await expect(sheet.getByText("Tasdiq kutilmoqda")).toBeVisible();
  expect(s.writesTo(/^\/api\/v1\/write-offs$/)[0]?.body).toMatchObject({
    promo_order_ref: "Buyruq 12, 01.10.2026",
    lines: [{ product_id: "p1", lot_id: null, qty: "1.000", reason: "gift", gift_kind: "promo_justified" }],
  });
});

test("BO-03: offline — view only, write-off disabled; no stock.view → no access", async ({ page }) => {
  const s = stub();
  await s.install(page);
  await page.goto("/app/warehouse/stock");
  await expect(page.getByRole("table", { name: "Qoldiq" }).getByRole("row").nth(1)).toBeVisible();
  await page.context().setOffline(true);
  await page.evaluate(() => window.dispatchEvent(new Event("offline")));
  await expect(page.getByText(/Internet yo'q — faqat ko'rish/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Hisobdan chiqarish" }).first()).toBeDisabled();
  await page.context().setOffline(false);

  const cashier = new Stub(["sales.create"]);
  await cashier.install(page);
  await page.route("**/api/v1/stock-balances**", (route) =>
    apiError(route, 403, "PERMISSION_DENIED", "errors.permission_denied"),
  );
  await page.goto("/app/warehouse/stock");
  await expect(page.getByText("Sizda bu bo'limga kirish huquqi yo'q").first()).toBeVisible();
});
