import { createEvent } from "effector";

import type { CenterMountParams, DateRange, ReportKey } from "../types/index.ts";

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
