/**
 * POS-01 (b3-pos-ops): device registration (B3-T17 — `POST /auth/devices/register`, CSRF re-fetched after the
 * sid change) → staff picker (permissions pull) → PIN (online `/auth/pin/verify`) → `shift.opened` with the
 * opening cash (US-M01-04); local PIN lockout offline (5 wrong → locked, 14 §12); hotkeys digits / Enter / Esc;
 * the iOS install instruction on POS-01 (B3-T11). Production build + page.route stubs (offline-stub.ts).
 */
import { expect, test } from "@playwright/test";

import { installSyncStub, STUB_DEVICE } from "./support/offline-stub.ts";
import { CASHIER, MANAGER, OPS_CASHIER, json, opsPull } from "./support/pos-ops.ts";
import { posBffSession } from "./support/pos-seed.ts";

const register = {
  id: "0190a000-0000-7000-8000-000000000c11",
  branch_id: "b-1",
  name: "Kassa 1",
  kind: "web",
  fiscal_module_id: null,
  txkm_contract_ref: null,
  fiscal_agent_id: null,
  fiscal_local_device_id: null,
  ofd_status: "registered",
  fm_state: "ok",
  last_unacked_receipt_at: null,
  fm_receipts_pending: null,
  tax_registered_at: null,
  archived_at: null,
  version: 1,
};

test("B3-T17 POS-01: register device → pick cashier → PIN → open shift", async ({ page }) => {
  const session = {
    ...posBffSession(),
    permissions: ["sales.create", "shift.open", "shift.close", "cash_register.manage"],
    scope: ["sales", "shift", "sync", "cash_register"],
    device: null,
  };
  const sync = await installSyncStub(page, { session, pull: opsPull([CASHIER, MANAGER]) });
  // after the registration the BFF session is device-bound (14 §7.2) — SEC-07 compares it with erp-device
  let sessionDevice: Record<string, unknown> | null = null;
  await page.route("**/auth/session", (route) => route.fulfill(json({ ...session, device: sessionDevice })));
  let csrfFetches = 0;
  await page.route("**/api/v1/auth/csrf", (route) => {
    csrfFetches += 1;
    return route.fulfill(json({ csrf_token: `csrf-${csrfFetches}` }));
  });
  await page.route("**/api/v1/cash-registers**", (route) => route.fulfill(json({ items: [register] })));
  const registered: unknown[] = [];
  await page.route("**/auth/devices/register", (route) => {
    registered.push(route.request().postDataJSON());
    sessionDevice = { ...STUB_DEVICE, cash_register_id: register.id };
    return route.fulfill(
      json(
        {
          id: STUB_DEVICE.id,
          kind: "web",
          cash_register_id: register.id,
          cash_register_name: "Kassa 1",
          branch_id: "b-1",
          branch_name: "Chilonzor-3",
          app_version: "web-pos",
          created: true,
          session: { ...session, device: { ...STUB_DEVICE, cash_register_id: register.id } },
        },
        201,
      ),
    );
  });
  const pinCalls: unknown[] = [];
  await page.route("**/auth/pin/verify", (route) => {
    pinCalls.push(route.request().postDataJSON());
    return route.fulfill(
      json({
        user_id: OPS_CASHIER,
        full_name: CASHIER.name,
        roles: ["cashier"],
        permissions: Object.keys(CASHIER.perms),
        verified_at: new Date().toISOString(),
        pin_local_hash: null,
      }),
    );
  });

  await page.goto("/pos/login");
  await expect(page.getByTestId("pos-login")).toBeVisible();
  await expect(page.getByText("Qurilmani ro'yxatdan o'tkazish").first()).toBeVisible();
  await expect(page.getByTestId("register-select")).toHaveValue(register.id);
  await page.getByTestId("register-submit").click();
  await expect.poll(() => registered).toEqual([{ cash_register_id: register.id, app_version: "web-pos" }]);

  // the device pulls its staff; the picker lists POS users (digit 1 = first)
  await expect(page.getByTestId("staff-list")).toContainText(CASHIER.name, { timeout: 15_000 });
  // CSRF is fetched again after the registration (the sid changed, 14 §7.2)
  await expect.poll(() => csrfFetches).toBeGreaterThanOrEqual(1);
  await page.getByRole("button", { name: new RegExp(CASHIER.name) }).click();
  await expect(page.getByTestId("pin-user")).toContainText(CASHIER.name);

  // PIN typed with the keyboard; Esc clears; Enter submits
  await page.keyboard.type("99");
  await expect(page.getByTestId("pin-dots")).toHaveAttribute("data-length", "2");
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("pin-dots")).toHaveAttribute("data-length", "0");
  await page.keyboard.type("1234");
  await page.keyboard.press("Enter");
  await expect.poll(() => pinCalls).toEqual([{ user_id: OPS_CASHIER, pin: "1234" }]);

  // step ②: opening cash (default 0 — no closed shift on this device), Enter opens the shift
  await expect(page.getByTestId("opening-cash")).toBeVisible();
  await page.getByTestId("opening-cash").fill("500000");
  await page.getByTestId("open-shift").click();
  await expect(page).toHaveURL(/\/pos\/sale/);
  await expect
    .poll(() => sync.pushRequests.flatMap((r) => r.events).filter((e) => e.type === "shift.opened").length)
    .toBe(1);
  const opened = sync.pushRequests.flatMap((r) => r.events).find((e) => e.type === "shift.opened");
  expect(opened?.actor_user_id).toBe(OPS_CASHIER);
  expect(opened?.payload).toMatchObject({
    cash_register_id: register.id,
    shift_no: 1,
    opening_cash: "500000.00",
    comment: null,
  });
  expect(Object.keys(opened?.payload ?? {}).sort()).toEqual([
    "cash_register_id",
    "comment",
    "id",
    "opening_cash",
    "shift_no",
  ]);
  expect(csrfFetches).toBeGreaterThanOrEqual(2);
});

