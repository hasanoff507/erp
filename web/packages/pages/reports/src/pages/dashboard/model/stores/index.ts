import { createStore } from "effector";

import type { DashboardPeriod } from "../types/index.ts";

/** Default "Bugun" (07 BO-02). */
export const $period = createStore<DashboardPeriod>("today");
