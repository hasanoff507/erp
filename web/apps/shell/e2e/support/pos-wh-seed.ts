/**
 * e2e seed of the POS warehouse / equipment screens (b3-pos-wh): registered device, a PIN-verified storekeeper
 * (sessionStorage + staff snapshot with the warehouse permissions), the first snapshot pull, and REST stubs for
 * `/warehouses`, `/stock-counts`, `/transfers`. No open shift is needed (contracts/pos-wh-routes.md).
 */
import { expect, type Page, type Route } from "@playwright/test";

import { STUB_DEVICE, type Body, type SyncStub } from "./offline-stub.ts";
import { CASHIER_ID, posBffSession, posPull, setDeviceSetting } from "./pos-seed.ts";

export const WH_PERMISSIONS = [
  "stock.view",
  "stock.count.create",
  "transfer.create",
  "transfer.receive",
  "purchases.receive",
];

export const WH_WAREHOUSES = [
  { id: "w-1", branch_id: STUB_DEVICE.branch_id, name: "Chilonzor ombori", type: "store", inventory_account: "2920", version: 1 },
  { id: "w-2", branch_id: "b-2", name: "Yunusobod ombori", type: "store", inventory_account: "2920", version: 1 },
]; // prettier-ignore

export function whSession(): Body {
  const base = posBffSession();
  return { ...base, permissions: [...(base.permissions as string[]), ...WH_PERMISSIONS] };
}

export function whPull(): Body {
  return posPull({ staffPermissions: WH_PERMISSIONS });
}

export const json = (route: Route, body: unknown, status = 200) =>
  route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });

async function idbCount(page: Page, db: string, store: string): Promise<number> {
  return page.evaluate(
    ({ db, store }) =>
      new Promise<number>((resolve) => {
        const open = indexedDB.open(db);
        open.onsuccess = () => {
          const conn = open.result;
          if (!conn.objectStoreNames.contains(store)) {
            conn.close();
            resolve(-1);
            return;
          }
          const req = conn.transaction(store, "readonly").objectStore(store).count();
          req.onsuccess = () => {
            conn.close();
            resolve(req.result);
          };
          req.onerror = () => resolve(-1);
        };
        open.onerror = () => resolve(-1);
      }),
    { db, store },
  );
}

/** Device + storekeeper + snapshot pull; ends on `path`. Requires `installSyncStub(page, {session: whSession(), pull: whPull()})`. */
export async function seedWarehousePos(page: Page, sync: SyncStub, path: string): Promise<void> {
  await page.route("**/api/v1/warehouses**", (route) => json(route, { items: WH_WAREHOUSES }));
  await page.goto("/pos/login");
  await expect.poll(() => idbCount(page, "erp-device", "device_settings")).toBeGreaterThanOrEqual(0);
  await setDeviceSetting(page, "device.identity", {
    deviceId: STUB_DEVICE.id,
    tenantId: "t-1",
    branchId: STUB_DEVICE.branch_id,
    cashRegisterId: STUB_DEVICE.cash_register_id,
  });
  await setDeviceSetting(page, "pos.device_names", {
    branchName: "Chilonzor-3",
    cashRegisterName: "Kassa 1",
  });
  await page.evaluate(
    ({ id, perms }) =>
      sessionStorage.setItem(
        "erp.pos.cashier",
        JSON.stringify({
          userId: id,
          fullName: "Dilnoza Rahimova",
          roleCodes: ["storekeeper"],
          permissions: perms,
          verifiedAt: new Date().toISOString(),
          via: "local",
        }),
      ),
    { id: CASHIER_ID, perms: WH_PERMISSIONS },
  );
  // /pos/login of a device-bound session may already have started (and been cut off in) the first pull; the
  // stub serves its data once — hand it out again for a clean snapshot (deterministic seeding)
  await page.goto("about:blank");
  sync.setPullData(whPull());
  await page.goto("/pos/sync");
  await expect.poll(() => idbCount(page, "erp-pos", "catalog"), { timeout: 30_000 }).toBeGreaterThan(0);
  await page.goto(path);
}

/** USB HID scanner burst (< 30 ms between keys + Enter), dispatched in the page. */
export async function scanCode(page: Page, code: string): Promise<void> {
  await page.evaluate((text) => {
    const target = document.activeElement ?? document.body;
    for (const ch of text)
      target.dispatchEvent(new KeyboardEvent("keydown", { key: ch, bubbles: true, cancelable: true }));
    target.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true }));
  }, code);
}
