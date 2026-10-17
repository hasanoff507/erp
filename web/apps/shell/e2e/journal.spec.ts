import { expect, test, type Page, type Route } from "@playwright/test";

/**
 * BO-08 «Buxgalteriya jurnali» (Bosqich 2 part) on the production build: ledger entries with the
 * column-named filters of 20 #9, cursor «Yana yuklash», «Dt oboroti = Kt oboroti» total, and the
 * «Qayta hisoblash navbati» (19 §18) with «Qayta urinish» of a failed job. Backend stubbed per test.
 */
const session = {
  user: { id: "u-1", full_name: "Gulnora Toshmatova", phone_masked: "+998 90 *** ** 67" },
  tenant: { id: "t-1", name: "Baraka do'koni" },
  branches: [{ id: "b-1", name: "Chilonzor-3" }],
  roles: ["accountant"],
  permissions: ["accounting.post", "stock.view"],
  scope: ["accounting", "stock"],
  client_id: "web-bff",
  sub_status: "active",
  access_expires_at: 0,
};

type Body = Record<string, unknown>;

function json(route: Route, status: number, body: unknown) {
  return route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
}

function entry(id: string, amount: string, patch: Body = {}): Body {
  return {
    id,
    entry_date: "2026-10-15",
    account_dt: "2920",
    account_kt: "0000",
    amount,
    branch_id: "b-1",
    doc_type: "stock_openings",
    doc_id: "so-1",
    doc_number: "OO-000001",
    analytics: {},
    reversal_of_id: null,
    ...patch,
  };
}

function job(id: string, status: string, patch: Body = {}): Body {
  return {
    id,
    warehouse_id: "w-1",
    product_id: "p-1",
    from_date: "2026-09-28",
    status,
    reason_doc_type: "goods_receipts",
    reason_doc_id: "gr-1",
    attempts: status === "failed" ? 3 : 1,
    last_error: status === "failed" ? "lock timeout" : null,
    created_at: "2026-10-01T05:00:00Z",
    finished_at: status === "done" ? "2026-10-01T05:01:00Z" : null,
    ...patch,
  };
}

interface Backend {
  ledgerQueries: URLSearchParams[];
  retries: { id: string; idempotencyKey: string | undefined; csrf: string | undefined }[];
}

async function stubBackend(page: Page, { retryStatus = 200 }: { retryStatus?: number } = {}) {
  const backend: Backend = { ledgerQueries: [], retries: [] };
  let jobs = [job("j-1", "done"), job("j-2", "failed")];

  await page.route("**/auth/session", (route) => json(route, 200, session));
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const method = request.method();
    if (path === "/api/v1/auth/csrf") return json(route, 200, { csrf_token: "csrf-e2e" });
    if (path === "/api/v1/ledger-entries" && method === "GET") {
      backend.ledgerQueries.push(url.searchParams);
      if (url.searchParams.get("cursor") === "c2") {
        return json(route, 200, {
          items: [
            entry("e3", "49999.50", {
              doc_type: "sales",
              doc_number: "K-000154",
              account_dt: "5010",
              account_kt: "9020",
            }),
          ],
          next_cursor: null,
        });
      }
      if (url.searchParams.get("account_dt") === "5010") {
        return json(route, 200, {
          items: [
            entry("e3", "49999.50", {
              doc_type: "sales",
              doc_number: "K-000154",
              account_dt: "5010",
              account_kt: "9020",
            }),
          ],
          next_cursor: null,
        });
      }
      return json(route, 200, {
        items: [
          entry("e1", "1200000.00"),
          entry("e2", "350000.50", { doc_number: null, reversal_of_id: "e0" }),
        ],
        next_cursor: "c2",
      });
    }
    if (path === "/api/v1/recost-jobs" && method === "GET") {
      const status = url.searchParams.get("status");
      return json(route, 200, {
        items: status ? jobs.filter((j) => j.status === status) : jobs,
        next_cursor: null,
      });
    }
    const retry = /^\/api\/v1\/recost-jobs\/(j-\d)\/retry$/.exec(path);
    if (retry && method === "POST") {
      const id = retry[1] ?? "";
      backend.retries.push({
        id,
        idempotencyKey: request.headers()["idempotency-key"],
        csrf: request.headers()["x-csrf-token"],
      });
      if (retryStatus !== 200) {
        jobs = jobs.map((j) => (j.id === id ? { ...j, status: "queued" } : j));
        return json(route, 409, {
          error: { code: "DOC_INVALID_STATE", message_key: "errors.doc_invalid_state", details: [] },
        });
      }
      const queued = job(id, "queued", { attempts: 3, last_error: "lock timeout" });
      jobs = jobs.map((j) => (j.id === id ? queued : j));
      return json(route, 200, queued);
    }
    if (path === "/api/v1/products/p-1") {
      return json(route, 200, {
        id: "p-1",
        name: "Shakar 1 kg",
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
        barcodes: [],
      });
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
    return json(route, 404, { error: { code: "NOT_FOUND", message_key: "errors.not_found", details: [] } });
  });
  return backend;
}

