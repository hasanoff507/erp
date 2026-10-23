/**
 * POS-10 — Inventarizatsiya (07 POS-10; 19 §14; QT-M05-05). Counting is fully offline: every scan / saved
 * line is a `stock_count.line_recorded` outbox event (absolute count, `recorded_at`); starting a count and
 * «Sanashni yakunlash» (`submit-for-review`) are online REST calls. The count document and the count list are
 * cached on the device (erp-device) so a count started online can be continued without internet.
 */
import { attach, combine, createEffect, createEvent, createStore, sample } from "effector";

import { api, toApiError } from "@shared/api";
import type { CountOut } from "@shared/models";
import { awaitEventResult, enqueueEvent, outbox, syncNow } from "@shared/offline";
import { $isOnline } from "@shared/state/network";

import { $posDevice, posActorId } from "#/entities/pos-session/index.ts";
import {
  WH_CACHE_KEYS,
  addQty,
  loadWarehouses,
  qty3,
  readCache,
  resolveScan,
  writeCache,
  type KeyValueStore,
  type ScanResult,
  type WarehouseRef,
} from "#/features/wh-scan/index.ts";
import { tashkentDate } from "#/shared/lib/dates.ts";

import {
  LINE_RECORDED,
  buildRows,
  filterRows,
  localCountsFromOutbox,
  localFor,
  pendingCountEvents,
  progressOf,
  upsertLocal,
  type CountEventRow,
  type CountFilter,
  type LocalCount,
} from "./lib.ts";

export * from "./lib.ts";

export interface StockCountDeps {
  online(): boolean;
  branchId(): string | null;
  actorId(): string | null;
  warehouses(online: boolean): Promise<WarehouseRef[]>;
  listCounts(warehouseId: string): Promise<CountOut[]>;
  getCount(id: string): Promise<CountOut>;
  startCount(warehouseId: string, docDate: string): Promise<CountOut>;
  submit(id: string): Promise<CountOut>;
  outboxRows(): Promise<CountEventRow[]>;
  enqueue(payload: Record<string, unknown>, actorUserId: string): Promise<{ clientEventId: string }>;
  /** Push now and wait until no event of this count is pending (false = still pending). */
  flush(countId: string): Promise<boolean>;
  resolve(code: string): Promise<ScanResult>;
  cache: KeyValueStore | undefined;
  now(): Date;
}

function defaultDeps(): StockCountDeps {
  return {
    online: () => $isOnline.getState(),
    branchId: () => $posDevice.getState()?.branchId ?? null,
    actorId: posActorId,
    warehouses: (online) => loadWarehouses(online),
    listCounts: async (warehouseId) =>
      (
        await api.stockCounts.listStockCounts({ status: "counting", warehouse_id: warehouseId, limit: 50 })
      ).items.map((c) => ({ ...c, lines: [] })),
    getCount: (id) => api.stockCounts.getStockCount(id),
    startCount: (warehouseId, docDate) =>
      api.stockCounts.createStockCount({ warehouse_id: warehouseId, doc_date: docDate }),
    submit: (id) => api.stockCounts.submitStockCount(id, {}),
    outboxRows: () => outbox.list({ status: ["pending", "accepted", "duplicate", "rejected"] }),
    enqueue: async (payload, actorUserId) => enqueueEvent(LINE_RECORDED, payload, { actorUserId }),
    flush: async (countId) => {
      await syncNow({ push: true, pull: false }).catch(() => undefined);
      const rows = await outbox.list({ status: ["pending", "rejected"] });
      const ids = rows
        .filter((r) => r.type === LINE_RECORDED && r.payload.count_id === countId)
        .map((r) => r.client_event_id);
      for (const id of ids) {
        const res = await awaitEventResult(id, { timeoutMs: 15_000 });
        if (!res || res.status === "rejected") return false;
      }
      return true;
    },
    resolve: (code) => resolveScan(code),
    cache: undefined,
    now: () => new Date(),
  };
}

const $deps = createStore<StockCountDeps | null>(null, { serialize: "ignore", skipVoid: false });
export const configureStockCount = createEvent<Partial<StockCountDeps>>();
$deps.on(configureStockCount, (prev, d) => ({ ...(prev ?? defaultDeps()), ...d }));
const deps = (d: StockCountDeps | null): StockCountDeps => d ?? defaultDeps();

