/**
 * BO-14 «Fiskal» → «OFD: N ta chek yuborilmagan» (07 BO-14; 18 §14.1–§14.2): fiscal receipts by status
 * (`GET /fiscal-receipts?status=`, default `failed`), «Qayta urinish» (`POST /fiscal-receipts/{id}/retry`,
 * `integrations.retry`, Idempotency-Key from the shared client) and the registers' fiscal module state
 * (`GET /cash-registers` → `fm_state`, `ofd_status`, unacknowledged receipts).
 */
import { combine, createEffect, createEvent, createStore, sample } from "effector";

import { api, toApiError, type ApiError } from "@shared/api";
import type {
  CashRegisterOut,
  FiscalReceiptOut,
  FiscalReceiptPage,
  FiscalRetryOut,
  ListFiscalReceiptsStatus,
} from "@shared/models";

export type FiscalReceipt = FiscalReceiptOut;
export type CashRegister = CashRegisterOut;
/** Status filter of the list; `null` = all statuses. */
export type ReceiptFilter = Exclude<ListFiscalReceiptsStatus, null>;
export const RECEIPT_FILTERS: readonly ReceiptFilter[] = ["failed", "pending", "sent", "fiscalized"];
export type LoadStatus = "idle" | "loading" | "error";
export const RECEIPTS_PAGE_SIZE = 20;

interface ListRequest {
  status: ReceiptFilter | null;
  cursor: string | null;
}

function wrap<P, R>(fn: (params: P) => Promise<R>) {
  return createEffect<P, R, ApiError>(async (params) => {
    try {
      return await fn(params);
    } catch (e) {
      throw toApiError(e);
    }
  });
}

// --- events ------------------------------------------------------------------------------------------
export const fiscalOpened = createEvent();
export const fiscalFilterChanged = createEvent<ReceiptFilter | null>();
export const fiscalMoreRequested = createEvent();
export const fiscalReloadRequested = createEvent();
export const fiscalRetryRequested = createEvent<string>();
export const fiscalRetryDismissed = createEvent();

// --- effects -----------------------------------------------------------------------------------------
export const listReceiptsFx = wrap<ListRequest, FiscalReceiptPage>(({ status, cursor }) =>
  api.sales.listFiscalReceipts({
    ...(status ? { status } : {}),
    ...(cursor ? { cursor } : {}),
    limit: RECEIPTS_PAGE_SIZE,
  }),
);
export const listRegistersFx = wrap<void, CashRegister[]>(async () => {
  const { items } = await api.branches.cashRegistersList();
  return items;
});
export const retryReceiptFx = wrap<string, FiscalRetryOut>((id) => api.sales.retryFiscalReceipt(id, {}));

// --- stores ------------------------------------------------------------------------------------------
export const $fiscalFilter = createStore<ReceiptFilter | null>("failed", { skipVoid: false });
export const $receipts = createStore<FiscalReceipt[]>([]);
export const $receiptsCursor = createStore<string | null>(null, { skipVoid: false });
export const $receiptsStatus = createStore<LoadStatus>("idle");
export const $receiptsError = createStore<ApiError | null>(null, { skipVoid: false });
export const $registers = createStore<CashRegister[]>([]);
export const $fiscalRetrying = createStore<readonly string[]>([]);
/** Receipts re-queued in this visit (status shown as «Navbatga qo'yildi» until the list reloads). */
export const $fiscalRequeued = createStore<readonly string[]>([]);
export const $fiscalRetryError = createStore<ApiError | null>(null, { skipVoid: false });
export const $receiptsMoreLoading = combine(
  listReceiptsFx.pending,
  $receiptsStatus,
  (pending, status) => pending && status !== "loading",
);
/** Registers whose fiscal module is not `ok` or with unacknowledged receipts — shown first. */
export const $registerNames = $registers.map((list) => new Map(list.map((r) => [r.id, r.name])));

// --- connections -------------------------------------------------------------------------------------
$fiscalFilter.on(fiscalFilterChanged, (_, f) => f);

sample({ clock: fiscalOpened, target: listRegistersFx });
$registers.on(listRegistersFx.doneData, (_, list) => list.filter((r) => r.archived_at === null));

sample({
  clock: [fiscalOpened, fiscalFilterChanged, fiscalReloadRequested],
  source: $fiscalFilter,
  fn: (status) => ({ status, cursor: null }),
  target: listReceiptsFx,
});
sample({
  clock: fiscalMoreRequested,
  source: { status: $fiscalFilter, cursor: $receiptsCursor, pending: listReceiptsFx.pending },
  filter: ({ cursor, pending }) => cursor !== null && !pending,
  fn: ({ status, cursor }) => ({ status, cursor }),
  target: listReceiptsFx,
});
const loaded = sample({
  clock: listReceiptsFx.done,
  source: $fiscalFilter,
  filter: (current, { params }) => current === params.status,
  fn: (_, payload) => payload,
});
$receipts.on(loaded, (list, { params, result }) =>
  params.cursor ? [...list, ...result.items] : result.items,
);
$receiptsCursor.on(loaded, (_, { result }) => result.next_cursor);
$receiptsStatus
  .on(listReceiptsFx, (status, { cursor }) => (cursor === null ? "loading" : status))
  .on(loaded, () => "idle")
  .on(listReceiptsFx.fail, (status, { params }) => (params.cursor === null ? "error" : status));
$receiptsError.on(listReceiptsFx.failData, (_, e) => e).reset(listReceiptsFx);
$fiscalRequeued.reset(loaded);

// Retry: only a receipt not yet fiscalized, one request per receipt at a time (18 §14.2).
sample({
  clock: fiscalRetryRequested,
  source: { receipts: $receipts, retrying: $fiscalRetrying, requeued: $fiscalRequeued },
  filter: ({ receipts, retrying, requeued }, id) =>
    !retrying.includes(id) && !requeued.includes(id) && receipts.some((r) => r.id === id && isRetryable(r)),
  fn: (_, id) => id,
  target: retryReceiptFx,
});
$fiscalRetrying
  .on(retryReceiptFx, (ids, id) => [...ids, id])
  .on(retryReceiptFx.finally, (ids, { params }) => ids.filter((id) => id !== params));
$fiscalRequeued.on(retryReceiptFx.done, (ids, { params }) => [...ids, params]);
$fiscalRetryError.on(retryReceiptFx.failData, (_, e) => e).reset(retryReceiptFx, fiscalRetryDismissed);
// Changed meanwhile (409 DOC_INVALID_STATE / 404): reload the list.
sample({
  clock: retryReceiptFx.failData,
  filter: (e) => e.status === 404 || e.status === 409,
  fn: () => undefined,
  target: fiscalReloadRequested,
});

// --- lib ---------------------------------------------------------------------------------------------
/** 18 §14.2: any receipt not yet fiscalized can be re-queued (a `fiscalized` one → 409 DOC_INVALID_STATE). */
export function isRetryable(r: Pick<FiscalReceipt, "status">): boolean {
  return r.status !== "fiscalized";
}

export function isReceiptFilter(value: string | null): value is ReceiptFilter {
  return value !== null && (RECEIPT_FILTERS as readonly string[]).includes(value);
}

/** Registers needing attention first (fiscal module not `ok`, unacknowledged receipts), then by name. */
export function registersByAttention(list: readonly CashRegister[]): CashRegister[] {
  const weight = (r: CashRegister) => (r.fm_state !== "ok" ? 0 : r.last_unacked_receipt_at ? 1 : 2);
  return [...list].sort((a, b) => weight(a) - weight(b) || a.name.localeCompare(b.name));
}
