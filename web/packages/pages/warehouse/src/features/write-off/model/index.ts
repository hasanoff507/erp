/**
 * «Hisobdan chiqarish» (07 BO-03, 19 §15, `stock.writeoff`, online only — qaror #54): lines (tovar,
 * partiya — ixtiyoriy, FIFO/AVECO when omitted — miqdor, sabab, sovg'a turi), aksiya buyrug'i
 * (`promo_justified` → majburiy), javobgar shaxs (→ 4730, else 9430). Submit = `POST /write-offs` →
 * `/post`: 200 posted, or 202 `{status:"draft", approval_request_id}` over the limit — «Tasdiq kutilmoqda»
 * (BO-16 approves and the server posts it).
 */
import { createEvent, createStore, sample } from "effector";

import { api, toApiError, type ApiError } from "@shared/api";
import type { StockLotOut, WriteOffCreate, WriteOffLineIn, WriteOffOut } from "@shared/models";

import { createProductSearch } from "#/entities/product/index.tsx";
import { compareQty, isPositive, qty3, subtractQty } from "#/shared/lib/decimal.ts";
import { apiFx, BULK_LIMIT } from "#/shared/lib/effect.ts";

export type WriteOff = WriteOffOut;
export type StockLot = StockLotOut;

/** Manual reasons (`expired_return` is created by customer returns only — qaror #48). */
export const WRITE_OFF_REASONS = ["expired", "damaged", "gift", "other"] as const;
export type WriteOffReason = (typeof WRITE_OFF_REASONS)[number];
export const GIFT_KINDS = ["other", "promo_justified"] as const;
export type GiftKind = (typeof GIFT_KINDS)[number];

/** Sentinel lot value: let the server allocate (FIFO/AVECO). */
export const AUTO_LOT = "auto";

export interface WriteOffLineDraft {
  key: string;
  productId: string;
  name: string;
  unitCode: string;
  lotId: string;
  qty: string;
  reason: WriteOffReason;
  giftKind: GiftKind;
}

export interface WriteOffForm {
  warehouseId: string;
  docDate: string;
  lines: WriteOffLineDraft[];
  promoOrderRef: string;
  responsibleUserId: string | null;
  comment: string;
}

export interface SubmitResult {
  doc: WriteOff;
  /** The draft was created but `post` was refused (422 INSUFFICIENT_STOCK, …). */
  postError: ApiError | null;
}

export type LineError = "qty" | "overLot" | null;

// --- lib -------------------------------------------------------------------------------------------

/** Available in a lot for a write-off: `qty_left − blocked_qty` (19 §15, INSUFFICIENT_STOCK). */
export function lotAvailable(lot: Pick<StockLot, "qty_left" | "blocked_qty">): string {
  return subtractQty(lot.qty_left, lot.blocked_qty);
}

export function lineError(line: WriteOffLineDraft, lots: readonly StockLot[]): LineError {
  if (!isPositive(line.qty)) return "qty";
  const lot = line.lotId === AUTO_LOT ? null : lots.find((l) => l.id === line.lotId);
  if (lot && compareQty(line.qty, lotAvailable(lot)) > 0) return "overLot";
  return null;
}

/** `promo_order_ref` is required when any gift line is `promo_justified` (19 §15). */
export function needsPromoRef(lines: readonly WriteOffLineDraft[]): boolean {
  return lines.some((l) => l.reason === "gift" && l.giftKind === "promo_justified");
}

export function toLineIn(line: WriteOffLineDraft): WriteOffLineIn {
  return {
    product_id: line.productId,
    lot_id: line.lotId === AUTO_LOT ? null : line.lotId,
    qty: qty3(line.qty),
    reason: line.reason,
    gift_kind: line.reason === "gift" ? line.giftKind : null,
  };
}

export function toBody(form: WriteOffForm): WriteOffCreate {
  return {
    warehouse_id: form.warehouseId,
    doc_date: form.docDate,
    lines: form.lines.map(toLineIn),
    promo_order_ref: needsPromoRef(form.lines)
      ? form.promoOrderRef.trim()
      : form.promoOrderRef.trim() || null,
    responsible_user_id: form.responsibleUserId,
    comment: form.comment.trim() || null,
  };
}

/** 202 path: still a draft, waiting in the approval queue (BO-16). */
export function isAwaitingApproval(doc: Pick<WriteOff, "status" | "approval_request_id">): boolean {
  return doc.status === "draft" && doc.approval_request_id !== null;
}

// --- effects ---------------------------------------------------------------------------------------

export const loadLotsFx = apiFx<{ warehouseId: string; productId: string }, StockLot[]>(
  async ({ warehouseId, productId }) => {
    const page = await api.inventory.listStockLots({
      warehouse_id: warehouseId,
      product_id: productId,
      limit: BULK_LIMIT,
    });
    return page.items;
  },
);

export const submitWriteOffFx = apiFx<WriteOffForm, SubmitResult>(async (form) => {
  const draft = await api.inventory.createWriteOff(toBody(form));
  try {
    return { doc: await api.inventory.postWriteOff(draft.id, {}), postError: null };
  } catch (e) {
    return { doc: draft, postError: toApiError(e) };
  }
});

/** «Qayta o'tkazish» of a draft whose post was refused (fix the stock first, then retry). */
export const repostWriteOffFx = apiFx<string, WriteOff>((id) => api.inventory.postWriteOff(id, {}));
/** «Qoralamani bekor qilish» — drop that draft instead. */
export const cancelWriteOffFx = apiFx<{ id: string; reason: string }, WriteOff>(({ id, reason }) =>
  api.inventory.cancelWriteOff(id, { reason }),
);

export const writeOffProductSearch = createProductSearch();

// --- stores / wiring -------------------------------------------------------------------------------

export const writeOffClosed = createEvent();
/** The sheet opened with a preset product (expiring lot row) — its lots are needed for the select. */
export const lotsRequested = createEvent<{ warehouseId: string; productId: string }>();

/** product_id → its lots in the warehouse (lot select). */
export const $lots = createStore<Record<string, StockLot[]>>({});
/** Last submit that ended in the approval queue (202) — the sheet shows «Tasdiq kutilmoqda». */
export const $awaiting = createStore<WriteOff | null>(null, { skipVoid: false });

sample({ clock: lotsRequested, target: loadLotsFx });
$lots
  .on(loadLotsFx.done, (known, { params, result }) => ({ ...known, [params.productId]: result }))
  .reset(writeOffClosed);
sample({
  clock: submitWriteOffFx.doneData,
  filter: ({ doc, postError }) => postError === null && isAwaitingApproval(doc),
  fn: ({ doc }) => doc,
  target: $awaiting,
});
sample({ clock: repostWriteOffFx.doneData, filter: isAwaitingApproval, target: $awaiting });
$awaiting.reset(writeOffClosed, submitWriteOffFx);

/** A created draft whose post was refused — the sheet offers «Qayta o'tkazish» / «Bekor qilish». */
export const $failedDraft = createStore<{ doc: WriteOff; error: ApiError } | null>(null, { skipVoid: false });
$failedDraft
  .on(submitWriteOffFx.doneData, (_, { doc, postError }) => (postError ? { doc, error: postError } : null))
  .on(repostWriteOffFx.failData, (state, error) => (state ? { ...state, error } : state))
  .on(repostWriteOffFx.done, () => null)
  .on(cancelWriteOffFx.done, () => null)
  .reset(writeOffClosed);
