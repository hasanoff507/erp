import { allSettled, fork } from "effector";
import { describe, expect, it } from "vitest";

import {
  $history,
  $historyTotals,
  $movements,
  $range,
  $rangeInvalid,
  $registerId,
  $reportData,
  $reportRequest,
  $shift,
  $vatMoves,
  DEFAULT_OPTIONS,
  agingDirectionChanged,
  branchFilterChanged,
  discountsGroupByChanged,
  loadReportFx,
  lostMargin,
  reportRequest,
  requestKey,
  stockSearchChanged,
  topOrderChanged,
  type ReportData,
  type ReportRequest,
  historyTotals,
  isRangeValid,
  lastMonths,
  listRegistersFx,
  listVatReturnsFx,
  loadHistoryFx,
  loadShiftFx,
  matchQuickRange,
  pageMounted,
  quickRange,
  rangeChanged,
  registerChanged,
  reportOpened,
  shiftSelected,
  vatPeriodChanged,
  type CashRegister,
  type HistoryRequest,
  type Shift,
  type ShiftRow,
  type VatReturnsRequest,
} from "./index.ts";

const TODAY = "2026-10-17";

function row(no: number, patch: Partial<ShiftRow> = {}): ShiftRow {
  return {
    shift_id: `sh-${no}`,
    shift_no: no,
    status: "closed",
    opened_at: "2026-10-16T03:00:00Z",
    closed_at: "2026-10-16T15:00:00Z",
    opening_cash: "200000.00",
    cash_sales: "1450000.00",
    cash_in: "50000.00",
    cash_out: "300000.00",
    expected_cash: "1400000.00",
    counted_cash: "1395000.00",
    variance: "-5000.00",
    variance_note: "Qaytim xatosi",
    counted_card_total: "820000.00",
    ...patch,
  };
}

function register(id: string): CashRegister {
  return {
    id,
    branch_id: "b-1",
    name: `Kassa ${id}`,
    kind: "web",
    fiscal_module_id: null,
    txkm_contract_ref: null,
    fiscal_agent_id: null,
    fiscal_local_device_id: null,
    ofd_status: "active",
    fm_state: "ok",
    last_unacked_receipt_at: null,
    fm_receipts_pending: null,
    tax_registered_at: null,
    archived_at: null,
    version: 1,
  };
}

const shift = { id: "sh-1", shift_no: 1, status: "closed" } as unknown as Shift;

function scope() {
  const historyCalls: HistoryRequest[] = [];
  const vatCalls: VatReturnsRequest[] = [];
  const s = fork({
    handlers: [
      [listRegistersFx, () => [register("cr-1"), register("cr-2")]],
      [
        loadHistoryFx,
        (req: HistoryRequest) => {
          historyCalls.push(req);
          return req.registerId === "cr-1"
            ? [row(1), row(2, { status: "open", closed_at: null, counted_cash: null, variance: null })]
            : [];
        },
      ],
      [loadShiftFx, () => ({ shift, movements: [] })],
      [
        listVatReturnsFx,
        (req: VatReturnsRequest) => {
          vatCalls.push(req);
          return { items: [], next_cursor: null };
        },
      ],
    ],
  });
  return { s, historyCalls, vatCalls };
}

