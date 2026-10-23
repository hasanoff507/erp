/**
 * e2e helpers of the POS operation screens (b3-pos-ops: POS-01/05/07/14/15): staff with local PIN verifiers
 * (PBKDF2 known-answer vector of contracts/device-auth.md — PIN 1234, 1000 iterations), limits, a seeded
 * device / cashier / open shift with an opening cash, raw IndexedDB writes into the app-created databases.
 */
import { expect, type Page } from "@playwright/test";

import { STUB_DEVICE, type Body, type SyncStub } from "./offline-stub.ts";
import { posPull } from "./pos-seed.ts";

/** pin 1234, 1000 iterations, salt 0x00..0x0f (contracts/device-auth.md §2). */
export const PIN_1234 =
  "pbkdf2_sha256$1000$AAECAwQFBgcICQoLDA0ODw==$IkDqKiJ1SjxGEDVu+OTXrPJa8qw9LRGGbel6i3gSxSw=";

export const OPS_CASHIER = "0190a000-0000-7000-8000-0000000000a1";
export const OPS_MANAGER = "0190a000-0000-7000-8000-0000000000a2";
export const OPS_SHIFT = "0190a000-0000-7000-8000-0000000000a3";

export const CASHIER_CODES = [
  "sales.create",
  "shift.open",
  "shift.close",
  "cash.count.shift",
  "cash.deposit",
  "cash.withdraw",
  "returns.create",
  "returns.approve",
];

export interface StaffSpec {
  id: string;
  name: string;
  role: string;
  perms: Record<string, string | null>;
  pinHash?: string | null;
}

export const CASHIER: StaffSpec = {
  id: OPS_CASHIER,
  name: "Dilnoza Rahimova",
  role: "cashier",
  perms: {
    "sales.create": null,
    "shift.open": null,
    "shift.close": null,
    "cash.count.shift": null,
    "cash.deposit": null,
    "cash.withdraw": "50000.0000",
    "returns.create": null,
    "returns.approve": "100000.0000",
  },
};

export const MANAGER: StaffSpec = {
  id: OPS_MANAGER,
  name: "Akmal Menejer",
  role: "manager",
  perms: {
    "sales.create": null,
    "shift.open": null,
    "shift.close": null,
    "cash.withdraw": null,
    "returns.create": null,
    "returns.approve": null,
    "card.manual_entry.approve": null,
  },
};

/** First pull with these staff rows (permissions + limits snapshots) on top of the sale seed's catalog. */
export function opsPull(staff: StaffSpec[] = [CASHIER, MANAGER], extra: Body = {}): Body {
  return {
    ...posPull(),
    permissions: {
      digest: "ops-1",
      staff_source: "auth",
      staff: staff.map((s) => ({
        user_id: s.id,
        full_name: s.name,
        role_ids: [],
        role_codes: [s.role],
        branch_ids: [],
        active: true,
        must_change_pin: false,
        pin_local_hash: s.pinHash === undefined ? PIN_1234 : s.pinHash,
        permissions: Object.entries(s.perms).map(([code, limit_value]) => ({ code, limit_value })),
      })),
    },
    limits: {
      digest: "ops-l1",
      users: staff.map((s) => ({
        user_id: s.id,
        limits: { ...s.perms },
      })),
    },
    ...extra,
  };
}

export async function idbPut(page: Page, db: string, store: string, value: Body): Promise<void> {
  await page.evaluate(
    ({ db, store, value }) =>
      new Promise<void>((resolve, reject) => {
        const open = indexedDB.open(db);
        open.onerror = () => reject(open.error ?? new Error("open failed"));
        open.onsuccess = () => {
          const conn = open.result;
          const tx = conn.transaction(store, "readwrite");
          tx.objectStore(store).put(value);
          tx.oncomplete = () => {
            conn.close();
            resolve();
          };
          tx.onerror = () => reject(tx.error ?? new Error("tx failed"));
        };
      }),
    { db, store, value },
  );
}

