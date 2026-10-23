/**
 * BO-07 «Soliq hisob-kitobi (ST)» block (07 BO-07; 20 #8a–#8d; 13 §2.26, §4.3; QT-M10-07): for the chosen
 * MONTH (a quarter has no ST document) — the period's tax settlements, «Qoralama hisoblash» (the server
 * computes base / amount: `vat_offset` = Σ input VAT → Dt 6410 / Kt 4410; `turnover_tax` = the vat-summary
 * figure → Dt 9430|9820 / Kt 6410, per branch), «O'tkazish» (the server recomputes; `recalculated`),
 * «Bekor qilish» (reason); «o'tkazishdan keyingi 6410 qoldig'i» — the 6410 row of
 * `GET /reports/trial-balance?period=&account=6410` (20 #11: `closing_balance` debit-positive — a liability is
 * negative and shown unsigned as «kredit qoldiq»; `by_tax_type`), re-read after every post / cancel; needs
 * `reports.finance.view` (`taxBalanceEnabled`). sample() only (24 §2).
 */
import { combine, createEvent, createStore, merge, sample } from "effector";

import { api, type ApiError } from "@shared/api";
import type { SettlementIn, SettlementOut, SettlementPosted, TrialBalanceRow } from "@shared/models";

import { apiFx, type LoadStatus } from "#/shared/lib/effect.ts";

import { $period, $summary, periodChanged } from "../../model/index.ts";

export type TaxSettlement = SettlementOut;
export type TaxKind = SettlementIn["tax_kind"];

const MONTH = /^\d{4}-(0[1-9]|1[0-2])$/;
export const isMonth = (period: string): boolean => MONTH.test(period);

/** The document kind of the period's regime (VAT payer → offset, turnover-tax payer → turnover tax). */
export function taxKindOf(regime: string | null | undefined): TaxKind | null {
  if (regime === "vat") return "vat_offset";
  if (regime === "turnover") return "turnover_tax";
  return null;
}

/**
 * Kinds the period needs: the regime's kind, plus the other one when the summary carries its block too —
 * a month where the regime changes settles both (VAT for the VAT days, turnover tax for the turnover days;
 * contracts/supplier-tax.md §2). The regime's kind comes first.
 */
export function taxKindsOf(
  s: { regime: string; outputVat: string | null; turnoverBase: string | null } | null,
): TaxKind[] {
  if (!s) return [];
  const vat = s.regime === "vat" || s.outputVat !== null;
  const turnover = s.regime === "turnover" || s.turnoverBase !== null;
  const kinds: TaxKind[] = [];
  if (vat) kinds.push("vat_offset");
  if (turnover) kinds.push("turnover_tax");
  return s.regime === "turnover" ? kinds.reverse() : kinds;
}

/** 13 §2.26 / §4.3 posting of a settlement: `{dt, kt}`. */
export function postingOf(s: Pick<TaxSettlement, "tax_kind" | "expense_account">): {
  dt: string;
  kt: string;
} {
  return s.tax_kind === "vat_offset"
    ? { dt: "6410", kt: "4410" }
    : { dt: s.expense_account ?? "9430", kt: "6410" };
}

/** Live documents first (draft, posted), cancelled ones after. */
export function sortSettlements(list: readonly TaxSettlement[]): TaxSettlement[] {
  const rank = (s: TaxSettlement) => (s.status === "cancelled" ? 1 : 0);
  return [...list].sort((a, b) => rank(a) - rank(b));
}

/**
 * A live (draft / posted) document already covers this kind (VAT offset: one per tenant and month;
 * turnover tax: one per branch and month) → no «Qoralama hisoblash».
 */
export function hasLiveFor(
  list: readonly TaxSettlement[],
  kind: TaxKind | null,
  branchId: string | null,
): boolean {
  if (!kind) return false;
  return list.some(
    (s) =>
      s.status !== "cancelled" && s.tax_kind === kind && (kind === "vat_offset" || s.branch_id === branchId),
  );
}

export function createBody(kind: TaxKind, period: string, branchId: string | null): SettlementIn {
  return { tax_kind: kind, period, ...(kind === "turnover_tax" && branchId ? { branch_id: branchId } : {}) };
}

// --- units ---------------------------------------------------------------------------------------------
export const stReloadRequested = createEvent();
export const stNoticeDismissed = createEvent();

