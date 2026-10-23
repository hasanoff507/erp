import type {
  CountCreate,
  CountLineIn,
  CountLineOut,
  CountOut,
  CountOutStatus,
  CountPage,
  CountPostOut,
  CountSummary,
} from "@shared/models";

export type Count = CountOut;
export type CountLine = CountLineOut;
export type CountStatus = CountOutStatus;
export type { CountCreate, CountLineIn, CountPage, CountPostOut, CountSummary };

/** «Inventarizatsiyalar» filter: `review` by default (07 BO-03 — farqni tasdiqlash navbati). */
export const COUNT_STATUSES: readonly CountStatus[] = ["review", "counting", "posted", "cancelled"];
export const DEFAULT_COUNT_FILTER: CountStatus = "review";

export type LoadStatus = "idle" | "loading" | "error";

export interface ListRequest {
  /** The current branch's warehouse (WEB-04: counts of other warehouses are not listed). */
  warehouseId: string | null;
  status: CountStatus | null;
  cursor: string | null;
}

export interface RecordLinesParams {
  id: string;
  lines: CountLineIn[];
}

export interface PostCountParams {
  id: string;
  /** `?treat_uncounted_as_zero=true` after 422 COUNT_LINES_INCOMPLETE (19 §14). */
  treatUncountedAsZero: boolean;
}

export interface CancelParams {
  id: string;
  reason: string;
}

/** A product found during the count that is not in the snapshot (added via POST /lines). */
export interface ExtraLine {
  productId: string;
  name: string;
}

/** Detail lines view (07 POS-10 tabs: Hammasi / Farqli / Sanalmagan). */
export type LineFilter = "all" | "diff" | "uncounted";

export interface CountTotals {
  /** Σ |amount| of shortage lines (2 dp). */
  shortage: string;
  /** Σ amount of surplus lines (2 dp). */
  surplus: string;
  uncounted: number;
  diffLines: number;
}

export const COUNT_PAGE_SIZE = 50;
