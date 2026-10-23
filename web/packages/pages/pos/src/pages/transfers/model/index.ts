/**
 * POS-09 — Ko'chirish (07 POS-09; 19 §13; QT-M06-04). «Yuborish» and «Qabul qilish» are outbox events
 * (`transfer.sent` / `transfer.received`) — they work offline and reach the server exactly once (dedupe by
 * `client_event_id`); «O'tkazish» (draft + post, e-TTN for vehicles) is an online REST call, its «Jo'natish»
 * again a `transfer.sent {transfer_id}` event. Incoming transfers and warehouses are cached on the device.
 */
import { attach, combine, createEffect, createEvent, createStore, sample } from "effector";

import { api, toApiError } from "@shared/api";
import type { TransferOut } from "@shared/models";
import { awaitEventResult, enqueueEvent, outbox, stock, type PushResultEntry } from "@shared/offline";
import { $isOnline } from "@shared/state/network";

import { $posDevice, posActorId, uuidv7 } from "#/entities/pos-session/index.ts";
import {
  WH_CACHE_KEYS,
  loadWarehouses,
  readCache,
  resolveScan,
  writeCache,
  type KeyValueStore,
  type ScanResult,
  type WarehouseRef,
} from "#/features/wh-scan/index.ts";
import { tashkentDate } from "#/shared/lib/dates.ts";
import { nextTempNumber } from "#/shared/lib/device-runtime.ts";

import {
  EMPTY_FORM,
  TRANSFER_RECEIVED,
  TRANSFER_SENT,
  addScanned,
  createBody,
  historyFromOutbox,
  locallyReceivedIds,
  receiveDefaults,
  receivedPayload,
  sendErrors,
  sentPayload,
  setAvailable,
  setLineQty,
  type SendForm,
  type TransferEventRow,
  type TransportMode,
} from "./lib.ts";

export * from "./lib.ts";

export interface TransfersDeps {
  online(): boolean;
  device(): { deviceId: string; branchId: string } | null;
  actorId(): string | null;
  warehouses(online: boolean): Promise<WarehouseRef[]>;
  incoming(branchId: string): Promise<TransferOut[]>;
  balance(productId: string, warehouseId: string): Promise<string | null>;
  create(form: SendForm, docDate: string): Promise<TransferOut>;
  outboxRows(): Promise<TransferEventRow[]>;
  enqueue(
    type: string,
    payload: Record<string, unknown>,
    actorUserId: string,
  ): Promise<{ clientEventId: string }>;
  awaitResult(clientEventId: string, timeoutMs: number): Promise<PushResultEntry | null>;
  resolve(code: string): Promise<ScanResult>;
  newId(): string;
  /** `temp_number` of an offline transfer — per-device counter (18 §4.1, SYNC-13), never wall-clock. */
  tempNumber(deviceId: string): Promise<string>;
  cache: KeyValueStore | undefined;
  now(): Date;
}

function defaultDeps(): TransfersDeps {
  return {
    online: () => $isOnline.getState(),
    device: () => {
      const d = $posDevice.getState();
      return d ? { deviceId: d.deviceId, branchId: d.branchId } : null;
    },
    actorId: posActorId,
    warehouses: (online) => loadWarehouses(online),
    incoming: async (branchId) =>
      (await api.transfers.listTransfers({ status: "sent", limit: 50 })).items.filter(
        (t) => t.to_branch_id === branchId,
      ),
    balance: async (productId, warehouseId) => {
      const rows = await stock.forProduct(productId);
      const row = rows.find((r) => r.warehouse_id === warehouseId);
      return typeof row?.qty === "string" ? row.qty : null;
    },
    create: async (form, docDate) => {
      const draft = await api.transfers.createTransfer(createBody(form, docDate));
      return api.transfers.postTransfer(draft.id, {});
    },
    outboxRows: () => outbox.list({ status: ["pending", "accepted", "duplicate", "rejected"] }),
    enqueue: (type, payload, actorUserId) =>
      enqueueEvent(type as "transfer.sent" | "transfer.received", payload, { actorUserId }),
    awaitResult: (id, timeoutMs) => awaitEventResult(id, { timeoutMs }),
    resolve: (code) => resolveScan(code),
    newId: () => uuidv7(),
    tempNumber: (deviceId) => nextTempNumber(deviceId),
    cache: undefined,
    now: () => new Date(),
  };
}

