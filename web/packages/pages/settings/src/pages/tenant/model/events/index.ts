import { createEvent } from "effector";

export const pageMounted = createEvent();
export const settingsReloadRequested = createEvent();

/** «Zaxira baholash usuli» card mounted (Soliq rejimi tab) — loads the method. */
export const valuationOpened = createEvent();
/** «Qayta hisoblash navbati» status line mounted — loads the counts. */
export const recostSummaryOpened = createEvent();
