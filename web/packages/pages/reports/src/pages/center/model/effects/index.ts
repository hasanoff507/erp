/**
 * BO-09 effects — generated clients only: `api.branches.cashRegistersList`, `api.cash.getCashHistory`
 * (20 #55), `api.cash.getShift` (z_report when closed / running totals while open),
 * `api.cash.listCashMovements` (18 §13.3), `api.tax.listVatMoves` (20 #2).
 */
import { createEffect } from "effector";

import { api, toApiError, type ApiError } from "@shared/api";

import { toVatReturnsParams } from "../lib/index.ts";
import type {
  CashMovement,
  CashRegister,
  HistoryRequest,
  Shift,
  ShiftRow,
  VatMovePage,
  VatReturnsRequest,
} from "../types/index.ts";

function wrap<P, R>(fn: (params: P) => Promise<R>) {
  return createEffect<P, R, ApiError>(async (params) => {
    try {
      return await fn(params);
    } catch (e) {
      throw toApiError(e);
    }
  });
}

export const listRegistersFx = wrap<void, CashRegister[]>(async () => {
  const { items } = await api.branches.cashRegistersList();
  return items;
});

export const loadHistoryFx = wrap<HistoryRequest, ShiftRow[]>(async ({ registerId, range }) => {
  const { items } = await api.cash.getCashHistory(registerId, { date_from: range.from, date_to: range.to });
  return items;
});

/** The shift (z_report when closed, running totals while open) and its cash movements («kim, nega»). */
export const loadShiftFx = wrap<string, { shift: Shift; movements: CashMovement[] }>(async (shiftId) => {
  const [shift, movements] = await Promise.all([
    api.cash.getShift(shiftId),
    api.cash.listCashMovements({ shift_id: shiftId, limit: 200 }),
  ]);
  return { shift, movements: movements.items };
});

export const listVatReturnsFx = wrap<VatReturnsRequest, VatMovePage>((req) =>
  api.tax.listVatMoves(toVatReturnsParams(req)),
);
