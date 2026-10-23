import { createEvent } from "effector";

import type { TelegramMountParams } from "../types/index.ts";

export const pageMounted = createEvent<TelegramMountParams>();
export const pageUnmounted = createEvent();

// «Telegram akkaunt»
/** «Telegramni ulash» / «Boshqa akkauntni ulash» / «Yangi havola» / «Qayta urinish». */
export const linkStartRequested = createEvent();
/** «Uzish» (after the confirmation dialog). */
export const unlinkRequested = createEvent();
export const statusReloadRequested = createEvent();

// «Ogohlantirishlar» / «Kunlik hisobot»
export const kindToggled = createEvent<{ kind: string; enabled: boolean }>();
export const dailyTimeChanged = createEvent<string>();
/** «Bekor qilish» — back to the saved settings. */
export const draftReset = createEvent();
/** «Saqlash». */
export const saveRequested = createEvent();
export const settingsReloadRequested = createEvent();

// Log
export const logMoreRequested = createEvent();
export const logReloadRequested = createEvent();
