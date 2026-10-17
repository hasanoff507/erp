import { expect, test } from "@playwright/test";

import { Stub, apiError, json, product, type Body } from "./warehouse-stub.ts";

/**
 * BO-03 «Inventarizatsiyalar» (07, 19 §14, US-M05-01…03) on the production build: the review list,
 * detail (kutilgan / sanalgan / farq / summa), «Farqni tasdiqlash» → 422 COUNT_LINES_INCOMPLETE →
 * «Sanalmaganlarni 0 deb olib tasdiqlash» (`?treat_uncounted_as_zero=true`); starting a count, the
 * back-office line entry and «Sanashni yakunlash» (submit-for-review).
 */
const PERMISSIONS = ["stock.view", "stock.count.create", "stock.count.post"];

function line(id: string, name: string, patch: Body = {}): Body {
  return {
    id,
    line_no: 1,
    product_id: `p${id}`,
    product_name: name,
    snapshot_qty: "10.000",
    expected: "10.000",
    counted: null,
    counted_at: null,
    diff: null,
    amount: null,
    ...patch,
  };
}

function count(status: string, lines: Body[], patch: Body = {}): Body {
  const counted = lines.filter((l) => l.counted !== null).length;
  return {
    id: "c-1",
    number: "INV-000012",
    status,
    doc_date: "2026-10-16",
    branch_id: "b-1",
    warehouse_id: "w-1",
    started_at: "2026-10-16T05:00:00Z",
    responsible_user_id: null,
    comment: null,
    line_count: lines.length,
    counted_count: counted,
    uncounted_count: lines.length - counted,
    created_by: "u-1",
    created_at: "2026-10-16T05:00:00Z",
    posted_at: null,
    cancelled_at: null,
    cancel_reason: null,
    lines,
    ...patch,
  };
}

const REVIEW_LINES = [
  line("1", "Choy ko'k 100 g", { counted: "8.000", diff: "-2.000", amount: "-24000.00" }),
  line("2", "Sut 2,5% 1 l", { counted: "11.000", diff: "1.000", amount: "5000.50" }),
  line("3", "Shakar"),
];

test("US-M05-02/03: review → «Farqni tasdiqlash» → incomplete → treat uncounted as zero", async ({
  page,
}) => {
  let state = count("review", REVIEW_LINES);
  const s = new Stub(PERMISSIONS);
  s.on("GET", /^\/api\/v1\/stock-counts$/, ({ route, url }) => {
    const status = url.searchParams.get("status");
    const { lines: _l, ...summary } = state;
    return json(route, 200, {
      items: !status || status === state.status ? [summary] : [],
      next_cursor: null,
    });
  })
    .on("GET", /^\/api\/v1\/stock-counts\/c-1$/, ({ route }) => json(route, 200, state))
    .on("POST", /^\/api\/v1\/stock-counts\/c-1\/post$/, ({ route, url }) => {
      if (url.searchParams.get("treat_uncounted_as_zero") !== "true") {
        return apiError(route, 422, "COUNT_LINES_INCOMPLETE", "errors.count_lines_incomplete", {
          uncounted_count: 1,
        });
      }
      state = count("posted", REVIEW_LINES, { posted_at: "2026-10-16T12:00:00Z" });
      return json(route, 200, {
        id: "c-1",
        number: "INV-000012",
        status: "posted",
        shortage_lines: [
          {
            line_id: "1",
            product_id: "p1",
            expected: "10.000",
            counted: "8.000",
            diff: "-2.000",
            amount: "-24000.00",
          },
          {
            line_id: "3",
            product_id: "p3",
            expected: "10.000",
            counted: "0.000",
            diff: "-10.000",
            amount: "-104000.00",
          },
        ],
        surplus_lines: [
          {
            line_id: "2",
            product_id: "p2",
            expected: "10.000",
            counted: "11.000",
            diff: "1.000",
            amount: "5000.50",
          },
        ],
      });
    });
  await s.install(page);
  await page.goto("/app/warehouse/stock?tab=counts");

  await expect(page.getByRole("tab", { name: /Inventarizatsiyalar\s*1/ })).toBeVisible();
  const table = page.getByRole("table", { name: "Inventarizatsiyalar" });
  const row = table.getByRole("row").filter({ hasText: "INV-000012" });
  await expect(row).toContainText("2 / 3 sanalgan");
  await expect(row).toContainText("Tasdiq kutilmoqda");
  const listed = s.queries.filter((q) => q.path === "/api/v1/stock-counts").at(-1);
  expect(listed?.query.get("status")).toBe("review");
  expect(listed?.query.get("warehouse_id")).toBe("w-1");
  await row.click();

  const sheet = page.getByRole("dialog", { name: "INV-000012" });
  const summary = sheet.getByRole("definition");
  await expect(summary.first()).toContainText(/24\s000/);
  const lines = sheet.getByRole("table", { name: "Sanash qatorlari" });
  await expect(lines.getByRole("row").filter({ hasText: "Choy ko'k 100 g" })).toContainText("−2");
  await expect(lines.getByRole("row").filter({ hasText: "Shakar" })).toContainText("sanalmagan");

  await sheet.getByRole("button", { name: "Farqni tasdiqlash" }).click();
  const dialog = page.getByRole("alertdialog", { name: "Farqni tasdiqlash" });
  await expect(dialog).toContainText(/Kamomad 24\s000 so'm, ortiqcha 5\s001 so'm hisobga olinadi/);
  await dialog.getByRole("button", { name: "Farqni tasdiqlash" }).click();
  await expect(dialog.getByText(/1 ta tovar sanalmagan\. Ularni 0 deb olib/)).toBeVisible();
  await dialog.getByRole("button", { name: "Sanalmaganlarni 0 deb olib tasdiqlash" }).click();
  await expect(page.getByText("Inventarizatsiya INV-000012 tasdiqlandi", { exact: true })).toBeVisible();
  await expect(sheet.getByText("Tasdiqlandi").first()).toBeVisible();

  const posts = s.writesTo(/\/stock-counts\/c-1\/post$/);
  expect(posts.map((p) => p.query.get("treat_uncounted_as_zero"))).toEqual([null, "true"]);
  expect(posts[1]?.idempotencyKey).toBeTruthy();
  expect(posts[1]?.csrf).toBe("csrf-e2e");
});

