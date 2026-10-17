import { expect, test, type Page, type Route } from "@playwright/test";

/**
 * BO-21 ③b «Boshlang'ich qoldiq» (07 `openingStockMethod`, optional) on the production build, signed in
 * after signup: Excel/CSV — the import flow with `kind=opening_stock` (19 §6: template → upload →
 * validate → commit → `line_count`), and «Qo'lda» — POST /stock-openings → /post (19 §16).
 * «Davom» never waits for ③b.
 */
const session = {
  user: { id: "u-1", full_name: "Akmal Karimov", phone_masked: "+998 90 *** ** 67" },
  tenant: { id: "t-1", name: "Baraka do'koni" },
  branches: [{ id: "b-1", name: "Asosiy filial" }],
  roles: ["owner"],
  permissions: ["catalog.manage", "stock.view", "stock.opening.manage", "reports.sales.view"],
  scope: ["catalog", "stock", "reports"],
  client_id: "web-bff",
  sub_status: "trial",
  access_expires_at: 0,
};

type Body = Record<string, unknown>;

function json(route: Route, status: number, body: unknown) {
  return route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
}

function product(id: string, name: string, barcode: string): Body {
  return {
    id,
    name,
    name_ru: null,
    category_id: null,
    unit_code: "pcs",
    mxik_code: null,
    package_code: null,
    vat_rate: "12.00",
    vat_exemption_code: null,
    is_marked: false,
    marking_group_code: null,
    is_weighed: false,
    min_stock: null,
    archived_at: null,
    version: 1,
    barcodes: [{ id: `bc-${id}`, barcode, kind: "ean13", units_per_barcode: "1.000" }],
    current_price: null,
    current_cost: null,
    markup_pct: null,
  };
}

function job(status: string, rows: { total: number; ok: number }, result: Body = {}): Body {
  return {
    id: "job-1",
    kind: "opening_stock",
    status,
    total_rows: rows.total,
    ok_rows: rows.ok,
    error_rows: rows.total - rows.ok,
    result,
    created_at: "2026-10-17T08:00:00Z",
  };
}

interface Backend {
  uploads: string[];
  commits: unknown[];
  openings: Body[];
  posts: string[];
  templates: string[];
}

async function stubBackend(page: Page): Promise<Backend> {
  const backend: Backend = { uploads: [], commits: [], openings: [], posts: [], templates: [] };
  let states: Body[] = [];

  await page.route("**/auth/session", (route) => json(route, 200, session));
  await page.route("**/auth/terms", (route) => json(route, 200, { items: [] }));
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const method = request.method();
    if (path === "/api/v1/auth/csrf") return json(route, 200, { csrf_token: "csrf-e2e" });
    if (path === "/api/v1/import-jobs/templates/opening_stock") {
      backend.templates.push(path);
      return route.fulfill({
        status: 200,
        contentType: "text/csv; charset=utf-8",
        headers: { "Content-Disposition": 'attachment; filename="opening_stock.csv"' },
        body: "barcode;qty;unit_cost;expiry_date\n",
      });
    }
    if (path === "/api/v1/import-jobs" && method === "POST") {
      backend.uploads.push(request.postData() ?? "");
      states = [job("validating", { total: 2, ok: 0 }), job("validated", { total: 2, ok: 2 })];
      return json(route, 201, { id: "job-1", kind: "opening_stock", status: "uploaded", total_rows: 0 });
    }
    if (path === "/api/v1/import-jobs/job-1/validate") {
      return json(route, 202, { job_id: "job-1", status: "validating" });
    }
    if (path === "/api/v1/import-jobs/job-1/commit") {
      backend.commits.push(request.postDataJSON());
      states = [job("committed", { total: 2, ok: 2 }, { created_doc_ids: ["so-9"], line_count: 2 })];
      return json(route, 202, { job_id: "job-1", status: "committing" });
    }
    if (path === "/api/v1/import-jobs/job-1" && method === "GET") {
      const next = states.length > 1 ? states.shift() : states[0];
      return json(route, 200, next ?? {});
    }
    if (path === "/api/v1/warehouses") {
      return json(route, 200, {
        items: [
          {
            id: "w-1",
            branch_id: "b-1",
            name: "Asosiy ombor",
            type: "store",
            inventory_account: "2920",
            version: 1,
          },
        ],
      });
    }
    if (path === "/api/v1/products" && method === "GET") {
      const search = url.searchParams.get("search") ?? "";
      const items = [
        product("p1", "Sut 2,5% 1 l", "4780012340054"),
        product("p2", "Non «Patir»", "4780012340047"),
      ].filter((p) => String(p.name).toLowerCase().includes(search.toLowerCase()));
      return json(route, 200, { items, total: items.length, page: 1, size: 10 });
    }
    if (path === "/api/v1/stock-openings" && method === "POST") {
      const body = request.postDataJSON() as Body;
      backend.openings.push(body);
      return json(route, 201, {
        id: "so-1",
        number: null,
        status: "draft",
        doc_date: body.doc_date,
        branch_id: "b-1",
        warehouse_id: body.warehouse_id,
        comment: null,
        line_count: 1,
        total_amount: "98005.00",
        created_at: "2026-10-17T08:00:00Z",
        posted_at: null,
        cancelled_at: null,
        cancel_reason: null,
        lines: [],
      });
    }
    if (path === "/api/v1/stock-openings/so-1/post") {
      backend.posts.push("so-1");
      return json(route, 200, {
        id: "so-1",
        number: "OO-000001",
        status: "posted",
        doc_date: "2026-10-17",
        branch_id: "b-1",
        warehouse_id: "w-1",
        comment: null,
        line_count: 1,
        total_amount: "98005.00",
        created_at: "2026-10-17T08:00:00Z",
        posted_at: "2026-10-17T08:00:01Z",
        cancelled_at: null,
        cancel_reason: null,
        lines: [],
      });
    }
    return json(route, 404, { error: { code: "NOT_FOUND", message_key: "errors.not_found", details: [] } });
  });
  return backend;
}

