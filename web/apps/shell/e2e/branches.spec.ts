import { expect, test, type Route } from "@playwright/test";

/**
 * BO-12 «Filiallar» on the production build: create a branch leaving the settlement category at
 * its default → «tekshiring» hint (QT-M14-04); change the category with the «faqat shu sanadan»
 * confirmation (QT-M14-03); WAREHOUSE_ACCOUNT_LOCKED on the warehouse account; ADDON_REQUIRED on
 * «+ Kassa qo'shish» → extra register offer → BO-19 (QT-M14-02 register side).
 */
const session = {
  user: { id: "u-1", full_name: "Akmal Karimov", phone_masked: "+998 90 *** ** 67" },
  tenant: { id: "t-1", name: "Baraka do'koni" },
  branches: [{ id: "b-1", name: "Chilonzor-3" }],
  roles: ["owner"],
  permissions: ["settings.branches", "cash_register.manage", "settings.users"],
  scope: ["settings", "cash_register"],
  client_id: "web-bff",
  sub_status: "active",
  access_expires_at: 0,
};

type Body = Record<string, unknown>;

function json(route: Route, status: number, body: unknown) {
  return route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
}

const envelope = (code: string, key: string, details: Body[] = []) => ({
  error: { code, message_key: key, details, request_id: "e2e" },
});

function branchRow(id: string, name: string, patch: Body = {}): Body {
  return {
    id,
    name,
    code: id === "b-1" ? "01" : "02",
    address: null,
    is_default: id === "b-1",
    settlement_category: "city_100k_plus",
    activity_type: "retail",
    version: 1,
    ...patch,
  };
}

