import { allSettled, fork } from "effector";
import { describe, expect, it } from "vitest";

import {
  $moves,
  $movesHasMore,
  $movesTotals,
  $period,
  $summary,
  $summaryStatus,
  isEmptySummary,
  listMovesFx,
  loadSummaryFx,
  movesKindChanged,
  movesMoreRequested,
  netSign,
  overCreditLimit,
  pageMounted,
  periodChanged,
  periodMonths,
  periodOptions,
  shiftMonth,
  summarize,
  toMovesParams,
  type MovesRequest,
  type VatMove,
  type VatSummary,
} from "./index.ts";

const TODAY = "2026-10-17";

function summary(period: string, patch: Partial<VatSummary> = {}): VatSummary {
  return {
    period,
    regime: "vat",
    output_vat: "2210400.00",
    input_vat: "1500000.00",
    net_vat: "710400.00",
    pending_credit_red_invoices: 1,
    pending_credit_pct: "6.40",
    pending_credit_invoices: [],
    turnover_base: null,
    turnover_rate_pct: null,
    turnover_amount: null,
    tax_settlement_id: null,
    ...patch,
  };
}

function move(id: string, period: string, patch: Partial<VatMove> = {}): VatMove {
  return {
    id,
    kind: "output",
    period,
    base_amount: "100000.00",
    vat_amount: "12000.00",
    doc_type: "sales",
    doc_id: `d-${id}`,
    einvoice_id: null,
    created_at: `${period}-05T08:00:00Z`,
    ...patch,
  };
}

function scope() {
  const summaryCalls: string[][] = [];
  const moveCalls: MovesRequest[] = [];
  const s = fork({
    handlers: [
      [
        loadSummaryFx,
        ({ months }: { months: readonly string[] }) => {
          summaryCalls.push([...months]);
          return months.map((m) => summary(m));
        },
      ],
      [
        listMovesFx,
        (req: MovesRequest) => {
          moveCalls.push(req);
          const month = req.months[req.monthIndex] ?? "";
          if (req.cursor === null && month === "2026-07")
            return { items: [move("a", month)], next_cursor: "c2" };
          if (req.cursor === "c2") return { items: [move("b", month)], next_cursor: null };
          return { items: [move(`m-${month}`, month)], next_cursor: null };
        },
      ],
    ],
  });
  return { s, summaryCalls, moveCalls };
}

describe("BO-07 VAT model (20 #1, #2; US-M10-01)", () => {
  it("mount → current month summary and register", async () => {
    const { s, summaryCalls, moveCalls } = scope();
    await allSettled(pageMounted, { scope: s, params: { today: TODAY } });
    expect(s.getState($period)).toBe("2026-10");
    expect(summaryCalls).toEqual([["2026-10"]]);
    expect(moveCalls[0]).toMatchObject({ months: ["2026-10"], monthIndex: 0, cursor: null });
    expect(s.getState($summary)).toMatchObject({ outputVat: "2210400.00", pendingCreditPct: "6.40" });
    expect(s.getState($summaryStatus)).toBe("idle");
    expect(s.getState($movesHasMore)).toBe(false);
  });

  it("a quarter sums its three months and pages the register month by month", async () => {
    const { s, summaryCalls, moveCalls } = scope();
    await allSettled(pageMounted, { scope: s, params: { today: TODAY } });
    await allSettled(periodChanged, { scope: s, params: "2026-Q3" });
    expect(summaryCalls.at(-1)).toEqual(["2026-07", "2026-08", "2026-09"]);
    expect(s.getState($summary)).toMatchObject({
      outputVat: "6631200.00",
      netVat: "2131200.00",
      pendingRedInvoices: 3,
      pendingCreditPct: null,
    });
    expect(s.getState($moves).map((m) => m.id)).toEqual(["a"]);
    expect(s.getState($movesHasMore)).toBe(true);
    await allSettled(movesMoreRequested, { scope: s }); // cursor in July
    await allSettled(movesMoreRequested, { scope: s }); // August
    await allSettled(movesMoreRequested, { scope: s }); // September
    expect(s.getState($moves).map((m) => m.id)).toEqual(["a", "b", "m-2026-08", "m-2026-09"]);
    expect(s.getState($movesHasMore)).toBe(false);
    expect(s.getState($movesTotals)).toEqual({ base: "400000.00", vat: "48000.00" });
    const sent = moveCalls.length;
    await allSettled(movesMoreRequested, { scope: s });
    expect(moveCalls).toHaveLength(sent);
  });

  it("a filter reloads the register from the first month", async () => {
    const { s, moveCalls } = scope();
    await allSettled(pageMounted, { scope: s, params: { today: TODAY } });
    await allSettled(movesKindChanged, { scope: s, params: "input" });
    expect(moveCalls.at(-1)).toMatchObject({
      monthIndex: 0,
      cursor: null,
      filters: { kind: "input", docType: null },
    });
    // An invalid period key is ignored.
    await allSettled(periodChanged, { scope: s, params: "2026-13" });
    expect(s.getState($period)).toBe("2026-10");
  });
});

describe("BO-07 lib", () => {
  it("periods: months, quarters, options", () => {
    expect(periodMonths("2026-09")).toEqual(["2026-09"]);
    expect(periodMonths("2026-Q4")).toEqual(["2026-10", "2026-11", "2026-12"]);
    expect(shiftMonth("2026-01", -1)).toBe("2025-12");
    const { months, quarters } = periodOptions(TODAY);
    expect(months[0]).toBe("2026-10");
    expect(months).toHaveLength(12);
    expect(quarters).toEqual(["2026-Q4", "2026-Q3", "2026-Q2", "2026-Q1"]);
  });

  it("summaries: turnover regime, empty, net sign, credit limit, mixed regime", () => {
    const turnover = summarize("2026-10", [
      summary("2026-10", {
        regime: "turnover",
        output_vat: null,
        input_vat: null,
        net_vat: null,
        pending_credit_red_invoices: null,
        pending_credit_pct: null,
        turnover_base: "18420000.00",
        turnover_rate_pct: "4.00",
        turnover_amount: "736800.00",
      }),
    ]);
    expect(turnover).toMatchObject({ regime: "turnover", turnoverAmount: "736800.00", outputVat: null });
    expect(
      isEmptySummary(
        summarize("2026-10", [
          summary("2026-10", { output_vat: "0.00", input_vat: "0.00", net_vat: "0.00" }),
        ])!,
      ),
    ).toBe(true);
    expect(netSign("-5.00")).toBe(-1);
    expect(netSign("5.00")).toBe(1);
    expect(overCreditLimit("10.50", "10.00")).toBe(true);
    expect(overCreditLimit("10.00", "10.00")).toBe(false);
    expect(
      summarize("2026-Q3", [
        summary("2026-07", { regime: "turnover" }),
        summary("2026-08"),
        summary("2026-09"),
      ])?.mixedRegime,
    ).toBe(true);
    expect(
      toMovesParams({
        months: ["2026-07", "2026-08"],
        monthIndex: 1,
        filters: { kind: null, docType: "returns" },
        cursor: "x",
      }),
    ).toEqual({ period: "2026-08", doc_type: "returns", cursor: "x", limit: 50 });
  });
});
