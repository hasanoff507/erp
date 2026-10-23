import { createEvent } from "effector";

/** `canTenant` = the viewer has `settings.tenant` (store-level card policy is loaded only then). */
export const pageMounted = createEvent<{ canTenant: boolean }>();
export const branchesReloadRequested = createEvent();
export const branchSelected = createEvent<string>();
export const branchDataReloadRequested = createEvent();
export const includeArchivedToggled = createEvent<boolean>();
export const verifyHintDismissed = createEvent<string>();
export const addressReminderDismissed = createEvent<string>();
