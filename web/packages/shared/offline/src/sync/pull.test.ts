import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { deviceIdentity } from "../device-settings.ts";
import { clockSkewMs } from "../lib/clock.ts";
import { computeFiscalLadder } from "../fiscal/ladder.ts";
import { enqueueEvent } from "../outbox/enqueue.ts";
import { outbox } from "../outbox/queries.ts";
import { catalog, prices } from "../repos/catalog.ts";
import { customers, fiscal, limits, settings, shift, staff, stock } from "../repos/reference.ts";
import { posDb } from "../runtime.ts";
import { CASHIER, DEVICE, SHIFT_ID, setupOffline, teardownOffline, type TestEnv } from "../testing/setup.ts";
import type { SyncPullResponse } from "../types.ts";
import { pullNow } from "./pull.ts";

const BRANCH = DEVICE.branchId;

const snapshotPage: SyncPullResponse = {
  cursor: "cur-1",
  has_more: true,
  server_time: "2026-10-14T05:00:00.000Z",
  device: { id: DEVICE.deviceId, branch_id: BRANCH, cash_register_id: DEVICE.cashRegisterId },
  catalog: [
    { entity: "category", id: "cat-1", name: "Ichimliklar", deleted: false },
    { entity: "category", id: "cat-2", name: "Bo'sh", deleted: false },
    { entity: "unit", id: "pcs", code: "pcs", is_fractional: false, deleted: false },
    {
      entity: "product",
      id: "p1",
      name: "Coca-Cola 1L",
      name_ru: "Кока-Кола 1л",
      category_id: "cat-1",
      unit_code: "pcs",
      is_marked: false,
      archived_at: null,
      deleted: false,
    },
  ],
  barcodes: [
    {
      id: "p1",
      product_id: "p1",
      barcodes: [{ barcode: "4780000123456", kind: "ean", units_per_barcode: "1.000" }],
      deleted: false,
    },
  ],
  prices: [
    {
      id: "p1",
      product_id: "p1",
      prices: [
        { price_id: "pr-all", branch_id: null, price: "9000.0000", valid_from: "2026-01-01T00:00:00Z" },
        { price_id: "pr-br", branch_id: BRANCH, price: "8500.0000", valid_from: "2026-02-01T00:00:00Z" },
        { price_id: "pr-fut", branch_id: BRANCH, price: "9900.0000", valid_from: "2027-01-01T00:00:00Z" },
      ],
      deleted: false,
    },
  ],
  customers: [
    {
      id: "c1",
      name: "Aliyev Vali",
      phone: "+998901234567",
      receivable_balance: "350000.00",
      credit_limit: "500000.00",
      open_debt_docs: [],
      deleted: false,
    },
  ],
  stock: [{ id: "w1:p1", warehouse_id: "w1", product_id: "p1", qty: "12.000", deleted: false }],
  permissions: {
    digest: "d1",
    staff: [
      {
        user_id: CASHIER,
        full_name: "Kassir Bir",
        role_codes: ["cashier"],
        branch_ids: [],
        active: true,
        must_change_pin: false,
        pin_local_hash:
          "pbkdf2_sha256$1000$AAECAwQFBgcICQoLDA0ODw==$IkDqKiJ1SjxGEDVu+OTXrPJa8qw9LRGGbel6i3gSxSw=",
        permissions: [{ code: "sales.create", limit_value: null }],
      },
      {
        user_id: "blocked-user",
        full_name: "Blocked",
        role_codes: [],
        branch_ids: [],
        active: false,
        must_change_pin: false,
        pin_local_hash: "pbkdf2_sha256$1000$AAECAwQFBgcICQoLDA0ODw==$x",
        permissions: [],
      },
    ],
  },
  limits: { digest: "l1", users: [{ user_id: CASHIER, limits: { "discount.give": "5.0000" } }] },
  shift: { digest: "s1", cash_register_id: DEVICE.cashRegisterId, open_shift: null, last_shift_no: 12 },
  settings: {
    digest: "st1",
    card_manual_fallback: "forbid",
    weight_barcode_templates: [
      { prefixes: ["22"], item_code_len: 5, value_len: 5, value_kind: "WEIGHT", decimals: 3, enabled: true },
    ],
    weight_barcode_version: "abc",
    marking_precheck: "warn",
    discount_rules: [],
    subscription: { status: "active" },
    card_terminals: [
      { id: "t1", cash_register_id: DEVICE.cashRegisterId, adapter: "fake", is_default: true },
    ],
  },
  marking_codes: [{ id: "m1", code: "CODE-1", product_id: "p1", status: "sold", deleted: false }],
  fiscal: [
    {
      entity: "cash_register",
      id: DEVICE.cashRegisterId,
      fm_state: "ok",
      last_unacked_receipt_at: null,
      fm_receipts_pending: 0,
      deleted: false,
    },
  ],
};

