/**
 * BO-08 right panel «Hisob qoldiqlari» (07 BO-08; 20 #11 `GET /reports/trial-balance?period=`): the trial
 * balance of the month of the journal's «Sana (gacha)» — opening, Dt / Kt turnover, closing per account
 * (debit-positive). Needs `reports.finance.view` (`balancesEnabled` on mount). sample() only (24 §2).
 */
import { createEvent, createStore, sample } from "effector";

import { api, type ApiError } from "@shared/api";
import type { TrialBalanceOut } from "@shared/models";

import { apiFx, type LoadStatus } from "#/shared/lib/effect.ts";

import { filtersApplied } from "../../model/index.ts";
import { cancelAdjustmentFx, createAdjustmentFx } from "../../adjustments/model/index.ts";

export type TrialBalance = TrialBalanceOut;

/** `YYYY-MM` of a `YYYY-MM-DD` date, or `null` when the date is empty / malformed. */
export function monthOf(date: string): string | null {
  return /^\d{4}-(0[1-9]|1[0-2])-\d{2}$/.test(date) ? date.slice(0, 7) : null;
}

export const balancesEnabled = createEvent<boolean>();
export const balancesReloadRequested = createEvent();

export const loadBalancesFx = apiFx<string, TrialBalance>((period) => api.reports.getTrialBalance({ period }));

export const $balancesEnabled = createStore(false);
export const $balancesPeriod = createStore<string | null>(null, { skipVoid: false });
export const $balances = createStore<TrialBalance | null>(null, { skipVoid: false });
export const $balancesStatus = createStore<LoadStatus>("idle");
export const $balancesError = createStore<ApiError | null>(null, { skipVoid: false });

$balancesEnabled.on(balancesEnabled, (_, on) => on);
$balancesPeriod.on(filtersApplied, (current, f) => monthOf(f.dateTo) ?? current);

sample({
  clock: [$balancesPeriod.updates, balancesReloadRequested, balancesEnabled],
  source: { enabled: $balancesEnabled, period: $balancesPeriod },
  filter: ({ enabled, period }) => enabled && period !== null,
  fn: ({ period }) => period ?? "",
  target: loadBalancesFx,
});
const loaded = sample({
  clock: loadBalancesFx.done,
  source: $balancesPeriod,
  filter: (period, { params }) => period === params,
  fn: (_, { result }) => result,
});
$balances.on(loaded, (_, tb) => tb);
$balancesStatus
  .on(loadBalancesFx, () => "loading")
  .on(loaded, () => "idle")
  .on(loadBalancesFx.fail, () => "error");
$balancesError.on(loadBalancesFx.failData, (_, e) => e).reset(loadBalancesFx);

// A manual entry changes the balances of its month.
sample({
  clock: [createAdjustmentFx.done, cancelAdjustmentFx.done],
  fn: () => undefined,
  target: balancesReloadRequested,
});
