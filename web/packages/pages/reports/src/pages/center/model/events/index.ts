import { createEvent } from "effector";

import type {
  AgingDirection,
  CenterMountParams,
  DateRange,
  DiscountsGroupBy,
  ReportKey,
  TopOrder,
} from "../types/index.ts";

export const pageMounted = createEvent<CenterMountParams>();
/** The report chosen in the catalogue (`?report=`), `null` — the catalogue only. */
export const reportOpened = createEvent<ReportKey | null>();

// «Kassa / smena tarixi»
export const registerChanged = createEvent<string>();
export const rangeChanged = createEvent<DateRange>();
export const historyReloadRequested = createEvent();
/** A shift row opened in the side panel (`null` closes it). */
export const shiftSelected = createEvent<string | null>();
export const shiftReloadRequested = createEvent();

// «QQS registri (qaytarishlar bilan)»
export const vatPeriodChanged = createEvent<string>();
export const vatMoreRequested = createEvent();
export const vatReloadRequested = createEvent();

// Bosqich 4 reports (`/reports/*`): shared branch filter + per-report options.
/** «Filial» filter (`null` = «Barcha filiallar»). */
export const branchFilterChanged = createEvent<string | null>();
export const topOrderChanged = createEvent<TopOrder>();
export const discountsGroupByChanged = createEvent<DiscountsGroupBy>();
export const agingDirectionChanged = createEvent<AgingDirection>();
/** «Ombor qoldig'i» search (debounced by SearchInput, ≤ 64). */
export const stockSearchChanged = createEvent<string>();
export const reportReloadRequested = createEvent();
