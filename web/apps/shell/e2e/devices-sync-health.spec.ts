import { expect, test, type Page, type Route } from "@playwright/test";

/**
 * BO-11 «Qurilmalar» (B3): per-device sync health from devices.last_sync_at / outbox_* (16 §3.1, §6 —
 * 24 h warning, 40 h critical), the oldest unsent event and last activity; revoking a web POS without
 * unsent events needs only a reason and says that recent users set a new PIN in this shop (16 §9).
 * Production build, strict CSP, backend stubbed with page.route(); the browser clock is fixed.
 */
const NOW = new Date("2026-10-17T12:00:00Z");
const hoursAgo = (h: number) => new Date(NOW.getTime() - h * 3_600_000).toISOString();

const session = {
  user: { id: "u-1", full_name: "Akmal Karimov", phone_masked: "+998 90 *** ** 67" },
  tenant: { id: "t-1", name: "Baraka do'koni" },
  branches: [{ id: "b-1", name: "Chilonzor-3" }],
  roles: ["manager"],
  permissions: ["devices.revoke"],
  scope: ["devices"],
  client_id: "web-bff",
  sub_status: "active",
  access_expires_at: 0,
  device: null,
};

type Body = Record<string, unknown>;

const device = (id: string, name: string, patch: Body): Body => ({
  id,
  kind: "web",
  app_version: "web-1.0.0",
  cash_register_id: `cr-${id}`,
  cash_register_name: name,
  branch_id: "b-1",
  last_seen_at: hoursAgo(0.2),
  last_sync_at: hoursAgo(0.5),
  outbox_pending_count: 0,
  outbox_oldest_pending_at: null,
  has_pending: false,
  revoked_at: null,
  ...patch,
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

test("sync health per device and revoking a web POS without unsent events", async ({ page }) => {
  const violations = collectCspViolations(page);
  await page.clock.setFixedTime(NOW);
  const revokes: Body[] = [];
  let devices: Body[] = [
    device("d-1", "Kassa 1", {}),
    device("d-2", "Kassa 2", {
      outbox_pending_count: 4,
      outbox_oldest_pending_at: hoursAgo(30),
      has_pending: true,
      last_sync_at: hoursAgo(2),
    }),
    device("d-3", "Kassa 3", {
      outbox_pending_count: 12,
      outbox_oldest_pending_at: hoursAgo(45),
      has_pending: true,
      last_sync_at: hoursAgo(44),
    }),
    device("d-4", "Kassa 4", { last_sync_at: null, last_seen_at: null }),
  ];
  await page.route("**/auth/session", (route) => json(route, 200, session));
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (path === "/api/v1/auth/csrf") return json(route, 200, { csrf_token: "csrf-e2e" });
    if (path === "/api/v1/branches")
      return json(route, 200, { items: [{ id: "b-1", name: "Chilonzor-3" }], total: 1, page: 1, size: 200 });
    if (path === "/api/v1/devices")
      return json(route, 200, { items: devices, total: devices.length, page: 1, size: 50 });
    if (path === "/api/v1/devices/d-1/revoke") {
      revokes.push(request.postDataJSON() as Body);
      devices = devices.map((d) => (d.id === "d-1" ? { ...d, revoked_at: NOW.toISOString() } : d));
      return json(route, 200, { id: "d-1", revoked_at: NOW.toISOString(), outbox_pending_count: 0 });
    }
    return json(route, 403, {
      error: { code: "PERMISSION_DENIED", message_key: "errors.permission_denied", details: [] },
    });
  });

  await page.goto("/app/settings/users?tab=devices");
  const ok = page.getByRole("row", { name: /Kassa 1/ });
  const warning = page.getByRole("row", { name: /Kassa 2/ });
  const critical = page.getByRole("row", { name: /Kassa 3/ });
  const fresh = page.getByRole("row", { name: /Kassa 4/ });
  await expect(ok.getByText("Sinxron", { exact: true })).toBeVisible();
  await expect(ok.getByText(/^oxirgi faollik: /)).toBeVisible();
  await expect(warning.getByText("24 soatdan ortiq kutmoqda")).toBeVisible();
  await expect(warning.getByText(/^eng eski yuborilmagan: /)).toBeVisible();
  await expect(warning.getByText("4 ta kutmoqda")).toBeVisible();
  await expect(critical.getByText("40 soatdan ortiq — fiskal muddat yaqin")).toBeVisible();
  await expect(fresh.getByText("Hali sinxronlanmagan")).toBeVisible();

  await ok.getByRole("button", { name: "Bekor qilish" }).click();
  const dialog = page.getByRole("alertdialog", { name: "Qurilmani bekor qilasizmi?" });
  await expect(dialog.getByText(/so'nggi 30 kunda ishlagan xodimlar shu do'konda/)).toBeVisible();
  await expect(dialog.getByRole("checkbox")).toHaveCount(0); // nothing unsent → no loss confirmation
  await dialog.getByLabel("Sabab").fill("Kassa almashtirildi");
  await dialog.getByRole("button", { name: "Qurilmani bekor qilish" }).click();
  await expect(dialog).toHaveCount(0);
  expect(revokes).toEqual([{ reason: "Kassa almashtirildi", confirm_pending_loss: false }]);
  await expect(ok.getByText("Bekor qilingan")).toBeVisible();
  await expect(ok.getByText("Sinxron", { exact: true })).toHaveCount(0); // revoked: no sync signal
  expect(violations).toEqual([]);
});

test("ru: health texts are translated", async ({ page }) => {
  await page.clock.setFixedTime(NOW);
  await page.addInitScript(() => window.localStorage.setItem("erp.lang", "ru"));
  await page.route("**/auth/session", (route) => json(route, 200, session));
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/v1/branches") return json(route, 200, { items: [], total: 0, page: 1, size: 200 });
    if (path === "/api/v1/devices")
      return json(route, 200, {
        items: [
          device("d-9", "Касса 9", {
            outbox_pending_count: 1,
            outbox_oldest_pending_at: hoursAgo(41),
            has_pending: true,
          }),
        ],
        total: 1,
        page: 1,
        size: 50,
      });
    return json(route, 403, {
      error: { code: "PERMISSION_DENIED", message_key: "errors.permission_denied", details: [] },
    });
  });
  await page.goto("/app/settings/users?tab=devices");
  const row = page.getByRole("row", { name: /Касса 9/ });
  await expect(row).toBeVisible();
  await expect(row.getByText("Более 40 часов — близок фискальный срок")).toBeVisible();
  await expect(row.getByText(/^самое старое неотправленное: /)).toBeVisible();
});
