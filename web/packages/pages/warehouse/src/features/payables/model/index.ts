/**
 * BO-04 fifth tab «Men qarzdorman» (07 BO-04; US-M08-11, QT-M08-14 — B4, w-debts): what we owe suppliers —
 * `GET /reports/debts-aging?direction=payable` (supplier, amount, due date, days, open documents; 20 #21) — whom,
 * how much, when; a row opens the supplier's book `GET /counterparties/{id}/debt-ledger?direction=payable`
 * (goods receipts, supplier payments / returns, openings; open part by FIFO, 18 §12.1) and «To'lash» opens the
 * existing «To'lov qayd etish» form (BP-12, supplier payments). View: `reports.finance.view`; pay: `purchases.pay`.
 */
import { createEvent, createStore, sample } from "effector";

import { api, type ApiError } from "@shared/api";
import { addMoney, type Money } from "@shared/lib/money";
import type { AgingRow, AgingSummary, DebtLedgerOut, DebtsAgingOut } from "@shared/models";

import { $currentBranchId } from "#/entities/refs/index.ts";
import { apiFx } from "#/shared/lib/effect.ts";

export type LoadStatus = "idle" | "loading" | "error";
export type DueState = "overdue" | "today" | "soon" | "later" | "none";

/** Due chip: overdue / today / within 7 days / later / no due date. */
export function dueState(due: string | null, today: string): DueState {
  if (!due) return "none";
  if (due < today) return "overdue";
  if (due === today) return "today";
  const soon = new Date(`${today}T00:00:00Z`);
  soon.setUTCDate(soon.getUTCDate() + 7);
  return due <= soon.toISOString().slice(0, 10) ? "soon" : "later";
}

/** «Qachon to'lash»: the earliest due date first (no date last), then the larger debt. */
export function byDue(rows: readonly AgingRow[]): AgingRow[] {
  return [...rows].sort((a, b) => {
    const da = a.due_date ?? "9999-12-31";
    const db = b.due_date ?? "9999-12-31";
    if (da !== db) return da < db ? -1 : 1;
    return b.balance.localeCompare(a.balance, undefined, { numeric: true });
  });
}

export function totalOf(rows: readonly Pick<AgingRow, "balance">[]): Money {
  return addMoney("0.00" as Money, ...rows.map((r) => r.balance as Money));
}

export const payablesOpened = createEvent();
export const payablesReloadRequested = createEvent();
export const payableLedgerOpened = createEvent<string>();
export const payableLedgerClosed = createEvent();

export const loadPayablesFx = apiFx<string | null, DebtsAgingOut>((branchId) =>
  api.reports.getDebtsAging({ direction: "payable", ...(branchId ? { branch_id: branchId } : {}) }),
);
export const loadPayableLedgerFx = apiFx<string, DebtLedgerOut>((supplierId) =>
  api.debts.getCounterpartyDebtLedger(supplierId, { direction: "payable", limit: 100 }),
);

export const $payables = createStore<AgingRow[]>([]);
export const $payablesSummary = createStore<AgingSummary | null>(null, { skipVoid: false });
export const $payablesStatus = createStore<LoadStatus>("idle");
export const $payablesError = createStore<ApiError | null>(null, { skipVoid: false });
export const $payableLedgerId = createStore<string | null>(null, { skipVoid: false })
  .on(payableLedgerOpened, (_, id) => id)
  .reset(payableLedgerClosed);
export const $payableLedger = createStore<DebtLedgerOut | null>(null, { skipVoid: false }).reset(
  payableLedgerClosed,
  payableLedgerOpened,
);
export const $payableLedgerError = createStore<ApiError | null>(null, { skipVoid: false }).reset(
  payableLedgerClosed,
  loadPayableLedgerFx,
);

const $opened = createStore(false).on(payablesOpened, () => true);
sample({
  clock: [payablesOpened, payablesReloadRequested],
  source: $currentBranchId,
  target: loadPayablesFx,
});
// the topbar branch changed while the tab was open
sample({
  clock: $currentBranchId.updates,
  source: $opened,
  filter: (opened) => opened,
  fn: (_, branch) => branch,
  target: loadPayablesFx,
});
const loaded = sample({
  clock: loadPayablesFx.done,
  source: $currentBranchId,
  filter: (branch, { params }) => branch === params,
  fn: (_, { result }) => result,
});
$payables.on(loaded, (_, r) => byDue(r.rows));
$payablesSummary.on(loaded, (_, r) => r.summary);
$payablesStatus
  .on(loadPayablesFx, () => "loading")
  .on(loaded, () => "idle")
  .on(loadPayablesFx.fail, () => "error");
$payablesError.on(loadPayablesFx.failData, (_, e) => e).reset(loadPayablesFx);

sample({ clock: payableLedgerOpened, target: loadPayableLedgerFx });
$payableLedger.on(
  sample({
    clock: loadPayableLedgerFx.done,
    source: $payableLedgerId,
    filter: (id, { params }) => id === params,
    fn: (_, { result }) => result,
  }),
  (_, r) => r,
);
$payableLedgerError.on(loadPayableLedgerFx.failData, (_, e) => e);
