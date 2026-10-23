/**
 * Shift closing hand-over between POS-07 and POS-15 (07): POS-07 «Smenani yopish» (confirmed) → POS-15
 * counts the cash → «Davom etish (Z-hisobot)» → POS-07 sends ONE `shift.closed` (18 §3.2) and shows the
 * Z-report. Nothing is sent from POS-15 (`cash_count.recorded` does not exist).
 */
import { createEvent, createStore } from "effector";

import type { Money } from "@shared/lib/money";

import { shiftClosedLocally } from "./index.ts";

export interface ShiftCount {
  shiftId: string;
  countedCash: Money;
  /** Terminalsiz (manual) card payments of the shift — the device computes it (18 §3.2). */
  countedCardTotal: Money | null;
  varianceNote: string | null;
  expectedCash: Money;
  variance: Money;
}

/** «Smenani yopasizmi? Keyin qayta ocholmaysiz» confirmed for this shift id. */
export const shiftCloseConfirmed = createEvent<string>();
export const shiftCloseCancelled = createEvent();
export const shiftCountSaved = createEvent<ShiftCount>();

export const $closeConfirmedFor = createStore<string | null>(null, { skipVoid: false })
  .on(shiftCloseConfirmed, (_, id) => id)
  .reset([shiftCloseCancelled, shiftClosedLocally]);
export const $shiftCount = createStore<ShiftCount | null>(null, { skipVoid: false })
  .on(shiftCountSaved, (_, c) => c)
  .reset([shiftCloseCancelled, shiftClosedLocally]);
