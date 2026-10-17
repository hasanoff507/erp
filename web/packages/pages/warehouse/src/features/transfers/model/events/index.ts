import { createEvent } from "effector";

import type { Transfer, TransferStatus } from "../types/index.ts";

/** «Ko'chirishlar» tab opened (first page with the current filter). */
export const transfersOpened = createEvent();
export const filterChanged = createEvent<TransferStatus | null>();
export const moreRequested = createEvent();
export const reloadRequested = createEvent();
/** Detail sheet of one transfer (`null` closes it). */
export const transferSelected = createEvent<string | null>();
/** «Yangilash» of one transfer (e.g. waiting for the e-TTN registration). */
export const transferRefreshRequested = createEvent<string>();
export const actionErrorDismissed = createEvent();
export const noticeDismissed = createEvent();
/** Row / detail «O'tkazish» — ignored while any transfer write is in flight (WEB-16). */
export const postRequested = createEvent<string>();
/** Open the detail of a transfer read elsewhere (the «Qoldiq» digest) — it need not be in the list. */
export const transferShown = createEvent<Transfer>();