let env: TestEnv;
beforeEach(async () => {
  env = await setupOffline();
});
afterEach(teardownOffline);

describe("pull (16 §1, §3.2, contracts/sync-pull.md)", () => {
  it("snapshot: scope=all with an empty cursor, pages until has_more=false, fills every repository", async () => {
    env.server.pullPages = [snapshotPage, { cursor: "cur-2", has_more: false, catalog: [] }];
    const outcome = await pullNow();
    expect(outcome.kind).toBe("done");
    expect(env.server.pullRequests).toEqual([
      { scope: "all", cursor: "", page_size: 500 },
      { scope: "all", cursor: "cur-1", page_size: 500 },
    ]);
    expect((await posDb().meta.get("pull.cursor"))?.value).toBe("cur-2");

    const hit = await catalog.byBarcode("4780000123456");
    expect(hit?.product.name).toBe("Coca-Cola 1L");
    expect(hit?.price).toBe("8500.0000"); // branch price wins, future price ignored
    expect(hit?.unitsPerBarcode).toBe("1.000");
    expect(await prices.current("p1")).toBe("8500.0000");
    expect((await catalog.search("coca")).map((v) => v.product.id)).toEqual(["p1"]);
    expect((await catalog.search("кока")).map((v) => v.product.id)).toEqual(["p1"]);
    expect((await catalog.categories()).map((c) => c.id)).toEqual(["cat-1"]); // only with products
    expect((await catalog.unit("pcs"))?.is_fractional).toBe(false);
    expect((await catalog.units()).map((u) => u.code)).toEqual(["pcs"]);
    expect((await customers.search("vali")).map((c) => c.id)).toEqual(["c1"]);
    expect((await customers.search("901234567")).map((c) => c.id)).toEqual(["c1"]);
    expect((await stock.forProduct("p1"))[0]?.qty).toBe("12.000");
    expect(await staff.hasPermission(CASHIER, "sales.create")).toBe(true);
    expect((await staff.get("blocked-user"))?.pin_local_hash).toBeNull(); // inactive → verifier dropped
    expect(await limits.value(CASHIER, "discount.give")).toBe("5.0000");
    expect((await shift.server())?.last_shift_no).toBe(12);
    const s = await settings.get();
    expect(s.cardManualFallback).toBe("forbid");
    expect(s.cardTerminals.map((t) => t.id)).toEqual(["t1"]);
    expect(s.weightBarcodeTemplates[0]?.prefixes).toEqual(["22"]);
    expect(s.subscriptionStatus).toBe("active");
    expect((await fiscal.register(DEVICE.cashRegisterId ?? ""))?.fm_state).toBe("ok");
  });

  it("deltas: deleted rows go, barcodes/prices replace the product's set, null snapshots keep the table", async () => {
    env.server.pullPages = [{ ...snapshotPage, has_more: false }];
    await pullNow();
    env.server.pullPages = [
      {
        cursor: "cur-3",
        has_more: false,
        catalog: [
          {
            entity: "product",
            id: "p1",
            name: "Coca-Cola 1L",
            category_id: "cat-1",
            unit_code: "pcs",
            deleted: true,
          },
        ],
        barcodes: [
          {
            id: "p1",
            product_id: "p1",
            barcodes: [{ barcode: "999", units_per_barcode: "6.000" }],
            deleted: false,
          },
        ],
        prices: [{ id: "p1", product_id: "p1", prices: [], deleted: false }],
        customers: [{ id: "c1", deleted: true }],
        permissions: null,
        settings: null,
      },
    ];
    await pullNow();
    expect(env.server.pullRequests.at(-1)?.cursor).toBe("cur-1");
    expect(await catalog.get("p1")).toBeUndefined();
    expect(await catalog.byBarcode("4780000123456")).toBeNull();
    expect((await posDb().barcodes.toArray()).map((b) => b.barcode)).toEqual(["999"]);
    expect(await prices.current("p1")).toBeNull();
    expect(await customers.get("c1")).toBeUndefined();
    expect((await staff.list()).length).toBe(2); // null snapshot = unchanged
    expect((await settings.get()).cardManualFallback).toBe("forbid");
  });

  it("a rejected cursor (422 field cursor) re-snapshots from scratch once", async () => {
    await posDb().meta.put({ key: "pull.cursor", value: "garbage" });
    await posDb().catalog.put({
      id: "stale",
      name: "Stale",
      name_ru: null,
      category_id: null,
      unit_code: "pcs",
      tokens: ["stale"],
    });
    env.server.pullFailures = [
      {
        kind: "http",
        status: 422,
        code: "VALIDATION_ERROR",
        details: [{ field: "cursor", messageKey: "validation.invalid" }],
      },
    ];
    env.server.pullPages = [{ ...snapshotPage, has_more: false }];
    expect((await pullNow()).kind).toBe("done");
    expect(env.server.pullRequests.map((r) => r.cursor)).toEqual(["garbage", ""]);
    expect(await catalog.get("stale")).toBeUndefined();
  });

  it("maps fiscal receipt acks onto local outbox events and refreshes the device identity", async () => {
    const r = await enqueueEvent(
      "sale.created",
      { id: "s1", shift_id: SHIFT_ID },
      {
        actorUserId: CASHIER,
        receiptSeq: { cashRegisterId: DEVICE.cashRegisterId ?? "", shiftId: SHIFT_ID },
      },
    );
    env.server.pullPages = [
      {
        cursor: "c",
        has_more: false,
        device: { id: DEVICE.deviceId, branch_id: "new-branch", cash_register_id: DEVICE.cashRegisterId },
        fiscal: [
          {
            entity: "receipt",
            id: "fr1",
            client_event_id: r.clientEventId,
            cash_register_id: DEVICE.cashRegisterId,
            status: "fiscalized",
            ofd_acked_at: "2026-10-14T06:00:00Z",
            deleted: false,
          },
        ],
      },
    ];
    await pullNow();
    expect(await outbox.get(r.clientEventId)).toMatchObject({
      ofd_acked_at: "2026-10-14T06:00:00Z",
      fiscal_unacked: 0,
    });
    expect((await computeFiscalLadder()).oldestUnackedAt).toBeNull();
    expect((await deviceIdentity.get())?.branchId).toBe("new-branch");
  });

  it("401 → probe → retry; 403 DEVICE_REVOKED stops; server_time feeds the trusted clock", async () => {
    env.server.pullFailures = [{ kind: "http", status: 401, code: "UNAUTHORIZED" }];
    env.server.pullPages = [{ cursor: "c", has_more: false, server_time: "2026-10-20T00:00:00.000Z" }];
    expect((await pullNow()).kind).toBe("done");
    expect(env.server.refreshCalls).toBe(1);
    expect((await posDb().meta.get("clock.max_seen_time"))?.value).toBe(
      Date.parse("2026-10-20T00:00:00.000Z"),
    );
    expect(clockSkewMs()).toBe(env.clock.now - Date.parse("2026-10-20T00:00:00.000Z")); // 16 §8 input
    env.server.pullFailures = [{ kind: "http", status: 403, code: "DEVICE_REVOKED" }];
    expect(await pullNow()).toEqual({ kind: "stopped", code: "DEVICE_REVOKED" });
  });
});
