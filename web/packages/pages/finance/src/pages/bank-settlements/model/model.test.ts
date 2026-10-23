/**
 * BO-24 model (07 BO-24; 20 #55a–#55h; 13 §2.18a; US-M11-04; QT-M11-07…-15 web parts).
 */
import { allSettled, fork } from "effector";
import { describe, expect, it } from "vitest";

import {
  $detail,
  $filters,
  $importResult,
  $postedTotals,
  $settlements,
  $transitView,
  emptyBankForm,
  formOf,
  getSettlementFx,
  importStatementFx,
  importedDraftsShown,
  isPatchEmpty,
  listSettlementsFx,
  loadTransitFx,
  netAmount,
  pageMounted,
  postSettlementFx,
  previewLines,
  settlementOpened,
  toCreateBody,
  toListParams,
  toPatchBody,
  transitFor,
  validateBankForm,
  commissionPct,
  type BankForm,
  type ListRequest,
  type Settlement,
  type SettlementDetail,
  type TransitBalance,
} from "./index.ts";

const TODAY = "2026-10-16";

function settlement(id: string, patch: Partial<Settlement> = {}): Settlement {
  return {
    id,
    number: "BT-01-2026-000012",
    branch_id: "b-1",
    doc_date: TODAY,
    status: "posted",
    source: "manual",
    method: "card",
    settled_from: "2026-10-15",
    settled_to: "2026-10-15",
    gross_amount: "950000.00",
    commission_amount: "9500.00",
    variance_amount: "0.00",
    net_amount: "940500.00",
    bank_ref: "123456",
    attachment_id: null,
    statement_import_id: null,
    comment: null,
    created_by: "u-1",
    created_at: "2026-10-16T09:00:00Z",
    posted_at: null,
    cancelled_at: null,
    cancelled_by: null,
    cancel_reason: null,
    version: 1,
    ...patch,
  };
}

const detail = (patch: Partial<SettlementDetail> = {}): SettlementDetail => ({
  ...settlement("d-1", { status: "draft", number: "BT-01-2026-000013" }),
  ledger_entries: [],
  ...patch,
});

const transit: TransitBalance[] = [
  {
    branch_id: "b-1",
    method: "card",
    balance: "950000.00",
    oldest_unsettled_date: "2026-10-15",
    card_breakdown: { integrated: "550000.00", manual: "400000.00" },
  },
  {
    branch_id: "b-1",
    method: "collection",
    balance: "2000000.00",
    oldest_unsettled_date: "2026-10-14",
    card_breakdown: null,
  },
  {
    branch_id: "b-2",
    method: "uzqr",
    balance: "120000.00",
    oldest_unsettled_date: "2026-10-15",
    card_breakdown: null,
  },
];

function scope() {
  const lists: ListRequest[] = [];
  const s = fork({
    handlers: [
      [
        listSettlementsFx,
        (req: ListRequest) => {
          lists.push(req);
          return {
            items: [
              settlement("s1"),
              settlement("s2", { status: "draft", number: null }),
              settlement("s3", { status: "cancelled" }),
            ],
            next_cursor: null,
          };
        },
      ],
      [loadTransitFx, () => ({ as_of: TODAY, items: transit })],
      [getSettlementFx, (id: string) => detail({ id })],
      [postSettlementFx, (id: string) => settlement(id)],
      [
        importStatementFx,
        () => ({
          import_id: "i-1",
          file_sha256: "x",
          account: "20208000000000000001",
          period_from: "2026-10-15",
          period_to: "2026-10-15",
          drafts_created: 3,
          draft_ids: ["a", "b", "c"],
          duplicates: 1,
          ignored_outgoing: 0,
          unmatched_lines: [
            {
              line_no: 40,
              number: "77",
              date: "2026-10-15",
              amount: "50000.00",
              payer_name: "NOMA'LUM",
              purpose: "?",
              reason: "unknown_method",
            },
          ],
          unmatched_card_transactions: [],
        }),
      ],
    ],
  });
  return { s, lists };
}

