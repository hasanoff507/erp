/**
 * e2e seed of a ready web POS (b3-pos-sale specs): a registered device (erp-device identity), a PIN-verified
 * cashier (sessionStorage, contracts/pos-session.md) and an open local shift (erp-pos `shift`) — written with
 * the raw IndexedDB API into the databases the app itself created (Dexie schema untouched). The pull stub
 * (offline-stub.ts) delivers catalog / prices / staff / settings.
 *
 *   const sync = await installSyncStub(page, { pull: posPull() });
 *   await seedReadyPos(page);   // ends on /pos/sale
 */
import { expect, type Page } from "@playwright/test";

import { posSession, STUB_DEVICE, type Body, type SyncStub } from "./offline-stub.ts";

export const CASHIER_ID = "0190a000-0000-7000-8000-0000000000u1";
export const SHIFT_ID = "0190a000-0000-7000-8000-0000000000s1";
export const TERMINAL_ID = "0190a000-0000-7000-8000-0000000000t1";

export const CASHIER_PERMISSIONS = [
  "sales.create",
  "sales.void",
  "discount.give",
  "debts.create",
  "stock.view",
];

const product = (id: string, name: string, extra: Body = {}): Body => ({
  entity: "product",
  id,
  name,
  name_ru: null,
  category_id: "cat-1",
  unit_code: "dona",
  vat_rate: "12.00",
  is_marked: false,
  is_weighed: false,
  archived_at: null,
  deleted: false,
  ...extra,
});

/** BFF session of the shop PC (scope = permission prefixes, see offline-stub `posSession`). */
export function posBffSession(): Body {
  return posSession(["sales.create", "shift.open", "shift.close", "stock.view", "debts.create"]);
}

export interface PosPullOptions {
  fiscal?: Body[];
  cardTerminals?: Body[];
  staffPermissions?: string[];
  /** Local PIN verifier of the cashier (PIN 1234, 1000 iterations — contracts/device-auth.md vector). */
  pinHash?: string | null;
}

export const PIN_1234_HASH =
  "pbkdf2_sha256$1000$AAECAwQFBgcICQoLDA0ODw==$IkDqKiJ1SjxGEDVu+OTXrPJa8qw9LRGGbel6i3gSxSw=";

