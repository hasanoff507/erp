/**
 * BO-07 «Soliq hisob-kitobi (ST)» block (20 #8a–#8d; 13 §2.26, §4.3; B4-T07 / QT-M10-07 web part).
 */
import { allSettled, fork } from "effector";
import { describe, expect, it } from "vitest";

import {
  listMovesFx,
  loadSummaryFx,
  pageMounted,
  periodChanged,
  type VatSummary,
} from "../../model/index.ts";

import {
  $lastPosted,
  $settlements,
  $sortedSettlements,
  $taxKind,
  createBody,
  createSettlementFx,
  hasLiveFor,
  listSettlementsFx,
  postSettlementFx,
  postingOf,
  taxKindOf,
  taxKindsOf,
  type TaxSettlement,
} from "./index.ts";

const TODAY = "2026-10-17";

function st(id: string, patch: Partial<TaxSettlement> = {}): TaxSettlement {
  return {
    id,
    number: null,
    branch_id: "b-1",
    doc_date: "2026-09-30",
    status: "draft",
    tax_kind: "vat_offset",
    period: "2026-09",
    base_amount: "84000.00",
    rate: null,
    amount: "84000.00",
    expense_account: null,
    comment: null,
    created_by: "u-1",
    created_at: null,
    posted_at: null,
    cancelled_at: null,
    cancel_reason: null,
    ...patch,
  };
}

const summary = (period: string, regime: "vat" | "turnover" = "vat"): VatSummary => ({
  period,
  regime,
  output_vat: "120000.00",
  input_vat: "84000.00",
  net_vat: "36000.00",
  pending_credit_red_invoices: null,
  pending_credit_pct: null,
  pending_credit_invoices: null,
  turnover_base: null,
  turnover_rate_pct: null,
  turnover_amount: null,
  tax_settlement_id: null,
});

function scope() {
  const listed: string[] = [];
  const created: unknown[] = [];
  let docs: TaxSettlement[] = [];
  const s = fork({
    handlers: [
      [loadSummaryFx, ({ months }: { months: readonly string[] }) => months.map((m) => summary(m))],
      [listMovesFx, () => ({ items: [], next_cursor: null })],
      [
        listSettlementsFx,
        (period: string) => {
          listed.push(period);
          return docs.filter((d) => d.period === period);
        },
      ],
      [
        createSettlementFx,
        (body: { period: string }) => {
          created.push(body);
          const doc = st("st-1", { period: body.period });
          docs = [doc];
          return doc;
        },
      ],
      [
        postSettlementFx,
        (id: string) => {
          docs = docs.map((d) => (d.id === id ? { ...d, status: "posted", number: "ST-01-2026-000001" } : d));
          return { ...docs[0]!, recalculated: false };
        },
      ],
    ],
  });
  return { s, listed, created };
}

describe("BO-07 ST block model", () => {
  it("test_qt_m10_07 web: month → list; «Qoralama hisoblash» → draft; «O'tkazish» → ST number", async () => {
    const { s, listed, created } = scope();
    await allSettled(pageMounted, { scope: s, params: { today: TODAY } });
    expect(listed).toEqual(["2026-10"]);
    expect(s.getState($taxKind)).toBe("vat_offset");
    await allSettled(periodChanged, { scope: s, params: "2026-09" });
    expect(listed.at(-1)).toBe("2026-09");
    await allSettled(createSettlementFx, { scope: s, params: createBody("vat_offset", "2026-09", "b-1") });
    expect(created).toEqual([{ tax_kind: "vat_offset", period: "2026-09" }]);
    expect(s.getState($settlements).map((d) => d.status)).toEqual(["draft"]);
    await allSettled(postSettlementFx, { scope: s, params: "st-1" });
    expect(s.getState($settlements)[0]).toMatchObject({ status: "posted", number: "ST-01-2026-000001" });
    expect(s.getState($lastPosted)?.recalculated).toBe(false);
  });

  it("a quarter has no ST list", async () => {
    const { s, listed } = scope();
    await allSettled(pageMounted, { scope: s, params: { today: TODAY } });
    await allSettled(periodChanged, { scope: s, params: "2026-Q3" });
    expect(listed).toEqual(["2026-10"]);
    expect(s.getState($sortedSettlements)).toEqual([]);
  });
});

describe("BO-07 ST lib", () => {
  it("kind by regime, postings (13 §2.26 / §4.3), live documents per kind / branch", () => {
    expect(taxKindOf("vat")).toBe("vat_offset");
    expect(taxKindOf("turnover")).toBe("turnover_tax");
    expect(taxKindOf(null)).toBeNull();
    // a month where the regime changes settles both kinds (the regime's own first)
    expect(taxKindsOf({ regime: "vat", outputVat: "1.00", turnoverBase: null })).toEqual(["vat_offset"]);
    expect(taxKindsOf({ regime: "turnover", outputVat: "120000.00", turnoverBase: "500000.00" })).toEqual([
      "turnover_tax",
      "vat_offset",
    ]);
    expect(taxKindsOf(null)).toEqual([]);
    expect(postingOf({ tax_kind: "vat_offset", expense_account: null })).toEqual({ dt: "6410", kt: "4410" });
    expect(postingOf({ tax_kind: "turnover_tax", expense_account: "9820" })).toEqual({
      dt: "9820",
      kt: "6410",
    });
    const list = [
      st("a", { tax_kind: "turnover_tax", branch_id: "b-1" }),
      st("b", { tax_kind: "turnover_tax", branch_id: "b-2", status: "cancelled" }),
    ];
    expect(hasLiveFor(list, "turnover_tax", "b-1")).toBe(true);
    expect(hasLiveFor(list, "turnover_tax", "b-2")).toBe(false);
    expect(hasLiveFor([st("c", { status: "cancelled" })], "vat_offset", null)).toBe(false);
    expect(createBody("turnover_tax", "2026-09", "b-2")).toEqual({
      tax_kind: "turnover_tax",
      period: "2026-09",
      branch_id: "b-2",
    });
  });
});