test("BO-08: journal for the current month, load more, Dt = Kt turnover, account filter", async ({
  page,
}) => {
  const backend = await stubBackend(page);
  await page.goto("/app/accounting/journal");
  await expect(page.getByRole("banner").getByRole("heading", { name: "Buxgalteriya jurnali" })).toBeVisible();

  const journal = page.getByRole("region", { name: "Provodkalar" });
  const table = journal.getByRole("table", { name: "Provodkalar" });
  const first = table.getByRole("row").nth(1);
  await expect(first).toContainText("OO-000001");
  await expect(first).toContainText("Chilonzor-3");
  await expect(first).toContainText("Boshlang'ich qoldiq");
  await expect(first).toContainText("Chakana savdodagi tovarlar");
  await expect(first).toContainText("1 200 000,00");
  const reversal = table.getByRole("row").nth(2);
  await expect(reversal).toContainText("raqamsiz");
  await expect(reversal).toContainText("Storno");

  // 20 #9: column-named filters, the current month up to today.
  const query = backend.ledgerQueries[0];
  expect(query?.get("entry_date__gte")).toMatch(/^\d{4}-\d{2}-01$/);
  expect(query?.get("entry_date__lte")).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  expect(query?.get("account_dt")).toBeNull();

  const turnover = journal.getByRole("group", { name: "Dt oboroti = Kt oboroti" });
  await expect(turnover).toContainText("1 550 000,50 so'm");

  await journal.getByRole("button", { name: "Yana yuklash" }).click();
  await expect(table.getByRole("row")).toHaveCount(4);
  await expect(table.getByRole("row").nth(3)).toContainText("K-000154");
  await expect(table.getByRole("row").nth(3)).toContainText("Sotuv / Z-hisobot");
  await expect(turnover).toContainText("1 600 000,00 so'm");
  await expect(journal.getByRole("button", { name: "Yana yuklash" })).toHaveCount(0);

  // «Hisob» filter → `account_dt` (Debet side by default).
  await page.getByRole("combobox", { name: "Hisob" }).click();
  await page.getByRole("option", { name: "5010 — Kassa (milliy valyuta)" }).click();
  await expect(table.getByRole("row")).toHaveCount(2);
  expect(backend.ledgerQueries.at(-1)?.get("account_dt")).toBe("5010");
  await page.getByRole("group", { name: "Hisob tomoni" }).getByRole("button", { name: "Kredit" }).click();
  await expect.poll(() => backend.ledgerQueries.at(-1)?.get("account_kt")).toBe("5010");

  // An inverted period is flagged and not sent.
  const sent = backend.ledgerQueries.length;
  await page.getByLabel("Sana (dan)").fill("2099-01-01");
  await expect(page.getByText("«Sana (dan)» «Sana (gacha)» dan keyin bo'lmasin")).toBeVisible();
  expect(backend.ledgerQueries).toHaveLength(sent);
});

test("BO-08: «Qayta hisoblash navbati» — retry a failed job (Idempotency-Key + CSRF)", async ({ page }) => {
  const backend = await stubBackend(page);
  await page.goto("/app/accounting/journal");

  const queue = page.getByRole("table", { name: "Qayta hisoblash navbati" });
  const failed = queue.getByRole("row").filter({ hasText: "Hisoblashda xato — qayta urinib ko'ring" });
  await expect(failed).toContainText("Shakar 1 kg");
  await expect(failed).not.toContainText("lock timeout");
  await expect(failed).toContainText("Asosiy ombor");
  await expect(failed).toContainText("28.09.2026");
  await expect(failed).toContainText("Xato");
  // A finished job has no retry.
  await expect(queue.getByRole("row").filter({ hasText: "Bajarildi" }).getByRole("button")).toHaveCount(0);

  await failed.getByRole("button", { name: "Qayta urinish — Shakar 1 kg" }).click();
  await expect(queue.getByRole("row").nth(2)).toContainText("Navbatda");
  expect(backend.retries).toHaveLength(1);
  expect(backend.retries[0]?.id).toBe("j-2");
  expect(backend.retries[0]?.idempotencyKey).toBeTruthy();
  expect(backend.retries[0]?.csrf).toBe("csrf-e2e");

  // Status filter → `?status=failed`; nothing failed any more.
  await page.getByRole("combobox", { name: "Holat" }).click();
  await page.getByRole("option", { name: "Xato" }).click();
  await expect(page.getByText("Navbat bo'sh")).toBeVisible();
});

test("BO-08: a refused retry (409) is explained and the queue is reloaded", async ({ page }) => {
  await stubBackend(page, { retryStatus: 409 });
  await page.goto("/app/accounting/journal");
  const queue = page.getByRole("table", { name: "Qayta hisoblash navbati" });
  await queue.getByRole("button", { name: "Qayta urinish — Shakar 1 kg" }).click();
  await expect(page.getByText("Hujjat bu amal uchun mos holatda emas")).toBeVisible();
  await expect(queue.getByRole("row").nth(2)).toContainText("Navbatda");
});

test("BO-08: without accounting.post the journal is closed (route permission)", async ({ page }) => {
  await page.route("**/auth/session", (route) =>
    json(route, 200, { ...session, roles: ["cashier"], permissions: ["sales.create", "stock.view"] }),
  );
  await page.goto("/app/accounting/journal");
  await expect(page.getByText("Sizda bu bo'limga kirish huquqi yo'q").first()).toBeVisible();
});
