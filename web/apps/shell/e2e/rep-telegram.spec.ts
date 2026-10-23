import { expect, test } from "@playwright/test";

import { RepStub, collectCspViolations, json, type Body } from "./rep-stub.ts";

/**
 * BO-20 «Telegram va bildirishnomalar» (B4-SCR-BO-20; US-M18-01 / QT-M18-01, US-M18-03 / QT-M18-06) on
 * the production build: link-start → one-time `bot_url` + code, the page polls the status until the bot
 * binds it → «Ulangan»; per-kind alert toggles + daily report time → PATCH with every kind (time only for
 * daily_report); the notifications log; «Uzish» → DELETE after confirmation; an expired link → the 07
 * error banner. Settings-tab bar shows «Telegram».
 */
const SETTINGS = [
  { kind: "daily_report", enabled: true, time: "21:00" },
  { kind: "low_stock", enabled: true, time: null },
  { kind: "expiry_soon", enabled: true, time: null },
  { kind: "cash_variance", enabled: true, time: null },
  { kind: "over_limit_action", enabled: true, time: null },
  { kind: "debt_due_today", enabled: false, time: null },
];

function stub(opts: { linkAfter?: number; expiresInMs?: number } = {}) {
  const s = new RepStub(["telegram.link", "notifications.manage", "settings.tenant"], "b-1");
  let statusCalls = 0;
  let linked = false;
  s.on("GET", /^\/api\/v1\/notifications\/telegram\/status$/, ({ route }) => {
    statusCalls += 1;
    if (opts.linkAfter !== undefined && statusCalls > opts.linkAfter) linked = true;
    return json(route, 200, {
      linked,
      chat_id: linked ? "123456789" : null,
      linked_at: linked ? "2026-10-17T09:49:00Z" : null,
    });
  })
    .on("POST", /^\/api\/v1\/notifications\/telegram\/link-start$/, ({ route }) =>
      json(route, 201, {
        link_code: "lnk_7Q4M2XKDabcdefghijk",
        bot_url: "https://t.me/erp_test_bot?start=lnk_7Q4M2XKDabcdefghijk",
        expires_at: new Date(Date.now() + (opts.expiresInMs ?? 600_000)).toISOString(),
      }),
    )
    .on("DELETE", /^\/api\/v1\/notifications\/telegram\/link$/, ({ route }) => {
      linked = false;
      opts.linkAfter = undefined;
      return route.fulfill({ status: 204 });
    })
    .on("GET", /^\/api\/v1\/notification-settings$/, ({ route }) => json(route, 200, { items: SETTINGS }))
    .on("PATCH", /^\/api\/v1\/notification-settings$/, ({ route, body }) =>
      json(route, 200, { items: (body as Body).items }),
    )
    .on("GET", /^\/api\/v1\/notifications-log$/, ({ route }) =>
      json(route, 200, {
        items: [
          {
            id: "l-2",
            channel: "telegram",
            recipient: "123456789",
            template: "low_stock",
            status: "sent",
            cost: null,
            created_at: new Date().toISOString(),
          },
          {
            id: "l-1",
            channel: "telegram",
            recipient: "123456789",
            template: "cash_variance",
            status: "failed",
            cost: null,
            created_at: "2026-09-30T16:00:00Z",
          },
        ],
        next_cursor: null,
      }),
    );
  return s;
}

test("QT-M18-01: link → one-time link and code → status polled until linked", async ({ page }) => {
  const violations = collectCspViolations(page);
  const s = stub({ linkAfter: 2 });
  await s.install(page);
  await page.goto("/app/settings/telegram");
  await expect(page.getByRole("heading", { name: "Telegram va bildirishnomalar" }).first()).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Sozlamalar bo'limlari" })).toContainText("Telegram");
  await expect(page.getByText("Ulanmagan")).toBeVisible();

  await page.getByRole("button", { name: "Telegramni ulash" }).click();
  const link = page.getByRole("link", { name: /t\.me\/erp_test_bot/ });
  await expect(link).toHaveAttribute("href", "https://t.me/erp_test_bot?start=lnk_7Q4M2XKDabcdefghijk");
  await expect(page.getByTestId("telegram-link-code")).toHaveText("lnk_7Q4M2XKDabcdefghijk");
  await expect(page.getByText(/Havola 10 daqiqa amal qiladi · \d{2}:\d{2} gacha/)).toBeVisible();
  expect(s.writes.find((w) => w.path.endsWith("/link-start"))?.idempotencyKey).toBeTruthy();

  // The bot binds the code (3rd status read) → «Ulangan», the link panel is gone.
  await expect(page.getByText("Ulangan", { exact: true })).toBeVisible({ timeout: 15_000 });
  await expect(link).toHaveCount(0);
  await expect(page.getByText(/«Kam qolgan tovar»/)).toBeVisible();

  // «Uzish» → confirmation → DELETE.
  await page.getByRole("button", { name: "Uzish" }).click();
  await page
    .getByRole("alertdialog")
    .or(page.getByRole("dialog"))
    .getByRole("button", { name: "Uzish" })
    .click();
  await expect(page.getByText("Ulanmagan")).toBeVisible();
  expect(s.writes.filter((w) => w.method === "DELETE")).toHaveLength(1);
  expect(violations).toEqual([]);
});

test("QT-M18-06 / US-M18-03: alert toggles and daily time are saved; log listed", async ({ page }) => {
  const s = stub();
  await s.install(page);
  await page.goto("/app/settings/telegram");
  await expect(page.getByText("4 / 5 yoqilgan")).toBeVisible();
  await page.getByRole("switch", { name: "Kam qolgan tovar" }).click();
  await expect(page.getByText("3 / 5 yoqilgan")).toBeVisible();
  await page.getByRole("combobox", { name: "Kunlik hisobot vaqti" }).click();
  await page.getByRole("option", { name: "22:00" }).click();
  await page.getByRole("button", { name: "Saqlash" }).click();
  await expect(page.getByText("Saqlandi")).toBeVisible();
  const patch = s.writes.find((w) => w.method === "PATCH");
  expect(patch?.body).toEqual({
    items: [
      { kind: "daily_report", enabled: true, time: "22:00" },
      { kind: "low_stock", enabled: false, time: null },
      { kind: "expiry_soon", enabled: true, time: null },
      { kind: "cash_variance", enabled: true, time: null },
      { kind: "over_limit_action", enabled: true, time: null },
      { kind: "debt_due_today", enabled: false, time: null },
    ],
  });
  expect(patch?.idempotencyKey).toBeTruthy();
  await expect(page.getByRole("button", { name: "Saqlash" })).toBeDisabled();

  const log = page.getByRole("table", { name: "Yuborilgan xabarlar" });
  await expect(log.getByRole("row").filter({ hasText: "Kam qolgan tovar" })).toContainText("Yuborildi");
  await expect(log.getByRole("row").filter({ hasText: "Kassa farqi" })).toContainText("Yuborilmadi");
});

test("BO-20 error state: the link expired without «Start»", async ({ page }) => {
  const s = stub({ expiresInMs: 1_000 });
  await s.install(page);
  await page.goto("/app/settings/telegram");
  await page.getByRole("button", { name: "Telegramni ulash" }).click();
  await expect(page.getByText(/Bot ulanmadi — havola muddati o'tgan/)).toBeVisible({ timeout: 10_000 });
  await page.getByRole("button", { name: "Qayta urinish" }).click();
  expect(s.writes.filter((w) => w.path.endsWith("/link-start")).length).toBeGreaterThanOrEqual(2);
});