export const listSettlementsFx = apiFx<string, TaxSettlement[]>(async (period) => {
  const page = await api.tax.listTaxSettlements({ period, limit: 50 });
  return page.items;
});
export const createSettlementFx = apiFx<SettlementIn, TaxSettlement>((body) =>
  api.tax.createTaxSettlement(body),
);
export const postSettlementFx = apiFx<string, SettlementPosted>((id) => api.tax.postTaxSettlement(id, {}));
export const cancelSettlementFx = apiFx<{ id: string; reason: string }, TaxSettlement>(({ id, reason }) =>
  api.tax.cancelTaxSettlement(id, { reason }),
);

export const $settlements = createStore<TaxSettlement[]>([]);
export const $stStatus = createStore<LoadStatus>("idle");
export const $stError = createStore<ApiError | null>(null, { skipVoid: false });
/** The last post answer (`recalculated` → «summa qayta hisoblandi»). */
export const $lastPosted = createStore<SettlementPosted | null>(null, { skipVoid: false });
export const $stActionError = createStore<ApiError | null>(null, { skipVoid: false });

export const $isMonthPeriod = $period.map(isMonth);
export const $taxKind = $summary.map((s) => taxKindOf(s?.regime ?? null));
export const $taxKinds = $summary.map(taxKindsOf);
export const $sortedSettlements = $settlements.map(sortSettlements);
export const $stBusy = combine(
  [createSettlementFx.pending, postSettlementFx.pending, cancelSettlementFx.pending],
  (flags) => flags.some(Boolean),
);

// Every period choice of the page (mount included) reloads the block; a quarter shows none.
sample({ clock: periodChanged, filter: isMonth, target: listSettlementsFx });
sample({ clock: stReloadRequested, source: $period, filter: isMonth, target: listSettlementsFx });
const listed = sample({
  clock: listSettlementsFx.done,
  source: $period,
  filter: (period, { params }) => period === params,
  fn: (_, { result }) => result,
});
$settlements.on(listed, (_, list) => list).reset(periodChanged);
$stStatus
  .on(listSettlementsFx, () => "loading")
  .on(listed, () => "idle")
  .on(listSettlementsFx.fail, () => "error");
$stError.on(listSettlementsFx.failData, (_, e) => e).reset(listSettlementsFx);

$lastPosted.on(postSettlementFx.doneData, (_, r) => r).reset(periodChanged, stNoticeDismissed);
// `validation.tax_settlement_exists` (another tab made it) → the list is simply re-read.
$stActionError
  .on(merge([createSettlementFx.failData, postSettlementFx.failData]), (_, e) => e)
  .reset(periodChanged, stNoticeDismissed, createSettlementFx, postSettlementFx);

sample({
  clock: merge([createSettlementFx.finally, postSettlementFx.finally, cancelSettlementFx.done]),
  fn: () => undefined,
  target: stReloadRequested,
});

// --- «O'tkazishdan keyingi 6410 qoldig'i» (20 #11) ------------------------------------------------------
export type Balance6410 = TrialBalanceRow;
export const taxBalanceEnabled = createEvent<boolean>();

/** The 6410 row of the month's trial balance (`null` — no movement and no balance on 6410). */
export const load6410Fx = apiFx<string, Balance6410 | null>(async (period) => {
  const tb = await api.reports.getTrialBalance({ period, account: "6410" });
  return tb.rows.find((r) => r.account === "6410") ?? null;
});

export const $taxBalanceEnabled = createStore(false);
export const $balance6410 = createStore<Balance6410 | null>(null, { skipVoid: false });
export const $balance6410Status = createStore<LoadStatus>("idle");

$taxBalanceEnabled.on(taxBalanceEnabled, (_, on) => on);
sample({
  clock: [periodChanged, stReloadRequested],
  source: { enabled: $taxBalanceEnabled, period: $period },
  filter: ({ enabled, period }) => enabled && isMonth(period),
  fn: ({ period }) => period,
  target: load6410Fx,
});
const loaded6410 = sample({
  clock: load6410Fx.done,
  source: $period,
  filter: (period, { params }) => period === params,
  fn: (_, { result }) => result,
});
$balance6410.on(loaded6410, (_, row) => row).reset(periodChanged);
$balance6410Status
  .on(load6410Fx, () => "loading")
  .on(loaded6410, () => "idle")
  .on(load6410Fx.fail, () => "error");
