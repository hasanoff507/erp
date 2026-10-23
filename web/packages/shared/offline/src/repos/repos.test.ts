import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { isOfflineError } from "../lib/errors.ts";
import { searchTokens } from "../lib/search.ts";
import { enqueueEvent } from "../outbox/enqueue.ts";
import { posDb } from "../runtime.ts";
import { CASHIER, DEVICE, SHIFT_ID, setupOffline, teardownOffline } from "../testing/setup.ts";
import type { BarcodeRow, PriceRow, ProductRow } from "../types.ts";
import { cardAttempts } from "./card-attempts.ts";
import { catalog, effectivePrice } from "./catalog.ts";

const BRANCH = DEVICE.branchId;

async function seedCatalog(count: number): Promise<void> {
  const products: ProductRow[] = [];
  const barcodes: BarcodeRow[] = [];
  const priceRows: PriceRow[] = [];
  for (let i = 0; i < count; i += 1) {
    const name = `Mahsulot ${i} ${i % 3 === 0 ? "sut" : i % 3 === 1 ? "non" : "choy"}`;
    products.push({
      id: `p${i}`,
      name,
      name_ru: null,
      category_id: `cat-${i % 20}`,
      unit_code: "pcs",
      tokens: searchTokens(name),
    });
    const code = `478${String(i).padStart(10, "0")}`;
    barcodes.push({ id: `p${i}:${code}`, product_id: `p${i}`, barcode: code, units_per_barcode: "1.000" });
    priceRows.push({
      id: `pr${i}`,
      product_id: `p${i}`,
      branch_id: null,
      branch_key: "*",
      price: "1000.0000",
      valid_from: "2026-01-01T00:00:00Z",
    });
  }
  const db = posDb();
  await db.catalog.bulkPut(products);
  await db.barcodes.bulkPut(barcodes);
  await db.prices.bulkPut(priceRows);
  await db.categories.bulkPut(
    Array.from({ length: 20 }, (_, i) => ({ id: `cat-${i}`, name: `Kategoriya ${i}`, sort_order: i })),
  );
}

beforeEach(async () => {
  await setupOffline();
});
afterEach(teardownOffline);

describe("effectivePrice (contracts/sync-pull.md device rule, 16 §5)", () => {
  const p = (id: string, branch: string | null, price: string, from: string): PriceRow => ({
    id,
    product_id: "x",
    branch_id: branch,
    branch_key: branch ?? "*",
    price,
    valid_from: from,
  });
  const now = Date.parse("2026-10-14T00:00:00Z");
  it("branch beats tenant-wide, latest valid_from wins, future and foreign branches are ignored", () => {
    const rows = [
      p("a", null, "100", "2026-09-01T00:00:00Z"),
      p("b", BRANCH, "90", "2026-01-01T00:00:00Z"),
      p("c", BRANCH, "95", "2026-05-01T00:00:00Z"),
      p("d", BRANCH, "99", "2026-12-01T00:00:00Z"),
      p("e", "other", "50", "2026-09-01T00:00:00Z"),
    ];
    expect(effectivePrice(rows, BRANCH, now)).toBe("95");
    expect(
      effectivePrice(
        rows.filter((r) => r.branch_id !== BRANCH),
        BRANCH,
        now,
      ),
    ).toBe("100");
    expect(effectivePrice([], BRANCH, now)).toBeNull();
  });
});

