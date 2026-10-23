/* eslint-disable @typescript-eslint/require-await -- the fakes implement async ports */
import { allSettled, fork } from "effector";
import { describe, expect, it, vi } from "vitest";

import type { TransferOut } from "@shared/models";

import type { ScanResult } from "#/features/wh-scan/index.ts";

import {
  $error,
  $form,
  $formErrors,
  $history,
  $incoming,
  $notice,
  addScanned,
  configureTransfers,
  destinationChanged,
  incomingSelected,
  isSendReady,
  receiveConfirmed,
  receiveLineError,
  receiveQtyChanged,
  scanned,
  sendConfirmed,
  transfersOpened,
  transportModeChanged,
  vehiclePlateChanged,
  type TransferEventRow,
  type TransfersDeps,
} from "./index.ts";

const WAREHOUSES = [
  { id: "w-1", branchId: "b-1", name: "Chilonzor ombori" },
  { id: "w-2", branchId: "b-2", name: "Yunusobod ombori" },
];
const INCOMING: TransferOut = {
  id: "t-9", number: "KO-02-2026-000003", status: "sent", doc_date: "2026-10-16", branch_id: "b-2",
  from_branch_id: "b-2", to_branch_id: "b-1", from_warehouse_id: "w-2", to_warehouse_id: "w-1",
  transport_mode: "on_foot_or_public", vehicle_plate: null, driver_name: null, ettn_ref: null, ettn: null,
  is_overdue: false, comment: null, created_by: "u-2", created_at: null, posted_at: null, sent_at: null,
  sent_by: null, received_at: null, received_by: null, cancelled_at: null, cancel_reason: null, warnings: [],
  lines: [
    { id: "tl-1", line_no: 1, product_id: "p-cola", product_name: "Coca-Cola", qty_sent: "10.000",
      qty_received: null, unit_cost: "9000.0000", lot_allocations: [] },
  ],
}; // prettier-ignore

const cola: ScanResult = {
  kind: "product",
  item: { productId: "p-cola", name: "Coca-Cola 1.5L", nameRu: null, unitCode: "pcs", isMarked: false,
    isWeighed: false, qty: "1.000", code: "4780000123454", markingCode: null },
}; // prettier-ignore

function setup(over: Partial<TransfersDeps> = {}) {
  const rows: TransferEventRow[] = [];
  let n = 0;
  const enqueue = vi.fn(async (type: string, payload: Record<string, unknown>, _actor: string) => {
    n += 1;
    rows.push({ client_event_id: `e-${n}`, type, status: "pending", retryable: null,
      created_at: `2026-10-17T06:0${n}:00Z`, payload, server: null, warnings: [], error_code: null, message: null }); // prettier-ignore
    return { clientEventId: `e-${n}` };
  });
  let id = 0;
  let temp = 0;
  const deps: Partial<TransfersDeps> = {
    online: () => false,
    device: () => ({ deviceId: "0190a000-0000-7000-8000-00000000d001", branchId: "b-1" }),
    actorId: () => "u-store",
    warehouses: async () => WAREHOUSES,
    incoming: async () => [INCOMING],
    balance: async () => "1.000",
    create: vi.fn(),
    outboxRows: async () => rows,
    enqueue,
    awaitResult: async () => null,
    resolve: async (code) => (code === "4780000123454" ? cola : { kind: "unknown", code }),
    newId: () => `id-${(id += 1)}`,
    tempNumber: async (deviceId) => `${deviceId}-${(temp += 1)}`,
    cache: undefined,
    now: () => new Date("2026-10-17T06:30:15Z"),
    ...over,
  };
  return { deps, rows, enqueue };
}

describe("POS-09 pure logic", () => {
  it("scan increments, marking codes are counted once", () => {
    const mk = (markingCode: string | null) => ({ ...cola.item, markingCode });
    let lines = addScanned([], mk("01046000000000152111"));
    lines = addScanned(lines, mk("01046000000000152111"));
    lines = addScanned(lines, mk("01046000000000152122"));
    expect(lines).toMatchObject([
      { qty: "2.000", markingCodes: ["01046000000000152111", "01046000000000152122"] },
    ]);
    expect(receiveLineError("10.000", "11")).toBe("range");
    expect(receiveLineError("10.000", "")).toBe("required");
    expect(receiveLineError("10.000", "0")).toBeNull();
    expect(isSendReady({ status: "posted", transport_mode: "vehicle", ettn: null })).toBe(false);
    expect(isSendReady({ status: "posted", transport_mode: "on_foot_or_public", ettn: null })).toBe(true);
  });
});