export type CountError =
  | { kind: "unknown_barcode"; code: string }
  | { kind: "check_digit" | "no_price"; code: string }
  | { kind: "no_actor" }
  | { kind: "api"; code: string; params?: Record<string, unknown> }
  | { kind: "not_synced" };

export interface CurrentItem {
  productId: string;
  name: string;
  code: string | null;
  isMarked: boolean;
  expected: string;
  counted: string;
  dirty: boolean;
}

// ---- events ---------------------------------------------------------------------------------------
export const stockCountOpened = createEvent();
export const countSelected = createEvent<string>();
export const countClosed = createEvent();
export const startRequested = createEvent();
export const scanned = createEvent<string>();
export const productPicked = createEvent<{ productId: string; name: string; isMarked?: boolean }>();
export const currentQtyChanged = createEvent<string>();
export const currentSaved = createEvent();
export const finishConfirmed = createEvent();
export const filterChanged = createEvent<CountFilter>();
export const errorDismissed = createEvent();

const apiError = (e: unknown): CountError => {
  const err = toApiError(e);
  return { kind: "api", code: err.code, params: { ...err.params } };
};

// ---- effects --------------------------------------------------------------------------------------
export const loadFx = attach({
  source: $deps,
  effect: createEffect(async (d: StockCountDeps | null) => {
    const x = deps(d);
    const online = x.online();
    const branchId = x.branchId();
    const warehouses = await x.warehouses(online);
    const warehouse = warehouses.find((w) => w.branchId === branchId) ?? null;
    let counts: CountOut[] = (await readCache<CountOut[]>(WH_CACHE_KEYS.counts, x.cache)) ?? [];
    if (online && warehouse) {
      counts = await x.listCounts(warehouse.id);
      await writeCache(WH_CACHE_KEYS.counts, counts, x.cache);
    }
    return { warehouse, counts: counts.filter((c) => !warehouse || c.warehouse_id === warehouse.id) };
  }),
});

export const loadCountFx = attach({
  source: $deps,
  mapParams: (id: string, d) => ({ id, d }),
  effect: createEffect(async ({ id, d }: { id: string; d: StockCountDeps | null }) => {
    const x = deps(d);
    let count = await readCache<CountOut>(WH_CACHE_KEYS.count(id), x.cache);
    if (x.online()) {
      try {
        count = await x.getCount(id);
        await writeCache(WH_CACHE_KEYS.count(id), count, x.cache);
      } catch (e) {
        if (!count) throw e;
      }
    }
    if (!count) throw new Error("count_not_cached");
    const local = localCountsFromOutbox(await x.outboxRows(), id);
    return { count, local };
  }),
});

export const startCountFx = attach({
  source: $deps,
  mapParams: (warehouseId: string, d) => ({ warehouseId, d }),
  effect: createEffect(async ({ warehouseId, d }: { warehouseId: string; d: StockCountDeps | null }) => {
    const x = deps(d);
    const count = await x.startCount(warehouseId, tashkentDate(x.now()));
    await writeCache(WH_CACHE_KEYS.count(count.id), count, x.cache);
    return count;
  }),
});

interface RecordInput {
  countId: string;
  productId: string | null;
  barcode: string | null;
  counted: string;
  name: string | null;
}

export const recordFx = attach({
  source: $deps,
  mapParams: (input: RecordInput, d) => ({ input, d }),
  effect: createEffect(async ({ input, d }: { input: RecordInput; d: StockCountDeps | null }) => {
    const x = deps(d);
    const actor = x.actorId();
    if (!actor) throw new Error("no_actor");
    const recordedAt = x.now().toISOString();
    const payload: Record<string, unknown> = {
      count_id: input.countId,
      counted: qty3(input.counted),
      recorded_at: recordedAt,
    };
    if (input.productId) payload.product_id = input.productId;
    if (input.barcode) payload.barcode = input.barcode.slice(0, 64);
    await x.enqueue(payload, actor);
    const local: LocalCount = {
      productId: input.productId,
      barcode: input.productId ? null : input.barcode,
      counted: qty3(input.counted),
      recordedAt,
      sync: "pending",
      name: input.name,
    };
    return local;
  }),
});

export const scanFx = attach({
  source: $deps,
  mapParams: (code: string, d) => ({ code, d }),
  effect: createEffect(async ({ code, d }: { code: string; d: StockCountDeps | null }) =>
    deps(d).resolve(code),
  ),
});