const $deps = createStore<TransfersDeps | null>(null, { serialize: "ignore", skipVoid: false });
export const configureTransfers = createEvent<Partial<TransfersDeps>>();
$deps.on(configureTransfers, (prev, d) => ({ ...(prev ?? defaultDeps()), ...d }));
const deps = (d: TransfersDeps | null): TransfersDeps => d ?? defaultDeps();

export type TransfersTab = "send" | "receive" | "history";

export type TransfersError =
  | { kind: "unknown_barcode" | "check_digit"; code: string }
  | { kind: "no_actor" | "no_device" }
  | { kind: "api"; code: string; params: Record<string, unknown> };

export type TransfersNotice =
  | { kind: "sent_local"; number: string | null; status: string | null; warnings: string[] }
  | { kind: "posted"; transfer: TransferOut }
  | { kind: "received_local"; status: string | null };

const apiError = (e: unknown): TransfersError => {
  if (e instanceof Error && (e.message === "no_actor" || e.message === "no_device"))
    return { kind: e.message };
  const err = toApiError(e);
  return { kind: "api", code: err.code, params: { ...err.params } };
};

// ---- events ---------------------------------------------------------------------------------------
export const transfersOpened = createEvent();
export const tabChanged = createEvent<TransfersTab>();
export const destinationChanged = createEvent<string | null>();
export const transportModeChanged = createEvent<TransportMode>();
export const vehiclePlateChanged = createEvent<string>();
export const driverNameChanged = createEvent<string>();
export const scanned = createEvent<string>();
export const productPicked = createEvent<{ productId: string; name: string }>();
export const lineQtyChanged = createEvent<{ productId: string; qty: string }>();
export const lineRemoved = createEvent<string>();
export const sendConfirmed = createEvent();
export const postRequested = createEvent();
export const sendExistingRequested = createEvent<string>();
export const incomingSelected = createEvent<string | null>();
export const receiveQtyChanged = createEvent<{ lineId: string; qty: string }>();
export const receiveConfirmed = createEvent();
export const noticeDismissed = createEvent();
export const errorDismissed = createEvent();

// ---- effects --------------------------------------------------------------------------------------
export const loadFx = attach({
  source: $deps,
  effect: createEffect(async (d: TransfersDeps | null) => {
    const x = deps(d);
    const online = x.online();
    const device = x.device();
    const warehouses = await x.warehouses(online);
    let incoming = (await readCache<TransferOut[]>(WH_CACHE_KEYS.incoming, x.cache)) ?? [];
    let cached = true;
    if (online && device) {
      try {
        incoming = await x.incoming(device.branchId);
        await writeCache(WH_CACHE_KEYS.incoming, incoming, x.cache);
        cached = false;
      } catch {
        /* keep the cached list */
      }
    }
    const rows = [...(await x.outboxRows())];
    return { device, warehouses, incoming, cached, rows };
  }),
});

const refreshHistoryFx = attach({
  source: $deps,
  effect: createEffect(async (d: TransfersDeps | null) => [...(await deps(d).outboxRows())]),
});

export const scanFx = attach({
  source: $deps,
  mapParams: (code: string, d) => ({ code, d }),
  effect: createEffect(async ({ code, d }: { code: string; d: TransfersDeps | null }) =>
    deps(d).resolve(code),
  ),
});

const balanceFx = attach({
  source: $deps,
  mapParams: (productId: string, d) => ({ productId, d }),
  effect: createEffect(async ({ productId, d }: { productId: string; d: TransfersDeps | null }) => {
    const x = deps(d);
    const own = await x.warehouses(false);
    const device = x.device();
    const wh = own.find((w) => w.branchId === device?.branchId);
    return { productId, qty: wh ? await x.balance(productId, wh.id) : null };
  }),
});

export const sendFx = attach({
  source: $deps,
  mapParams: (form: SendForm, d) => ({ form, d }),
  effect: createEffect(async ({ form, d }: { form: SendForm; d: TransfersDeps | null }) => {
    const x = deps(d);
    const actor = x.actorId();
    if (!actor) throw new Error("no_actor");
    const device = x.device();
    if (!device) throw new Error("no_device");
    const now = x.now();
    const payload = sentPayload(
      form,
      { id: x.newId(), lineId: () => x.newId(), tempNumber: await x.tempNumber(device.deviceId) },
      tashkentDate(now),
    );
    const { clientEventId } = await x.enqueue(TRANSFER_SENT, payload, actor);
    // online: show the server answer when it comes quickly; offline: the event waits in the outbox
    const result = x.online() ? await x.awaitResult(clientEventId, 8_000) : null;
    return { payload, result };
  }),
});

