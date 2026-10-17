import { allSettled, fork } from "effector";
import { describe, expect, it } from "vitest";

import {
  $history,
  $historyTotals,
  $movements,
  $range,
  $rangeInvalid,
  $registerId,
  $shift,
  $vatMoves,
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