export const submitFx = attach({
  source: $deps,
  mapParams: (id: string, d) => ({ id, d }),
  effect: createEffect(async ({ id, d }: { id: string; d: StockCountDeps | null }) => {
    const x = deps(d);
    if (pendingCountEvents(await x.outboxRows(), id) > 0 && !(await x.flush(id))) {
      throw Object.assign(new Error("not_synced"), { notSynced: true });
    }
    return x.submit(id);
  }),
});

// ---- stores ---------------------------------------------------------------------------------------
export const $warehouse = createStore<WarehouseRef | null>(null, { skipVoid: false }).on(
  loadFx.doneData,
  (_, r) => r.warehouse,
);
export const $counts = createStore<CountOut[]>([])
  .on(loadFx.doneData, (_, r) => r.counts)
  .on(startCountFx.doneData, (list, c) => [c, ...list.filter((x) => x.id !== c.id)]);
export const $loaded = createStore(false).on(loadFx.finally, () => true);
export const $count = createStore<CountOut | null>(null, { skipVoid: false })
  .on(loadCountFx.doneData, (_, r) => r.count)
  .on(startCountFx.doneData, (_, c) => c)
  .reset(countClosed);
export const $local = createStore<Map<string, LocalCount>>(new Map(), { serialize: "ignore" })
  .on(loadCountFx.doneData, (_, r) => r.local)
  .on(startCountFx.doneData, () => new Map())
  .on(recordFx.doneData, (map, c) => upsertLocal(map, c))
  .reset(countClosed);
export const $current = createStore<CurrentItem | null>(null, { skipVoid: false })
  .on(currentQtyChanged, (c, counted) => (c ? { ...c, counted, dirty: true } : c))
  .reset(countClosed, countSelected);
export const $filter = createStore<CountFilter>("all").on(filterChanged, (_, f) => f);
export const $error = createStore<CountError | null>(null, { skipVoid: false }).reset(
  errorDismissed,
  countClosed,
  countSelected,
);
export const $submitted = createStore<CountOut | null>(null, { skipVoid: false })
  .on(submitFx.doneData, (_, c) => c)
  .reset(countSelected, countClosed, startCountFx.doneData);

export const $rows = combine($count, $local, (count, local) => buildRows(count, local));
export const $visibleRows = combine($rows, $filter, (rows, f) => filterRows(rows, f));
export const $progress = $rows.map(progressOf);
export const $busy = combine(
  [loadFx.pending, loadCountFx.pending, startCountFx.pending, submitFx.pending],
  (flags) => flags.some(Boolean),
);
export const $submitting = submitFx.pending;
/** Unknown barcodes recorded for this count (sent with `barcode` only — the server resolves them). */
export const $unknownCodes = $local.map((m) =>
  [...m.values()].filter((c) => !c.productId).map((c) => ({ code: c.barcode ?? "", counted: c.counted })),
);

// ---- wiring ---------------------------------------------------------------------------------------
sample({ clock: stockCountOpened, target: loadFx });
// exactly one open count of this warehouse → continue it directly
sample({
  clock: loadFx.doneData,
  source: $count,
  filter: (current, r) => current === null && r.counts.length === 1,
  fn: (_, r) => r.counts[0]?.id ?? "",
  target: countSelected,
});
sample({ clock: countSelected, target: loadCountFx });
sample({
  clock: startRequested,
  source: $warehouse,
  filter: (w) => w !== null,
  fn: (w) => (w as WarehouseRef).id,
  target: startCountFx,
});
sample({ clock: scanned, filter: $count.map(Boolean), target: scanFx });

/** Count of a product before this scan: local (newest) → server line → 0. */
function previousCount(
  count: CountOut | null,
  local: ReadonlyMap<string, LocalCount>,
  productId: string,
): string {
  const mine = localFor(local, productId);
  if (mine) return mine.counted;
  return count?.lines.find((l) => l.product_id === productId)?.counted ?? "0.000";
}
function expectedFor(count: CountOut | null, productId: string): string {
  const line = count?.lines.find((l) => l.product_id === productId);
  return line ? line.expected || line.snapshot_qty : "0.000";
}