export const sendExistingFx = attach({
  source: $deps,
  mapParams: (transferId: string, d) => ({ transferId, d }),
  effect: createEffect(async ({ transferId, d }: { transferId: string; d: TransfersDeps | null }) => {
    const x = deps(d);
    const actor = x.actorId();
    if (!actor) throw new Error("no_actor");
    const { clientEventId } = await x.enqueue(TRANSFER_SENT, { transfer_id: transferId }, actor);
    const result = x.online() ? await x.awaitResult(clientEventId, 8_000) : null;
    return { payload: { transfer_id: transferId }, result };
  }),
});

export const postFx = attach({
  source: $deps,
  mapParams: (form: SendForm, d) => ({ form, d }),
  effect: createEffect(async ({ form, d }: { form: SendForm; d: TransfersDeps | null }) => {
    const x = deps(d);
    return x.create(form, tashkentDate(x.now()));
  }),
});

export const receiveFx = attach({
  source: $deps,
  mapParams: (input: { transfer: TransferOut; qty: Record<string, string> }, d) => ({ input, d }),
  effect: createEffect(
    async ({
      input,
      d,
    }: {
      input: { transfer: TransferOut; qty: Record<string, string> };
      d: TransfersDeps | null;
    }) => {
      const x = deps(d);
      const actor = x.actorId();
      if (!actor) throw new Error("no_actor");
      const payload = receivedPayload(input.transfer, input.qty);
      const { clientEventId } = await x.enqueue(TRANSFER_RECEIVED, payload, actor);
      const result = x.online() ? await x.awaitResult(clientEventId, 8_000) : null;
      return { transferId: input.transfer.id, result };
    },
  ),
});

// ---- stores ---------------------------------------------------------------------------------------
export const $tab = createStore<TransfersTab>("send").on(tabChanged, (_, t) => t);
export const $warehouses = createStore<WarehouseRef[]>([]).on(loadFx.doneData, (_, r) => r.warehouses);
const $branchId = createStore<string | null>(null, { skipVoid: false }).on(
  loadFx.doneData,
  (_, r) => r.device?.branchId ?? null,
);
export const $source = combine(
  $warehouses,
  $branchId,
  (list, b) => list.find((w) => w.branchId === b) ?? null,
);
export const $destinations = combine($warehouses, $branchId, (list, b) =>
  list.filter((w) => w.branchId !== b),
);
export const $loaded = createStore(false).on(loadFx.finally, () => true);

export const $form = createStore<SendForm>(EMPTY_FORM)
  .on(destinationChanged, (f, id) => ({ ...f, toWarehouseId: id }))
  .on(transportModeChanged, (f, m) => ({ ...f, transportMode: m }))
  .on(vehiclePlateChanged, (f, v) => ({ ...f, vehiclePlate: v.slice(0, 16) }))
  .on(driverNameChanged, (f, v) => ({ ...f, driverName: v.slice(0, 255) }))
  .on(lineQtyChanged, (f, { productId, qty }) => ({ ...f, lines: setLineQty(f.lines, productId, qty) }))
  .on(lineRemoved, (f, id) => ({ ...f, lines: f.lines.filter((l) => l.productId !== id) }))
  .on(balanceFx.doneData, (f, { productId, qty }) => ({ ...f, lines: setAvailable(f.lines, productId, qty) }))
  .on(sendFx.done, () => EMPTY_FORM)
  .on(postFx.done, () => EMPTY_FORM);
sample({
  clock: $source,
  source: $form,
  fn: (f, w) => ({ ...f, fromWarehouseId: w?.id ?? null }),
  target: $form,
});
sample({
  clock: [sendFx.done, postFx.done],
  source: $source,
  fn: (w) => ({ ...EMPTY_FORM, fromWarehouseId: w?.id ?? null }),
  target: $form,
});
export const $formErrors = $form.map(sendErrors);

export const $outboxRows = createStore<TransferEventRow[]>([])
  .on(loadFx.doneData, (_, r) => r.rows)
  .on(refreshHistoryFx.doneData, (_, rows) => rows);
export const $history = $outboxRows.map(historyFromOutbox);
const $incomingAll = createStore<TransferOut[]>([]).on(loadFx.doneData, (_, r) => r.incoming);
export const $incomingCached = createStore(false).on(loadFx.doneData, (_, r) => r.cached);
export const $incoming = combine($incomingAll, $outboxRows, (list, rows) => {
  const done = locallyReceivedIds(rows);
  return list.filter((t) => !done.has(t.id));
});
export const $selectedIncomingId = createStore<string | null>(null, { skipVoid: false })
  .on(incomingSelected, (_, id) => id)
  .reset(receiveFx.done);
