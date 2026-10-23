import { expect, test, type Page, type Route } from "@playwright/test";

/**
 * BO-14 «Zaxira baholash usuli» (19 §17, US-M04-05) on the production build: the current method and
 * since when, «Usulni o'zgartirish» → confirmation «keyingi hisobot yilidan» → PATCH {method} →
 * pending change shown; 409 VALUATION_METHOD_CHANGE_NOT_ALLOWED; read-only without
 * `valuation.settings.manage`; the «Qayta hisoblash navbati» status line (qaror #56c).
 */
const session = {
  user: { id: "u-1", full_name: "Akmal Karimov", phone_masked: "+998 90 *** ** 67" },
  tenant: { id: "t-1", name: "Baraka do'koni" },
  branches: [{ id: "b-1", name: "Chilonzor-3" }],
  roles: ["owner"],
  permissions: ["settings.tenant", "stock.view", "valuation.settings.manage", "accounting.post"],
  scope: ["settings", "stock", "valuation", "accounting"],
  client_id: "web-bff",
  sub_status: "active",
  access_expires_at: 0,
};

type Body = Record<string, unknown>;

function json(route: Route, status: number, body: unknown) {
  return route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
}

const tenantSettings: Body = {
  name: "Baraka do'koni",
  legal_form: "llc",
  go_live_date: "2026-10-01",
  accepted_terms_version: "2026-01",
  accepted_terms_at: "2026-10-01T10:00:00Z",
  version: 3,
  settings: {
    bank_account: null,
    bank_mfo: null,
    supplier_overpay_policy: "warn",
    vat_diff_tolerance_amount: "1000.00",
    marking_precheck: "warn",
    discount_posting: "gross_9050",
    owner_withdrawal_account: "4890",
    payment_org_commission_account: "9430",
    turnover_tax_account: "9430",
    negative_stock_policy: "allow",
    ai_training_consent: false,
    ai_cross_border_enabled: false,
    card_manual_fallback: "manager_approval",
    fiscal_policy: { debt_receipt_split: "single", credit_sale_receipt: "none" },
  },
  tax_regime: { current: "vat", history: [{ regime: "vat", valid_from: "2026-10-01" }] },
  integrations: {
    ofd: { status: "connected" },
    faktura_uz: { status: "not_connected", connected_at: null },
    crpt: { status: "not_connected", key_last4: null },
    click: { status: "not_connected", connected_at: null },
    payme: { status: "not_connected", connected_at: null },
    uzum: { status: "not_connected", connected_at: null },
    uzqr: { status: "not_connected", connected_at: null, cash_register_ids: [] },
  },
};

async function stubBackend(page: Page, permissions: string[], patchStatus = 200) {
  const patches: Body[] = [];
  let valuation: Body = { current_method: "aveco", effective_from: "2026-01-01", pending_change: null };
  await page.route("**/auth/session", (route) => json(route, 200, { ...session, permissions }));
  await page.route("**/auth/terms", (route) => json(route, 200, { items: [] }));
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const method = request.method();
    if (path === "/api/v1/auth/csrf") return json(route, 200, { csrf_token: "csrf-e2e" });
    if (path === "/api/v1/tenant/settings") return json(route, 200, tenantSettings);
    if (path === "/api/v1/valuation-settings" && method === "GET") return json(route, 200, valuation);
    if (path === "/api/v1/valuation-settings" && method === "PATCH") {
      const body = request.postDataJSON() as Body;
      patches.push(body);
      if (patchStatus === 409) {
        valuation = { ...valuation, pending_change: { method: "fifo", effective_from: "2027-01-01" } };
        return json(route, 409, {
          error: {
            code: "VALUATION_METHOD_CHANGE_NOT_ALLOWED",
            message_key: "errors.valuation_method_change_not_allowed",
            details: [],
          },
        });
      }
      valuation = {
        current_method: "aveco",
        effective_from: "2026-01-01",
        pending_change: { method: body.method, effective_from: "2027-01-01" },
      };
      return json(route, 200, { current_method: "aveco", pending_change: valuation.pending_change });
    }
    if (path === "/api/v1/recost-jobs") {
      const status = url.searchParams.get("status");
      const items = status === "queued" ? [{ id: "j-1", status: "queued" }] : status === "failed" ? [] : [];
      return json(route, 200, { items, next_cursor: null });
    }
    return json(route, 404, { error: { code: "NOT_FOUND", message_key: "errors.not_found", details: [] } });
  });
  return patches;
}