test("US-M05-01: start a count, enter counted quantities in the back office, submit for review", async ({
  page,
}) => {
  let state = count("counting", [line("1", "Choy ko'k 100 g"), line("2", "Sut 2,5% 1 l")], { number: null });
  const s = new Stub(PERMISSIONS, [product("p1", "Choy ko'k 100 g")]);
  s.on("POST", /^\/api\/v1\/stock-counts$/, ({ route }) => json(route, 201, state))
    .on("GET", /^\/api\/v1\/stock-counts\/c-1$/, ({ route }) => json(route, 200, state))
    .on("POST", /^\/api\/v1\/stock-counts\/c-1\/lines$/, ({ route, body }) => {
      const sent = body?.lines as { product_id: string; counted: string }[];
      state = {
        ...state,
        lines: (state.lines as Body[]).map((l) => {
          const hit = sent.find((x) => x.product_id === l.product_id);
          return hit ? { ...l, counted: hit.counted, diff: "-1.000", amount: "-17500.00" } : l;
        }),
      };
      return json(route, 200, state);
    })
    .on("POST", /^\/api\/v1\/stock-counts\/c-1\/submit-for-review$/, ({ route }) => {
      state = { ...state, status: "review" };
      return json(route, 200, state);
    });
  await s.install(page);
  await page.goto("/app/warehouse/stock");
  await page.getByRole("button", { name: "Inventarizatsiya", exact: true }).click();
  const start = page.getByRole("alertdialog", { name: "Inventarizatsiyani boshlaysizmi?" });
  await expect(start).toContainText("Asosiy ombor — butun ombor");
  await start.getByRole("button", { name: "Boshlash" }).click();
  expect(s.writesTo(/^\/api\/v1\/stock-counts$/)[0]?.body).toMatchObject({
    warehouse_id: "w-1",
    responsible_user_id: null,
  });

  const sheet = page.getByRole("dialog", { name: "Raqamsiz" });
  await sheet.getByLabel("Sanalgan miqdor — Choy ko'k 100 g").fill("9");
  await expect(sheet.getByRole("button", { name: "Sanashni yakunlash" })).toBeDisabled();
  await sheet.getByRole("button", { name: "Saqlash (1)" }).click();
  await expect(sheet.getByRole("button", { name: "Saqlash (0)" })).toBeDisabled();
  expect(s.writesTo(/\/stock-counts\/c-1\/lines$/)[0]?.body).toEqual({
    lines: [{ product_id: "p1", counted: "9.000" }],
  });

  await sheet.getByRole("button", { name: "Sanashni yakunlash" }).click();
  const confirm = page.getByRole("alertdialog", { name: "Barcha tovarlar sanaldimi?" });
  await expect(confirm).toContainText("1 ta tovar hali sanalmagan");
  await confirm.getByRole("button", { name: "Sanashni yakunlash" }).click();
  await expect(sheet.getByText("Tasdiq kutilmoqda").first()).toBeVisible();
  expect(s.writesTo(/submit-for-review$/)).toHaveLength(1);
});

test("WEB-08: a refused «Sanashni yakunlash» is shown inside the confirmation dialog", async ({ page }) => {
  const state = count("counting", [line("1", "Choy ko'k 100 g", { counted: "9.000" })], {
    number: "INV-000013",
  });
  const s = new Stub(PERMISSIONS);
  s.on("GET", /^\/api\/v1\/stock-counts$/, ({ route }) => {
    const { lines: _l, ...summary } = state;
    return json(route, 200, { items: [summary], next_cursor: null });
  })
    .on("GET", /^\/api\/v1\/stock-counts\/c-1$/, ({ route }) => json(route, 200, state))
    .on("POST", /^\/api\/v1\/stock-counts\/c-1\/submit-for-review$/, ({ route }) =>
      apiError(route, 409, "DOC_INVALID_STATE", "errors.doc_invalid_state"),
    );
  await s.install(page);
  await page.goto("/app/warehouse/stock?tab=counts");
  await page
    .getByRole("table", { name: "Inventarizatsiyalar" })
    .getByRole("row")
    .filter({ hasText: "INV-000013" })
    .click();
  const sheet = page.getByRole("dialog", { name: "INV-000013" });
  await sheet.getByRole("button", { name: "Sanashni yakunlash" }).click();
  const confirm = page.getByRole("alertdialog", { name: "Barcha tovarlar sanaldimi?" });
  await confirm.getByRole("button", { name: "Sanashni yakunlash" }).click();
  await expect(confirm.getByRole("alert")).toBeVisible();
  await expect(confirm).toBeVisible();
  expect(s.writesTo(/submit-for-review$/)).toHaveLength(1);
});