describe("BO-09 «Kassa / smena tarixi» (US-M16-03, QT-M16-04)", () => {
  it("opening the report picks the first register and loads this month's shifts", async () => {
    const { s, historyCalls } = scope();
    await allSettled(pageMounted, { scope: s, params: { today: TODAY } });
    await allSettled(reportOpened, { scope: s, params: "cash-history" });
    expect(s.getState($registerId)).toBe("cr-1");
    expect(historyCalls).toEqual([{ registerId: "cr-1", range: { from: "2026-10-01", to: TODAY } }]);
    expect(s.getState($history)).toHaveLength(2);
    expect(s.getState($historyTotals)).toEqual({
      openingCash: "400000.00",
      cashSales: "2900000.00",
      cashIn: "100000.00",
      cashOut: "600000.00",
      variance: "-5000.00",
    });
  });

  it("a shift row opens its panel; another register closes it; an inverted range is not sent", async () => {
    const { s, historyCalls } = scope();
    await allSettled(pageMounted, { scope: s, params: { today: TODAY } });
    await allSettled(reportOpened, { scope: s, params: "cash-history" });
    await allSettled(shiftSelected, { scope: s, params: "sh-1" });
    expect(s.getState($shift)?.id).toBe("sh-1");
    expect(s.getState($movements)).toEqual([]);

    await allSettled(registerChanged, { scope: s, params: "cr-2" });
    expect(s.getState($shift)).toBeNull();
    expect(historyCalls.at(-1)?.registerId).toBe("cr-2");

    const sent = historyCalls.length;
    await allSettled(rangeChanged, { scope: s, params: { from: "2026-10-10", to: "2026-10-01" } });
    expect(s.getState($rangeInvalid)).toBe(true);
    expect(historyCalls).toHaveLength(sent);
    expect(s.getState($history)).toEqual([]);
  });

  it("«QQS registri (qaytarishlar bilan)» asks for doc_type=returns of the chosen month", async () => {
    const { s, vatCalls } = scope();
    await allSettled(pageMounted, { scope: s, params: { today: TODAY } });
    await allSettled(reportOpened, { scope: s, params: "vat-returns" });
    await allSettled(vatPeriodChanged, { scope: s, params: "2026-09" });
    expect(vatCalls).toEqual([
      { period: "2026-10", cursor: null },
      { period: "2026-09", cursor: null },
    ]);
    expect(s.getState($vatMoves)).toEqual([]);
  });
});

describe("BO-09 lib", () => {
  it("quick ranges, matching, validity, months", () => {
    expect(quickRange("today", TODAY)).toEqual({ from: TODAY, to: TODAY });
    expect(quickRange("week", TODAY)).toEqual({ from: "2026-10-11", to: TODAY });
    expect(quickRange("month", TODAY)).toEqual({ from: "2026-10-01", to: TODAY });
    expect(matchQuickRange({ from: "2026-10-11", to: TODAY }, TODAY)).toBe("week");
    expect(matchQuickRange({ from: "2026-09-11", to: TODAY }, TODAY)).toBeNull();
    expect(isRangeValid({ from: "2026-10-01", to: "" })).toBe(false);
    expect(lastMonths(TODAY, 3)).toEqual(["2026-10", "2026-09", "2026-08"]);
    expect(historyTotals([]).variance).toBe("0.00");
  });

  it("the range store starts at «Oy»", async () => {
    const { s } = scope();
    await allSettled(pageMounted, { scope: s, params: { today: TODAY } });
    expect(s.getState($range)).toEqual({ from: "2026-10-01", to: TODAY });
  });
});

