import { expect, test, type Route } from "@playwright/test";

/**
 * BO-14 «Do'kon sozlamalari» (Bosqich 1 part) on the production build: merge-PATCH carries only the
 * changed fields (never ai_cross_border/terms — QT-M17-08 UI side); tax regime change from the 1st of
 * next month (20 #40c); AI cross-border consent only via POST /tenant/consents with the current
 * `ai_cross_border` terms version (qaror #61). Later-stage sections are visible but disabled.
 */
const session = {
  user: { id: "u-1", full_name: "Akmal Karimov", phone_masked: "+998 90 *** ** 67" },
  tenant: { id: "t-1", name: "Baraka do'koni" },
  branches: [{ id: "b-1", name: "Chilonzor-3" }],
  roles: ["owner"],
  permissions: ["settings.tenant", "settings.users", "settings.branches"],
  scope: ["settings"],
  client_id: "web-bff",
  sub_status: "active",
  access_expires_at: 0,
};

type Body = Record<string, unknown>;

function json(route: Route, status: number, body: unknown) {
  return route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
}

function tenantSettings(version: number, patch: Body = {}, settingsPatch: Body = {}): Body {
  return {
    name: "Baraka do'koni",
    legal_form: "llc",
    go_live_date: "2026-10-01",
    accepted_terms_version: "2026-01",
    accepted_terms_at: "2026-10-01T10:00:00Z",
    version,
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
      ...settingsPatch,
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
    ...patch,
  };
}

