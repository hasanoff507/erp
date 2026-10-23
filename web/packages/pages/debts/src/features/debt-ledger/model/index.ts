/**
 * «Qarz daftari» — the paper-book view of one counterparty (US-M08-06, QT-M08-09; 18 §12.1):
 * `GET /counterparties/{id}/debt-ledger?direction=&cursor=&limit=` — one row per document, newest first,
 * signed amount (+ debt grew, − shrank), running balance after the row, status of debt rows
 * (open / partially_paid / paid / written_off), goods, who wrote it, the documents a payment closed.
 * `payable` = «Men qarzdorman» (US-M08-11, QT-M08-14 payable half).
 */
import { createEvent, createStore, sample } from "effector";

import { api, type ApiError } from "@shared/api";
import type { DebtLedgerOut, LedgerEntry, LedgerProduct } from "@shared/models";

import type { Direction } from "#/entities/debtor/index.ts";
import { apiFx } from "#/shared/lib/effect.ts";

export const LEDGER_PAGE = 50;

export interface LedgerTarget {
  counterpartyId: string;
  direction: Direction;
}

export interface LedgerRequest extends LedgerTarget {
  cursor: string | null;
}

export const ledgerOpened = createEvent<LedgerTarget>();
export const ledgerClosed = createEvent();
export const ledgerMoreRequested = createEvent();
export const ledgerReloadRequested = createEvent();

export const loadLedgerFx = apiFx<LedgerRequest, DebtLedgerOut>(({ counterpartyId, direction, cursor }) =>
  api.debts.getCounterpartyDebtLedger(counterpartyId, {
    direction,
    limit: LEDGER_PAGE,
    ...(cursor ? { cursor } : {}),
  }),
);

export const $ledgerTarget = createStore<LedgerTarget | null>(null, { skipVoid: false })
  .on(ledgerOpened, (_, t) => t)
  .reset(ledgerClosed);
export const $ledger = createStore<DebtLedgerOut | null>(null, { skipVoid: false }).reset(ledgerClosed);
export const $ledgerStatus = createStore<"idle" | "loading" | "error">("idle").reset(ledgerClosed);
export const $ledgerError = createStore<ApiError | null>(null, { skipVoid: false }).reset(
  ledgerClosed,
  loadLedgerFx,
);

sample({
  clock: [ledgerOpened, sample({ clock: ledgerReloadRequested, source: $ledgerTarget })],
  filter: (t): t is LedgerTarget => t !== null,
  fn: (t) => ({ ...(t as LedgerTarget), cursor: null }),
  target: loadLedgerFx,
});
sample({
  clock: ledgerMoreRequested,
  source: { target: $ledgerTarget, ledger: $ledger, pending: loadLedgerFx.pending },
  filter: ({ target, ledger, pending }) => target !== null && !!ledger?.next_cursor && !pending,
  fn: ({ target, ledger }) => ({ ...(target as LedgerTarget), cursor: ledger?.next_cursor ?? null }),
  target: loadLedgerFx,
});

/** An answer for a ledger that is no longer open is dropped. */
const loaded = sample({
  clock: loadLedgerFx.done,
  source: $ledgerTarget,
  filter: (t, { params }) =>
    t !== null && t.counterpartyId === params.counterpartyId && t.direction === params.direction,
  fn: (_, payload) => payload,
});
$ledger.on(loaded, (current, { params, result }) =>
  params.cursor && current ? { ...result, entries: [...current.entries, ...result.entries] } : result,
);
$ledgerStatus
  .on(loadLedgerFx, (s, { cursor }) => (cursor === null ? "loading" : s))
  .on(loaded, () => "idle")
  .on(loadLedgerFx.fail, (s, { params }) => (params.cursor === null ? "error" : s));
$ledgerError.on(loadLedgerFx.failData, (_, e) => e);

// --- presentation (pure) -------------------------------------------------------------------------------

export type LedgerDocKey =
  | "sales"
  | "returns"
  | "debt_openings"
  | "debt_payments"
  | "debt_writeoffs"
  | "goods_receipts"
  | "supplier_payments"
  | "supplier_returns"
  | "cash_movements"
  | "payment"
  | "other";

/** i18n key suffix of a ledger row (`debts:ledger.doc.*`). */
export function entryDocKey(entry: Pick<LedgerEntry, "doc_type" | "kind">): LedgerDocKey {
  switch (entry.doc_type) {
    case "sales":
    case "returns":
    case "debt_openings":
    case "debt_payments":
    case "debt_writeoffs":
    case "goods_receipts":
    case "supplier_payments":
    case "supplier_returns":
    case "cash_movements":
      return entry.doc_type;
    default:
      return entry.kind === "payment" ? "payment" : "other";
  }
}

/** «non, sut, shakar» — goods of a debt row in the UI language (name_ru when Russian and present). */
export function productsText(products: readonly LedgerProduct[], lang: string, max = 4): string {
  const names = products.map((p) => (lang === "ru" && p.name_ru ? p.name_ru : p.name));
  const shown = names.slice(0, max).join(", ");
  return names.length > max ? `${shown} +${names.length - max}` : shown;
}

/** Tone of the signed amount: debt grew (destructive), shrank (success), unchanged. */
export function amountTone(amount: string): "debt" | "payment" | "zero" {
  if (amount.startsWith("-")) return "payment";
  return /^0+(\.0+)?$/.test(amount) ? "zero" : "debt";
}
