import { expect, test, type Page, type Route } from "@playwright/test";

/**
 * BO-05 prices (07, 19 §4, US-M09-01/02) on the production build:
 * new price → POST /price-changes → /post (posted) → history shows the new price;
 * a manager (no prices.approve) changes > 10% → «Tasdiq kerak» + banner → 202 pending_approval state.
 */
const owner = {
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
const manager = {
  ...owner,
  user: { id: "u-2", full_name: "Dilshod Toshev", phone_masked: "+998 91 *** ** 12" },
  roles: ["manager"],
  permissions: ["stock.view", "catalog.manage", "prices.edit"],
};

type Body = Record<string, unknown>;
type HistoryItem = {
  price: string;
  valid_from: string;
  valid_to: string | null;
  set_by: string | null;
  set_by_name: string | null;
  price_change_doc_id: string | null;
  branch_id: string | null;
};

function product(id: string, name: string, nameRu: string | null): Body {
  return {
    id,
    name,
    name_ru: nameRu,
    category_id: null,
    unit_code: "pcs",
    mxik_code: "10101001001000000",
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
    current_price: null,
  };
}

const NAMES: Record<string, string> = {
  "u-1": "Akmal Karimov",
  "u-2": "Dilshod Toshev",
  "u-3": "Laylo Rahimova",
};

const at = (price: string, from: string, to: string | null, by: string | null = "u-1"): HistoryItem => ({
  price,
  valid_from: from,
  valid_to: to,
  set_by: by,
  set_by_name: by ? (NAMES[by] ?? null) : null,
  price_change_doc_id: "doc-0",
  branch_id: null,
});

function json(route: Route, status: number, body: unknown) {
  return route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
}

interface Backend {
  creates: Body[];
  posts: number;
  history: Record<string, HistoryItem[]>;
}

async function stubBackend(
  page: Page,
  session: Body,
  postStatus: "posted" | "pending_approval",
  { paged = false }: { paged?: boolean } = {},
): Promise<Backend> {
  const state: Backend = {
    creates: [],
    posts: 0,
    history: {
      p1: [
        at("13500.0000", "2026-09-01T05:00:00Z", null, "u-3"),
        at("12000.0000", "2026-08-01T05:00:00Z", "2026-09-01T05:00:00Z", null),
      ],
      p2: [at("21000.0000", "2026-09-01T05:00:00Z", null)],
      p3: [at("5000.0000", "2026-09-01T05:00:00Z", null)],
    },
  };
  const products = [product("p1", "Sut 2,5% 1 l", "Молоко 2,5% 1 л"), product("p2", "Choy ko'k 100 g", null)];
  // `paged`: 21 products → page 2 holds «Non» (p3), to check that drafts survive paging.
  const page2 = [product("p3", "Non", null)];

  await page.route("**/auth/session", (route) => json(route, 200, session));
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url());
    const method = route.request().method();
    const path = url.pathname;
    if (path === "/api/v1/auth/csrf") return json(route, 200, { csrf_token: "csrf-e2e" });
    if (path === "/api/v1/units") return json(route, 200, { items: [{ code: "pcs", is_fractional: false }] });
    if (path === "/api/v1/product-categories")
      return json(route, 200, { items: [], total: 0, page: 1, size: 200 });
    if (path === "/api/v1/products" && method === "GET") {
      if (!paged) return json(route, 200, { items: products, total: products.length, page: 1, size: 20 });
      const second = url.searchParams.get("page") === "2";
      return json(route, 200, {
        items: second ? page2 : products,
        total: 21,
        page: second ? 2 : 1,
        size: 20,
      });
    }
    const prices = /^\/api\/v1\/products\/(p\d)\/prices$/.exec(path);
    if (prices && method === "GET") {
      return json(route, 200, { items: state.history[prices[1] ?? ""] ?? [], next_cursor: null });
    }
    if (path === "/api/v1/price-changes" && method === "POST") {
      const body = route.request().postDataJSON() as Body;
      state.creates.push(body);
      const lines = (body.lines as Body[]).map((l, i) => ({
        id: `l-${i}`,
        line_no: i + 1,
        product_id: l.product_id,
        branch_id: l.branch_id ?? null,
        old_price: "0.0000",
        new_price: l.new_price,
        valid_from: l.valid_from ?? null,
      }));
      return json(route, 201, {
        id: "doc-1",
        status: "draft",
        number: null,
        doc_date: body.doc_date,
        branch_id: "b-1",
        comment: null,
        posted_at: null,
        approval_request_id: null,
        warnings: [],
        lines,
      });
    }
    if (path === "/api/v1/price-changes/doc-1/post" && method === "POST") {
      state.posts += 1;
      const lines = (state.creates.at(-1)?.lines as Body[]) ?? [];
      if (postStatus === "posted") {
        for (const l of lines) {
          const id = String(l.product_id);
          const old = state.history[id] ?? [];
          const now = new Date(Date.now() - 60_000).toISOString();
          state.history[id] = [
            at(String(l.new_price), now, null),
            ...old.map((h, i) => (i === 0 ? { ...h, valid_to: now } : h)),
          ];
        }
      }
      return json(route, postStatus === "posted" ? 200 : 202, {
        id: "doc-1",
        status: postStatus,
        number: "NO-0001",
        doc_date: "2026-10-17",
        branch_id: "b-1",
        comment: null,
        posted_at: postStatus === "posted" ? "2026-10-17T06:00:00Z" : null,
        approval_request_id: postStatus === "posted" ? null : "ar-1",
        warnings: postStatus === "posted" ? [] : ["APPROVAL_REQUIRED"],
        lines: lines.map((l, i) => ({
          id: `l-${i}`,
          line_no: i + 1,
          product_id: l.product_id,
          branch_id: null,
          old_price: "0.0000",
          new_price: l.new_price,
          valid_from: null,
        })),
      });
    }
    return json(route, 404, { error: { code: "NOT_FOUND", message_key: "errors.not_found", details: [] } });
  });
  return state;
}

