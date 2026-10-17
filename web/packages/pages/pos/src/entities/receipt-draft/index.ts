/** Open receipt of the POS sale panel (07 POS-02) — store, events and the receipt arithmetic. */
import { $draft } from "./model/stores/index.ts";
import { priceLines } from "./model/lib/calc.ts";

export * from "./model/stores/index.ts";
export * from "./model/lib/calc.ts";
export type * from "./model/types/index.ts";

/** Lines with their computed amounts and the receipt totals. */
export const $totals = $draft.map((d) => priceLines(d.lines, d.discount));