test("BO-14: AVECO → FIFO is scheduled from 1 January (pending change)", async ({ page }) => {
  const patches = await stubBackend(page, session.permissions);
  await page.goto("/app/settings/tenant?tab=tax");
  const main = page.locator("#main");
  const card = main.getByRole("region", { name: "Zaxira baholash usuli" });
  await expect(card).toContainText("O'rtacha narx (AVECO)");
  await expect(card).toContainText("01.01.2026 dan amal qiladi");
  await expect(card).toContainText("keyingi hisobot yilidan kuchga kiradi");

  await card.getByRole("button", { name: "Usulni o'zgartirish" }).click();
  const dialog = page.getByRole("dialog", { name: "Zaxira usuli FIFO ga o'zgartirilsinmi?" });
  await expect(dialog).toContainText("faqat keyingi hisobot yili boshidan");
  await expect(dialog).toContainText(/\(01\.01\.\d{4}\)/);
  await dialog.getByRole("button", { name: "FIFO ga o'zgartirish" }).click();
  await expect(dialog).toHaveCount(0);

  expect(patches).toEqual([{ method: "fifo" }]);
  await expect(page.getByText("Zaxira usuli 01.01.2027 dan FIFO ga o'zgaradi").first()).toBeVisible();
  await expect(card).toContainText("01.01.2027 dan: FIFO");
  // Once a year: no second change is offered while one is scheduled.
  await expect(card.getByRole("button", { name: "Usulni o'zgartirish" })).toHaveCount(0);
  // Current method keeps its `effective_from` (PATCH answers without it).
  await expect(card).toContainText("01.01.2026 dan amal qiladi");
});

test("BO-14: 409 VALUATION_METHOD_CHANGE_NOT_ALLOWED is explained, the scheduled change is shown", async ({
  page,
}) => {
  await stubBackend(page, session.permissions, 409);
  await page.goto("/app/settings/tenant?tab=tax");
  const card = page.locator("#main").getByRole("region", { name: "Zaxira baholash usuli" });
  await card.getByRole("button", { name: "Usulni o'zgartirish" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByRole("button", { name: "FIFO ga o'zgartirish" }).click();
  await expect(dialog.getByText("Baholash usuli bu yil uchun allaqachon o'zgartirilgan")).toBeVisible();
  await dialog.getByRole("button", { name: "Bekor qilish" }).click();
  await expect(card).toContainText("01.01.2027 dan: FIFO");
});

test("BO-14: without valuation.settings.manage the method is read-only; recost status line", async ({
  page,
}) => {
  await stubBackend(page, ["settings.tenant", "stock.view"]);
  await page.goto("/app/settings/tenant?tab=tax");
  const main = page.locator("#main");
  const card = main.getByRole("region", { name: "Zaxira baholash usuli" });
  await expect(card).toContainText("O'rtacha narx (AVECO)");
  await expect(card.getByRole("button", { name: "Usulni o'zgartirish" })).toHaveCount(0);
  await expect(card).toContainText("Usulni Egasi yoki Buxgalter o'zgartiradi.");

  await main.getByRole("tab", { name: "Xavfsizlik" }).click();
  const line = main.getByRole("region", { name: "Qayta hisoblash navbati" });
  await expect(line).toContainText("Navbatda 1 ta ish — tannarx qayta hisoblanmoqda");
  // No accounting.post → no link to the journal.
  await expect(line.getByRole("link")).toHaveCount(0);
});
