import { createEvent } from "effector";

import type { JournalFilters, JournalMountParams, RecostStatus } from "../types/index.ts";

export const pageMounted = createEvent<JournalMountParams>();

/** A filter control changed (partial patch); the list reloads from the first page. */
export const filtersChanged = createEvent<Partial<JournalFilters>>();
/** «Filtrlarni tozalash» — back to the current month, all accounts and documents. */
export const filtersReset = createEvent();
/** Filters actually applied (internal: mount, change, reset) — one list request per application. */
export const filtersApplied = createEvent<JournalFilters>();
/** «Yana yuklash» — next cursor page. */
export const moreRequested = createEvent();
/** ErrorState «Qayta urinish». */
export const reloadRequested = createEvent();

/** «Qayta hisoblash navbati»: status filter (`null` = all). */
export const recostFilterChanged = createEvent<RecostStatus | null>();
export const recostMoreRequested = createEvent();
export const recostReloadRequested = createEvent();
/** «Qayta urinish» of a failed job. */
export const recostRetryRequested = createEvent<string>();
export const recostRetryDismissed = createEvent();
