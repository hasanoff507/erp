import { expect, test, type Page } from "@playwright/test";

import { Stub, json, type Body } from "./warehouse-stub.ts";

/**
 * BO-24 «Bank tushumi tasdig'i» (B4-SCR-BO-24; 20 #55a–#55h; US-M11-04; QT-M11-07/-09/-10/-11 web parts)
 * on the production build: the 5710 transit panel (card split integrated / terminal-less), statement import
 * → result (drafts, duplicates, unmatched lines) → «Qoralamalarni ko'rish» → open the draft → edit the
 * commission (PATCH with version, Ctrl+S) → «O'tkazish» confirm → posted with its ledger lines; a manual
 * draft above the transit balance shows the server's field error with the available amount.
 */
function settlement(id: string, patch: Body = {}): Body {
  return {
    id,
    number: null,
    branch_id: "b-1",
    doc_date: "2026-10-16",
    status: "draft",
    source: "statement_import",
    method: "card",
    settled_from: "2026-10-15",
    settled_to: "2026-10-15",
    gross_amount: "950000.00",
    commission_amount: "9500.00",
    variance_amount: "0.00",
    net_amount: "940500.00",
    bank_ref: "123456",
    attachment_id: null,
    statement_import_id: "imp-1",
    comment: null,
    created_by: "u-1",
    created_at: "2026-10-16T09:00:00Z",
    posted_at: null,
    cancelled_at: null,
    cancelled_by: null,
    cancel_reason: null,
    version: 1,
    ...patch,
  };
}

const TRANSIT = {
  as_of: "2026-10-16",
  items: [
    {
      branch_id: "b-1",
      method: "card",
      balance: "950000.00",
      oldest_unsettled_date: "2026-10-15",
      card_breakdown: { integrated: "550000.00", manual: "400000.00" },
    },
    {
      branch_id: "b-1",
      method: "collection",
      balance: "2000000.00",
      oldest_unsettled_date: "2026-10-14",
      card_breakdown: null,
    },
    {
      branch_id: "b-2",
      method: "uzqr",
      balance: "120000.00",
      oldest_unsettled_date: "2026-10-15",
      card_breakdown: null,
    },
  ],
};

const IMPORT_RESULT = {
  import_id: "imp-1",
  file_sha256: "ab",
  account: "20208000900100200300",
  period_from: "2026-10-15",
  period_to: "2026-10-15",
  drafts_created: 1,
  draft_ids: ["d-1"],
  duplicates: 1,
  ignored_outgoing: 2,
  unmatched_lines: [
    {
      line_no: 41,
      number: "77",
      date: "2026-10-15",
      amount: "50000.00",
      payer_name: "NOMA'LUM MCHJ",
      purpose: "To'lov",
      reason: "unknown_method",
    },
  ],
  unmatched_card_transactions: [],
};

/** The multipart import is answered by its own route (the shared stub parses JSON bodies only). */
async function install(page: Page) {
  const docs: Body[] = [];
  const s = stub(docs);
  await s.install(page);
  const imports: { contentType: string; idempotencyKey: string | undefined; body: string }[] = [];
  await page.route("**/api/v1/bank-settlements/imports", (route) => {
    const request = route.request();
    imports.push({
      contentType: request.headers()["content-type"] ?? "",
      idempotencyKey: request.headers()["idempotency-key"],
      body: request.postData() ?? "",
    });
    docs.push(settlement("d-1"));
    return json(route, 201, IMPORT_RESULT);
  });
  return { s, imports };
}

function stub(docs: Body[]) {
  const s = new Stub(["bank_settlements.manage"])
    .on("GET", /^\/api\/v1\/bank-settlements\/transit-balances$/, ({ route }) => json(route, 200, TRANSIT))
    .on("GET", /^\/api\/v1\/bank-settlements$/, ({ route }) =>
      json(route, 200, { items: docs, next_cursor: null }),
    )
    .on("GET", /^\/api\/v1\/bank-settlements\/([^/]+)$/, ({ route, match }) => {
      const d = docs.find((x) => x.id === match[1]);
      return d
        ? json(route, 200, {
            ...d,
            ledger_entries:
              d.status === "posted"
                ? [
                    {
                      id: "l1",
                      entry_date: "2026-10-16",
                      account_dt: "5110",
                      account_kt: "5710",
                      amount: d.net_amount,
                      analytics: {},
                      reversal_of_id: null,
                    },
                    {
                      id: "l2",
                      entry_date: "2026-10-16",
                      account_dt: "9430",
                      account_kt: "5710",
                      amount: d.commission_amount,
                      analytics: {},
                      reversal_of_id: null,
                    },
                  ]
                : [],
          })
        : json(route, 404, {
            error: { code: "NOT_FOUND", message_key: "errors.not_found", params: {}, details: [] },
          });
    })
    .on("PATCH", /^\/api\/v1\/bank-settlements\/([^/]+)$/, ({ route, match, body }) => {
      const d = docs.find((x) => x.id === match[1]);
      if (!d) return json(route, 404, {});
      Object.assign(d, {
        commission_amount: body?.commission_amount ?? d.commission_amount,
        net_amount: "941000.00",
        version: (typeof d.version === "number" ? d.version : 1) + 1,
      });
      return json(route, 200, d);
    })
    .on("POST", /^\/api\/v1\/bank-settlements\/([^/]+)\/post$/, ({ route, match }) => {
      const d = docs.find((x) => x.id === match[1]);
      if (!d) return json(route, 404, {});
      Object.assign(d, {
        status: "posted",
        number: "BT-01-2026-000012",
        posted_at: "2026-10-16T10:00:00Z",
        version: (typeof d.version === "number" ? d.version : 1) + 1,
      });
      return json(route, 200, d);
    })
    .on("POST", /^\/api\/v1\/bank-settlements$/, ({ route }) =>
      json(route, 422, {
        error: {
          code: "VALIDATION_ERROR",
          message_key: "errors.validation",
          params: { available: "950000.00" },
          details: [{ field: "gross_amount", message_key: "validation.bank_settlement_exceeds_in_transit" }],
        },
      }),
    );
  return s;
}

