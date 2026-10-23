import { createEvent } from "effector";

import type { ExpenseFilters, ExpensesMountParams, ExpensesTab, Notice } from "../types/index.ts";

export const pageMounted = createEvent<ExpensesMountParams>();
export const tabChanged = createEvent<ExpensesTab>();
export const filtersChanged = createEvent<Partial<ExpenseFilters>>();
export const moreRequested = createEvent();
export const reloadRequested = createEvent();
export const categoriesReloadRequested = createEvent();
export const rulesReloadRequested = createEvent();
/** «Keyinroq» on a due reminder — hidden for this visit (the cron reminds again tomorrow). */
export const ruleSnoozed = createEvent<string>();
export const noticeShown = createEvent<Notice>();
export const noticeDismissed = createEvent();
export const actionErrorDismissed = createEvent();