export const $selectedIncoming = combine(
  $incomingAll,
  $selectedIncomingId,
  (list, id) => list.find((t) => t.id === id) ?? null,
);
export const $receiveQty = createStore<Record<string, string>>({})
  .on(receiveQtyChanged, (q, { lineId, qty }) => ({ ...q, [lineId]: qty }))
  .reset(receiveFx.done);
sample({
  clock: $selectedIncoming,
  fn: (t) => (t ? receiveDefaults(t) : {}),
  target: $receiveQty,
});

/** The online «O'tkazish» result kept on screen (status steps, «Jo'natish» once the e-TTN is registered). */
export const $posted = createStore<TransferOut | null>(null, { skipVoid: false })
  .on(postFx.doneData, (_, t) => t)
  .reset(sendExistingFx.done, tabChanged);

export const $notice = createStore<TransfersNotice | null>(null, { skipVoid: false })
  .on([sendFx.doneData, sendExistingFx.doneData], (_, { payload, result }) => {
    const server = result?.server ?? null;
    return {
      kind: "sent_local",
      number:
        (typeof server?.number === "string" ? server.number : null) ??
        (typeof payload.temp_number === "string" ? payload.temp_number : null),
      status: typeof server?.status === "string" ? server.status : null,
      warnings: result?.warnings ?? [],
    };
  })
  .on(postFx.doneData, (_, transfer) => ({ kind: "posted", transfer }))
  .on(receiveFx.doneData, (_, { result }) => {
    const server = result?.server ?? null;
    return { kind: "received_local", status: typeof server?.status === "string" ? server.status : null };
  })
  .reset(noticeDismissed, tabChanged);

export const $error = createStore<TransfersError | null>(null, { skipVoid: false })
  .on([sendFx.failData, sendExistingFx.failData, postFx.failData, receiveFx.failData], (_, e) => apiError(e))
  .on(scanFx.doneData, (e, r) =>
    r.kind === "unknown"
      ? { kind: "unknown_barcode", code: r.code }
      : r.kind === "rejected" && r.reason === "check_digit"
        ? { kind: "check_digit", code: r.code }
        : r.kind === "product"
          ? null
          : e,
  ) // prettier-ignore
  .reset(errorDismissed, tabChanged);

export const $acting = combine(
  [sendFx.pending, sendExistingFx.pending, postFx.pending, receiveFx.pending],
  (flags) => flags.some(Boolean),
);

// ---- wiring ---------------------------------------------------------------------------------------
sample({ clock: transfersOpened, target: loadFx });
sample({
  clock: scanned,
  source: $tab,
  filter: (tab) => tab === "send",
  fn: (_, code) => code,
  target: scanFx,
});
const productScanned = sample({
  clock: scanFx.doneData,
  filter: (r) => r.kind === "product",
  fn: (r) => (r as Extract<ScanResult, { kind: "product" }>).item,
});
$form.on(productScanned, (f, item) => ({ ...f, lines: addScanned(f.lines, item) }));
$form.on(productPicked, (f, p) => ({
  ...f,
  lines: addScanned(f.lines, {
    productId: p.productId, name: p.name, nameRu: null, unitCode: "", isMarked: false, isWeighed: false,
    qty: "1.000", code: "", markingCode: null,
  }),
})); // prettier-ignore
sample({
  clock: [productScanned.map((i) => i.productId), productPicked.map((p) => p.productId)],
  target: balanceFx,
});

const validSend = (f: SendForm): boolean => sendErrors(f).length === 0;
sample({ clock: sendConfirmed, source: $form, filter: (f) => validSend(f), target: sendFx });
sample({ clock: postRequested, source: $form, filter: (f) => validSend(f), target: postFx });
sample({ clock: sendExistingRequested, target: sendExistingFx });
sample({
  clock: receiveConfirmed,
  source: { transfer: $selectedIncoming, qty: $receiveQty },
  filter: ({ transfer }) => transfer !== null,
  fn: ({ transfer, qty }) => ({ transfer: transfer as TransferOut, qty }),
  target: receiveFx,
});
sample({
  clock: [sendFx.finally, sendExistingFx.finally, receiveFx.finally, tabChanged],
  fn: () => undefined,
  target: refreshHistoryFx,
});
