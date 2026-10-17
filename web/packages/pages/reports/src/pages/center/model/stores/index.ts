import { createStore } from "effector";

import type { ApiError } from "@shared/api";

import type {
  CashMovement,
  CashRegister,
  DateRange,
  LoadStatus,
  ReportKey,
  Shift,
  ShiftRow,
  VatMove,
} from "../types/index.ts";

export const $today = createStore("1970-01-01");
export const $report = createStore<ReportKey | null>(null, { skipVoid: false });

// --- «Kassa / smena tarixi» --------------------------------------------------------------------------
export const $registers = createStore<CashRegister[]>([]);
export const $registersError = createStore<ApiError | null>(null, { skipVoid: false });
export const $registerId = createStore<string | null>(null, { skipVoid: false });
export const $range = createStore<DateRange>({ from: "1970-01-01", to: "1970-01-01" });
export const $history = createStore<ShiftRow[]>([]);
export const $historyStatus = createStore<"idle" | "loading" | "error">("idle");
export const $historyError = createStore<ApiError | null>(null, { skipVoid: false });

export const $shiftId = createStore<string | null>(null, { skipVoid: false });
export const $shift = createStore<Shift | null>(null, { skipVoid: false });
export const $movements = createStore<CashMovement[]>([]);
export const $shiftStatus = createStore<LoadStatus>("idle");
export const $shiftError = createStore<ApiError | null>(null, { skipVoid: false });

// --- «QQS registri (qaytarishlar bilan)» -------------------------------------------------------------
export const $vatPeriod = createStore("1970-01");
export const $vatMoves = createStore<VatMove[]>([]);
export const $vatCursor = createStore<string | null>(null, { skipVoid: false });
export const $vatStatus = createStore<LoadStatus>("idle");
export const $vatError = createStore<ApiError | null>(null, { skipVoid: false });