describe("BO-24 bank settlements model", () => {
  it("mount: list (branch filter), transit view, posted totals", async () => {
    const { s, lists } = scope();
    await allSettled(pageMounted, { scope: s, params: { today: TODAY, branchId: "b-1" } });
    expect(toListParams(lists[0]!)).toEqual({ branch_id: "b-1", limit: 50 });
    expect(s.getState($settlements)).toHaveLength(3);
    expect(s.getState($postedTotals)).toMatchObject({
      count: 1,
      gross: "950000.00",
      commission: "9500.00",
      net: "940500.00",
    });
    const view = s.getState($transitView);
    expect(view.rows.map((r) => r.key)).toEqual(["card_integrated", "card_manual", "uzqr", "collection"]);
    expect(view.totals).toEqual({ "b-1": "2950000.00", "b-2": "120000.00" });
    expect(view.total).toBe("3070000.00");
  });

  it("test_qt_m11_10 web: import → result; «Qoralamalarni ko'rish» filters statement drafts", async () => {
    const { s, lists } = scope();
    await allSettled(pageMounted, { scope: s, params: { today: TODAY, branchId: null } });
    await allSettled(importStatementFx, {
      scope: s,
      params: { file: new File(["x"], "v.txt"), branchId: null },
    });
    expect(s.getState($importResult)?.drafts_created).toBe(3);
    await allSettled(importedDraftsShown, { scope: s });
    expect(s.getState($filters)).toMatchObject({ status: "draft", source: "statement_import" });
    expect(toListParams(lists.at(-1)!)).toMatchObject({ status: "draft", source: "statement_import" });
  });

  it("opening a document loads its detail; post reloads it", async () => {
    const { s } = scope();
    await allSettled(pageMounted, { scope: s, params: { today: TODAY, branchId: null } });
    await allSettled(settlementOpened, { scope: s, params: "d-9" });
    expect(s.getState($detail)?.id).toBe("d-9");
    await allSettled(settlementOpened, { scope: s, params: "new" });
    expect(s.getState($detail)).toBeNull();
    await allSettled(settlementOpened, { scope: s, params: "d-9" });
    await allSettled(postSettlementFx, { scope: s, params: "d-9" });
    expect(s.getState($detail)?.id).toBe("d-9");
  });
});

describe("BO-24 lib (13 §2.18a)", () => {
  const form = (patch: Partial<BankForm>): BankForm => ({
    ...emptyBankForm(TODAY, "b-1"),
    method: "card",
    gross: "950000.00",
    commission: "9500.00",
    ...patch,
  });

  it("test_qt_m11_07 web: card settlement — net, commission share, preview lines Dt 5110 / Dt 9430", () => {
    const f = form({});
    expect(netAmount(f)).toBe("940500.00");
    expect(commissionPct(f.gross, f.commission)).toBe("1.00");
    expect(previewLines(f)).toEqual([
      { dt: "5110", kt: "5710", amount: "940500.00" },
      { dt: "9430", kt: "5710", amount: "9500.00" },
    ]);
    expect(validateBankForm(f, TODAY)).toEqual({});
    expect(toCreateBody(f)).toEqual({
      branch_id: "b-1",
      doc_date: TODAY,
      method: "card",
      settled_from: "2026-10-15",
      settled_to: "2026-10-15",
      gross_amount: "950000.00",
      commission_amount: "9500.00",
      variance_amount: "0.00",
      bank_ref: null,
      attachment_id: null,
      comment: null,
    });
  });

  it("test_qt_m11_13 web: collection shortage → Dt 9410 commission, Dt 5910 shortage; surplus → Kt 9390", () => {
    const shortage = form({
      method: "collection",
      gross: "2000000.00",
      commission: "10000.00",
      variance: "-5000.00",
    });
    expect(netAmount(shortage)).toBe("1985000.00");
    expect(previewLines(shortage)).toEqual([
      { dt: "5110", kt: "5710", amount: "1985000.00" },
      { dt: "9410", kt: "5710", amount: "10000.00" },
      { dt: "5910", kt: "5710", amount: "5000.00" },
    ]);
    const surplus = form({
      method: "collection",
      gross: "100000.00",
      commission: "0.00",
      variance: "2000.00",
    });
    expect(previewLines(surplus)).toEqual([
      { dt: "5110", kt: "5710", amount: "102000.00" },
      { dt: "5710", kt: "9390", amount: "2000.00" },
    ]);
  });

  it("field checks: commission ≥ gross, variance outside collection, period order, future date", () => {
    expect(validateBankForm(form({ commission: "950000.00" }), TODAY)).toEqual({
      commission: "validation.bank_commission_ge_gross",
    });
    expect(validateBankForm(form({ variance: "10.00" }), TODAY)).toEqual({
      variance: "validation.not_allowed",
    });
    expect(
      validateBankForm(
        form({ settledFrom: "2026-10-15", settledTo: "2026-10-14", docDate: "2026-10-17" }),
        TODAY,
      ),
    ).toEqual({ settledTo: "validation.date_range", docDate: "validation.doc_date_in_future" });
    expect(validateBankForm(form({ settledTo: "2026-10-17", settledFrom: "2026-10-17" }), TODAY)).toEqual({
      settledTo: "validation.date_range",
    });
    expect(validateBankForm({ ...emptyBankForm(TODAY, null) }, TODAY)).toEqual({
      branchId: "validation.required",
      method: "validation.required",
      gross: "validation.required",
    });
  });

  it("20 #55h: PATCH sends only the changed fields + version; transit suggestion per branch × method", () => {
    const d = detail({ version: 3 });
    expect(isPatchEmpty(toPatchBody(formOf(d), d))).toBe(true);
    expect(toPatchBody({ ...formOf(d), commission: "9000.00", bankRef: " 777 " }, d)).toEqual({
      version: 3,
      commission_amount: "9000.00",
      bank_ref: "777",
    });
    expect(transitFor(transit, "b-1", "card")).toBe("950000.00");
    expect(transitFor(transit, "b-2", "card")).toBeNull();
  });
});
