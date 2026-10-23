import { createEvent } from "effector";

import type { DashboardMountParams, DashboardPeriod } from "../types/index.ts";

export const pageMounted = createEvent<DashboardMountParams>();
export const pageUnmounted = createEvent();
export const periodChanged = createEvent<DashboardPeriod>();
/** «Qayta urinish» / «Yangilash». */
export const reloadRequested = createEvent();
