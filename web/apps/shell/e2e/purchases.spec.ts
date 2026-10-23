import { expect, test } from "@playwright/test";

import { Stub, WAREHOUSES, apiError, json, product, type Body } from "./warehouse-stub.ts";

/**
 * BO-04 «Xaridlar» (07, 19 §8–§12, US-M07-01…05) on the production build: purchase order create → send;
 * goods receipt from the order with a discrepancy reason → post; supplier return (12-month refusal,
 * then posted with «Qo'shimcha e-faktura kutilmoqda»); supplier create with the STIR lookup suggestion.
 */
const PERMISSIONS = [
  "stock.view",
  "purchases.create",
  "purchases.receive",
  "purchases.post",
  "purchases.return",
];

const SUPPLIER = { id: "s-1", name: "«Barakali Don» MChJ", stir: "305112847" };

function supplierRow(patch: Body = {}): Body {
  return {
    id: "s-1",
    kind: "company",
    name: SUPPLIER.name,
    phone: null,
    stir: SUPPLIER.stir,
    legal_address: null,
    bank_account: null,
    bank_mfo: null,
    vat_payer: true,
    is_customer: false,
    is_supplier: true,
    credit_limit: null,
    standing_discount_pct: null,
    notify_consent: false,
    notify_consent_at: null,
    note: null,
    archived_at: null,
    created_at: "2026-10-01T05:00:00Z",
    updated_at: "2026-10-01T05:00:00Z",
    version: 1,
    receivable_balance: "0.00",
    payable_balance: "2400000.00",
    ...patch,
  };
}

function order(status: string, patch: Body = {}): Body {
  return {
    id: "o-1",
    number: status === "draft" ? null : "Z-01-2026-000231",
    status,
    doc_date: "2026-10-14",
    branch_id: "b-1",
    warehouse_id: "w-1",
    supplier_id: "s-1",
    supplier: SUPPLIER,
    comment: null,
    total: "3000000.00",
    line_count: 1,
    created_by: "u-1",
    created_by_name: "Akmal Karimov",
    created_at: "2026-10-14T05:00:00Z",
    updated_at: "2026-10-14T05:00:00Z",
    sent_at: status === "draft" ? null : "2026-10-14T06:20:00Z",
    cancelled_at: null,
    cancel_reason: null,
    lines: [
      {
        id: "pl-1",
        line_no: 1,
        product_id: "p1",
        product_name: "Guruch «Lazer»",
        unit_code: "kg",
        qty: "200.000",
        price: "15000.0000",
        amount: "3000000.00",
      },
    ],
    received_lines: [{ product_id: "p1", ordered_qty: "200.000", received_qty: "0.000" }],
    ...patch,
  };
}

function receipt(status: string, patch: Body = {}): Body {
  return {
    id: "r-1",
    number: status === "draft" ? null : "M-01-2026-000154",
    status,
    doc_date: "2026-10-16",
    branch_id: "b-1",
    warehouse_id: "w-1",
    supplier_id: "s-1",
    supplier: SUPPLIER,
    po_id: "o-1",
    kind: "purchase",
    source: "purchase_order",
    paid_immediately: false,
    einvoice_id: null,
    einvoice_risk_flag: null,
    ettn_ref: null,
    ettn_status: "none",
    poa_id: null,
    poa_number: null,
    comment: null,
    line_count: 1,
    net_total: "2850000.00",
    vat_total: "342000.00",
    total: "3192000.00",
    created_by: "u-1",
    created_by_name: "Jasur B.",
    created_at: "2026-10-16T05:00:00Z",
    updated_at: "2026-10-16T05:00:00Z",
    posted_at: status === "posted" ? "2026-10-16T10:12:00Z" : null,
    cancelled_at: null,
    cancel_reason: null,
    marking_acceptance: null,
    lines: [
      {
        id: "rl-1",
        line_no: 1,
        product_id: "p1",
        product_name: "Guruch «Lazer»",
        unit_code: "kg",
        qty: "190.000",
        cost: "15000.0000",
        vat_rate: "12.00",
        vat_exemption_code: null,
        vat_amount: "342000.00",
        net_amount: "2850000.00",
        total_amount: "3192000.00",
        expiry_date: null,
        discrepancy_reason: "short",
        is_marked: false,
        marking_codes: [],
        lot_id: status === "posted" ? "lot-9" : null,
        lot_qty_left: status === "posted" ? "190.000" : null,
        returned_qty: "0.000",
      },
    ],
    ...patch,
  };
}