describe("catalog queries (24 §5.1)", () => {
  it("search: word prefixes over all words, category filter only without a query, exact barcode first", async () => {
    await seedCatalog(60);
    expect((await catalog.search("mahs sut", { limit: 100 })).length).toBe(20);
    expect((await catalog.search("", { categoryId: "cat-3" })).map((v) => v.product.id).sort()).toEqual([
      "p23",
      "p3",
      "p43",
    ]);
    const byCode = await catalog.search("4780000000042", { categoryId: "cat-3" });
    expect(byCode[0]?.product.id).toBe("p42");
    expect(byCode[0]?.price).toBe("1000.0000");
    expect((await catalog.categories()).map((c) => c.id)).toHaveLength(20);
    expect(await catalog.byBarcode("nope")).toBeNull();
  });

  it("QT-NFR-01 budget: barcode → product + price under 100 ms with 10 000 products (local IndexedDB)", async () => {
    await seedCatalog(10_000);
    await catalog.byBarcode("4780000000001"); // warm-up (opens indexes)
    const samples: number[] = [];
    for (const i of [17, 4242, 9999, 512, 7777]) {
      const t0 = performance.now();
      const hit = await catalog.byBarcode(`478${String(i).padStart(10, "0")}`);
      samples.push(performance.now() - t0);
      expect(hit?.product.id).toBe(`p${i}`);
    }
    expect(Math.max(...samples)).toBeLessThan(100);
    await catalog.warmUp(); // done on page mount / after a pull
    const t0 = performance.now();
    const found = await catalog.search("mahsulot 4242");
    expect(performance.now() - t0).toBeLessThan(100);
    expect(found[0]?.product.id).toBe("p4242");
  }, 60_000);

  it("QT-NFR-02 budget: finishing a sale (outbox write) takes well under 1 s", async () => {
    const lines = Array.from({ length: 50 }, (_, i) => ({
      product_id: `p${i}`,
      qty: "1.000",
      price: "1000.00",
      line_total: "1000",
    }));
    await enqueueEvent("sale.created", { id: "warm", lines }, { actorUserId: CASHIER });
    const t0 = performance.now();
    await enqueueEvent(
      "sale.created",
      { id: "s1", shift_id: SHIFT_ID, lines, payments: [{ method: "cash", amount: "50000.00" }] },
      {
        actorUserId: CASHIER,
        receiptSeq: { cashRegisterId: DEVICE.cashRegisterId ?? "", shiftId: SHIFT_ID },
      },
    );
    expect(performance.now() - t0).toBeLessThan(1000);
  });
});

describe("cardAttempts (16 §2.1, 15 §9.3 — PAN-free)", () => {
  const base = {
    attempt_id: "a1",
    card_terminal_id: "t1",
    kind: "purchase" as const,
    amount: "1000.00",
    client_event_id: null,
    status: "pending" as const,
    started_at: "2026-10-14T00:00:00Z",
  };

  it("refuses card data keys and malformed masks", async () => {
    await expect(cardAttempts.put({ ...base, pan: "8600123412341234" })).rejects.toSatisfy((e) =>
      isOfflineError(e, "CARD_DATA_FORBIDDEN"),
    );
    await expect(cardAttempts.put({ ...base, result: { card_mask: "8600123412341234" } })).rejects.toSatisfy(
      (e) => isOfflineError(e, "CARD_DATA_FORBIDDEN"),
    );
    await expect(cardAttempts.put({ ...base, result: { track2: "x" } })).rejects.toSatisfy((e) =>
      isOfflineError(e, "CARD_DATA_FORBIDDEN"),
    );
    await cardAttempts.put({ ...base, result: { card_mask: "8600****1234", rrn: "123456789012" } });
    expect(await cardAttempts.count()).toBe(1);
  });

  it("pending/unknown block removal and are listed as unresolved per terminal", async () => {
    await cardAttempts.put(base);
    await cardAttempts.put({ ...base, attempt_id: "a2", card_terminal_id: "t2", status: "declined" });
    expect((await cardAttempts.unresolved("t1")).map((a) => a.attempt_id)).toEqual(["a1"]);
    expect(await cardAttempts.unresolved("t2")).toEqual([]);
    await expect(cardAttempts.remove("a1")).rejects.toSatisfy((e) =>
      isOfflineError(e, "CARD_OUTCOME_UNKNOWN"),
    );
    await cardAttempts.update("a1", { status: "unknown" });
    await cardAttempts.update("a1", { status: "declined", resolved_by: "status_query" });
    await cardAttempts.remove("a1");
    await cardAttempts.remove("a2");
    expect(await cardAttempts.count()).toBe(0);
  });
});
