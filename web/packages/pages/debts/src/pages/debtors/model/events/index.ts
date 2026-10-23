import { createEvent } from "effector";

import type { DebtorTab, Direction } from "#/entities/debtor/index.ts";

import type { DebtorsMountParams } from "../types/index.ts";

export const pageMounted = createEvent<DebtorsMountParams>();
export const directionChanged = createEvent<Direction>();
export const tabChanged = createEvent<DebtorTab>();
/** «Mijoz qidirish» — name words or phone digits (client-side over the loaded rows). */
export const searchChanged = createEvent<string>();
export const pageChanged = createEvent<number>();
export const rowSelected = createEvent<string | null>();
export const reloadRequested = createEvent();