/** First pull (`scope=all`): two piece products, one weighed (scale PLU 12345), staff, settings. */
export function posPull(opts: PosPullOptions = {}): Body {
  const validFrom = "2026-01-01T00:00:00Z";
  return {
    catalog: [
      { entity: "unit", id: "dona", code: "dona", is_fractional: false, deleted: false },
      { entity: "unit", id: "kg", code: "kg", is_fractional: true, deleted: false },
      { entity: "category", id: "cat-1", name: "Non va un", parent_id: null, deleted: false },
      product("p-bread", "Non Patir", { name_ru: "Лепёшка", code: "1001" }),
      product("p-milk", "Sut 1 l", { code: "1002" }),
      product("p-beef", "Mol go'shti", { unit_code: "kg", is_weighed: true, code: "12345" }),
    ],
    barcodes: [
      {
        id: "p-bread",
        product_id: "p-bread",
        barcodes: [{ barcode: "4780000000011", kind: "ean", units_per_barcode: "1.000" }],
      },
      {
        id: "p-milk",
        product_id: "p-milk",
        barcodes: [{ barcode: "4780000000028", kind: "ean", units_per_barcode: "1.000" }],
      },
      { id: "p-beef", product_id: "p-beef", barcodes: [] },
    ],
    prices: [
      {
        id: "p-bread",
        product_id: "p-bread",
        prices: [{ price_id: "pr-1", branch_id: null, price: "4000.0000", valid_from: validFrom }],
      },
      {
        id: "p-milk",
        product_id: "p-milk",
        prices: [{ price_id: "pr-2", branch_id: null, price: "13500.0000", valid_from: validFrom }],
      },
      {
        id: "p-beef",
        product_id: "p-beef",
        prices: [{ price_id: "pr-3", branch_id: null, price: "95000.0000", valid_from: validFrom }],
      },
    ],
    permissions: {
      digest: "d1",
      staff_source: "auth",
      staff: [
        {
          user_id: CASHIER_ID,
          full_name: "Dilnoza Rahimova",
          role_ids: [],
          role_codes: ["cashier"],
          branch_ids: [],
          active: true,
          must_change_pin: false,
          pin_local_hash: opts.pinHash ?? null,
          permissions: (opts.staffPermissions ?? CASHIER_PERMISSIONS).map((code) => ({
            code,
            limit_value: code === "discount.give" ? "5.0000" : null,
          })),
        },
      ],
    },
    limits: { digest: "l1", users: [{ user_id: CASHIER_ID, limits: { "discount.give": "5.0000" } }] },
    shift: {
      digest: "s1",
      cash_register_id: STUB_DEVICE.cash_register_id,
      open_shift: null,
      last_shift_no: 0,
    },
    fiscal: opts.fiscal ?? [
      {
        entity: "cash_register",
        id: STUB_DEVICE.cash_register_id,
        fm_state: "ok",
        last_unacked_receipt_at: null,
        fm_receipts_pending: 0,
        deleted: false,
      },
    ],
    settings: {
      digest: "st1",
      tenant: { name: "Baraka do'koni", legal_form: "llc", stir: "301234567" },
      tenant_settings: {},
      weight_barcode_templates: [
        {
          prefixes: ["22"],
          item_code_len: 5,
          value_len: 5,
          value_kind: "WEIGHT",
          decimals: 3,
          enabled: true,
        },
        {
          prefixes: ["21"],
          item_code_len: 5,
          value_len: 5,
          value_kind: "AMOUNT",
          decimals: 0,
          enabled: true,
        },
      ],
      weight_barcode_version: "w1",
      card_manual_fallback: "manager_approval",
      marking_precheck: "warn",
      negative_stock_policy: "allow",
      discount_rules: [],
      subscription: { status: "active", current_period_end: null, grace_ends_at: null },
      branch: { id: STUB_DEVICE.branch_id, code: "01", name: "Chilonzor-3" },
      cash_register: { id: STUB_DEVICE.cash_register_id, name: "Kassa 1", kind: "web" },
      card_terminals: opts.cardTerminals ?? [],
      card_bin_rules: [],
    },
  };
}

export const FAKE_TERMINAL: Body = {
  id: TERMINAL_ID,
  name: "Sinov terminali",
  vendor: "fake",
  model: "fake",
  adapter: "fake",
  driver: "fake",
  cash_register_id: STUB_DEVICE.cash_register_id,
  agent_id: null,
  local_id: "fake-1",
  host: null,
  port: null,
  tid: "T0000001",
  mid: null,
  is_default: true,
  status: "active",
  capabilities: {},
  health_status: "online",
};

