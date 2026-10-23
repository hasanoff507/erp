import { expect, test, type Page, type Route } from "@playwright/test";

/**
 * BO-11 «Xodimlar» on the production build (strict CSP): invite a cashier (phone, name, role, branch)
 * → POST /admin/users → the row shows «Taklif yuborildi · Telegram» (QT-M13-04); revoke ONE session
 * of a user, the other stays (QT-M13-07); password reset with confirmation (QT-M13-06); block with
 * «Xodimni bloklaysizmi?» → status «Bloklangan» (QT-M13-05). Backend stubbed with page.route().
 */
const session = {
  user: { id: "u-1", full_name: "Akmal Karimov", phone_masked: "+998 90 *** ** 67" },
  tenant: { id: "t-1", name: "Baraka do'koni" },
  branches: [{ id: "b-1", name: "Chilonzor-3" }],
  roles: ["owner"],
  permissions: ["settings.users", "devices.revoke", "settings.tenant", "settings.branches"],
  scope: ["settings", "devices"],
  client_id: "web-bff",
  sub_status: "active",
  access_expires_at: 0,
};

type Body = Record<string, unknown>;

const roles = [
  { id: "r-owner", name: "Egasi", is_system: true, system_code: "owner", version: 1 },
  { id: "r-manager", name: "Menejer", is_system: true, system_code: "manager", version: 1 },
  { id: "r-cashier", name: "Kassir", is_system: true, system_code: "cashier", version: 1 },
  { id: "r-store", name: "Omborchi", is_system: true, system_code: "storekeeper", version: 1 },
  { id: "r-acc", name: "Buxgalter", is_system: true, system_code: "accountant", version: 1 },
];

const sessionRow = (id: string, ua: string): Body => ({
  session_id: id,
  client_id: "web-bff",
  device_id: null,
  device_kind: "web",
  created_at: "2026-10-16T07:58:00Z",
  last_seen_at: "2026-10-16T09:10:00Z",
  ip: "10.0.0.5",
  user_agent: ua,
  current: false,
});

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

