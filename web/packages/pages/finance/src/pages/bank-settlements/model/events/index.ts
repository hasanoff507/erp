import { createEvent } from "effector";

import type { BankMountParams, SettlementFilters } from "../types/index.ts";

export const pageMounted = createEvent<BankMountParams>();
export const filtersChanged = createEvent<Partial<SettlementFilters>>();
export const moreRequested = createEvent();
export const reloadRequested = createEvent();
export const transitReloadRequested = createEvent();
/** Route `:id` (a document) / `new` / nothing. */
export const settlementOpened = createEvent<string | null>();
export const detailReloadRequested = createEvent();
export const importResultDismissed = createEvent();
/** «Qoralamalarni ko'rish» after an import. */
export const importedDraftsShown = createEvent();
