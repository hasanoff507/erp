import { expect, test, type Page } from "@playwright/test";

import { Stub, apiError, json, type Body } from "./warehouse-stub.ts";

/**
 * BO-04 «Yetkazib beruvchiga to'lov» (B4-SCR-BO-04 B4 part; 19 §11; 13 §2.16; qaror #47; US-M07-04,
 * US-M08-11; QT-M07-05 web part) on the production build: supplier → open documents oldest first → the
 * auto allocation preview → overpay warning (advance 4310) → «To'lovni qayd etish» (bank, server allocates);
 * a manual split; the `block` overpay policy; cancel with a reason.
 */
const SUPPLIER = { id: "s-1", name: "«Barakali Don» MChJ", stir: "305112847" };

const OPEN_DOCS = {
  supplier_id: "s-1",
  payable_balance: "1500000.00",
  advance_balance: "0.00",
  items: [
    {
      target_doc_type: "debt_openings",
      target_doc_id: "do-1",
      number: "BQ-01-2026-000001",
      doc_date: "2026-08-01",
      due_date: null,
      total: "500000.00",
      outstanding: "500000.00",
      einvoice_id: null,
      einvoice_risk_flag: null,
      vat_pending: "0.00",
    },
    {
      target_doc_type: "goods_receipts",
      target_doc_id: "gr-1",
      number: "KR-01-2026-000017",
      doc_date: "2026-09-10",
      due_date: "2026-10-10",
      total: "1120000.00",
      outstanding: "1000000.00",
      einvoice_id: "e-1",
      einvoice_risk_flag: "red",
      vat_pending: "120000.00",
    },
  ],
};

function payment(patch: Body = {}): Body {
  return {
    id: "p-1",
    number: "SP-01-2026-000001",
    status: "posted",
    doc_date: "2026-10-17",
    branch_id: "b-1",
    supplier_id: "s-1",
    supplier: SUPPLIER,
    method: "bank",
    amount: "1800000.00",
    cash_register_id: null,
    shift_id: null,
    allocations: [
      {
        target_doc_type: "debt_openings",
        target_doc_id: "do-1",
        target_number: "BQ-01-2026-000001",
        target_doc_date: "2026-08-01",
        amount: "500000.00",
        vat_credit_unlocked: "0.00",
      },
      {
        target_doc_type: "goods_receipts",
        target_doc_id: "gr-1",
        target_number: "KR-01-2026-000017",
        target_doc_date: "2026-09-10",
        amount: "1000000.00",
        vat_credit_unlocked: "107142.86",
      },
    ],
    advance_amount: "300000.00",
    vat_credit_unlocked: [{ einvoice_id: "e-1", vat_amount: "107142.86" }],
    comment: null,
    created_by: "u-1",
    created_by_name: "Akmal Karimov",
    created_at: "2026-10-17T06:00:00Z",
    posted_at: "2026-10-17T06:00:00Z",
    cancelled_at: null,
    cancel_reason: null,
    ...patch,
  };
}

function stub(opts: { block?: boolean } = {}) {
  const payments: Body[] = [];
  const s = new Stub(["stock.view", "purchases.pay"])
    .on("GET", /^\/api\/v1\/supplier-payments$/, ({ route }) =>
      json(route, 200, { items: payments, next_cursor: null }),
    )
    .on("GET", /^\/api\/v1\/supplier-payments\/open-documents$/, ({ route, url }) => {
      expect(url.searchParams.get("supplier_id")).toBe("s-1");
      return json(route, 200, OPEN_DOCS);
    })
    .on("GET", /^\/api\/v1\/counterparties$/, ({ route }) =>
      json(route, 200, {
        items: [
          {
            ...SUPPLIER,
            kind: "company",
            phone: null,
            is_supplier: true,
            is_customer: false,
            archived_at: null,
          },
        ],
        total: 1,
        page: 1,
        size: 10,
      }),
    )
    .on("GET", /^\/api\/v1\/shifts$/, ({ route }) => json(route, 200, { items: [], next_cursor: null }))
    .on("GET", /^\/api\/v1\/cash-registers$/, ({ route }) => json(route, 200, { items: [] }))
    .on("POST", /^\/api\/v1\/supplier-payments$/, ({ route, body }) => {
      if (opts.block)
        return apiError(route, 422, "SUPPLIER_OVERPAY_BLOCKED", "errors.supplier_overpay_blocked", {
          debt: "1500000.00",
          amount: typeof body?.amount === "string" ? body.amount : "",
        });
      const created = payment({ amount: body?.amount });
      payments.unshift(created);
      return json(route, 201, {
        ...created,
        warnings: [
          {
            code: "SUPPLIER_OVERPAY_ADVANCE",
            params: { debt: "1500000.00", amount: "1800000.00", advance: "300000.00" },
          },
        ],
      });
    })
    .on("GET", /^\/api\/v1\/supplier-payments\/([^/]+)$/, ({ route, match }) => {
      const p = payments.find((x) => x.id === match[1]);
      return p ? json(route, 200, p) : apiError(route, 404, "NOT_FOUND", "errors.not_found");
    })
    .on("POST", /^\/api\/v1\/supplier-payments\/([^/]+)\/cancel$/, ({ route, match }) => {
      const p = payments.find((x) => x.id === match[1]);
      if (p)
        Object.assign(p, {
          status: "cancelled",
          cancelled_at: "2026-10-17T07:00:00Z",
          cancel_reason: "Xato",
        });
      return json(route, 200, p);
    });
  return s;
}

