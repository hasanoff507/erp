import { expect, test, type Page, type Route } from "@playwright/test";

/**
 * Product import (US-M04-04, 19 §6) on the production build: template download → upload → async
 * validate (poll) → error rows → fix and re-upload → commit (poll) → result → products appear.
 * The backend is stubbed per test (responses shaped like the generated @shared/models types).
 */
const session = {
  user: { id: "u-1", full_name: "Akmal Karimov", phone_masked: "+998 90 *** ** 67" },
  tenant: { id: "t-1", name: "Baraka do'koni" },
  branches: [{ id: "b-1", name: "Chilonzor-3" }],
  roles: ["owner"],
  permissions: ["stock.view", "catalog.manage", "prices.edit", "prices.approve"],
  scope: ["stock", "catalog", "prices"],
  client_id: "web-bff",
  sub_status: "active",
  access_expires_at: 0,
};

type Json = Record<string, unknown> | unknown[];
type Handler = (req: { method: string; path: string; url: URL; route: Route }) => Promise<boolean> | boolean;

async function stubBackend(page: Page, handler: Handler) {
  await page.route("**/auth/session", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(session) }),
  );
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url());
    const method = route.request().method();
    if (url.pathname === "/api/v1/auth/csrf") return json(route, 200, { csrf_token: "csrf-e2e" });
    if (await handler({ method, path: url.pathname, url, route })) return;
    if (url.pathname === "/api/v1/units") {
      return json(route, 200, {
        items: [
          { code: "pcs", is_fractional: false },
          { code: "kg", is_fractional: true },
        ],
      });
    }
    if (url.pathname === "/api/v1/product-categories")
      return json(route, 200, { items: [], total: 0, page: 1, size: 200 });
    return json(route, 404, { error: { code: "NOT_FOUND", message_key: "errors.not_found", details: [] } });
  });
}

function json(route: Route, status: number, body: Json) {
  return route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
}

function job(
  id: string,
  status: string,
  rows: { total: number; ok: number; errors: number },
  result: Json = {},
) {
  return {
    id,
    kind: "products",
    status,
    total_rows: rows.total,
    ok_rows: rows.ok,
    error_rows: rows.errors,
    result,
    created_at: "2026-10-17T08:00:00Z",
  };
}

function product(id: string, name: string, barcode: string) {
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
    barcodes: [{ id: `b-${id}`, barcode, kind: "ean", units_per_barcode: "1.000" }],
  };
}

const XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";