/** Raw IndexedDB put into an existing (app-created) database. */
async function idbPut(page: Page, db: string, store: string, value: Body): Promise<void> {
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

async function idbCount(page: Page, db: string, store: string): Promise<number> {
  return page.evaluate(
    ({ db, store }) =>
      new Promise<number>((resolve) => {
        void indexedDB.databases().then((list) => {
          if (!list.some((d) => d.name === db)) {
            resolve(-1);
            return;
          }
          count();
        });
        const count = () => {
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
        };
      }),
    { db, store },
  );
}

export async function setDeviceSetting(page: Page, key: string, value: unknown): Promise<void> {
  await idbPut(page, "erp-device", "device_settings", { key, value });
}

export interface SeedOptions {
  /** First-pull data handed out again right before the seeding reload (default: posPull()). */
  pull?: Body;
  /** Device setting `printer.transport` (default: system_print — the OS dialog is stubbed). */
  printer?: string | null;
  /** Skip the open shift (guard / no-shift tests). */
  withShift?: boolean;
}

/**
 * Registers the device, signs the cashier in and opens a local shift, then lands on /pos/sale.
 * Requires `installSyncStub(page, …)` first; pass the same pull data as `opts.pull` when it is not posPull().
 */
export async function seedReadyPos(page: Page, sync: SyncStub, opts: SeedOptions = {}): Promise<void> {
  await page.addInitScript(() => {
    // system_print opens the OS dialog — in e2e it "prints" at once (afterprint restores the app)
    window.print = () => {
      window.dispatchEvent(new Event("afterprint"));
    };
  });
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
  const printer = opts.printer === undefined ? "system_print" : opts.printer;
  if (printer) await setDeviceSetting(page, "printer.transport", printer);
  await page.evaluate(
    ({ id, perms }) =>
      sessionStorage.setItem(
        "erp.pos.cashier",
        JSON.stringify({
          userId: id,
          fullName: "Dilnoza Rahimova",
          roleCodes: ["cashier"],
          permissions: perms,
          verifiedAt: new Date().toISOString(),
          via: "local",
        }),
      ),
    { id: CASHIER_ID, perms: CASHIER_PERMISSIONS },
  );
  // The first page may already have started (and been cut off in) the snapshot pull, and the stub serves
  // its pull data once: leave the app, hand the data out again, then let one clean pull fill erp-pos.
  await page.goto("about:blank");
  sync.setPullData(opts.pull ?? posPull());
  await page.goto("/pos/sync");
  await expect.poll(() => idbCount(page, "erp-pos", "catalog"), { timeout: 15_000 }).toBeGreaterThan(0);
  if (opts.withShift !== false) {
    await idbPut(page, "erp-pos", "shift", {
      id: SHIFT_ID,
      cash_register_id: STUB_DEVICE.cash_register_id,
      shift_no: 214,
      opened_at: new Date(Date.now() - 3_600_000).toISOString(),
      opened_by: CASHIER_ID,
      status: "open",
    });
  }
  await page.goto("/pos/sale");
  await posSaleReady(page);
}

/** POS-02 is ready for keys and scans (the global POS keys and the scanner wedge are attached). */
export async function posSaleReady(page: Page): Promise<void> {
  await expect(page.getByTestId("barcode-field")).toBeVisible();
  await expect(page.locator("html[data-pos-keys=on][data-pos-scanner=on]")).toHaveCount(1);
}

/**
 * A USB HID scanner burst (06 §1.6): keydown events < 30 ms apart + Enter, dispatched inside the page so the
 * timing is the scanner's, not the test driver's. Resolves with `performance.now()` of the terminating Enter.
 */
export async function scan(page: Page, code: string): Promise<number> {
  return page.evaluate((text) => {
    // A real scanner's keys arrive 1–5 ms apart; a busy CI machine may pause this loop for > 30 ms, which a
    // wall clock would read as human typing. The wedge reads Date.now(), so the burst runs on a 1 ms/key clock.
    const realNow = Date.now.bind(Date);
    // start well after the last real keystroke, so a key pressed just before is never glued to the code
    let t = realNow() + 1_000;
    Date.now = () => (t += 1);
    const target = document.activeElement ?? document.body;
    let at = 0;
    try {
      for (const ch of text)
        target.dispatchEvent(new KeyboardEvent("keydown", { key: ch, bubbles: true, cancelable: true }));
      at = performance.now();
      target.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true }));
    } finally {
      Date.now = realNow;
    }
    return at;
  }, code);
}

/** `performance.now()` when the receipt shows `count` lines (MutationObserver, in page). */
export async function whenLines(page: Page, count: number): Promise<number> {
  return page.evaluate(
    (n) =>
      new Promise<number>((resolve) => {
        const check = () => document.querySelectorAll('[data-testid="receipt-line"]').length >= n;
        if (check()) {
          resolve(performance.now());
          return;
        }
        const mo = new MutationObserver(() => {
          if (check()) {
            mo.disconnect();
            resolve(performance.now());
          }
        });
        mo.observe(document.body, { childList: true, subtree: true });
      }),
    count,
  );
}