async function openForm(page: Page) {
  await page.goto("/app/purchases?tab=payments");
  await expect(page.getByRole("tab", { name: "Yetkazib beruvchiga to'lov" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await page.getByTestId("payment-new").click();
  const sheet = page.getByRole("dialog", { name: "Yetkazib beruvchiga to'lov" });
  await sheet.getByLabel("Yetkazib beruvchi").click();
  await page.getByRole("searchbox", { name: "Yetkazib beruvchi qidirish" }).fill("Baraka");
  await page.getByRole("button", { name: /Barakali Don/ }).click();
  await expect(sheet.getByTestId("payable")).toContainText(/1\s500\s000,00/);
  return sheet;
}

test("B4-SCR-BO-04: oldest-first preview, overpay → advance warning, posted, then cancelled", async ({
  page,
}) => {
  const s = stub();
  await s.install(page);
  const sheet = await openForm(page);

  const table = sheet.getByTestId("allocation-table");
  await expect(table.getByRole("row").nth(1)).toContainText("Boshlang'ich qarz BQ-01-2026-000001");
  await expect(table.getByRole("row").nth(2)).toContainText("QQS krediti kutilmoqda");
  await sheet.getByTestId("payment-amount").fill("1800000");
  await expect(table.getByRole("row").nth(1)).toContainText(/500\s000,00/);
  await expect(table.getByRole("row").nth(2)).toContainText(/1\s000\s000,00/);
  await expect(sheet.getByTestId("overpay-warning")).toContainText(
    /Ortiqcha 300\s000,00 so'm avans sifatida yoziladi/,
  );
  await sheet.getByTestId("payment-submit").click();

  await expect.poll(() => s.writesTo(/^\/api\/v1\/supplier-payments$/).length).toBe(1);
  const write = s.writesTo(/^\/api\/v1\/supplier-payments$/)[0];
  expect(write?.body).toEqual({
    supplier_id: "s-1",
    amount: "1800000.00",
    method: "bank",
    doc_date: expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/) as unknown as string,
    comment: null,
  });
  expect(write?.idempotencyKey).toBeTruthy();
  await expect(page.getByTestId("payment-created")).toContainText(/avans sifatida yozildi/);

  const list = page.getByRole("table", { name: "Yetkazib beruvchiga to'lovlar" });
  await list.getByRole("row").filter({ hasText: "SP-01-2026-000001" }).click();
  const detail = page.getByRole("dialog", { name: "SP-01-2026-000001" });
  await expect(detail).toContainText("QQS krediti ochildi");
  await detail.getByTestId("payment-cancel").click();
  const confirm = page.getByRole("alertdialog", { name: "To'lovni bekor qilish" });
  await confirm.getByRole("textbox").fill("Xato");
  await confirm.getByRole("button", { name: "Bekor qilish" }).click();
  await expect
    .poll(() => s.writesTo(/\/supplier-payments\/p-1\/cancel$/)[0]?.body)
    .toEqual({ reason: "Xato" });
});

test("BO-04: manual split must equal the debt part; the block policy refuses an overpay", async ({
  page,
}) => {
  const s = stub({ block: true });
  await s.install(page);
  const sheet = await openForm(page);
  await sheet.getByTestId("payment-amount").fill("700000");
  await sheet.getByTestId("manual-split").click();
  await sheet.getByRole("textbox", { name: "KR-01-2026-000017 uchun summa" }).fill("600000");
  await sheet.getByTestId("payment-submit").click();
  await expect(sheet).toContainText("Taqsimot jami qarz qismiga teng emas.");
  expect(s.writesTo(/^\/api\/v1\/supplier-payments$/)).toHaveLength(0);
  await sheet.getByRole("textbox", { name: "BQ-01-2026-000001 uchun summa" }).fill("100000");
  await sheet.getByTestId("payment-submit").click();
  await expect
    .poll(() => s.writesTo(/^\/api\/v1\/supplier-payments$/)[0]?.body?.allocations)
    .toEqual([
      { target_doc_type: "debt_openings", target_doc_id: "do-1", amount: "100000.00" },
      { target_doc_type: "goods_receipts", target_doc_id: "gr-1", amount: "600000.00" },
    ]);
  // qaror #47 `block`: the server refusal is explained with the debt and the amount
  await expect(sheet.getByTestId("payment-error")).toContainText(
    /qarz 1\s500\s000,00 so'm, to'lov 700\s000,00 so'm/,
  );
});