describe("POS-09 model — QT-M06-04 offline transfer", () => {
  it("offline «Yuborish» writes one transfer.sent event with the 19 §13 payload", async () => {
    const { deps, enqueue } = setup();
    const scope = fork();
    await allSettled(configureTransfers, { scope, params: deps });
    await allSettled(transfersOpened, { scope });
    expect(scope.getState($form).fromWarehouseId).toBe("w-1");

    await allSettled(scanned, { scope, params: "4780000123454" });
    await allSettled(scanned, { scope, params: "4780000123454" });
    expect(scope.getState($form).lines).toMatchObject([
      { productId: "p-cola", qty: "2.000", available: "1.000" },
    ]);
    expect(scope.getState($formErrors)).toEqual(["to_required", "plate_required"]);

    await allSettled(sendConfirmed, { scope }); // invalid → nothing written
    expect(enqueue).not.toHaveBeenCalled();

    await allSettled(destinationChanged, { scope, params: "w-2" });
    await allSettled(vehiclePlateChanged, { scope, params: " 01A123BC " });
    await allSettled(sendConfirmed, { scope });
    expect(enqueue).toHaveBeenCalledTimes(1);
    expect(enqueue.mock.calls[0]?.[0]).toBe("transfer.sent");
    expect(enqueue.mock.calls[0]?.[1]).toEqual({
      id: "id-1",
      temp_number: "0190a000-0000-7000-8000-00000000d001-1",
      doc_date: "2026-10-17",
      from_warehouse_id: "w-1",
      to_warehouse_id: "w-2",
      transport_mode: "vehicle",
      vehicle_plate: "01A123BC",
      lines: [{ line_id: "id-2", product_id: "p-cola", qty_sent: "2.000" }],
    });
    expect(enqueue.mock.calls[0]?.[2]).toBe("u-store");
    expect(scope.getState($form).lines).toEqual([]);
    expect(scope.getState($notice)).toMatchObject({
      kind: "sent_local",
      number: "0190a000-0000-7000-8000-00000000d001-1",
    });
    expect(scope.getState($history)).toMatchObject([{ kind: "sent", sync: "pending", lines: 1 }]);
  });

  it("on foot: no plate needed; online answer with ETTN_REQUIRED warning is shown", async () => {
    const { deps, enqueue } = setup({
      online: () => true,
      awaitResult: async (id) => ({ client_event_id: id, status: "accepted", server: { id: "t-1", number: "KO-01-2026-000010", status: "posted" },
        error_code: null, message: null, retryable: false, warnings: ["ETTN_REQUIRED"] }) as never, // prettier-ignore
    });
    const scope = fork();
    await allSettled(configureTransfers, { scope, params: deps });
    await allSettled(transfersOpened, { scope });
    await allSettled(scanned, { scope, params: "4780000123454" });
    await allSettled(destinationChanged, { scope, params: "w-2" });
    await allSettled(transportModeChanged, { scope, params: "on_foot_or_public" });
    expect(scope.getState($formErrors)).toEqual([]);
    await allSettled(sendConfirmed, { scope });
    expect(enqueue.mock.calls[0]?.[1]).not.toHaveProperty("vehicle_plate");
    expect(scope.getState($notice)).toEqual({
      kind: "sent_local",
      number: "KO-01-2026-000010",
      status: "posted",
      warnings: ["ETTN_REQUIRED"],
    });
  });

  it("receive (offline, cached list): transfer.received with per-line qty; the transfer leaves the list", async () => {
    const store = new Map<string, unknown>([["pos.wh.incoming_transfers", [INCOMING]]]);
    const cache = {
      get: async <T>(k: string) => store.get(k) as T | undefined,
      set: async (k: string, v: unknown) => void store.set(k, v),
      remove: async (k: string) => void store.delete(k),
    };
    const { deps, enqueue } = setup({ cache });
    const scope = fork();
    await allSettled(configureTransfers, { scope, params: deps });
    await allSettled(transfersOpened, { scope });
    expect(scope.getState($incoming).map((t) => t.id)).toEqual(["t-9"]);
    await allSettled(incomingSelected, { scope, params: "t-9" });
    await allSettled(receiveQtyChanged, { scope, params: { lineId: "tl-1", qty: "9.5" } });
    await allSettled(receiveConfirmed, { scope });
    expect(enqueue).toHaveBeenCalledWith(
      "transfer.received",
      { transfer_id: "t-9", lines: [{ transfer_line_id: "tl-1", qty_received: "9.500" }] },
      "u-store",
    );
    expect(scope.getState($incoming)).toEqual([]);
  });

  it("SYNC-13: two transfers in the same second get distinct temp numbers (device counter)", async () => {
    const { deps, enqueue } = setup();
    const scope = fork();
    await allSettled(configureTransfers, { scope, params: deps });
    await allSettled(transfersOpened, { scope });
    for (let i = 0; i < 2; i += 1) {
      await allSettled(scanned, { scope, params: "4780000123454" });
      await allSettled(destinationChanged, { scope, params: "w-2" });
      await allSettled(transportModeChanged, { scope, params: "on_foot_or_public" });
      await allSettled(sendConfirmed, { scope });
    }
    const numbers = enqueue.mock.calls.map((c) => c[1].temp_number);
    expect(numbers).toHaveLength(2);
    expect(new Set(numbers).size).toBe(2);
  });

  it("no cashier → refused, nothing written", async () => {
    const { deps, enqueue } = setup({ actorId: () => null });
    const scope = fork();
    await allSettled(configureTransfers, { scope, params: deps });
    await allSettled(transfersOpened, { scope });
    await allSettled(scanned, { scope, params: "4780000123454" });
    await allSettled(destinationChanged, { scope, params: "w-2" });
    await allSettled(transportModeChanged, { scope, params: "on_foot_or_public" });
    await allSettled(sendConfirmed, { scope });
    expect(enqueue).not.toHaveBeenCalled();
    expect(scope.getState($error)).toEqual({ kind: "no_actor" });
  });
});