test("create a branch with the default category, verify it, warehouse lock and register add-on", async ({
  page,
}) => {
  const branches: Body[] = [branchRow("b-1", "Chilonzor-3")];
  const creates: Body[] = [];
  const updates: Body[] = [];

  await page.route("**/auth/session", (route) => json(route, 200, session));
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const method = request.method();
    if (path === "/api/v1/auth/csrf") return json(route, 200, { csrf_token: "csrf-e2e" });
    if (path === "/api/v1/branches" && method === "GET") {
      return json(route, 200, { items: branches, total: branches.length, page: 1, size: 200 });
    }
    if (path === "/api/v1/branches" && method === "POST") {
      const body = request.postDataJSON() as Body;
      creates.push(body);
      const created = branchRow("b-2", String(body.name), { settlement_category: body.settlement_category });
      branches.push(created);
      return json(route, 201, {
        ...created,
        warehouse: { id: "w-2", type: "store", inventory_account: "2920" },
      });
    }
    const detail = /^\/api\/v1\/branches\/(b-\d)$/.exec(path);
    if (detail && method === "GET") {
      const b = branches.find((x) => x.id === detail[1]) ?? branches[0];
      return json(route, 200, { ...b, today_sales: "1250000.00", stock_value: "8400000.00" });
    }
    if (detail && method === "PATCH") {
      const body = request.postDataJSON() as Body;
      updates.push(body);
      const index = branches.findIndex((x) => x.id === detail[1]);
      branches[index] = { ...branches[index], settlement_category: body.settlement_category, version: 2 };
      return json(route, 200, { ...branches[index] });
    }
    if (/\/tax-settings$/.test(path)) {
      return json(route, 200, {
        items: [{ valid_from: "2026-10-01", settlement_category: "city_100k_plus", activity_type: "retail" }],
        total: 1,
        page: 1,
        size: 200,
      });
    }
    if (path === "/api/v1/warehouses" && method === "GET") {
      return json(route, 200, {
        items: [
          {
            id: `w-${url.searchParams.get("branch_id") ?? "x"}`,
            branch_id: url.searchParams.get("branch_id"),
            name: "Asosiy ombor",
            type: "store",
            inventory_account: "2920",
            version: 1,
          },
        ],
      });
    }
    if (path.startsWith("/api/v1/warehouses/") && method === "PATCH") {
      return json(route, 409, envelope("WAREHOUSE_ACCOUNT_LOCKED", "errors.warehouse_account_locked"));
    }
    if (path === "/api/v1/cash-registers" && method === "GET") return json(route, 200, { items: [] });
    if (path === "/api/v1/cash-registers" && method === "POST") {
      return json(route, 402, envelope("ADDON_REQUIRED", "errors.addon_required"));
    }
    return json(route, 404, envelope("NOT_FOUND", "errors.not_found"));
  });

  await page.goto("/app/settings/branches");
  const main = page.locator("#main");
  await expect(main.getByRole("heading", { name: "Filiallar", exact: true })).toBeVisible();
  await expect(main.getByText("Shahar, 100 ming+ aholi — 4%").first()).toBeVisible();
  await expect(main.getByText(/1\s250\s000/)).toBeVisible();

  // --- New branch, category left at the default (US-M14-04 negative) --------------------------------
  await page.getByRole("button", { name: "Filial qo'shish" }).click();
  const create = page.getByRole("dialog", { name: "Yangi filial" });
  await expect(create.getByText(/«Shahar, 100 ming\+» \(4%\) qo'yiladi/)).toBeVisible();
  await create.getByLabel("Filial nomi").fill("Yunusobod-1");
  await create.getByRole("button", { name: "Filialni saqlash" }).click();
  await expect(create).toHaveCount(0);
  expect(creates).toEqual([
    {
      name: "Yunusobod-1",
      address: null,
      settlement_category: "city_100k_plus",
      warehouse: { type: "store" },
    },
  ]);
  await expect(main.getByText(/Aholi punkti toifasi standart qiymatda qoldi/)).toBeVisible();

  // --- Verify → «Boshqa aholi punkti — 2%» with the from-date confirmation (QT-M14-03) ---------------
  await main.getByRole("button", { name: "Tekshirish" }).click();
  const edit = page.getByRole("dialog", { name: /Yunusobod-1 — tahrirlash/ });
  await edit.getByRole("radio", { name: /Boshqa aholi punkti — 2%/ }).click();
  await edit.getByRole("button", { name: "Saqlash" }).click();
  const confirm = page.getByRole("alertdialog", { name: "O'zgarishlarni saqlaysizmi?" });
  await expect(confirm.getByText(/faqat 01\.\d{2}\.\d{4} dan qo'llanadi/)).toBeVisible();
  await confirm.getByRole("button", { name: "Saqlash" }).click();
  await expect(confirm).toHaveCount(0);
  expect(updates).toEqual([{ settlement_category: "other", version: 1 }]);
  await expect(main.getByText(/Aholi punkti toifasi standart qiymatda qoldi/)).toHaveCount(0);
  await expect(
    main.getByRole("button", { name: /Yunusobod-1/ }).getByText("Boshqa aholi punkti — 2%"),
  ).toBeVisible();

  // --- Warehouse account locked (WAREHOUSE_ACCOUNT_LOCKED) -------------------------------------------
  await main.getByLabel("Asosiy ombor — tovar hisobi").selectOption("2910");
  await main
    .getByRole("listitem")
    .filter({ hasText: "Asosiy ombor" })
    .getByRole("button", { name: "Saqlash" })
    .click();
  await expect(main.getByText("Omborda harakat bor", { exact: false })).toBeVisible();
  await expect(main.getByLabel("Asosiy ombor — tovar hisobi")).toBeDisabled();

  // --- Register over the plan limit → add-on offer ------------------------------------------------
  await main.getByRole("button", { name: "Kassa qo'shish" }).click();
  const add = page.getByRole("dialog", { name: /yangi kassa/ });
  await add.getByLabel("Kassa nomi").fill("Kassa 2");
  await add.getByRole("button", { name: "Qo'shish" }).click();
  const addon = page.getByRole("alertdialog", { name: "Qo'shimcha kassa kerak" });
  await expect(addon.getByText(/\+39 000 so'm\/oy/)).toBeVisible();
  await expect(addon.getByRole("link", { name: "Obunaga o'tish" })).toHaveAttribute("href", "/app/billing");
});
