/**
 * BO-09 effects — generated clients only: `api.branches.cashRegistersList`, `api.cash.getCashHistory`
 * (20 #55), `api.cash.getShift` (z_report when closed / running totals while open),
 * `api.cash.listCashMovements` (18 §13.3), `api.tax.listVatMoves` (20 #2); Bosqich 4 — `api.reports.*`
 * (sales, top-products, stock, profit-and-loss, discounts, debts-aging).
 */
import { createEffect } from "effector";

import { api, toApiError, type ApiError } from "@shared/api";

import { toVatReturnsParams } from "../lib/index.ts";
import {
  TOP_LIMIT,
  type CashMovement,
  type CashRegister,
  type HistoryRequest,
  type ReportData,
  type ReportRequest,
  type Shift,
  type ShiftRow,
  type VatMovePage,
  type VatReturnsRequest,
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

/** The open `/reports/*` report (20 #12, #18, #19, #19a, #20, #21). */
export const loadReportFx = wrap<ReportRequest, ReportData>(async (req) => {
  const branch = req.branchId ? { branch_id: req.branchId } : {};
  switch (req.kind) {
    case "sales":
      return {
        kind: "sales",
        data: await api.reports.getSales({
          date_from: req.range.from,
          date_to: req.range.to,
          group_by: req.report === "cashier-sales" ? "cashier" : "day",
          ...branch,
        }),
      };
    case "top-products":
      return {
        kind: "top-products",
        data: await api.reports.getTopProducts({
          date_from: req.range.from,
          date_to: req.range.to,
          order: req.order,
          limit: TOP_LIMIT,
          ...branch,
        }),
      };
    case "stock":
      return {
        kind: "stock",
        data: await api.reports.getStock({
          ...branch,
          ...(req.belowMinOnly ? { below_min_only: true } : {}),
          ...(req.search ? { search: req.search } : {}),
        }),
      };
    case "profit-and-loss":
      return {
        kind: "profit-and-loss",
        data: await api.reports.getProfitAndLoss({
          date_from: req.range.from,
          date_to: req.range.to,
          ...branch,
        }),
      };
    case "discounts":
      return {
        kind: "discounts",
        data: await api.reports.getDiscounts({
          date_from: req.range.from,
          date_to: req.range.to,
          group_by: req.groupBy,
          ...branch,
        }),
      };
    case "debts-aging":
      return {
        kind: "debts-aging",
        data: await api.reports.getDebtsAging({ direction: req.direction, as_of: req.asOf, ...branch }),
      };
  }
});