test("invite a cashier, revoke one session, reset the password and block a user", async ({ page }) => {
  const violations = collectCspViolations(page);
  const staff: Body[] = [
    {
      user_id: "u-1",
      name: "Akmal Karimov",
      phone: "+998909112045",
      role_ids: ["r-owner"],
      branch_ids: ["b-1"],
      status: "active",
      last_login_at: "2026-10-16T18:40:00Z",
    },
    {
      user_id: "u-2",
      name: "Sardor M.",
      phone: "+998973021688",
      role_ids: ["r-manager"],
      branch_ids: ["b-1"],
      status: "active",
      last_login_at: "2026-10-16T14:10:00Z",
    },
  ];
  let sessions: Body[] = [sessionRow("s-1", "Chrome · Windows"), sessionRow("s-2", "Android POS")];
  const created: Body[] = [];
  const revoked: string[] = [];
  const patches: Body[] = [];
  let passwordResets = 0;

  await page.route("**/auth/session", (route) => json(route, 200, session));
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const method = request.method();
    if (path === "/api/v1/auth/csrf") return json(route, 200, { csrf_token: "csrf-e2e" });
    if (path === "/api/v1/roles") return json(route, 200, { items: roles, total: 5, page: 1, size: 200 });
    if (path === "/api/v1/branches") {
      return json(route, 200, {
        items: [
          {
            id: "b-1",
            name: "Chilonzor-3",
            code: "01",
            address: null,
            is_default: true,
            settlement_category: "city_100k_plus",
            activity_type: "retail",
            version: 1,
          },
        ],
        total: 1,
        page: 1,
        size: 200,
      });
    }
    if (path === "/api/v1/admin/users" && method === "GET") {
      return json(route, 200, { items: staff, next_cursor: null });
    }
    if (path === "/api/v1/admin/users" && method === "POST") {
      const body = request.postDataJSON() as Body;
      created.push(body);
      expect(request.headers()["idempotency-key"]).toBeTruthy();
      return json(route, 201, {
        user_id: "u-9",
        name: body.name,
        phone: body.phone,
        role_ids: body.role_ids,
        branch_ids: body.branch_ids,
        status: "active",
        last_login_at: null,
        channel_used: "telegram",
      });
    }
    if (path === "/api/v1/admin/users/u-1/sessions") return json(route, 200, { items: [] });
    if (path === "/api/v1/admin/users/u-1/devices") return json(route, 200, { items: [] });
    if (path === "/api/v1/admin/users/u-2/sessions") return json(route, 200, { items: sessions });
    if (path === "/api/v1/admin/users/u-2/devices") return json(route, 200, { items: [] });
    if (path === "/api/v1/admin/users/u-2/sessions/s-1/revoke") {
      revoked.push("s-1");
      sessions = sessions.filter((s) => s.session_id !== "s-1");
      return json(route, 200, { user_id: "u-2", sessions_revoked: 1 });
    }
    if (path === "/api/v1/admin/users/u-2/reset-password") {
      passwordResets += 1;
      const ended = sessions.length;
      sessions = [];
      return json(route, 200, { user_id: "u-2", sessions_revoked: ended, channel_used: "sms" });
    }
    if (path === "/api/v1/admin/users/u-2" && method === "PATCH") {
      patches.push(request.postDataJSON() as Body);
      return json(route, 200, { user_id: "u-2", status: "blocked", sessions_revoked: 0 });
    }
    return json(route, 404, { error: { code: "NOT_FOUND", message_key: "errors.not_found", details: [] } });
  });

  await page.goto("/app/settings/users");
  await expect(page.locator("#main").getByRole("heading", { name: "Xodimlar va huquqlar" })).toBeVisible();
  await expect(page.getByRole("row", { name: /Akmal Karimov \(siz\)/ })).toBeVisible();

  // --- Invite (US-M13-04) --------------------------------------------------------------------------
  await page.getByRole("button", { name: "Xodim qo'shish" }).first().click();
  const dialog = page.getByRole("dialog", { name: "Yangi xodimni taklif qilish" });
  await expect(dialog).toBeVisible();
  // The owner role is not offered.
  await expect(dialog.getByRole("checkbox", { name: "Egasi" })).toHaveCount(0);
  await dialog.getByRole("button", { name: "Taklif yuborish" }).click();
  await expect(dialog.getByText("Bu maydonni to'ldirish shart").first()).toBeVisible();

  await dialog.getByLabel("Telefon").fill("90 111 22 33");
  await dialog.getByLabel("To'liq ism").fill("Dilnoza R.");
  await dialog.getByRole("checkbox", { name: "Kassir" }).click();
  await expect(dialog.getByRole("checkbox", { name: "Chilonzor-3" })).toBeChecked();
  await dialog.getByRole("button", { name: "Taklif yuborish" }).click();

  await expect(dialog).toHaveCount(0);
  expect(created).toEqual([
    { phone: "+998901112233", name: "Dilnoza R.", role_ids: ["r-cashier"], branch_ids: ["b-1"] },
  ]);
  const newRow = page.getByRole("row", { name: /Dilnoza R\./ });
  await expect(newRow).toBeVisible();
  await expect(newRow.getByText("Taklif yuborildi · Telegram")).toBeVisible();
  await expect(page.getByText("Kod Telegram orqali yuborildi").first()).toBeVisible();

  // --- The owner cannot block himself (QT-M13-09, UI side) -----------------------------------------
  await page.getByRole("row", { name: /Akmal Karimov \(siz\)/ }).click();
  const ownSheet = page.getByRole("dialog", { name: "Akmal Karimov" });
  await expect(ownSheet.getByRole("button", { name: "Bloklash" })).toBeDisabled();
  await expect(ownSheet.getByText("O'zingizni bloklab bo'lmaydi")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(ownSheet).toHaveCount(0);

  // --- Sessions: revoke exactly one (US-M13-07) ------------------------------------------------------
  await page.getByRole("row", { name: /Sardor M\./ }).click();
  const sheet = page.getByRole("dialog", { name: "Sardor M." });
  await expect(sheet).toBeVisible();
  const list = sheet.getByRole("list", { name: "Seanslar ro'yxati" });
  await expect(list.getByRole("listitem")).toHaveCount(2);
  await list
    .getByRole("listitem")
    .filter({ hasText: "Chrome · Windows" })
    .getByRole("button", { name: /Seansni tugatish/ })
    .click();
  await expect(list.getByRole("listitem")).toHaveCount(1);
  await expect(list.getByText("Android POS")).toBeVisible();
  expect(revoked).toEqual(["s-1"]);

  // --- Password reset with confirmation (US-M13-06) ------------------------------------------------
  await sheet.getByRole("button", { name: "Parolni tiklash" }).click();
  const confirmReset = page.getByRole("alertdialog", { name: "Parolni tiklaysizmi?" });
  await expect(confirmReset.getByText(/Telegram bot orqali/)).toBeVisible();
  await confirmReset.getByRole("button", { name: "Parolni tiklash" }).click();
  await expect(confirmReset).toHaveCount(0);
  expect(passwordResets).toBe(1);
  await expect(page.getByText("Kod SMS orqali yuborildi").first()).toBeVisible();
  await expect(sheet.getByText("Faol seans yo'q")).toBeVisible();

  // --- Block (US-M13-05) ----------------------------------------------------------------------------
  await sheet.getByRole("button", { name: "Bloklash" }).click();
  const confirmBlock = page.getByRole("alertdialog", { name: "Xodimni bloklaysizmi?" });
  await confirmBlock.getByRole("button", { name: "Bloklash" }).click();
  await expect(confirmBlock).toHaveCount(0);
  expect(patches).toEqual([{ status: "blocked" }]);
  await expect(sheet.getByText("Bloklangan")).toBeVisible();
  await expect(sheet.getByRole("button", { name: "Blokdan chiqarish" })).toBeVisible();

  expect(violations).toEqual([]);
});

