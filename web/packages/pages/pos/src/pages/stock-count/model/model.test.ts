/* eslint-disable @typescript-eslint/require-await -- the fakes implement async ports */
import { allSettled, fork } from "effector";
import { describe, expect, it, vi } from "vitest";

import type { CountOut } from "@shared/models";

import type { KeyValueStore, ScanResult } from "#/features/wh-scan/index.ts";

import {
  $count,
  $current,
  $error,
  $progress,
  $rows,
  $submitted,
  buildRows,
  configureStockCount,
  currentQtyChanged,
  currentSaved,
  filterRows,
  finishConfirmed,
  localCountsFromOutbox,
  pendingCountEvents,
  progressOf,
  scanned,
  stockCountOpened,
  type CountEventRow,
  type StockCountDeps,
} from "./index.ts";

const COUNT: CountOut = {
  id: "c-1", number: "INV-01-2026-000007", status: "counting", doc_date: "2026-10-17", branch_id: "b-1",
  warehouse_id: "w-1", started_at: "2026-10-17T05:00:00Z", responsible_user_id: null, comment: null,
  line_count: 2, counted_count: 0, uncounted_count: 2, created_by: "u-1", created_at: null, posted_at: null,
  cancelled_at: null, cancel_reason: null,
  lines: [
    { id: "l-1", line_no: 1, product_id: "p-cola", product_name: "Coca-Cola 1.5L", snapshot_qty: "10.000",
      expected: "10.000", counted: null, counted_at: null, diff: null, amount: null },
    { id: "l-2", line_no: 2, product_id: "p-milk", product_name: "Sut 1 l", snapshot_qty: "4.000",
      expected: "4.000", counted: "4.000", counted_at: "2026-10-17T05:10:00Z", diff: "0.000", amount: null },
  ],
}; // prettier-ignore

function memoryStore(init: Record<string, unknown> = {}): KeyValueStore {
  const data = new Map(Object.entries(init));
  return {
    get: async <T>(k: string) => data.get(k) as T | undefined,
    set: async (k, v) => void data.set(k, v),
    remove: async (k) => void data.delete(k),
  };
}

const cola: ScanResult = {
  kind: "product",
  item: { productId: "p-cola", name: "Coca-Cola 1.5L", nameRu: null, unitCode: "pcs", isMarked: false,
    isWeighed: false, qty: "1.000", code: "4780000123454", markingCode: null },
}; // prettier-ignore

function setup(over: Partial<StockCountDeps> = {}) {
  const outbox: CountEventRow[] = [];
  const enqueue = vi.fn(async (payload: Record<string, unknown>, _actor: string) => {
    outbox.push({ type: "stock_count.line_recorded", status: "pending", retryable: null,
      created_at: "2026-10-17T06:00:00Z", payload }); // prettier-ignore
    return { clientEventId: `e-${outbox.length}` };
  });
  const deps: Partial<StockCountDeps> = {
    online: () => true,
    branchId: () => "b-1",
    actorId: () => "u-cashier",
    warehouses: async () => [{ id: "w-1", branchId: "b-1", name: "Asosiy ombor" }],
    listCounts: async () => [{ ...COUNT, lines: [] }],
    getCount: async () => COUNT,
    startCount: async () => COUNT,
    submit: vi.fn(async () => ({ ...COUNT, status: "review" as const })),
    outboxRows: async () => outbox,
    enqueue,
    flush: vi.fn(async () => true),
    resolve: async (code) => (code === "4780000123454" ? cola : { kind: "unknown", code }),
    cache: memoryStore(),
    now: () => new Date("2026-10-17T06:00:00Z"),
    ...over,
  };
  return { deps, outbox, enqueue };
}

describe("POS-10 pure logic", () => {
  it("latest recorded_at wins; non-retryable rejected events are ignored", () => {
    const rows: CountEventRow[] = [
      { type: "stock_count.line_recorded", status: "accepted", retryable: null, created_at: "a",
        payload: { count_id: "c-1", product_id: "p-cola", counted: "3.000", recorded_at: "2026-10-17T06:00:00Z" } },
      { type: "stock_count.line_recorded", status: "pending", retryable: null, created_at: "b",
        payload: { count_id: "c-1", product_id: "p-cola", counted: "5.000", recorded_at: "2026-10-17T06:01:00Z" } },
      { type: "stock_count.line_recorded", status: "rejected", retryable: false, created_at: "c",
        payload: { count_id: "c-1", product_id: "p-cola", counted: "99.000", recorded_at: "2026-10-17T06:02:00Z" } },
      { type: "stock_count.line_recorded", status: "pending", retryable: null, created_at: "d",
        payload: { count_id: "c-2", product_id: "p-cola", counted: "1.000", recorded_at: "2026-10-17T06:03:00Z" } },
    ]; // prettier-ignore
    const local = localCountsFromOutbox(rows, "c-1");
    expect([...local.values()]).toEqual([
      {
        productId: "p-cola",
        barcode: null,
        counted: "5.000",
        recordedAt: "2026-10-17T06:01:00Z",
        sync: "pending",
      },
    ]);
    expect(pendingCountEvents(rows, "c-1")).toBe(1);
    const table = buildRows(COUNT, local);
    expect(table.map((r) => [r.productId, r.counted, r.diff])).toEqual([
      ["p-cola", "5.000", "-5.000"],
      ["p-milk", "4.000", "0.000"],
    ]);
    expect(progressOf(table)).toMatchObject({ counted: 2, shortage: 1, surplus: 0, left: 0, match: 1 });
    expect(filterRows(table, "diff").map((r) => r.productId)).toEqual(["p-cola"]);
    expect(filterRows(table, "match").map((r) => r.productId)).toEqual(["p-milk"]);
    expect(filterRows(buildRows(COUNT, new Map()), "uncounted").map((r) => r.productId)).toEqual(["p-cola"]);
  });
});

