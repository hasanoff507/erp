/** BO-09 wiring — sample() only (24 §2). */
import { combine, sample } from "effector";

import { listRegistersFx, listVatReturnsFx, loadHistoryFx, loadShiftFx } from "../effects/index.ts";
import {
  historyReloadRequested,
  pageMounted,
  rangeChanged,
  registerChanged,
  reportOpened,
  shiftReloadRequested,
  shiftSelected,
  vatMoreRequested,
  vatPeriodChanged,
  vatReloadRequested,
} from "../events/index.ts";
import { historyTotals, isRangeValid, quickRange, sameRange } from "../lib/index.ts";
import {
  $history,
  $historyError,
  $historyStatus,
  $movements,
  $range,
  $registerId,
  $registers,
  $registersError,
  $report,
  $shift,
  $shiftError,
  $shiftId,
  $shiftStatus,
  $today,
  $vatCursor,
  $vatError,
  $vatMoves,
  $vatPeriod,
  $vatStatus,
} from "../stores/index.ts";
import type { HistoryRequest } from "../types/index.ts";

export const $historyTotals = $history.map(historyTotals);
export const $rangeInvalid = $range.map((r) => !isRangeValid(r));
export const $vatMoreLoading = combine(
  listVatReturnsFx.pending,
  $vatStatus,
  (pending, status) => pending && status !== "loading",
);

// --- mount -------------------------------------------------------------------------------------------
$today.on(pageMounted, (_, { today }) => today);
$range.on(pageMounted, (_, { today }) => quickRange("month", today));
$vatPeriod.on(pageMounted, (_, { today }) => today.slice(0, 7));
$report.on(reportOpened, (_, report) => report);

// --- «Kassa / smena tarixi» --------------------------------------------------------------------------
sample({
  clock: reportOpened,
  source: $registers,
  filter: (registers, report) => report === "cash-history" && registers.length === 0,
  fn: () => undefined,
  target: listRegistersFx,
});
$registers.on(listRegistersFx.doneData, (_, list) => list);
$registersError.on(listRegistersFx.failData, (_, e) => e).reset(listRegistersFx);
// The first register is chosen by default (the report needs one).
sample({
  clock: listRegistersFx.doneData,
  source: $registerId,
  filter: (current, list) => list.length > 0 && (current === null || !list.some((r) => r.id === current)),
  fn: (_, list) => list[0]?.id ?? "",
  target: registerChanged,
});
$registerId.on(registerChanged, (_, id) => id);
$range.on(rangeChanged, (_, range) => range);

const historyRequest = (registerId: string | null, range: { from: string; to: string }) =>
  registerId !== null && isRangeValid(range);
sample({
  clock: [registerChanged, rangeChanged, historyReloadRequested],
  source: { registerId: $registerId, range: $range },
  filter: ({ registerId, range }) => historyRequest(registerId, range),
  fn: ({ registerId, range }): HistoryRequest => ({ registerId: registerId ?? "", range }),
  target: loadHistoryFx,
});
// The register's history is shown again when the report is reopened.
sample({
  clock: reportOpened,
  source: { registerId: $registerId, range: $range },
  filter: ({ registerId, range }, report) => report === "cash-history" && historyRequest(registerId, range),
  fn: ({ registerId, range }): HistoryRequest => ({ registerId: registerId ?? "", range }),
  target: loadHistoryFx,
});

// Answers for another register / period are dropped.
const historyLoaded = sample({
  clock: loadHistoryFx.done,
  source: { registerId: $registerId, range: $range },
  filter: ({ registerId, range }, { params }) =>
    registerId === params.registerId && sameRange(range, params.range),
  fn: (_, { result }) => result,
});
$history.on(historyLoaded, (_, rows) => rows);
$historyStatus
  .on(loadHistoryFx, () => "loading")
  .on(historyLoaded, () => "idle")
  .on(loadHistoryFx.fail, () => "error");
$historyError.on(loadHistoryFx.failData, (_, e) => e).reset(loadHistoryFx);
// An invalid range or another register empties the table and closes the shift panel.
sample({ clock: [registerChanged, rangeChanged], fn: () => [], target: $history });
$shiftId.on(shiftSelected, (_, id) => id).reset(registerChanged, rangeChanged);

// --- shift panel (z-report / running totals + cash movements) ------------------------------------------
sample({
  clock: [shiftSelected, sample({ clock: shiftReloadRequested, source: $shiftId })],
  filter: (id): id is string => id !== null,
  target: loadShiftFx,
});
const shiftLoaded = sample({
  clock: loadShiftFx.done,
  source: $shiftId,
  filter: (current, { params }) => current === params,
  fn: (_, { result }) => result,
});
$shift.on(shiftLoaded, (_, { shift }) => shift).reset(shiftSelected, registerChanged, rangeChanged);
$movements
  .on(shiftLoaded, (_, { movements }) => movements)
  .reset(shiftSelected, registerChanged, rangeChanged);
$shiftStatus
  .on(loadShiftFx, () => "loading")
  .on(shiftLoaded, () => "idle")
  .on(loadShiftFx.fail, () => "error");
$shiftError.on(loadShiftFx.failData, (_, e) => e).reset(loadShiftFx);

// --- «QQS registri (qaytarishlar bilan)» -------------------------------------------------------------
$vatPeriod.on(vatPeriodChanged, (_, period) => period);
sample({
  clock: [
    sample({ clock: reportOpened, filter: (r) => r === "vat-returns" }),
    vatPeriodChanged,
    vatReloadRequested,
  ],
  source: $vatPeriod,
  fn: (period) => ({ period, cursor: null }),
  target: listVatReturnsFx,
});
sample({
  clock: vatMoreRequested,
  source: { period: $vatPeriod, cursor: $vatCursor, pending: listVatReturnsFx.pending },
  filter: ({ cursor, pending }) => cursor !== null && !pending,
  fn: ({ period, cursor }) => ({ period, cursor }),
  target: listVatReturnsFx,
});
const vatLoaded = sample({
  clock: listVatReturnsFx.done,
  source: $vatPeriod,
  filter: (period, { params }) => period === params.period,
  fn: (_, payload) => payload,
});
$vatMoves.on(vatLoaded, (list, { params, result }) =>
  params.cursor ? [...list, ...result.items] : result.items,
);
$vatCursor.on(vatLoaded, (_, { result }) => result.next_cursor);
$vatStatus
  .on(listVatReturnsFx, (status, { cursor }) => (cursor === null ? "loading" : status))
  .on(vatLoaded, () => "idle")
  .on(listVatReturnsFx.fail, (status, { params }) => (params.cursor === null ? "error" : status));
$vatError.on(listVatReturnsFx.failData, (_, e) => e).reset(listVatReturnsFx);