test("QT-M09-01 owner: new price → saved (posted) → old price goes to history", async ({ page }) => {
  const backend = await stubBackend(page, owner, "posted");
  await page.goto("/app/catalog/prices");

  const table = page.getByRole("table", { name: "Chakana narxlar" });
  const input = table.getByRole("textbox", { name: "Yangi narx — Sut 2,5% 1 l" });
  await expect(input).toHaveValue("13 500");
  // The first row is selected: its history is in the right panel.
  const history = page.getByRole("list", { name: "Narx tarixi" });
  await expect(history.getByText("13 500 so'm")).toBeVisible();
  // «kim o'rnatdi» (19 §4 set_by_name): a named user; a row without an author → «tizim».
  const rows = history.getByRole("listitem");
  await expect(rows.nth(0)).toContainText("Laylo Rahimova");
  await expect(rows.nth(1)).toContainText("tizim");

  await input.fill("14000");
  const row = table.getByRole("row").filter({ hasText: "Sut 2,5% 1 l" });
  await expect(row.getByText("O'zgaradi")).toBeVisible();
  await expect(row.getByText("+3,7%")).toBeVisible();
  await expect(page.getByText(/^1 ta o'zgarish · \d{2}\.\d{2}\.\d{4} dan amal qiladi/)).toBeVisible();
  // The owner has prices.approve → no approval banner.
  await expect(page.getByText(/dan katta — Egasi tasdig'i kerak/)).toHaveCount(0);

  await page.getByRole("button", { name: /Saqlash/ }).click();
  await expect(page.getByText("Narxlar saqlandi (1 ta).", { exact: false })).toBeVisible();
  expect(backend.posts).toBe(1);
  expect(backend.creates[0]).toMatchObject({
    lines: [{ product_id: "p1", new_price: "14000.0000", valid_from: null, branch_id: null }],
  });

  await expect(history.getByText("14 000 so'm")).toBeVisible();
  await expect(history.getByText("13 500 so'm")).toBeVisible();
  await expect(history.getByText("Amalda")).toHaveCount(1);
  await expect(rows.nth(0)).toContainText("siz"); // the viewer's own change
  await expect(rows.nth(1)).toContainText("Laylo Rahimova");
  await expect(input).toHaveValue("14 000");
});

test("QT-M09-02 manager: change > 10% → «Tasdiq kerak» banner → 202 pending approval, old price stays", async ({
  page,
}) => {
  const backend = await stubBackend(page, manager, "pending_approval");
  await page.goto("/app/catalog/prices");

  const table = page.getByRole("table", { name: "Chakana narxlar" });
  const input = table.getByRole("textbox", { name: "Yangi narx — Choy ko'k 100 g" });
  await expect(input).toHaveValue("21 000");
  await input.fill("23500");

  const row = table.getByRole("row").filter({ hasText: "Choy ko'k 100 g" });
  await expect(row.getByText("Tasdiq kerak")).toBeVisible();
  await expect(row.getByText("+11,9%")).toBeVisible();
  const banner = page
    .getByRole("status")
    .filter({ hasText: "1 ta o'zgarish 10% dan katta — Egasi tasdig'i kerak" });
  await expect(banner).toBeVisible();
  await expect(banner).toContainText("Choy ko'k 100 g: 21 000 so'm → 23 500 so'm (+11,9%)");
  await expect(banner.getByRole("link", { name: "Tasdiqlash navbati" })).toHaveAttribute(
    "href",
    "/app/approvals",
  );

  // Ctrl+S saves (07 BO-05 keyboard shortcut).
  await input.press("Control+s");
  await expect(
    page.getByText("Narx o'zgarishi (1 ta) Egasi tasdig'ini kutmoqda.", { exact: false }),
  ).toBeVisible();
  expect(backend.posts).toBe(1);
  // Pending: the current price did not change; the edit is cleared.
  await expect(input).toHaveValue("21 000");
  await expect(page.getByText(/dan katta — Egasi tasdig'i kerak/)).toHaveCount(0);
});

test("cashier-like user without prices.edit cannot open BO-05 (route permission)", async ({ page }) => {
  await page.route("**/auth/session", (route) =>
    json(route, 200, {
      ...owner,
      roles: ["cashier"],
      permissions: ["sales.create", "stock.view"],
      scope: ["sales", "stock"],
    }),
  );
  await page.goto("/app/catalog/prices");
  await expect(page.getByText("Sizda bu bo'limga kirish huquqi yo'q")).toBeVisible();
});

test("drafts survive paging: edits on page 1 and page 2 are saved in one document", async ({ page }) => {
  const backend = await stubBackend(page, owner, "posted", { paged: true });
  await page.goto("/app/catalog/prices");
  const table = page.getByRole("table", { name: "Chakana narxlar" });

  const milk = table.getByRole("textbox", { name: "Yangi narx — Sut 2,5% 1 l" });
  await expect(milk).toHaveValue("13 500");
  await milk.fill("14000");
  await page.getByRole("button", { name: "Keyingi sahifa" }).click();
  const bread = table.getByRole("textbox", { name: "Yangi narx — Non" });
  await expect(bread).toHaveValue("5 000");
  await bread.fill("5200");
  // The footer counts every draft, not only the visible page.
  await expect(page.getByText(/^2 ta o'zgarish · /)).toBeVisible();

  await page.getByRole("button", { name: /Saqlash/ }).click();
  await expect(page.getByText("Narxlar saqlandi (2 ta).", { exact: false })).toBeVisible();
  expect(backend.creates[0]).toMatchObject({
    lines: [
      { product_id: "p1", new_price: "14000.0000" },
      { product_id: "p3", new_price: "5200.0000" },
    ],
  });
});

test("changing the price scope with unsaved edits asks first", async ({ page }) => {
  await stubBackend(page, owner, "posted");
  await page.goto("/app/catalog/prices");
  const table = page.getByRole("table", { name: "Chakana narxlar" });
  const milk = table.getByRole("textbox", { name: "Yangi narx — Sut 2,5% 1 l" });
  await expect(milk).toHaveValue("13 500");
  await milk.fill("14000");

  const scope = page.getByRole("combobox", { name: "Narx qaysi filial uchun" });
  await scope.click();
  await page.getByRole("option", { name: "Faqat Chilonzor-3" }).click();
  const dialog = page.getByRole("alertdialog", { name: "Narx doirasini o'zgartirasizmi?" });
  await expect(dialog).toContainText("1 ta narx o'zgarishi bekor qilinadi");
  // Cancel keeps the edit and the scope.
  await dialog.getByRole("button", { name: "Bekor qilish", exact: true }).click();
  await expect(dialog).toHaveCount(0);
  await expect(milk).toHaveValue("14 000");
  await expect(scope).toContainText("Barcha filiallar");

  await scope.click();
  await page.getByRole("option", { name: "Faqat Chilonzor-3" }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Doirani o'zgartirish" }).click();
  await expect(scope).toContainText("Faqat Chilonzor-3");
  await expect(milk).toHaveValue("13 500");
  await expect(page.getByText(/^0 ta o'zgarish · /)).toBeVisible();
});