function header(doc: Body): Body {
  const { lines: _l, received_lines: _r, ...rest } = doc;
  return rest;
}

test("US-M07-01: «Yangi xaridnoma» → supplier, lines → «Saqlash va yuborish»", async ({ page }) => {
  let current: Body | null = null;
  const s = new Stub(PERMISSIONS, [product("p1", "Guruch «Lazer»", { unit_code: "kg" })]);
  s.on("GET", /^\/api\/v1\/purchase-orders$/, ({ route }) =>
    json(route, 200, { items: current ? [header(current)] : [], next_cursor: null }),
  )
    .on("GET", /^\/api\/v1\/counterparties$/, ({ route, url }) => {
      expect(url.searchParams.get("is_supplier")).toBe("true");
      return json(route, 200, { items: [supplierRow()], total: 1, page: 1, size: 10 });
    })
    .on("GET", /^\/api\/v1\/counterparties\/s-1\/debt-balance$/, ({ route }) =>
      json(route, 200, { payable: "2400000.00", receivable: "0.00" }),
    )
    .on("POST", /^\/api\/v1\/purchase-orders$/, ({ route }) => {
      current = order("draft");
      return json(route, 201, current);
    })
    .on("POST", /^\/api\/v1\/purchase-orders\/o-1\/send$/, ({ route }) => {
      current = order("sent");
      return json(route, 200, current);
    });
  await s.install(page);
  await page.goto("/app/purchases");
  await expect(page.getByRole("banner").getByRole("heading", { name: "Xaridlar" })).toBeVisible();

  await page.getByRole("button", { name: "Yangi xaridnoma" }).click();
  const sheet = page.getByRole("dialog", { name: "Yangi xaridnoma" });
  await expect(sheet.getByLabel("Yetkazib beruvchi")).toHaveText("Yetkazib beruvchini tanlang");
  await sheet.getByLabel("Yetkazib beruvchi").click();
  await page.getByRole("searchbox", { name: "Yetkazib beruvchi qidirish" }).fill("Baraka");
  await page.getByRole("button", { name: /Barakali Don/ }).click();
  await sheet.getByRole("button", { name: "Tovar qo'shish" }).click();
  await page.getByRole("searchbox", { name: "Tovar qidirish" }).fill("Guruch");
  await page.getByRole("button", { name: /Guruch «Lazer»/ }).click();
  await sheet.getByLabel("Miqdor").fill("200");
  await sheet.getByLabel("Narx").fill("15000");
  await expect(sheet.getByText(/Jami: 3\s000\s000 so'm/)).toBeVisible();
  await sheet.getByRole("button", { name: "Saqlash va yuborish" }).click();
  await expect(page.getByText("Xaridnoma Z-01-2026-000231 yuborildi", { exact: true })).toBeVisible();

  const create = s.writesTo(/^\/api\/v1\/purchase-orders$/)[0];
  expect(create?.body).toMatchObject({
    supplier_id: "s-1",
    warehouse_id: "w-1",
    lines: [{ product_id: "p1", qty: "200.000", price: "15000.0000" }],
  });
  expect(create?.idempotencyKey).toBeTruthy();
  expect(s.writesTo(/\/purchase-orders\/o-1\/send$/)[0]?.csrf).toBe("csrf-e2e");

  const detail = page.getByRole("region", { name: "Xaridnoma tafsiloti" });
  await expect(detail).toContainText("Z-01-2026-000231");
  await expect(detail).toContainText("Yuborildi");
  await expect(detail).toContainText(/Joriy qarzimiz \(6010\): 2\s400\s000 so'm/);
});

test("US-M07-02/03: receipt from a sent order with a discrepancy → «O'tkazish»", async ({ page }) => {
  let current: Body | null = null;
  const s = new Stub(PERMISSIONS, [product("p1", "Guruch «Lazer»", { unit_code: "kg" })]);
  s.on("GET", /^\/api\/v1\/purchase-orders$/, ({ route, url }) => {
    const status = url.searchParams.get("status");
    return json(route, 200, {
      items: !status || status === "sent" ? [header(order("sent"))] : [],
      next_cursor: null,
    });
  })
    .on("GET", /^\/api\/v1\/purchase-orders\/o-1$/, ({ route }) => json(route, 200, order("sent")))
    .on("GET", /^\/api\/v1\/counterparties\/s-1\/debt-balance$/, ({ route }) =>
      json(route, 200, { payable: "0.00", receivable: "0.00" }),
    )
    .on("GET", /^\/api\/v1\/goods-receipts$/, ({ route }) =>
      json(route, 200, { items: current ? [header(current)] : [], next_cursor: null }),
    )
    .on("GET", /^\/api\/v1\/goods-receipts\/r-1$/, ({ route }) => json(route, 200, current))
    .on("POST", /^\/api\/v1\/goods-receipts$/, ({ route }) => {
      current = receipt("draft");
      return json(route, 201, current);
    })
    .on("POST", /^\/api\/v1\/goods-receipts\/r-1\/post$/, ({ route }) => {
      current = receipt("posted");
      return json(route, 200, {
        ...current,
        lots_created: [{ lot_id: "lot-9", product_id: "p1", qty_in: "190.000", unit_cost: "15000.0000" }],
      });
    });
  await s.install(page);
  await page.goto("/app/purchases");
  await page
    .getByRole("table", { name: "Xaridnomalar" })
    .getByRole("row")
    .filter({ hasText: "Z-01-2026-000231" })
    .click();
  await page.getByRole("button", { name: "Kirim yaratish" }).click();

  const sheet = page.getByRole("dialog", { name: "Yangi kirim" });
  await expect(sheet.getByLabel("Yetkazib beruvchi")).toBeDisabled();
  await expect(sheet.getByLabel("Yetkazib beruvchi")).toHaveText(SUPPLIER.name);
  const qty = sheet.getByLabel("Miqdor — Guruch «Lazer»");
  await expect(qty).toHaveValue("200");
  await expect(sheet.getByLabel("Tannarx — Guruch «Lazer»")).toHaveValue(/15\s000/);
  await qty.fill("190");
  await sheet.getByRole("button", { name: "Qoralama saqlash" }).click();
  await expect(sheet.getByText("Miqdor xaridnomadan farq qiladi — sababni tanlang")).toBeVisible();
  expect(s.writesTo(/^\/api\/v1\/goods-receipts$/)).toHaveLength(0);
  await sheet.getByRole("combobox", { name: "Nomuvofiqlik sababi — Guruch «Lazer»" }).click();
  await page.getByRole("option", { name: "Kam keldi" }).click();
  await sheet.getByRole("button", { name: "Qoralama saqlash" }).click();
  await expect(page.getByText("Kirim qoralamasi saqlandi", { exact: true })).toBeVisible();
  expect(s.writesTo(/^\/api\/v1\/goods-receipts$/)[0]?.body).toMatchObject({
    po_id: "o-1",
    supplier_id: null,
    warehouse_id: "w-1",
    kind: "purchase",
    lines: [
      {
        product_id: "p1",
        qty: "190.000",
        cost: "15000.0000",
        vat_rate: "12.00",
        discrepancy_reason: "short",
      },
    ],
  });

  const detail = page.getByRole("dialog", { name: "Qoralama" });
  await expect(detail).toContainText(/3\s192\s000,00 so'm/);
  await detail.getByRole("button", { name: "O'tkazish" }).click();
  await page
    .getByRole("alertdialog", { name: "Kirimni o'tkazasizmi?" })
    .getByRole("button", { name: "O'tkazish" })
    .click();
  await expect(
    page.getByText("Kirim M-01-2026-000154 o'tkazildi — 1 ta partiya", { exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("dialog", { name: "M-01-2026-000154" })).toContainText("O'tkazildi");
  expect(s.writesTo(/\/goods-receipts\/r-1\/post$/)[0]?.idempotencyKey).toBeTruthy();
});

test("US-M07-05: supplier return from a posted receipt — 12-month refusal, then posted", async ({ page }) => {
  let ret: Body | null = null;
  let tooOld = true;
  const returned = (status: string, patch: Body = {}): Body => ({
    id: "sr-1",
    number: status === "posted" ? "MV-01-2026-000007" : null,
    status,
    doc_date: "2026-10-16",
    branch_id: "b-1",
    warehouse_id: "w-1",
    supplier_id: "s-1",
    supplier: SUPPLIER,
    receipt_id: "r-1",
    receipt_number: "M-01-2026-000154",
    reason: "damaged",
    comment: null,
    line_count: 1,
    net_total: "75000.00",
    vat_total: "9000.00",
    invoice_total: "84000.00",
    vat_adjustment_status: status === "posted" ? "awaiting_einvoice" : null,
    created_by: "u-1",
    created_by_name: null,
    created_at: "",
    updated_at: "",
    posted_at: null,
    cancelled_at: null,
    cancel_reason: null,
    lines: [
      {
        id: "srl-1",
        line_no: 1,
        receipt_line_id: "rl-1",
        lot_id: "lot-9",
        product_id: "p1",
        product_name: "Guruch «Lazer»",
        unit_code: "kg",
        qty: "5.000",
        cost: "15000.0000",
        vat_amount: "9000.00",
        net_amount: "75000.00",
        invoice_amount: "84000.00",
      },
    ],
    ...patch,
  });
  const s = new Stub(PERMISSIONS);
  s.on("GET", /^\/api\/v1\/goods-receipts$/, ({ route }) =>
    json(route, 200, { items: [header(receipt("posted"))], next_cursor: null }),
  )
    .on("GET", /^\/api\/v1\/goods-receipts\/r-1$/, ({ route }) => json(route, 200, receipt("posted")))
    .on("GET", /^\/api\/v1\/supplier-returns$/, ({ route }) =>
      json(route, 200, { items: ret ? [header(ret)] : [], next_cursor: null }),
    )
    .on("GET", /^\/api\/v1\/supplier-returns\/sr-1$/, ({ route }) => json(route, 200, ret))
    .on("POST", /^\/api\/v1\/supplier-returns$/, ({ route }) => {
      ret = returned("draft");
      return json(route, 201, ret);
    })
    .on("POST", /^\/api\/v1\/supplier-returns\/sr-1\/post$/, ({ route }) => {
      if (tooOld) {
        return apiError(route, 409, "DOC_INVALID_STATE", "errors.doc_invalid_state", {
          reason: "reverse_sale_required",
          receipt_doc_date: "2025-09-01",
        });
      }
      ret = returned("posted");
      return json(route, 200, ret);
    });
  await s.install(page);
  await page.goto("/app/purchases?tab=receipts");
  await page
    .getByRole("table", { name: "Kirimlar" })
    .getByRole("row")
    .filter({ hasText: "M-01-2026-000154" })
    .click();
  await page
    .getByRole("dialog", { name: "M-01-2026-000154" })
    .getByRole("button", { name: "Qaytarish" })
    .click();

  const sheet = page.getByRole("dialog", { name: "Yetkazib beruvchiga qaytarish" });
  await expect(sheet.getByLabel("Kirim hujjati")).toContainText("M-01-2026-000154");
  const qty = sheet.getByLabel("Qaytariladigan miqdor — Guruch «Lazer»");
  await qty.fill("200");
  await expect(sheet.getByText("Partiya qoldig'idan oshmasin")).toBeVisible();
  await qty.fill("5");
  await sheet.getByRole("combobox", { name: "Qaytarish sababi" }).click();
  await page.getByRole("option", { name: "Shikastlangan" }).click();
  await sheet.getByRole("button", { name: "Qoralama saqlash" }).click();
  await expect.poll(() => s.writesTo(/^\/api\/v1\/supplier-returns$/).length).toBe(1);
  expect(s.writesTo(/^\/api\/v1\/supplier-returns$/)[0]?.body).toMatchObject({
    receipt_id: "r-1",
    reason: "damaged",
    lines: [{ receipt_line_id: "rl-1", lot_id: "lot-9", qty: "5.000" }],
  });

  const detail = page.getByRole("dialog", { name: "Qoralama" });
  await detail.getByRole("button", { name: "Qaytarishni o'tkazish" }).click();
  await page
    .getByRole("alertdialog", { name: "Qaytarishni tasdiqlaysizmi?" })
    .getByRole("button", { name: "Qaytarishni o'tkazish" })
    .click();
  await expect(
    detail.getByText(/12 oydan ko'p vaqt o'tgan — yetkazib beruvchiga qaytarish emas, teskari realizatsiya/),
  ).toBeVisible();

  tooOld = false;
  await detail.getByRole("button", { name: "Qaytarishni o'tkazish" }).click();
  await page
    .getByRole("alertdialog", { name: "Qaytarishni tasdiqlaysizmi?" })
    .getByRole("button", { name: "Qaytarishni o'tkazish" })
    .click();
  await expect(page.getByText("Qaytarish MV-01-2026-000007 o'tkazildi", { exact: true })).toBeVisible();
  await expect(page.getByRole("dialog", { name: "MV-01-2026-000007" })).toContainText(
    "Qo'shimcha e-faktura kutilmoqda",
  );
});

test("19 §9: new supplier — STIR lookup suggestion applied, saved with is_supplier", async ({ page }) => {
  let created: Body | null = null;
  const s = new Stub(PERMISSIONS);
  s.on("GET", /^\/api\/v1\/counterparties$/, ({ route }) =>
    json(route, 200, {
      items: created ? [{ ...created, receivable_balance: "0.00", payable_balance: "0.00" }] : [],
      total: created ? 1 : 0,
      page: 1,
      size: 20,
    }),
  )
    .on("POST", /^\/api\/v1\/counterparties\/lookup-by-stir$/, ({ route, body }) =>
      body?.stir === "305112847"
        ? json(route, 200, {
            stir: "305112847",
            kind: "company",
            name: "«Barakali Don» MChJ",
            legal_address: "Toshkent sh., Chilonzor t., 5-uy",
            bank_account: "20208000900123456001",
            bank_mfo: "00014",
            vat_payer: true,
            director_name: "Karimov A.",
            existing_counterparty_id: null,
          })
        : apiError(route, 404, "NOT_FOUND", "errors.not_found", { resource: "company" }),
    )
    .on("POST", /^\/api\/v1\/counterparties$/, ({ route, body }) => {
      created = supplierRow({
        ...body,
        id: "s-9",
        payable_balance: undefined,
        receivable_balance: undefined,
      });
      return json(route, 201, created);
    })
    .on("GET", /^\/api\/v1\/counterparties\/s-9$/, ({ route }) => json(route, 200, created))
    .on("GET", /^\/api\/v1\/counterparties\/s-9\/debt-balance$/, ({ route }) =>
      json(route, 200, { payable: "0.00", receivable: "0.00" }),
    );
  await s.install(page);
  await page.goto("/app/purchases?tab=suppliers");
  await page.getByRole("button", { name: "Yangi yetkazib beruvchi" }).click();
  const sheet = page.getByRole("dialog", { name: "Yangi yetkazib beruvchi" });

  await sheet.getByLabel("STIR").fill("111111111");
  await sheet.getByRole("button", { name: "Soliq bazasidan to'ldirish" }).click();
  await expect(sheet.getByText(/STIR bo'yicha korxona topilmadi/)).toBeVisible();

  await sheet.getByLabel("STIR").fill("305112847");
  await sheet.getByRole("button", { name: "Soliq bazasidan to'ldirish" }).click();
  const found = sheet.getByRole("region", { name: "Topilgan rekvizitlar" });
  await expect(found).toContainText("«Barakali Don» MChJ");
  await expect(found).toContainText("rahbar Karimov A.");
  // A suggestion only — nothing is saved until the user applies and saves it.
  expect(s.writesTo(/^\/api\/v1\/counterparties$/)).toHaveLength(0);
  await found.getByRole("button", { name: "Qo'llash" }).click();
  await expect(sheet.getByLabel("Nomi")).toHaveValue("«Barakali Don» MChJ");
  await expect(sheet.getByLabel("Yuridik manzil")).toHaveValue("Toshkent sh., Chilonzor t., 5-uy");
  await sheet.getByRole("button", { name: "Saqlash" }).click();

  await expect(page.getByText("«Barakali Don» MChJ qo'shildi", { exact: true })).toBeVisible();
  expect(s.writesTo(/^\/api\/v1\/counterparties$/)[0]?.body).toMatchObject({
    kind: "company",
    name: "«Barakali Don» MChJ",
    stir: "305112847",
    legal_address: "Toshkent sh., Chilonzor t., 5-uy",
    bank_account: "20208000900123456001",
    bank_mfo: "00014",
    vat_payer: true,
    is_supplier: true,
    is_customer: false,
  });
  const detail = page.getByRole("dialog", { name: "«Barakali Don» MChJ" });
  await expect(detail.getByRole("group", { name: "Qarz qoldig'i" })).toContainText("0 so'm");
  await page.keyboard.press("Escape");
  await expect(page.getByRole("table", { name: "Yetkazib beruvchilar" })).toContainText("305112847");
});

test("WEB-08: a refused «Yuborish» is shown inside the confirmation dialog", async ({ page }) => {
  const s = new Stub(PERMISSIONS, [product("p1", "Guruch «Lazer»", { unit_code: "kg" })]);
  s.on("GET", /^\/api\/v1\/purchase-orders$/, ({ route }) =>
    json(route, 200, { items: [header(order("draft"))], next_cursor: null }),
  )
    .on("GET", /^\/api\/v1\/purchase-orders\/o-1$/, ({ route }) => json(route, 200, order("draft")))
    .on("GET", /^\/api\/v1\/counterparties\/s-1\/debt-balance$/, ({ route }) =>
      json(route, 200, { payable: "0.00", receivable: "0.00" }),
    )
    .on("POST", /^\/api\/v1\/purchase-orders\/o-1\/send$/, ({ route }) =>
      apiError(route, 409, "DOC_INVALID_STATE", "errors.doc_invalid_state"),
    );
  await s.install(page);
  await page.goto("/app/purchases");
  await page
    .getByRole("table", { name: "Xaridnomalar" })
    .getByRole("row")
    .filter({ hasText: "Barakali Don" })
    .click();
  await page
    .getByRole("region", { name: "Xaridnoma tafsiloti" })
    .getByRole("button", { name: "Yuborish" })
    .click();
  const confirm = page.getByRole("alertdialog");
  await confirm.getByRole("button", { name: "Yuborish" }).click();
  await expect(confirm.getByRole("alert")).toBeVisible();
  await expect(confirm).toBeVisible();
  expect(s.writesTo(/\/purchase-orders\/o-1\/send$/)).toHaveLength(1);
});

test("WEB-20: ?new=1 without a warehouse opens nothing and leaves the URL", async ({ page }) => {
  const s = new Stub(PERMISSIONS);
  // Chilonzor-3 (the chosen branch) has no warehouse.
  s.on("GET", /^\/api\/v1\/warehouses$/, ({ route }) =>
    json(route, 200, { items: WAREHOUSES.filter((w) => w.branch_id !== "b-1") }),
  );
  await s.install(page);
  await page.goto("/app/purchases?tab=orders&new=1");
  await expect(page.getByRole("banner").getByRole("heading", { name: "Xaridlar" })).toBeVisible();
  await expect.poll(() => new URL(page.url()).searchParams.has("new")).toBe(false);
  expect(new URL(page.url()).searchParams.get("tab")).toBe("orders");
  await expect(page.getByRole("dialog", { name: "Yangi xaridnoma" })).toHaveCount(0);
});

test("WEB-20: ?new=1 with a warehouse opens the sheet once and leaves the URL", async ({ page }) => {
  const s = new Stub(PERMISSIONS);
  await s.install(page);
  await page.goto("/app/purchases?tab=orders&new=1");
  await expect(page.getByRole("dialog", { name: "Yangi xaridnoma" })).toBeVisible();
  await expect.poll(() => new URL(page.url()).searchParams.has("new")).toBe(false);
});
