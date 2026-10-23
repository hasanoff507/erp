/**
 * BO-08 «Davrni yopish» card (07 BO-08; 20 #14–#16; 13 §5.1; qaror #23, #69): the **oldest open month**
 * (the month after the last closed one; with nothing closed yet — the previous calendar month, corrected by
 * the server's `params.expected_period` on `409 PERIOD_CLOSE_OUT_OF_ORDER`), its readiness (blockers
 * `recost_pending` / `fiscal_pending` / `devices_unsynced` disable the button; warnings are listed in the
 * confirmation dialog), and `POST /period-closings`. A closed month is never reopened. sample() only (24 §2).
 */
import { combine, createEvent, createStore, sample } from "effector";

import { api, type ApiError } from "@shared/api";
import type { PeriodClosingOut, ReadinessOut } from "@shared/models";

import { apiFx, type LoadStatus } from "#/shared/lib/effect.ts";

export type Readiness = ReadinessOut;
export type PeriodClosing = PeriodClosingOut;
export type Blocker = ReadinessOut["blockers"][number];
export type Warning = ReadinessOut["warnings"][number];

const MONTH = /^(\d{4})-(0[1-9]|1[0-2])$/;

/** Digits → integer without Number()/parseInt (money lint rule, qaror #57). */
function int(digits: string | undefined): number {
  let n = 0;
  for (const c of digits ?? "") n = n * 10 + (c.charCodeAt(0) - 48);
  return n;
}

export function isMonth(value: unknown): value is string {
  return typeof value === "string" && MONTH.test(value);
}

/** `YYYY-MM` shifted by `delta` months. */
export function shiftMonth(month: string, delta: number): string {
  const m = MONTH.exec(month);
  if (!m) return month;
  const index = int(m[1]) * 12 + int(m[2]) - 1 + delta;
  return `${Math.floor(index / 12)}-${String((index % 12) + 1).padStart(2, "0")}`;
}

/**
 * The month to close: the one after the last closed month; nothing closed yet — the previous calendar month
 * (the server knows the first activity month and answers `expected_period` if it is earlier).
 */
export function candidatePeriod(lastClosed: string | null, today: string): string {
  return lastClosed ? shiftMonth(lastClosed, 1) : shiftMonth(today.slice(0, 7), -1);
}

/** 20 #15 `validation.period_not_ended`: a month can be closed only after its last day (Asia/Tashkent). */
export function periodEnded(period: string, today: string): boolean {
  return isMonth(period) && period < today.slice(0, 7);
}

/** «{Oy}ni yopish» is enabled: readiness of this very month says ready, and the month has ended. */
export function canClose(readiness: Readiness | null, period: string | null, today: string): boolean {
  return (
    readiness !== null &&
    period !== null &&
    readiness.period === period &&
    readiness.ready &&
    readiness.blockers.length === 0 &&
    periodEnded(period, today)
  );
}

/** `409 PERIOD_CLOSE_OUT_OF_ORDER` → the month the server expects (`params.expected_period`). */
export function expectedPeriodOf(error: ApiError): string | null {
  if (error.code !== "PERIOD_CLOSE_OUT_OF_ORDER") return null;
  const expected = error.params.expected_period;
  return isMonth(expected) ? expected : null;
}

/** The newest closed month of the list (20 #14 answers `period DESC`, but do not rely on the order). */
export function lastClosedOf(items: readonly PeriodClosing[]): string | null {
  let last: string | null = null;
  for (const c of items) if (isMonth(c.period) && (last === null || c.period > last)) last = c.period;
  return last;
}

// --- units ---------------------------------------------------------------------------------------------
export const closingMounted = createEvent<{ today: string }>();
export const closingReloadRequested = createEvent();
export const closingNoticeDismissed = createEvent();

export const listClosingsFx = apiFx<void, PeriodClosing[]>(async () => {
  const page = await api.accounting.listPeriodClosings({ limit: 12 });
  return page.items;
});
export const readinessFx = apiFx<string, Readiness>((period) => api.accounting.getPeriodClosingReadiness(period));
export const closePeriodFx = apiFx<string, PeriodClosing>((period) => api.accounting.closePeriod({ period }));

export const $closingToday = createStore("1970-01-01");
export const $lastClosed = createStore<string | null>(null, { skipVoid: false });
/** The oldest open month shown on the card (`null` until the closings list answered). */
export const $candidate = createStore<string | null>(null, { skipVoid: false });
export const $readiness = createStore<Readiness | null>(null, { skipVoid: false });
export const $closingStatus = createStore<LoadStatus>("idle");
export const $closingError = createStore<ApiError | null>(null, { skipVoid: false });
/** The last refused close (409 / 422) — shown on the card. */
export const $closeError = createStore<ApiError | null>(null, { skipVoid: false });
/** The month just closed (success notice). */
export const $justClosed = createStore<string | null>(null, { skipVoid: false });

export const $canClose = combine($readiness, $candidate, $closingToday, canClose);
export const $periodNotEnded = combine(
  $candidate,
  $closingToday,
  (period, today) => period !== null && !periodEnded(period, today),
);

$closingToday.on(closingMounted, (_, { today }) => today);
sample({ clock: [closingMounted, closingReloadRequested], target: listClosingsFx });
$lastClosed.on(listClosingsFx.doneData, (_, items) => lastClosedOf(items));
/** The month the card shows was (re)decided — its readiness is read every time. */
const candidateSet = createEvent<string>();
sample({
  clock: listClosingsFx.doneData,
  source: $closingToday,
  fn: (today, items) => candidatePeriod(lastClosedOf(items), today),
  target: candidateSet,
});
// The server knows the first activity month: an out-of-order answer moves the card to the expected month.
sample({
  clock: closePeriodFx.failData,
  filter: (e) => expectedPeriodOf(e) !== null,
  fn: (e) => expectedPeriodOf(e) ?? "",
  target: candidateSet,
});
$candidate.on(candidateSet, (_, period) => period);
sample({ clock: candidateSet, filter: isMonth, target: readinessFx });
const readinessLoaded = sample({
  clock: readinessFx.done,
  source: $candidate,
  filter: (current, { params }) => current === params,
  fn: (_, { result }) => result,
});
$readiness.on(readinessLoaded, (_, r) => r).reset(candidateSet);
$closingStatus
  .on([listClosingsFx, readinessFx], () => "loading")
  .on(readinessLoaded, () => "idle")
  .on([listClosingsFx.fail, readinessFx.fail], () => "error");
$closingError
  .on([listClosingsFx.failData, readinessFx.failData], (_, e) => e)
  .reset(listClosingsFx, readinessFx);

$justClosed.on(closePeriodFx.doneData, (_, c) => c.period).reset(closingNoticeDismissed, closePeriodFx);
$closeError.on(closePeriodFx.failData, (_, e) => e).reset(closePeriodFx, closingNoticeDismissed);
// Closed → the next month becomes the candidate; already closed by someone else → re-read the list.
sample({
  clock: [
    closePeriodFx.done,
    sample({ clock: closePeriodFx.failData, filter: (e) => e.code === "PERIOD_ALREADY_CLOSED" }),
  ],
  fn: () => undefined,
  target: closingReloadRequested,
});
// Not ready any more (a blocker appeared meanwhile) → the readiness is read again.
sample({
  clock: closePeriodFx.failData,
  source: $candidate,
  filter: (period, e) => isMonth(period) && e.code === "PERIOD_CLOSE_NOT_READY",
  fn: (period) => period ?? "",
  target: readinessFx,
});
