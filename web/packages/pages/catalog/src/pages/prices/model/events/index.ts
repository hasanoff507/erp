import { createEvent } from "effector";

import type { PriceScope } from "../types/index.ts";

export const pageMounted = createEvent();
export const searchChanged = createEvent<string>();
export const categoryChanged = createEvent<string | null>();
export const pageChanged = createEvent<number>();
export const listRefreshRequested = createEvent();

/** `newPrice` of one row (decimal string from MoneyInput, "" = no change). */
export const draftChanged = createEvent<{ productId: string; value: string }>();
/** «Bekor qilish» — drop every edited price. */
export const draftsReset = createEvent();
/** `effectiveFrom` (YYYY-MM-DD, ≥ today) — one date for the whole document (07 BO-05). */
export const effectiveFromChanged = createEvent<string>();
export const scopeChanged = createEvent<PriceScope>();

/** Right panel: the product whose history / nameRu is shown. */
export const productSelected = createEvent<string>();
export const historyMoreRequested = createEvent();

/** «Saqlash» (Ctrl+S). */
export const saveRequested = createEvent();
export const resultDismissed = createEvent();