async function storeCount(page: Page, db: string, store: string): Promise<number> {
  return page.evaluate(
    ({ db, store }) =>
      new Promise<number>((resolve) => {
        void indexedDB.databases().then((list) => {
          if (!list.some((d) => d.name === db)) return resolve(-1);
          const open = indexedDB.open(db);
          open.onsuccess = () => {
            const conn = open.result;
            if (!conn.objectStoreNames.contains(store)) {
              conn.close();
              return resolve(-1);
            }
            const req = conn.transaction(store, "readonly").objectStore(store).count();
            req.onsuccess = () => {
              conn.close();
              resolve(req.result);
            };
            req.onerror = () => resolve(-1);
          };
          open.onerror = () => resolve(-1);
        });
      }),
    { db, store },
  );
}

export interface OpsSeed {
  cashier?: StaffSpec;
  /** First-pull body served again before the seeding reload (default: opsPull()). */
  pull?: Body;
  openingCash?: string;
  withShift?: boolean;
}

/** Registered device + PIN-verified cashier (sessionStorage) + open shift; ends on `path`. */
export async function seedOps(page: Page, sync: SyncStub, path: string, opts: OpsSeed = {}): Promise<void> {
  const cashier = opts.cashier ?? CASHIER;
  // GET /shifts/{id} (running_totals) answers at once — the screens never wait on the dev proxy
  await page.route("**/api/v1/shifts/**", (route) =>
    route.fulfill(
      json({ error: { code: "NOT_FOUND", message_key: "errors.not_found", params: {}, details: [] } }, 404),
    ),
  );
  await page.addInitScript(() => {
    window.print = () => {
      window.dispatchEvent(new Event("afterprint"));
    };
  });
  await page.goto("/pos/login");
  await expect.poll(() => storeCount(page, "erp-device", "device_settings")).toBeGreaterThanOrEqual(0);
  await idbPut(page, "erp-device", "device_settings", {
    key: "device.identity",
    value: {
      deviceId: STUB_DEVICE.id,
      tenantId: "t-1",
      branchId: STUB_DEVICE.branch_id,
      cashRegisterId: STUB_DEVICE.cash_register_id,
    },
  });
  await idbPut(page, "erp-device", "device_settings", {
    key: "pos.device_names",
    value: { branchName: "Chilonzor-3", cashRegisterName: "Kassa 1" },
  });
  await idbPut(page, "erp-device", "device_settings", { key: "printer.transport", value: "system_print" });
  await page.evaluate(
    (c) =>
      sessionStorage.setItem(
        "erp.pos.cashier",
        JSON.stringify({
          userId: c.id,
          fullName: c.name,
          roleCodes: [c.role],
          permissions: Object.keys(c.perms),
          verifiedAt: new Date().toISOString(),
          via: "local",
        }),
      ),
    cashier,
  );
  // POS-01 may already have started (and been cut off in) the first pull of the device-bound session; the
  // stub serves its data once, so hand it out again for the reload below (deterministic seeding)
  await page.goto("about:blank");
  sync.setPullData(opts.pull ?? opsPull());
  await page.goto("/pos/sync");
  await expect.poll(() => storeCount(page, "erp-pos", "permissions"), { timeout: 15_000 }).toBeGreaterThan(0);
  if (opts.withShift !== false) {
    await idbPut(page, "erp-pos", "shift", {
      id: OPS_SHIFT,
      cash_register_id: STUB_DEVICE.cash_register_id,
      shift_no: 214,
      opened_at: new Date(Date.now() - 3_600_000).toISOString(),
      opened_by: cashier.id,
      status: "open",
      opening_cash: opts.openingCash ?? "0.00",
    });
  }
  await page.goto(path);
}

export function json(body: unknown, status = 200) {
  return { status, contentType: "application/json", body: JSON.stringify(body) };
}