const openingSection = (page: Page) => page.getByRole("region", { name: /Boshlang'ich qoldiq/ });

test("BO-21 ③b Excel/CSV: opening_stock template → upload → validate → commit → line count", async ({
  page,
}) => {
  const backend = await stubBackend(page);
  await page.goto("/onboarding");
  await expect(page.getByRole("heading", { level: 1, name: "Tovarlar" })).toBeVisible();

  const section = openingSection(page);
  const methods = section.getByRole("group", { name: "Boshlang'ich qoldiqni kiritish usuli" });
  await methods.getByRole("button", { name: /Excel\/CSV fayl/ }).click();
  await expect(section.getByText("barcode;qty;unit_cost;expiry_date")).toBeVisible();

  const download = page.waitForEvent("download");
  await section.getByRole("button", { name: "Shablonni yuklab olish" }).click();
  expect((await download).suggestedFilename()).toBe("opening_stock.csv");

  await section.locator('input[type="file"]').setInputFiles({
    name: "qoldiq.csv",
    mimeType: "text/csv",
    buffer: Buffer.from("barcode;qty;unit_cost\n4780012340054;10;9800\n4780012340047;5;2500\n"),
  });
  await section.getByRole("button", { name: "Yuklash va tekshirish" }).click();
  await expect(
    section.getByText("Barcha qatorlar to'g'ri: 2 ta qator boshlang'ich qoldiqqa kiritiladi."),
  ).toBeVisible();
  expect(backend.uploads[0]).toContain("opening_stock");

  await section.getByRole("button", { name: "Import qilish (2)" }).click();
  await expect(section.getByText("Boshlang'ich qoldiq kiritildi: 2 ta qator")).toBeVisible();
  await expect(section.getByText("Bu bosqichda boshlang'ich qoldiqqa 2 ta qator kiritildi")).toBeVisible();
  expect(backend.commits).toEqual([{ skip_error_rows: true }]);

  // Optional step: «Davom» goes on to ④.
  await page.getByRole("button", { name: "Davom", exact: true }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Boshlang'ich qarzlar" })).toBeVisible();
});

test("BO-21 ③b «Qo'lda»: product, qty, cost, expiry → POST /stock-openings → /post", async ({ page }) => {
  const backend = await stubBackend(page);
  await page.goto("/onboarding");
  const section = openingSection(page);
  await section
    .getByRole("group", { name: "Boshlang'ich qoldiqni kiritish usuli" })
    .getByRole("button", { name: /Qo'lda/ })
    .click();
  await expect(section.getByText("Ombor: Asosiy ombor")).toBeVisible();

  await section.getByLabel("Tovar qidirish").fill("sut");
  await section
    .getByRole("list", { name: "Topilgan tovarlar" })
    .getByRole("button", { name: /Sut 2,5% 1 l/ })
    .click();

  const save = section.getByRole("button", { name: "Qoldiqni saqlash (1)" });
  await expect(save).toBeDisabled();
  await section.getByRole("textbox", { name: "Miqdor — Sut 2,5% 1 l" }).fill("10");
  await section.getByRole("textbox", { name: "Tannarx — Sut 2,5% 1 l" }).fill("9800,5");
  await section.getByLabel("Yaroqlilik muddati — Sut 2,5% 1 l").fill("2026-12-31");
  await expect(save).toBeEnabled();
  await save.click();

  await expect(section.getByText(/OO-000001 hujjati o'tkazildi: 1 ta qator/)).toBeVisible();
  await expect(section.getByText("Bu bosqichda boshlang'ich qoldiqqa 1 ta qator kiritildi")).toBeVisible();
  expect(backend.openings).toHaveLength(1);
  expect(backend.openings[0]).toMatchObject({
    warehouse_id: "w-1",
    lines: [{ product_id: "p1", qty: "10.000", unit_cost: "9800.5000", expiry_date: "2026-12-31" }],
  });
  expect(String(backend.openings[0]?.doc_date)).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  expect(backend.posts).toEqual(["so-1"]);
});
