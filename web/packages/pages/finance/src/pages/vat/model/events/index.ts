import { createEvent } from "effector";

import type { MoveDocType, MoveKind, PeriodKey, VatMountParams } from "../types/index.ts";

export const pageMounted = createEvent<VatMountParams>();
/** «Davr» — a month `YYYY-MM` or a quarter `YYYY-Qn`. */
export const periodChanged = createEvent<PeriodKey>();
/** ErrorState «Qayta urinish» of the summary. */
export const summaryReloadRequested = createEvent();

/** QQS registri filters (20 #2). */
export const movesKindChanged = createEvent<MoveKind | null>();
export const movesDocTypeChanged = createEvent<MoveDocType | null>();
export const movesMoreRequested = createEvent();
export const movesReloadRequested = createEvent();