test("US-M04-04 download template → upload → error rows → fix & re-upload → commit → products appear", async ({
  page,
}) => {
  const uploads: string[] = [];
  const commits: unknown[] = [];
  let committed = false;
  // GET /import-jobs/{id} answers per job, in order (last one repeats).
  const states: Record<string, ReturnType<typeof job>[]> = {
    "job-1": [
      job("job-1", "validating", { total: 3, ok: 0, errors: 0 }),
      job("job-1", "validated", { total: 3, ok: 2, errors: 1 }),
    ],
    "job-2": [job("job-2", "validated", { total: 3, ok: 3, errors: 0 })],
  };

  await stubBackend(page, async ({ method, path, route }) => {
    if (method === "GET" && path === "/api/v1/import-jobs/templates/products") {
      await route.fulfill({
        status: 200,
        contentType: "text/csv; charset=utf-8",
        headers: { "Content-Disposition": 'attachment; filename="products.csv"' },
        body: "name;name_ru;barcode;unit_code;mxik_code;vat_rate;price;category;is_marked\n",
      });
      return true;
    }
    if (method === "POST" && path === "/api/v1/import-jobs") {
      const body = route.request().postData() ?? "";
      expect(body).toContain('name="kind"');
      expect(body).toContain("products");
      const id = uploads.length === 0 ? "job-1" : "job-2";
      uploads.push(id);
      await json(route, 201, { id, kind: "products", status: "uploaded", total_rows: 0 });
      return true;
    }
    const validate = /^\/api\/v1\/import-jobs\/(job-\d)\/validate$/.exec(path);
    if (method === "POST" && validate) {
      await json(route, 202, { job_id: validate[1], status: "validating" });
      return true;
    }
    const commit = /^\/api\/v1\/import-jobs\/(job-\d)\/commit$/.exec(path);
    if (method === "POST" && commit) {
      commits.push(route.request().postDataJSON());
      committed = true;
      states["job-2"] = [
        job("job-2", "committing", { total: 3, ok: 3, errors: 0 }),
        job(
          "job-2",
          "committed",
          { total: 3, ok: 3, errors: 0 },
          { created_product_count: 3, created_doc_ids: ["doc-1"] },
        ),
      ];
      await json(route, 202, { job_id: commit[1], status: "committing" });
      return true;
    }
    const errors = /^\/api\/v1\/import-jobs\/(job-\d)\/errors$/.exec(path);
    if (method === "GET" && errors) {
      await json(route, 200, {
        items: [
          { row: 3, field: "barcode", code: "BARCODE_DUPLICATE", message: "validation.barcode_duplicate" },
        ],
        next_cursor: null,
      });
      return true;
    }
    const get = /^\/api\/v1\/import-jobs\/(job-\d)$/.exec(path);
    if (method === "GET" && get) {
      const queue = states[get[1] ?? ""] ?? [];
      const next = queue.length > 1 ? queue.shift() : queue[0];
      await json(route, 200, next ?? {});
      return true;
    }
    if (method === "GET" && path === "/api/v1/products") {
      const items = committed
        ? [
            product("p1", "Non «Patir»", "4780012340047"),
            product("p2", "Sut 2,5% 1 l", "4780012340054"),
            product("p3", "Choy ko'k 100 g", "4780012340061"),
          ]
        : [];
      await json(route, 200, { items, total: items.length, page: 1, size: 25 });
      return true;
    }
    return false;
  });

  await page.goto("/app/catalog/products/import");
  await expect(
    page.getByRole("banner").getByRole("heading", { name: "Tovarlarni import qilish" }),
  ).toBeVisible();
  // Only `products` in Bosqich 1: the other kinds are shown as the next phase.
  await expect(page.getByText("Boshlang'ich qoldiq")).toBeVisible();
  await expect(page.getByText("Keyingi bosqich", { exact: true })).toHaveCount(1);
  await expect(page.getByText("Onboarding", { exact: true })).toHaveCount(1);

  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Shablonni yuklab olish" }).click();
  expect((await download).suggestedFilename()).toBe("products.csv");

  const fileInput = page.locator('input[type="file"]');
  // Client-side type check (17 §12).
  await fileInput.setInputFiles({
    name: "tovarlar.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("%PDF"),
  });
  await expect(page.getByText("Faqat XLSX, CSV fayllari qabul qilinadi")).toBeVisible();

  await fileInput.setInputFiles({
    name: "tovarlar.xlsx",
    mimeType: XLSX,
    buffer: Buffer.from("PK-fake-xlsx"),
  });
  await expect(page.getByText("tovarlar.xlsx")).toBeVisible();
  await page.getByRole("button", { name: "Yuklash va tekshirish" }).click();

  // Validation finished with one bad row.
  await expect(page.getByRole("heading", { name: "3. Tekshiruv natijasi" })).toBeVisible();
  const summary = page.getByRole("definition");
  await expect(summary).toHaveText(["3", "2", "1"]);
  const errors = page.getByRole("table", { name: "Xatoli qatorlar" });
  await expect(errors.getByRole("row").nth(1)).toContainText("3");
  await expect(errors.getByRole("row").nth(1)).toContainText("barcode");
  await expect(errors.getByRole("row").nth(1)).toContainText(
    "Bu shtrix-kod boshqa tovarda yoki faylda takrorlangan",
  );

  // Fix the file and upload again (a new job).
  await page.getByRole("button", { name: "Tuzatib qayta yuklash" }).click();
  await fileInput.setInputFiles({
    name: "tovarlar-tuzatilgan.xlsx",
    mimeType: XLSX,
    buffer: Buffer.from("PK-fixed"),
  });
  await page.getByRole("button", { name: "Yuklash va tekshirish" }).click();
  await expect(page.getByText("Barcha qatorlar to'g'ri: 3 ta tovar import qilinadi.")).toBeVisible();
  await expect(page.getByRole("table", { name: "Xatoli qatorlar" })).toHaveCount(0);

  await page.getByRole("button", { name: "Import qilish (3)" }).click();
  await expect(page.getByText("Import yakunlandi: 3 ta tovar yaratildi")).toBeVisible();
  expect(commits).toEqual([{ skip_error_rows: true }]);
  expect(uploads).toEqual(["job-1", "job-2"]);

  await page.getByRole("link", { name: "Tovarlar ro'yxatiga o'tish" }).click();
  await expect(page).toHaveURL(/\/app\/catalog\/products$/);
  const table = page.getByRole("table", { name: "Tovarlar" });
  await expect(table.getByText("Non «Patir»")).toBeVisible();
  await expect(table.getByText("Choy ko'k 100 g")).toBeVisible();
});

test("server rejects the file (IMPORT_FILE_INVALID) → message on the dropzone, nothing validated", async ({
  page,
}) => {
  let validated = false;
  await stubBackend(page, async ({ method, path, route }) => {
    if (method === "POST" && path === "/api/v1/import-jobs") {
      await json(route, 422, {
        error: {
          code: "IMPORT_FILE_INVALID",
          message_key: "errors.import_file_invalid",
          details: [],
          request_id: "e2e",
        },
      });
      return true;
    }
    if (path.endsWith("/validate")) validated = true;
    return false;
  });

  await page.goto("/app/catalog/products/import");
  await page
    .locator('input[type="file"]')
    .setInputFiles({ name: "buzuq.csv", mimeType: "text/csv", buffer: Buffer.from("\u0000\u0001") });
  await page.getByRole("button", { name: "Yuklash va tekshirish" }).click();
  await expect(page.getByText("Fayl formati yoki kodlashi noto'g'ri")).toBeVisible();
  await expect(page.getByRole("button", { name: "Yuklash va tekshirish" })).toBeVisible();
  expect(validated).toBe(false);
});

test("a user without catalog.manage sees NoPermissionState on the import screen", async ({ page }) => {
  await page.route("**/auth/session", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ ...session, roles: ["cashier"], permissions: ["stock.view"], scope: ["stock"] }),
    }),
  );
  await page.goto("/app/catalog/products/import");
  await expect(page.getByText("Sizda bu bo'limga kirish huquqi yo'q")).toBeVisible();
});