test("invited membership, cross-tenant credential refusal, partial counts and search over all pages", async ({
  page,
}) => {
  const member = (id: string, name: string, patch: Body = {}): Body => ({
    user_id: id,
    name,
    phone: `+99890${id.replace(/\D/g, "").padStart(7, "0")}`,
    role_ids: ["r-cashier"],
    branch_ids: ["b-1"],
    status: "active",
    last_login_at: "2026-10-16T14:10:00Z",
    ...patch,
  });
  const firstPage = [
    member("u-1", "Akmal Karimov", { role_ids: ["r-owner"] }),
    member("u-3", "", { status: "invited", invited_name: "Dilshod T." }),
    member("u-4", "Nodira K."),
  ];
  const secondPage = [member("u-7", "Zafar Yo'ldoshev")];
  const cursors: (string | null)[] = [];
  let resets = 0;

  await page.route("**/auth/session", (route) => json(route, 200, session));
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    if (path === "/api/v1/auth/csrf") return json(route, 200, { csrf_token: "csrf-e2e" });
    if (path === "/api/v1/roles") return json(route, 200, { items: roles, total: 5, page: 1, size: 200 });
    if (path === "/api/v1/branches") return json(route, 200, { items: [], total: 0, page: 1, size: 200 });
    if (path === "/api/v1/admin/users" && request.method() === "GET") {
      const cursor = url.searchParams.get("cursor");
      cursors.push(cursor);
      return cursor
        ? json(route, 200, { items: secondPage, next_cursor: null })
        : json(route, 200, { items: firstPage, next_cursor: "c-2" });
    }
    if (/\/admin\/users\/u-\d+\/(sessions|devices)$/.test(path)) return json(route, 200, { items: [] });
    if (path === "/api/v1/admin/users/u-4/reset-password") {
      resets += 1;
      return json(route, 422, {
        error: {
          code: "VALIDATION_ERROR",
          message_key: "validation.credential_shared_across_tenants",
          details: [],
        },
      });
    }
    return json(route, 404, { error: { code: "NOT_FOUND", message_key: "errors.not_found", details: [] } });
  });

  await page.goto("/app/settings/users");
  // More pages exist → the counts say they cover only the loaded rows.
  await expect(page.getByText(/^Ko'rsatilgan: 3 xodim/)).toBeVisible();

  // Membership `invited`: own badge, the invited name, no password/PIN reset.
  const invitedRow = page.getByRole("row", { name: /Dilshod T\./ });
  await expect(invitedRow.getByText("Taklif yuborilgan")).toBeVisible();
  await invitedRow.click();
  const invitedSheet = page.getByRole("dialog", { name: "Dilshod T." });
  await expect(invitedSheet.getByRole("button", { name: "Tahrirlash" })).toBeVisible();
  await expect(invitedSheet.getByRole("button", { name: "Parolni tiklash" })).toHaveCount(0);
  await expect(invitedSheet.getByRole("button", { name: "PINni qayta o'rnatish" })).toHaveCount(0);
  await page.keyboard.press("Escape");
  await expect(invitedSheet).toHaveCount(0);

  // Reset refused because the user also works in another store → the explanation is shown.
  await page.getByRole("row", { name: /Nodira K\./ }).click();
  const sheet = page.getByRole("dialog", { name: "Nodira K." });
  await sheet.getByRole("button", { name: "Parolni tiklash" }).click();
  const confirmReset = page.getByRole("alertdialog", { name: "Parolni tiklaysizmi?" });
  await confirmReset.getByRole("button", { name: "Parolni tiklash" }).click();
  await expect(confirmReset.getByText(/Bu xodim boshqa do'konda ham ishlaydi/)).toBeVisible();
  expect(resets).toBe(1);
  await page.keyboard.press("Escape");
  await expect(confirmReset).toHaveCount(0);
  await page.keyboard.press("Escape");
  await expect(sheet).toHaveCount(0);

  // Searching loads the remaining pages, so a member on page 2 is found.
  await page.getByRole("searchbox", { name: "Ism yoki telefon bo'yicha qidirish" }).fill("Zafar");
  await expect(page.getByRole("row", { name: /Zafar Yo'ldoshev/ })).toBeVisible();
  expect(cursors).toEqual([null, "c-2"]);
  await expect(page.getByText(/^4 xodim · 3 faol/)).toBeVisible();
});

test("a member with devices.revoke only (manager) sees just the Qurilmalar tab", async ({ page }) => {
  await page.route("**/auth/session", (route) =>
    json(route, 200, {
      ...session,
      roles: ["manager"],
      permissions: ["devices.revoke", "telegram.link"],
      scope: ["devices", "telegram"],
    }),
  );
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/v1/branches") return json(route, 200, { items: [], total: 0, page: 1, size: 200 });
    if (path === "/api/v1/devices") return json(route, 200, { items: [], total: 0, page: 1, size: 50 });
    return json(route, 403, {
      error: { code: "PERMISSION_DENIED", message_key: "errors.permission_denied", details: [] },
    });
  });
  await page.goto("/app/settings/users");
  await expect(page.getByRole("tab", { name: "Qurilmalar" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Xodimlar" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Xodim qo'shish" })).toHaveCount(0);
  await expect(page.getByText("Qurilma yo'q")).toBeVisible();
});

test("revoke a device with unsent events: reason + explicit pending-loss confirmation", async ({ page }) => {
  const revokes: Body[] = [];
  let devices: Body[] = [
    {
      id: "d-1",
      kind: "android",
      app_version: "1.4.2",
      cash_register_id: "cr-1",
      cash_register_name: "Kassa 1 · Chilonzor-3",
      branch_id: "b-1",
      last_seen_at: "2026-10-16T09:00:00Z",
      last_sync_at: "2026-10-16T08:58:00Z",
      outbox_pending_count: 37,
      outbox_oldest_pending_at: "2026-10-16T07:00:00Z",
      has_pending: true,
      revoked_at: null,
    },
  ];
  await page.route("**/auth/session", (route) => json(route, 200, session));
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (path === "/api/v1/auth/csrf") return json(route, 200, { csrf_token: "csrf-e2e" });
    if (path === "/api/v1/roles") return json(route, 200, { items: roles, total: 5, page: 1, size: 200 });
    if (path === "/api/v1/admin/users") return json(route, 200, { items: [], next_cursor: null });
    if (path === "/api/v1/branches") return json(route, 200, { items: [], total: 0, page: 1, size: 200 });
    if (path === "/api/v1/devices")
      return json(route, 200, { items: devices, total: devices.length, page: 1, size: 50 });
    if (path === "/api/v1/devices/d-1/revoke") {
      revokes.push(request.postDataJSON() as Body);
      devices = devices.map((d) => ({ ...d, revoked_at: "2026-10-16T10:00:00Z" }));
      return json(route, 200, { id: "d-1", revoked_at: "2026-10-16T10:00:00Z", outbox_pending_count: 37 });
    }
    return json(route, 404, { error: { code: "NOT_FOUND", message_key: "errors.not_found", details: [] } });
  });

  await page.goto("/app/settings/users?tab=devices");
  const row = page.getByRole("row", { name: /Kassa 1 · Chilonzor-3/ });
  await expect(row.getByText("37 ta kutmoqda")).toBeVisible();
  await row.getByRole("button", { name: "Bekor qilish" }).click();

  const dialog = page.getByRole("alertdialog", { name: "Qurilmani bekor qilasizmi?" });
  await expect(dialog.getByText("Qurilmada 37 ta yuborilmagan voqea bor — avval sinxronlang.")).toBeVisible();
  const confirm = dialog.getByRole("button", { name: "Qurilmani bekor qilish" });
  await expect(confirm).toBeDisabled();
  await dialog.getByLabel("Sabab").fill("Qurilma yo'qolgan");
  await expect(confirm).toBeDisabled();
  await dialog.getByRole("checkbox", { name: /yo'qolishi mumkinligini tushunaman/ }).click();
  await confirm.click();

  await expect(dialog).toHaveCount(0);
  expect(revokes).toEqual([{ reason: "Qurilma yo'qolgan", confirm_pending_loss: true }]);
  await expect(row.getByText("Bekor qilingan")).toBeVisible();
});