test("save changed policies, schedule a tax regime and give the AI cross-border consent", async ({
  page,
}) => {
  let current = tenantSettings(3);
  const patches: Body[] = [];
  const regimes: Body[] = [];
  const consents: Body[] = [];

  await page.route("**/auth/session", (route) => json(route, 200, session));
  await page.route("**/auth/terms", (route) =>
    json(route, 200, {
      items: [
        {
          kind: "terms",
          version: "2026-01",
          text_url: "https://erp.uz/terms",
          text_sha256: "a",
          effective_from: "2026-01-01",
        },
        {
          kind: "ai_cross_border",
          version: "ai-2026-02",
          text_url: "https://erp.uz/ai",
          text_sha256: "b",
          effective_from: "2026-02-01",
        },
      ],
    }),
  );
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const method = request.method();
    if (path === "/api/v1/auth/csrf") return json(route, 200, { csrf_token: "csrf-e2e" });
    if (path === "/api/v1/tenant/settings" && method === "GET") return json(route, 200, current);
    if (path === "/api/v1/tenant/settings" && method === "PATCH") {
      const body = request.postDataJSON() as Body;
      patches.push(body);
      const settingsPatch = (body.settings ?? {}) as Body;
      current = tenantSettings(4, { name: body.name ?? current.name }, settingsPatch);
      const { tax_regime: _t, integrations: _i, ...plain } = current;
      return json(route, 200, plain);
    }
    if (path === "/api/v1/tenant/tax-regimes") {
      const body = request.postDataJSON() as Body;
      regimes.push(body);
      current = {
        ...current,
        tax_regime: { current: "vat", history: [{ regime: "vat", valid_from: "2026-10-01" }, body] },
      };
      return json(route, 201, body);
    }
    if (path === "/api/v1/tenant/consents") {
      const body = request.postDataJSON() as Body;
      consents.push(body);
      current = tenantSettings(5, {}, { ai_cross_border_enabled: true });
      return json(route, 201, { ...body, at: "2026-10-17T09:00:00Z", ai_cross_border_enabled: true });
    }
    return json(route, 404, { error: { code: "NOT_FOUND", message_key: "errors.not_found", details: [] } });
  });

  await page.goto("/app/settings/tenant");
  const main = page.locator("#main");
  await expect(main.getByRole("heading", { name: "Do'kon sozlamalari" })).toBeVisible();
  const save = main.getByRole("button", { name: "Saqlash" });
  await expect(save).toBeDisabled();

  // --- Store name + marking precheck → only the changed fields are sent ------------------------------
  await main.getByLabel("Do'kon nomi").fill("Mega Market");
  await main.getByRole("tab", { name: "Fiskal" }).click();
  await main.getByRole("button", { name: "Bloklash" }).click();
  await save.click();
  await expect(page.getByText("Sozlamalar saqlandi").first()).toBeVisible();
  expect(patches).toEqual([{ version: 3, name: "Mega Market", settings: { marking_precheck: "block" } }]);
  await expect(save).toBeDisabled();

  // --- Tax regime from the 1st of next month (20 #40c) ------------------------------------------------
  await main.getByRole("tab", { name: "Soliq rejimi" }).click();
  await expect(main.getByText("QQS to'lovchi").first()).toBeVisible();
  await main.getByRole("button", { name: "Rejimni o'zgartirish" }).click();
  const regime = page.getByRole("dialog", { name: "Soliq rejimini o'zgartirish" });
  await regime.getByRole("radio", { name: "Aylanma solig'i" }).click();
  await regime.getByRole("button", { name: /dan o'zgartirish$/ }).click();
  await expect(regime).toHaveCount(0);
  expect(regimes).toHaveLength(1);
  expect(regimes[0]).toMatchObject({ regime: "turnover" });
  expect(String(regimes[0]?.valid_from)).toMatch(/^\d{4}-\d{2}-01$/);
  await expect(main.getByText(/Rejalashtirilgan: Aylanma solig'i/)).toBeVisible();
  // Costing method (Bosqich 2, its own spec valuation.spec.ts): the card is on this tab.
  await expect(main.getByRole("heading", { name: "Zaxira baholash usuli" })).toBeVisible();

  // --- AI cross-border consent (owner only, POST /tenant/consents) -----------------------------------
  await main.getByRole("tab", { name: "Xavfsizlik" }).click();
  await main.getByRole("switch", { name: /AI xizmatiga/ }).click();
  const consent = page.getByRole("dialog", { name: "Chet elga uzatishga rozilik" });
  await expect(consent.getByText(/versiya ai-2026-02/)).toBeVisible();
  await consent.getByRole("button", { name: "Roziman" }).click();
  await expect(consent).toHaveCount(0);
  expect(consents).toEqual([{ purpose: "ai_cross_border", terms_version: "ai-2026-02", accepted: true }]);
  await expect(main.getByText("Berilgan", { exact: true })).toBeVisible();
  // The consent never went through PATCH.
  expect(JSON.stringify(patches)).not.toContain("ai_cross_border");
});

test("errors on another tab switch to it and are summarised (client and server)", async ({ page }) => {
  const patches: Body[] = [];
  await page.route("**/auth/session", (route) => json(route, 200, session));
  await page.route("**/auth/terms", (route) => json(route, 200, { items: [] }));
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const method = request.method();
    if (path === "/api/v1/auth/csrf") return json(route, 200, { csrf_token: "csrf-e2e" });
    if (path === "/api/v1/tenant/settings" && method === "GET") return json(route, 200, tenantSettings(3));
    if (path === "/api/v1/tenant/settings" && method === "PATCH") {
      patches.push(request.postDataJSON() as Body);
      return json(route, 422, {
        error: {
          code: "VALIDATION_ERROR",
          message_key: "errors.validation",
          details: [{ field: "settings.marking_precheck", message_key: "validation.invalid_choice" }],
        },
      });
    }
    return json(route, 404, { error: { code: "NOT_FOUND", message_key: "errors.not_found", details: [] } });
  });

  await page.goto("/app/settings/tenant");
  const main = page.locator("#main");
  const save = main.getByRole("button", { name: "Saqlash" });

  // Client error on «Do'kon» while «Fiskal» is open → back to «Do'kon», summary banner, nothing sent.
  await main.getByLabel("Do'kon nomi").fill("M");
  await main.getByRole("tab", { name: "Fiskal" }).click();
  await main.getByRole("button", { name: "Bloklash" }).click();
  await save.click();
  await expect(main.getByRole("tab", { name: /^Do'kon/ })).toHaveAttribute("aria-selected", "true");
  await expect(main.getByText("Saqlanmadi — xatolarni tuzating: Do'kon")).toBeVisible();
  await expect(main.getByLabel("Do'kon nomi")).toBeFocused();
  expect(patches).toEqual([]);

  // Server error on a «Fiskal» field while «Do'kon» is open → switches to «Fiskal».
  await main.getByLabel("Do'kon nomi").fill("Mega Market");
  await save.click();
  await expect(main.getByRole("tab", { name: /^Fiskal/ })).toHaveAttribute("aria-selected", "true");
  await expect(main.getByText("Saqlanmadi — xatolarni tuzating: Fiskal")).toBeVisible();
  await expect(main.getByText("Ro'yxatdan birini tanlang").first()).toBeVisible();
  expect(patches).toHaveLength(1);
});

test("a non-owner (no settings.tenant) gets NoPermissionState", async ({ page }) => {
  await page.route("**/auth/session", (route) =>
    json(route, 200, { ...session, roles: ["manager"], permissions: ["telegram.link"], scope: ["telegram"] }),
  );
  await page.goto("/app/settings/tenant");
  await expect(page.getByText("Sizda bu bo'limga kirish huquqi yo'q").first()).toBeVisible();
});
