import { expect, test, type Page, type Route } from "@playwright/test";

/**
 * Product catalog (19 §1, US-M09-05) on the production build: create a product with MXIK search
 * and a barcode (BARCODE_DUPLICATE shown on the field), then give a barcode-less product an internal
 * EAN-13 («Ichki shtrix-kod yaratish»). The first Sheet of the catalog → no CSP violations.
 * The list shows `current_price` (19 §1) in «Joriy narx»; a product without a price → «narx yo'q».
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

type Body = Record<string, unknown>;

function product(id: string, name: string, patch: Body = {}): Body {
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
    barcodes: [],
    current_price: null,
    ...patch,
  };
}

function json(route: Route, status: number, body: unknown) {
  return route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
}

function collectCspViolations(page: Page): string[] {
  const violations: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error" && /Content Security Policy/i.test(msg.text())) violations.push(msg.text());
  });
  page.on("pageerror", (err) => {
    if (/Content Security Policy/i.test(err.message)) violations.push(err.message);
  });
  return violations;
}

const MXIK = "10101001001000000";
const EAN = "4780012340047";

test("QT-M09-05/QT-M09-08 create a product with MXIK search and a barcode; internal barcode for a product without one", async ({
  page,
}) => {
  const violations = collectCspViolations(page);
  const products: Body[] = [product("p-old", "Non «Patir»", { current_price: "4000.0000" })];
  const creates: Body[] = [];
  let internalGenerated = false;

  await page.route("**/auth/session", (route) => json(route, 200, session));
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url());
    const method = route.request().method();
    const path = url.pathname;
    if (path === "/api/v1/auth/csrf") return json(route, 200, { csrf_token: "csrf-e2e" });
    if (path === "/api/v1/units") {
      return json(route, 200, {
        items: [
          { code: "kg", is_fractional: true },
          { code: "pcs", is_fractional: false },
        ],
      });
    }
    if (path === "/api/v1/product-categories") {
      return json(route, 200, {
        items: [{ id: "c-1", name: "Bakaleya", parent_id: null, archived_at: null, version: 1 }],
        total: 1,
        page: 1,
        size: 200,
      });
    }
    if (path === "/api/v1/mxik-codes" && method === "GET") {
      expect(url.searchParams.get("query")).toBe("choy");
      return json(route, 200, {
        items: [
          { code: MXIK, name: "Choy, qora, qadoqlangan", vat_hint: "12.00" },
          { code: "10101001002000000", name: "Choy, ko'k", vat_hint: "12.00" },
        ],
      });
    }
    if (path === `/api/v1/mxik-codes/${MXIK}`) {
      return json(route, 200, {
        items: [{ code: MXIK, name: "Choy, qora, qadoqlangan", vat_hint: "12.00" }],
        source: "live",
      });
    }
    if (path === "/api/v1/products" && method === "GET") {
      return json(route, 200, { items: products, total: products.length, page: 1, size: 25 });
    }
    if (path === "/api/v1/products" && method === "POST") {
      const body = route.request().postDataJSON() as Body;
      creates.push(body);
      expect(route.request().headers()["idempotency-key"]).toBeTruthy();
      if (creates.length === 1) {
        return json(route, 409, {
          error: {
            code: "BARCODE_DUPLICATE",
            message_key: "errors.barcode_duplicate",
            params: { barcode: body.barcode },
            details: [],
            request_id: "e2e",
          },
        });
      }
      const created = product("p-new", String(body.name), {
        mxik_code: body.mxik_code,
        category_id: body.category_id,
        barcodes: [{ id: "bc-1", barcode: body.barcode, kind: "ean", units_per_barcode: "1.000" }],
      });
      products.unshift({ ...created, current_price: null });
      const out: Body = { ...created };
      delete out.current_price; // list-only field (19 §1)
      return json(route, 201, out);
    }
    if (path === "/api/v1/products/p-new" && method === "GET") return json(route, 200, products[0]);
    if (path === "/api/v1/products/p-old" && method === "GET") {
      return json(
        route,
        200,
        internalGenerated
          ? product("p-old", "Non «Patir»", {
              barcodes: [
                { id: "bc-2", barcode: "0400000000013", kind: "internal", units_per_barcode: "1.000" },
              ],
            })
          : product("p-old", "Non «Patir»"),
      );
    }
    if (path === "/api/v1/products/p-old/barcodes/internal-generate" && method === "POST") {
      internalGenerated = true;
      return json(route, 201, { barcode: "0400000000013", kind: "internal", units_per_barcode: "1.000" });
    }
    return json(route, 404, { error: { code: "NOT_FOUND", message_key: "errors.not_found", details: [] } });
  });

  await page.goto("/app/catalog/products");
  const table = page.getByRole("table", { name: "Tovarlar" });
  await expect(table.getByText("Non «Patir»")).toBeVisible();
  await expect(table.getByText("Shtrix-kodsiz")).toBeVisible();
  await expect(table.getByRole("columnheader", { name: "Joriy narx" })).toBeVisible();
  await expect(table.getByRole("row", { name: /Non «Patir»/ })).toContainText("4 000 so'm");

  await page.getByRole("button", { name: "Tovar qo'shish" }).click();
  await expect(page).toHaveURL(/\/app\/catalog\/products\/new$/);
  const sheet = page.getByRole("dialog", { name: "Yangi tovar" });
  await expect(sheet).toBeVisible();

  await sheet.getByRole("textbox", { name: "Nomi", exact: true }).fill("Choy qora 100 g");
  await sheet.getByRole("textbox", { name: /^Rus tilidagi nomi/ }).fill("Чай чёрный 100 г");

  // MXIK search (debounced, ≥ 3 chars) → pick → code filled and verified.
  await sheet.getByRole("button", { name: "Qidirish" }).click();
  await page.getByRole("searchbox", { name: "MXIK klassifikatoridan qidirish" }).fill("choy");
  await page.getByRole("button", { name: /Choy, qora, qadoqlangan/ }).click();
  await expect(sheet.getByLabel("MXIK (IKPU) kodi")).toHaveValue(MXIK);
  await expect(sheet.getByText("Choy, qora, qadoqlangan")).toBeVisible();

  // A wrong check digit is caught on the client.
  await sheet.getByRole("textbox", { name: /^Shtrix-kod/ }).fill("4780012340048");
  await sheet.getByRole("button", { name: "Yaratish" }).click();
  await expect(sheet.getByText("Shtrix-kodning nazorat raqami mos kelmadi")).toBeVisible();
  expect(creates).toHaveLength(0);

  // Server: the barcode belongs to another product (409 BARCODE_DUPLICATE) → shown on the field.
  await sheet.getByRole("textbox", { name: /^Shtrix-kod/ }).fill(EAN);
  await sheet.getByRole("button", { name: "Yaratish" }).click();
  await expect(sheet.getByText("Bu shtrix-kod boshqa tovarda bor")).toBeVisible();

  // Retry succeeds (the stub accepts the second attempt) → the card of the new product opens.
  await sheet.getByRole("button", { name: "Yaratish" }).click();
  await expect(page).toHaveURL(/\/app\/catalog\/products\/p-new$/);
  expect(creates[1]).toMatchObject({
    name: "Choy qora 100 g",
    name_ru: "Чай чёрный 100 г",
    unit_code: "pcs",
    mxik_code: MXIK,
    vat_rate: "12.00",
    barcode: EAN,
    is_marked: false,
    is_weighed: false,
  });
  const card = page.getByRole("dialog", { name: "Choy qora 100 g" });
  await expect(card.getByText(EAN)).toBeVisible();
  // It has a barcode → no internal-code button.
  await expect(card.getByRole("button", { name: "Ichki shtrix-kod yaratish" })).toHaveCount(0);
  await card.getByRole("button", { name: "Yopish" }).last().click();
  await expect(page).toHaveURL(/\/app\/catalog\/products$/);
  await expect(table.getByRole("row", { name: /Choy qora 100 g/ })).toContainText("narx yo'q");

  // US-M09-05: a product without a barcode gets an internal EAN-13 (04…).
  await table.getByText("Non «Patir»").click();
  const old = page.getByRole("dialog", { name: "Non «Patir»" });
  await old.getByRole("button", { name: "Ichki shtrix-kod yaratish" }).click();
  await expect(page.getByText("Ichki shtrix-kod yaratildi: 0400000000013", { exact: true })).toBeVisible();
  await expect(old.getByText("0400000000013")).toBeVisible();
  await expect(old.getByText("Ichki", { exact: true })).toBeVisible();

  expect(violations).toEqual([]);
});

