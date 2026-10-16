import { createEvent } from "effector";

import type { DashboardPeriod } from "../types/index.ts";

export const pageMounted = createEvent();
export const periodChanged = createEvent<DashboardPeriod>();