describe("POS-10 model (QT-M05-05: each scan → stock_count.line_recorded)", () => {
  it("opens the only count, scans write absolute counts, −/+ then Enter saves", async () => {
    const { deps, enqueue } = setup();
    const scope = fork();
    await allSettled(configureStockCount, { scope, params: deps });
    await allSettled(stockCountOpened, { scope });
    expect(scope.getState($count)?.id).toBe("c-1");

    await allSettled(scanned, { scope, params: "4780000123454" });
    await allSettled(scanned, { scope, params: "4780000123454" });
    expect(enqueue).toHaveBeenCalledTimes(2);
    expect(enqueue.mock.calls[1]?.[0]).toEqual({
      count_id: "c-1",
      product_id: "p-cola",
      barcode: "4780000123454",
      counted: "2.000",
      recorded_at: "2026-10-17T06:00:00.000Z",
    });
    expect(enqueue.mock.calls[1]?.[1]).toBe("u-cashier");
    expect(scope.getState($current)).toMatchObject({ productId: "p-cola", counted: "2.000", dirty: false });

    await allSettled(currentQtyChanged, { scope, params: "7" });
    expect(scope.getState($current)?.dirty).toBe(true);
    await allSettled(currentSaved, { scope });
    expect(enqueue.mock.calls[2]?.[0]).toMatchObject({ counted: "7.000" });
    expect(scope.getState($current)).toMatchObject({ counted: "7.000", dirty: false });
    expect(scope.getState($rows)[0]).toMatchObject({ counted: "7.000", diff: "-3.000", sync: "pending" });
    expect(scope.getState($progress).counted).toBe(2);
  });

  it("unknown barcode → banner + barcode-only event (server resolves, 19 §14)", async () => {
    const { deps, enqueue } = setup();
    const scope = fork();
    await allSettled(configureStockCount, { scope, params: deps });
    await allSettled(stockCountOpened, { scope });
    await allSettled(scanned, { scope, params: "999000111" });
    expect(scope.getState($error)).toEqual({ kind: "unknown_barcode", code: "999000111" });
    expect(enqueue.mock.calls[0]?.[0]).toEqual({
      count_id: "c-1",
      barcode: "999000111",
      counted: "1.000",
      recorded_at: "2026-10-17T06:00:00.000Z",
    });
  });

  it("offline: the count comes from the device cache; finishing waits for the events to sync", async () => {
    const cache = memoryStore({
      "pos.wh.counts": [{ ...COUNT, lines: [] }],
      "pos.wh.count.c-1": COUNT,
      "pos.wh.warehouses": [{ id: "w-1", branchId: "b-1", name: "Asosiy ombor" }],
    });
    const flush = vi.fn(async () => false);
    const submit = vi.fn(async () => COUNT);
    const { deps } = setup({ online: () => false, cache, flush, submit, getCount: async () => Promise.reject(new Error("net")),
      warehouses: async () => [{ id: "w-1", branchId: "b-1", name: "Asosiy ombor" }] }); // prettier-ignore
    const scope = fork();
    await allSettled(configureStockCount, { scope, params: deps });
    await allSettled(stockCountOpened, { scope });
    expect(scope.getState($count)?.lines).toHaveLength(2);
    await allSettled(scanned, { scope, params: "4780000123454" });
    await allSettled(finishConfirmed, { scope });
    expect(flush).toHaveBeenCalledWith("c-1");
    expect(submit).not.toHaveBeenCalled();
    expect(scope.getState($error)).toEqual({ kind: "not_synced" });

    flush.mockResolvedValueOnce(true);
    await allSettled(finishConfirmed, { scope });
    expect(submit).toHaveBeenCalledWith("c-1");
    expect(scope.getState($submitted)?.id).toBe("c-1");
    expect(scope.getState($count)).toBeNull();
  });

  it("scanner burst: the second scan does not wait for the first enqueue (counts 1 then 2)", async () => {
    const { deps, enqueue } = setup();
    const slow = vi.fn(async (payload: Record<string, unknown>, actor: string) => {
      await new Promise((r) => setTimeout(r, 30));
      return enqueue(payload, actor);
    });
    const scope = fork();
    await allSettled(configureStockCount, { scope, params: { ...deps, enqueue: slow } });
    await allSettled(stockCountOpened, { scope });
    await Promise.all([
      allSettled(scanned, { scope, params: "4780000123454" }),
      allSettled(scanned, { scope, params: "4780000123454" }),
    ]);
    expect(slow.mock.calls.map((c) => c[0].counted)).toEqual(["1.000", "2.000"]);
  });

  it("no PIN-verified cashier → nothing is written", async () => {
    const { deps, enqueue } = setup({ actorId: () => null });
    const scope = fork();
    await allSettled(configureStockCount, { scope, params: deps });
    await allSettled(stockCountOpened, { scope });
    await allSettled(scanned, { scope, params: "4780000123454" });
    expect(enqueue).not.toHaveBeenCalled();
    expect(scope.getState($error)).toEqual({ kind: "no_actor" });
  });
});