test("a user with stock.view only sees the catalog read-only", async ({ page }) => {
  await page.route("**/auth/session", (route) =>
    json(route, 200, { ...session, roles: ["cashier"], permissions: ["stock.view"], scope: ["stock"] }),
  );
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/v1/units") return json(route, 200, { items: [{ code: "pcs", is_fractional: false }] });
    if (path === "/api/v1/product-categories")
      return json(route, 200, { items: [], total: 0, page: 1, size: 200 });
    if (path === "/api/v1/products") {
      return json(route, 200, { items: [product("p-1", "Sut 1 l")], total: 1, page: 1, size: 25 });
    }
    if (path === "/api/v1/products/p-1") return json(route, 200, product("p-1", "Sut 1 l"));
    return json(route, 404, { error: { code: "NOT_FOUND", message_key: "errors.not_found", details: [] } });
  });

  await page.goto("/app/catalog/products");
  await expect(page.getByRole("table", { name: "Tovarlar" }).getByText("Sut 1 l")).toBeVisible();
  await expect(page.getByRole("button", { name: "Tovar qo'shish" })).toHaveCount(0);
  await page.getByRole("table", { name: "Tovarlar" }).getByText("Sut 1 l").click();
  const card = page.getByRole("dialog", { name: "Sut 1 l" });
  await expect(card.getByRole("textbox", { name: "Nomi", exact: true })).toBeDisabled();
  await expect(card.getByRole("button", { name: "Saqlash" })).toHaveCount(0);
});