describe("BO-09 Bosqich 4 reports (`/reports/*`)", () => {
  function reportsScope() {
    const calls: ReportRequest[] = [];
    const s = fork({
      handlers: [
        [
          loadReportFx,
          (req: ReportRequest): ReportData => {
            calls.push(req);
            if (req.kind === "sales") {
              const row = {
                group_key: "2026-10-17",
                group_label: null,
                total_sales: "100.00",
                gross_sales: "100.00",
                returns_total: "0.00",
                receipt_count: 1,
                avg_receipt: "100.00",
              };
              return {
                kind: "sales",
                data: {
                  date_from: req.range.from,
                  date_to: req.range.to,
                  branch_id: req.branchId,
                  group_by: req.report === "cashier-sales" ? "cashier" : "day",
                  rows: [row],
                  total: row,
                  unsynced_devices: 0,
                  data_complete: true,
                },
              };
            }
            return {
              kind: "stock",
              data: {
                branch_id: req.branchId,
                consolidated: req.branchId === null,
                items: [],
                branches: [],
                total: { value: "0.00", positions: 0, below_min_count: 0 },
              },
            };
          },
        ],
      ],
    });
    return { s, calls };
  }

  it("QT-M12-01: «Kunlik savdo» asks group_by=day for the period and the topbar branch", async () => {
    const { s, calls } = reportsScope();
    await allSettled(pageMounted, { scope: s, params: { today: TODAY, branchId: "b-1" } });
    await allSettled(reportOpened, { scope: s, params: "daily-sales" });
    expect(calls).toEqual([
      { kind: "sales", report: "daily-sales", range: { from: "2026-10-01", to: TODAY }, branchId: "b-1" },
    ]);
    expect(s.getState($reportData)?.kind).toBe("sales");

    // «Barcha filiallar» → consolidated (no branch_id); «Bugun».
    await allSettled(branchFilterChanged, { scope: s, params: null });
    await allSettled(rangeChanged, { scope: s, params: quickRange("today", TODAY) });
    expect(calls.at(-1)).toEqual({
      kind: "sales",
      report: "daily-sales",
      range: { from: TODAY, to: TODAY },
      branchId: null,
    });
  });

  it("QT-M12-02 / QT-M04-03 / QT-M03-03 requests: top order, stock (below-min), discounts grouping, aging as-of", async () => {
    const { s, calls } = reportsScope();
    await allSettled(pageMounted, { scope: s, params: { today: TODAY } });
    await allSettled(reportOpened, { scope: s, params: "top-products" });
    await allSettled(topOrderChanged, { scope: s, params: "bottom" });
    expect(calls.at(-1)).toMatchObject({ kind: "top-products", order: "bottom", branchId: null });

    await allSettled(reportOpened, { scope: s, params: "low-stock" });
    expect(calls.at(-1)).toEqual({ kind: "stock", branchId: null, belowMinOnly: true, search: "" });
    await allSettled(stockSearchChanged, { scope: s, params: " Non " });
    expect(calls.at(-1)).toEqual({ kind: "stock", branchId: null, belowMinOnly: true, search: "Non" });

    await allSettled(reportOpened, { scope: s, params: "discounts" });
    await allSettled(discountsGroupByChanged, { scope: s, params: "product" });
    expect(calls.at(-1)).toMatchObject({ kind: "discounts", groupBy: "product" });

    await allSettled(reportOpened, { scope: s, params: "debts-aging" });
    await allSettled(agingDirectionChanged, { scope: s, params: "payable" });
    expect(calls.at(-1)).toEqual({ kind: "debts-aging", asOf: TODAY, branchId: null, direction: "payable" });

    await allSettled(reportOpened, { scope: s, params: "profit-and-loss" });
    expect(calls.at(-1)).toEqual({
      kind: "profit-and-loss",
      range: { from: "2026-10-01", to: TODAY },
      branchId: null,
    });
  });

  it("an inverted period sends nothing; the old answer is not shown for new filters", async () => {
    const { s, calls } = reportsScope();
    await allSettled(pageMounted, { scope: s, params: { today: TODAY } });
    await allSettled(reportOpened, { scope: s, params: "daily-sales" });
    const sent = calls.length;
    await allSettled(rangeChanged, { scope: s, params: { from: "2026-10-10", to: "2026-10-01" } });
    expect(calls).toHaveLength(sent);
    expect(s.getState($reportRequest)).toBeNull();
    expect(s.getState($reportData)).toBeNull();
  });

  it("cash-history / vat-returns are not `/reports/*` requests; quarter range; lost margin", () => {
    expect(reportRequest("cash-history", { from: TODAY, to: TODAY }, null, DEFAULT_OPTIONS)).toBeNull();
    expect(quickRange("quarter", TODAY)).toEqual({ from: "2026-10-01", to: TODAY });
    expect(quickRange("quarter", "2026-09-05")).toEqual({ from: "2026-07-01", to: "2026-09-05" });
    expect(requestKey(null)).toBe("");
    expect(lostMargin({ margin: "1200.00", margin_without_discounts: "1500.00" })).toBe("300.00");
  });
});
