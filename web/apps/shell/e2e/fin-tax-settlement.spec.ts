import { expect, test } from "@playwright/test";

import { Stub, json, type Body } from "./warehouse-stub.ts";

/**
 * BO-07 «Soliq hisob-kitobi (ST)» block (B4-T07 web half; 20 #8a–#8d; 13 §2.26; QT-M10-07 web part) on the
 * production build: the chosen month has no document → «Qoralama hisoblash» (the server computes the
 * amount) → the draft with Dt 6410 / Kt 4410 → «O'tkazish» confirm «{davr} uchun {amount} provodka
 * yoziladi» → ST number; cancel with a reason. A quarter shows no ST actions.
 */
function summary(period: string): Body {
  return {
    period,
    regime: "vat",
    output_vat: "120000.00",
    input_vat: "84000.00",
    net_vat: "36000.00",
    pending_credit_red_invoices: null,
    pending_credit_pct: null,
    turnover_base: null,
    turnover_rate_pct: null,
    turnover_amount: null,
    tax_settlement_id: null,
  };
}

function settlement(period: string, patch: Body = {}): Body {
  return {
    id: "st-1",
    number: null,
    branch_id: "b-1",
    doc_date: `${period}-28`,
    status: "draft",
    tax_kind: "vat_offset",
    period,
    base_amount: "84000.00",
    rate: null,
    amount: "84000.00",
    expense_account: null,
    comment: null,
    created_by: "u-1",
    created_at: "2026-10-17T06:00:00Z",
    posted_at: null,
    cancelled_at: null,
    cancel_reason: null,
    ...patch,
  };
}

function stub() {
  let doc: Body | null = null;
  const s = new Stub(["tax.vat.view", "accounting.post"])
    .on("GET", /^\/api\/v1\/reports\/vat-summary$/, ({ route, url }) =>
      json(route, 200, summary(url.searchParams.get("period") ?? "")),
    )
    .on("GET", /^\/api\/v1\/vat-moves$/, ({ route }) => json(route, 200, { items: [], next_cursor: null }))
    .on("GET", /^\/api\/v1\/tax-settlements$/, ({ route, url }) =>
      json(route, 200, {
        items: doc && doc.period === url.searchParams.get("period") ? [doc] : [],
        next_cursor: null,
      }),
    )
    .on("POST", /^\/api\/v1\/tax-settlements$/, ({ route, body }) => {
      doc = settlement(typeof body?.period === "string" ? body.period : "");
      return json(route, 201, doc);
    })
    .on("POST", /^\/api\/v1\/tax-settlements\/st-1\/post$/, ({ route }) => {
      doc = { ...doc, status: "posted", number: "ST-01-2026-000003", posted_at: "2026-10-17T06:05:00Z" };
      return json(route, 200, { ...doc, recalculated: false });
    })
    .on("POST", /^\/api\/v1\/tax-settlements\/st-1\/cancel$/, ({ route }) => {
      doc = { ...doc, status: "cancelled", cancel_reason: "Qayta hisoblash kerak" };
      return json(route, 200, doc);
    });
  return s;
}

test("B4-T07 web: ST draft → post → cancel on BO-07", async ({ page }) => {
  const s = stub();
  await s.install(page);
  await page.goto("/app/tax/vat");
  const card = page.getByTestId("tax-settlement");
  await expect(card).toContainText("Dt 6410 / Kt 4410");
  await expect(card).toContainText("hujjat yo'q");

  await card.getByTestId("st-create-vat_offset").click();
  await expect
    .poll(() => s.writesTo(/^\/api\/v1\/tax-settlements$/)[0]?.body)
    .toMatchObject({
      tax_kind: "vat_offset",
      period: expect.stringMatching(/^\d{4}-\d{2}$/) as unknown as string,
    });
  expect(s.writesTo(/^\/api\/v1\/tax-settlements$/)[0]?.body).not.toHaveProperty("branch_id");
  const row = card.getByTestId("st-row");
  await expect(row).toContainText("Qoralama");
  await expect(row.getByTestId("st-amount")).toHaveText(/84\s000,00/);
  await expect(row).toContainText("Provodka: Dt 6410 Byudjetga to'lovlar bo'yicha qarz / Kt 4410");
  await expect(card.getByTestId("st-create-vat_offset")).toBeDisabled();

  await row.getByTestId("st-post").click();
  const confirm = page.getByRole("alertdialog", { name: "Soliq hisob-kitobini o'tkazasizmi?" });
  await expect(confirm).toContainText(/uchun 84\s000,00 so'm provodka yoziladi/);
  await confirm.getByRole("button", { name: "O'tkazish" }).click();
  await expect.poll(() => s.writesTo(/\/tax-settlements\/st-1\/post$/).length).toBe(1);
  await expect(card.getByTestId("st-posted")).toHaveText("Hujjat o'tkazildi: ST-01-2026-000003.");
  await expect(row).toContainText("O'tkazilgan");

  await row.getByRole("button", { name: "Bekor qilish" }).click();
  const cancel = page.getByRole("alertdialog", { name: "Soliq hisob-kitobini bekor qilish" });
  await cancel.getByTestId("cancel-reason").fill("Qayta hisoblash kerak");
  await cancel.getByRole("button", { name: "Bekor qilish" }).click();
  await expect
    .poll(() => s.writesTo(/\/tax-settlements\/st-1\/cancel$/)[0]?.body)
    .toEqual({
      reason: "Qayta hisoblash kerak",
    });
  await expect(row).toContainText("Bekor qilingan");
  // a cancelled document frees the period for a new draft
  await expect(card.getByTestId("st-create-vat_offset")).toBeEnabled();
});

test("BO-07: a quarter has no ST document", async ({ page }) => {
  const s = stub();
  await s.install(page);
  await page.goto("/app/tax/vat");
  await page.getByRole("combobox", { name: "Davr" }).click();
  await page
    .getByRole("option", { name: /-chorak$/ })
    .first()
    .click();
  await expect(page.getByTestId("tax-settlement")).toContainText("davr sifatida oyni tanlang");
  await expect(page.getByTestId("st-create-vat_offset")).toHaveCount(0);
});
