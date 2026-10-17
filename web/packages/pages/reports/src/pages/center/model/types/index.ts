import type {
  CashHistoryItem,
  CashMovementOut,
  CashRegisterOut,
  ShiftOut,
  VatMoveOut,
  VatMovePage,
} from "@shared/models";

export type ShiftRow = CashHistoryItem;
export type CashMovement = CashMovementOut;
export type CashRegister = CashRegisterOut;
export type Shift = ShiftOut;
export type VatMove = VatMoveOut;
export type { VatMovePage };

/**
 * 07 BO-09 catalogue. Bosqich 3 builds «Kassa / smena tarixi» (US-M16-03, `GET /cash-registers/{id}/
 * cash-history`) and «QQS registri (qaytarishlar bilan)» (`GET /vat-moves?doc_type=returns`, `tax.vat.view`);
 * the other reports are later stages («Tez orada»).
 */
export type ReportKey = "cash-history" | "vat-returns";
export const REPORT_KEYS: readonly ReportKey[] = ["cash-history", "vat-returns"];

export type LoadStatus = "idle" | "loading" | "error";

/** 07 BO-09 quick period buttons. */
export type QuickRange = "today" | "week" | "month";
export const QUICK_RANGES: readonly QuickRange[] = ["today", "week", "month"];

export interface DateRange {
  /** `YYYY-MM-DD` (inclusive). */
  from: string;
  to: string;
}

export interface HistoryRequest {
  registerId: string;
  range: DateRange;
}

export interface VatReturnsRequest {
  period: string;
  cursor: string | null;
}

export interface CenterMountParams {
  /** Local date `YYYY-MM-DD`. */
  today: string;
}

/** Σ of the shown shifts (decimal strings). */
export interface HistoryTotals {
  openingCash: string;
  cashSales: string;
  cashIn: string;
  cashOut: string;
  variance: string;
}

export const VAT_PAGE_SIZE = 50;
