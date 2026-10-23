/**
 * SEC-07 (16 §12): the back-office «Chiqish» on a POS device browser wipes the POS cache (`erp-pos`)
 * and the PIN-verified cashier before the BFF logout, keeps `erp-device`; a back-office-only browser
 * logs out as before and gets no device database.
 */
import { expect, test, type Page } from "@playwright/test";

import { posSession, STUB_DEVICE } from "./support/offline-stub.ts";

const DEVICE_IDENTITY = {
  deviceId: STUB_DEVICE.id,
  tenantId: "t-1",
  branchId: STUB_DEVICE.branch_id,
  cashRegisterId: STUB_DEVICE.cash_register_id,
};

async function stubBackOffice(page: Page) {
  const logouts: string[] = [];
  let signedIn = true;
  await page.route("**/auth/session", (route) =>
    signedIn
      ? route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(posSession()) })
      : route.fulfill({
          status: 401,
          contentType: "application/json",
          body: JSON.stringify({
            error: { code: "UNAUTHORIZED", message_key: "errors.unauthorized", details: [] },
          }),
        }),
  );
  await page.route("**/api/v1/auth/csrf", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ csrf_token: "c" }),
    }),
  );
  await page.route("**/auth/logout", (route) => {
    logouts.push(route.request().method());
    signedIn = false;
    return route.fulfill({ status: 204 });
  });
  await page.route("**/api/v1/**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ items: [], next_cursor: null }),
    }),
  );
  return logouts;
}

/** Creates `erp-device` exactly as Dexie schema v2 does (IDB version 20) and stores the identity. */
async function seedDeviceIdentity(page: Page) {
  await page.evaluate(
    (identity) =>
      new Promise<void>((resolve, reject) => {
        const req = indexedDB.open("erp-device", 20);
        req.onupgradeneeded = () => {
          req.result.createObjectStore("device_settings", { keyPath: "key" });
          req.result.createObjectStore("pin_lockouts", { keyPath: "user_id" });
        };
        req.onsuccess = () => {
          const tx = req.result.transaction("device_settings", "readwrite");
          tx.objectStore("device_settings").put({ key: "device.identity", value: identity });
          tx.oncomplete = () => {
            req.result.close();
            resolve();
          };
          tx.onerror = () => reject(new Error(String(tx.error)));
        };
        req.onerror = () => reject(new Error(String(req.error)));
      }),
    DEVICE_IDENTITY,
  );
}

const dbNames = (page: Page) =>
  page.evaluate(async () => (await indexedDB.databases()).map((d) => d.name ?? "").sort());

async function openUserMenuAndLogout(page: Page) {
  await page.getByRole("button", { name: "Foydalanuvchi menyusi" }).first().click();
  await page.getByRole("menuitem", { name: "Chiqish" }).click();
}

test("SEC-07: BO logout on a POS device browser wipes erp-pos and the cashier, keeps erp-device", async ({
  page,
}) => {
  const logouts = await stubBackOffice(page);
  await page.goto("/app/dashboard");
  await expect(page.getByRole("button", { name: "Foydalanuvchi menyusi" }).first()).toBeVisible();
  await seedDeviceIdentity(page);
  await page.evaluate(() => sessionStorage.setItem("erp.pos.cashier", JSON.stringify({ userId: "u-9" })));

  await openUserMenuAndLogout(page);

  await expect.poll(() => logouts.length).toBe(1);
  expect(await page.evaluate(() => sessionStorage.getItem("erp.pos.cashier"))).toBeNull();
  const names = await dbNames(page);
  expect(names).toContain("erp-device");
  expect(names).not.toContain("erp-pos");
});

test("SEC-07: a back-office-only browser logs out without creating device databases", async ({ page }) => {
  const logouts = await stubBackOffice(page);
  await page.goto("/app/dashboard");
  await expect(page.getByRole("button", { name: "Foydalanuvchi menyusi" }).first()).toBeVisible();
  await openUserMenuAndLogout(page);
  await expect.poll(() => logouts.length).toBe(1);
  const names = await dbNames(page);
  expect(names).not.toContain("erp-device");
  expect(names).not.toContain("erp-pos");
});