test("POS-01 offline: wrong PIN 5× locks the cashier locally (14 §12, qaror #54)", async ({ page }) => {
  const sync = await installSyncStub(page, { session: posBffSession(), pull: opsPull([CASHIER, MANAGER]) });
  await page.goto("/pos/login");
  // the device-bound session is adopted (no registration step) and the staff list arrives
  await expect(page.getByTestId("staff-list")).toContainText(CASHIER.name, { timeout: 15_000 });
  await sync.setOffline(true);
  await page.getByRole("button", { name: new RegExp(CASHIER.name) }).click();
  for (let i = 0; i < 4; i += 1) {
    await page.keyboard.type("0000");
    await page.keyboard.press("Enter");
    await expect(page.getByTestId("pin-error")).toContainText(`Qolgan urinishlar: ${4 - i}`);
  }
  await page.keyboard.type("0000");
  await page.keyboard.press("Enter");
  await expect(page.getByTestId("pin-error")).toContainText("Ko'p noto'g'ri urinish");
  // even the right PIN is refused while locked
  await page.keyboard.type("1234");
  await page.keyboard.press("Enter");
  await expect(page.getByTestId("pin-error")).toContainText("Ko'p noto'g'ri urinish");
  await expect(page.getByTestId("opening-cash")).toHaveCount(0);
});

test("POS-01 offline: the right PIN signs in with the local PBKDF2 verifier", async ({ page }) => {
  const sync = await installSyncStub(page, { session: posBffSession(), pull: opsPull([CASHIER, MANAGER]) });
  await page.goto("/pos/login");
  await expect(page.getByTestId("staff-list")).toContainText(CASHIER.name, { timeout: 15_000 });
  await sync.setOffline(true);
  await page.keyboard.press("1");
  await page.keyboard.type("1234");
  await page.keyboard.press("Enter");
  await expect(page.getByTestId("signed-in-cashier")).toContainText(CASHIER.name);
  await expect(page.getByText("PIN lokal tekshirildi (offlayn)")).toBeVisible();
  await expect(page.getByTestId("opening-cash")).toBeVisible();
});

test("POS-01: a storekeeper (no shift.open) lands on the warehouse hub, no shift step", async ({ page }) => {
  const storekeeper = {
    id: "0190a000-0000-7000-8000-0000000000a9",
    name: "Bobur Omborchi",
    role: "storekeeper",
    perms: { "transfer.create": null, "stock.count.create": null },
  };
  const sync = await installSyncStub(page, { session: posBffSession(), pull: opsPull([storekeeper]) });
  await page.goto("/pos/login");
  await expect(page.getByTestId("staff-list")).toContainText(storekeeper.name, { timeout: 15_000 });
  await sync.setOffline(true);
  await page.keyboard.press("1");
  await page.keyboard.type("1234");
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/pos\/warehouse$/);
  expect(sync.pushRequests.flatMap((r) => r.events).filter((e) => e.type === "shift.opened")).toHaveLength(0);
});

test.describe("B3-T11 iOS", () => {
  test.use({
    userAgent:
      "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1",
  });
  test("POS-01 shows the iOS install note in the installed (Home Screen) app", async ({ page }) => {
    await page.addInitScript(() => {
      Object.defineProperty(window.navigator, "standalone", { value: true });
      const original = window.matchMedia.bind(window);
      window.matchMedia = (q: string) =>
        q.includes("display-mode: standalone") ? { ...original(q), matches: true } : original(q);
    });
    await installSyncStub(page, { session: posBffSession(), pull: opsPull() });
    await page.goto("/pos/login");
    await expect(page.getByTestId("pos-login-ios")).toContainText("iPhone va iPad");
    await expect(page.getByTestId("pos-login-ios")).toContainText("bulut printer");
  });
});