test("B4-SCR-BO-24: transit panel; statement import → review the draft → commission edit → post", async ({
  page,
}) => {
  const { s, imports } = await install(page);
  await page.goto("/app/finance/bank-settlements");
  await expect(
    page.getByRole("banner").getByRole("heading", { name: "Bank tushumi tasdig'i" }),
  ).toBeVisible();

  // QT-M11-09: 5710 by branch × method, the card row split (20 #55b card_breakdown).
  const transit = page.getByTestId("transit-table");
  await expect(transit.getByRole("row").filter({ hasText: "Karta (integratsiyalangan)" })).toContainText(
    /550\s000,00/,
  );
  await expect(transit.getByRole("row").filter({ hasText: "Karta (terminalsiz)" })).toContainText(
    /400\s000,00/,
  );
  await expect(page.getByTestId("transit-total")).toHaveText(/3\s070\s000,00/);

  // QT-M11-10: the import only proposes drafts.
  await page.getByTestId("bank-import").click();
  const dialog = page.getByRole("alertdialog", { name: "Bank ko'chirmasini yuklash" });
  await dialog.locator('input[type="file"]').setInputFiles({
    name: "vypiska_15-10-2026.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("1CClientBankExchange\r\nВерсияФормата=1.03\r\n"),
  });
  await dialog.getByRole("button", { name: "Yuklash" }).click();
  await expect.poll(() => imports.length).toBe(1);
  expect(imports[0]?.idempotencyKey).toBeTruthy();
  expect(imports[0]?.contentType).toContain("multipart/form-data");
  expect(imports[0]?.body).toContain("vypiska_15-10-2026.txt");
  const result = page.getByTestId("import-result");
  await expect(result).toContainText(
    "1 ta qoralama yaratildi · 1 ta dublikat o'tkazib yuborildi · 1 ta qator mos kelmadi",
  );
  await result.getByRole("button", { name: "Mos kelmaganlar (1)" }).click();
  await expect(page.getByTestId("unmatched-lines")).toContainText("To'lovchi (usul) aniqlanmadi");
  await result.getByRole("button", { name: "Qoralamalarni ko'rish" }).click();
  await expect
    .poll(() => {
      const q = s.queries.filter((x) => x.path === "/api/v1/bank-settlements").at(-1)?.query;
      return q ? `${q.get("status")}|${q.get("source")}` : "";
    })
    .toBe("draft|statement_import");

  // Review the draft: commission 9 500 → 9 000 (PATCH with version), then post.
  const table = page.getByRole("table", { name: "Bank tushumi hujjatlari" });
  await table.getByRole("row").filter({ hasText: "Importdan" }).click();
  await expect(page).toHaveURL(/\/app\/finance\/bank-settlements\/d-1$/);
  await expect(page.getByTestId("bank-net")).toHaveText(/940\s500,00/);
  await page.getByTestId("bank-commission").fill("9000");
  await expect(page.getByTestId("bank-net")).toHaveText(/941\s000,00/);
  await page.getByTestId("bank-commission").press("Control+s");
  await expect
    .poll(() => s.writesTo(/\/bank-settlements\/d-1$/)[0]?.body)
    .toEqual({
      version: 1,
      commission_amount: "9000.00",
    });
  await page.getByTestId("bank-post").click();
  const confirm = page.getByRole("alertdialog", { name: "Hujjatni o'tkazasizmi?" });
  await expect(confirm).toContainText(
    /Bank hisobiga 941\s000,00 so'm o'tkaziladi, komissiya 9\s000,00 so'm xarajatga yoziladi/,
  );
  await confirm.getByRole("button", { name: "O'tkazish" }).click();
  await expect.poll(() => s.writesTo(/\/bank-settlements\/d-1\/post$/).length).toBe(1);
  await expect(page.getByRole("heading", { name: "BT-01-2026-000012" })).toBeVisible();
  await expect(page.getByTestId("bank-lines")).toContainText("5110");
  await expect(page.getByTestId("bank-lines")).toContainText("9430");
});

test("BO-24: a manual draft above the transit balance — field error with the available amount", async ({
  page,
}) => {
  const { s } = await install(page);
  await page.goto("/app/finance/bank-settlements");
  await page.getByTestId("bank-new").click();
  await expect(page).toHaveURL(/\/bank-settlements\/new$/);
  const panel = page.getByRole("region", { name: "Yangi bank tushumi" });
  await panel.getByRole("combobox", { name: "To'lov usuli" }).click();
  await page.getByRole("option", { name: "Karta" }).click();
  await expect(panel).toContainText(/Yo'ldagi pul qoldig'i: 950\s000,00/);
  await panel.getByRole("button", { name: "Qoldiqni qo'yish" }).click();
  await expect(page.getByTestId("bank-gross")).toHaveValue(/950\s000/);
  await page.getByTestId("bank-gross").fill("1000000");
  await page.getByTestId("bank-save").click();
  await expect
    .poll(() => s.writesTo(/^\/api\/v1\/bank-settlements$/)[0]?.body)
    .toMatchObject({
      branch_id: "b-1",
      method: "card",
      gross_amount: "1000000.00",
      commission_amount: "0.00",
      variance_amount: "0.00",
    });
  await expect(panel).toContainText(/Summa yo'ldagi pul qoldig'idan katta — mavjud: 950\s000,00/);
});