// QT-M05-05: each scan writes a `stock_count.line_recorded` event at once (absolute count).
const productScanned = sample({
  clock: scanFx.doneData,
  source: { count: $count, local: $local, current: $current },
  filter: (_, r) => r.kind === "product",
  fn: ({ count, local, current }, r) => {
    const item = (r as Extract<ScanResult, { kind: "product" }>).item;
    // an unsaved −/+ edit of the same product is the base of the next scan
    const base =
      current && current.productId === item.productId && current.dirty
        ? current.counted
        : previousCount(count, local, item.productId);
    return {
      count: count as CountOut,
      item,
      counted: addQty(base, item.qty),
    };
  },
});
$current.on(productScanned, (_, { count, item, counted }) => ({
  productId: item.productId,
  name: item.name,
  code: item.code,
  isMarked: item.isMarked,
  expected: expectedFor(count, item.productId),
  counted,
  dirty: false,
}));
// the next scan's base must not wait for the async enqueue of this one (fast scanner bursts)
const pendingLocal = (
  productId: string | null,
  barcode: string | null,
  counted: string,
  name: string | null,
) => ({
  productId,
  barcode,
  counted,
  recordedAt: "",
  sync: "pending" as const,
  name,
});
$local.on(productScanned, (map, { item, counted }) =>
  upsertLocal(map, pendingLocal(item.productId, null, counted, item.name)),
);
sample({
  clock: productScanned,
  fn: ({ count, item, counted }): RecordInput => ({
    countId: count.id,
    productId: item.productId,
    barcode: item.markingCode ? null : item.code,
    counted,
    name: item.name,
  }),
  target: recordFx,
});

// unknown barcode: error banner + the barcode-only event (19 §14: accepted, BARCODE_NOT_IN_CATALOG)
const unknownScanned = sample({
  clock: scanFx.doneData,
  source: { count: $count, local: $local },
  filter: (_, r) => r.kind === "unknown",
  fn: ({ count, local }, r) => {
    const code = (r as Extract<ScanResult, { kind: "unknown" }>).code;
    const prev = [...local.values()].find((c) => !c.productId && c.barcode === code)?.counted ?? "0.000";
    return { count: count as CountOut, code, counted: addQty(prev, "1") };
  },
});
$error.on(unknownScanned, (_, { code }) => ({ kind: "unknown_barcode", code }));
$local.on(unknownScanned, (map, { code, counted }) =>
  upsertLocal(map, pendingLocal(null, code, counted, null)),
);
sample({
  clock: unknownScanned,
  fn: ({ count, code, counted }): RecordInput => ({
    countId: count.id,
    productId: null,
    barcode: code,
    counted,
    name: null,
  }),
  target: recordFx,
});
$error.on(scanFx.doneData, (e, r) =>
  r.kind === "rejected" && r.reason !== "empty" ? { kind: r.reason, code: r.code } : e,
);
$error.on(productScanned, () => null);

// manual add (product search) — the card opens, nothing is recorded until «Qatorni saqlash»
sample({
  clock: productPicked,
  source: { count: $count, local: $local },
  fn: ({ count, local }, p): CurrentItem => ({
    productId: p.productId,
    name: p.name,
    code: null,
    isMarked: p.isMarked === true,
    expected: expectedFor(count, p.productId),
    counted: previousCount(count, local, p.productId),
    dirty: true,
  }),
  target: $current,
});

sample({
  clock: currentSaved,
  source: { count: $count, current: $current },
  filter: ({ count, current }) => count !== null && current !== null,
  fn: ({ count, current }): RecordInput => ({
    countId: (count as CountOut).id,
    productId: (current as CurrentItem).productId,
    barcode: (current as CurrentItem).code,
    counted: (current as CurrentItem).counted,
    name: (current as CurrentItem).name,
  }),
  target: recordFx,
});
$current.on(recordFx.done, (c, { params }) =>
  c && c.productId === params.productId ? { ...c, counted: qty3(params.counted), dirty: false } : c,
);
$error.on(recordFx.failData, (_, e) => (e.message === "no_actor" ? { kind: "no_actor" } : apiError(e)));

sample({
  clock: finishConfirmed,
  source: $count,
  filter: (c) => c !== null,
  fn: (c) => (c as CountOut).id,
  target: submitFx,
});
$error.on(submitFx.failData, (_, e) =>
  (e as { notSynced?: boolean }).notSynced ? { kind: "not_synced" } : apiError(e),
);
$error.on(startCountFx.failData, (_, e) => apiError(e));
$error.on(loadCountFx.failData, (_, e) =>
  e.message === "count_not_cached" ? { kind: "api", code: "NETWORK_ERROR" } : apiError(e),
);
$counts.on(submitFx.doneData, (list, c) => list.filter((x) => x.id !== c.id));
$count.on(submitFx.doneData, () => null);
