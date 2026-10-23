import { createEvent } from "effector";

import type { BalancesView, StockMountParams, StockTab } from "../types/index.ts";

export const pageMounted = createEvent<StockMountParams>();
export const tabChanged = createEvent<StockTab>();

/** «Qidirish» (debounced by SearchInput, max 64). */
export const searchChanged = createEvent<string>();
/** «Faqat kam qoldiq» → `low_stock=true`. */
export const lowOnlyToggled = createEvent<boolean>();
/** «Muddati 7 kunda tugaydi» → lots view (`GET /stock-lots?expiring_within_days=7`). */
export const viewChanged = createEvent<BalancesView>();
export const moreRequested = createEvent();
export const reloadRequested = createEvent();
export const lotsMoreRequested = createEvent();
/** KPI cards, banner and tab badges are read again (after a write, «Yangilash»). */
export const summaryRefreshRequested = createEvent();
