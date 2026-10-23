import { allSettled, fork } from "effector";
import { describe, expect, it } from "vitest";

import type { Money } from "@shared/lib/money";
import type { AgingRow, CounterpartyOut, DebtsAgingOut, SyncExceptionOut } from "@shared/models";
import { $activeBranchId } from "@shared/state/session";

import {
  bucketCards,
  filterRows,
  matchesSearch,
  overLimit,
  promiseState,
  tabCounts,
} from "#/entities/debtor/index.ts";
import {
  submitBankPaymentFx,
  toBankPaymentRequest,
  validateBankPayment,
} from "#/features/bank-payment/index.ts";
import { toCardForm, toCardPatch, validateCard } from "#/features/customer-card/index.ts";
import {
  $ledger,
  amountTone,
  entryDocKey,
  ledgerMoreRequested,
  ledgerOpened,
  loadLedgerFx,
  productsText,
} from "#/features/debt-ledger/index.ts";
import { toOpeningRequest, validateOpening } from "#/features/debt-opening/index.ts";
import { validateWriteoff } from "#/features/debt-writeoff/index.ts";
import { toOverpayments } from "#/features/overpayments/index.ts";

import {
  $counts,
  $page,
  $pageRows,
  $rows,
  $selected,
  $tab,
  $visible,
  $visibleTotal,
  directionChanged,
  loadAgingFx,
  pageChanged,
  pageMounted,
  reloadRequested,
  rowSelected,
  searchChanged,
  tabChanged,
  type AgingRequest,
} from "./index.ts";

const TODAY = "2026-10-16";
const m = (v: string) => v as Money;

function row(id: string, patch: Partial<AgingRow> = {}): AgingRow {
  return {
    counterparty_id: id,
    name: `Mijoz ${id}`,
    phone: "+998901234567",
    balance: "100000.00",
    credit_limit: null,
    due_date: null,
    overdue_since: "2026-10-01",
    days_overdue: 15,
    bucket: "0-30",
    promise_date: null,
    open_docs: 1,
    limit_exceeded_offline: false,
    doubtful_flag: false,
    doubtful_flag_id: null,
    last_payment_amount: null,
    last_payment_date: null,
    ...patch,
  };
}

const ROWS: AgingRow[] = [
  row("a", { name: "Aliyev Botir", balance: "450000.00", promise_date: TODAY, phone: "+998901112233" }),
  row("b", {
    name: "Karimova Malika",
    balance: "1240000.00",
    bucket: "60+",
    days_overdue: 64,
    due_date: "2026-10-10",
  }),
  row("c", {
    name: "Rahimov Jasur",
    balance: "950000.00",
    limit_exceeded_offline: true,
    credit_limit: "900000.00",
  }),
  row("d", { name: "Tursunova Nigora", balance: "320000.00", promise_date: "2026-10-20" }),
];

describe("debtor rules (07 BO-06 tabs, US-M08-09/10)", () => {
  it("«Bugun/o'tgan va'da» = promise (or due) date ≤ today; 60+ = bucket; limit = offline flag", () => {
    expect(promiseState(ROWS[0] as AgingRow, TODAY)).toBe("today");
    expect(promiseState(ROWS[1] as AgingRow, TODAY)).toBe("overdue");
    expect(promiseState(ROWS[3] as AgingRow, TODAY)).toBe("future");
    expect(promiseState(ROWS[2] as AgingRow, TODAY)).toBe("none");
    expect(filterRows(ROWS, "due", "", TODAY).map((r) => r.counterparty_id)).toEqual(["a", "b"]);
    expect(filterRows(ROWS, "aged", "", TODAY).map((r) => r.counterparty_id)).toEqual(["b"]);
    expect(filterRows(ROWS, "over_limit", "", TODAY).map((r) => r.counterparty_id)).toEqual(["c"]);
    expect(tabCounts(ROWS, TODAY)).toEqual({ due: 2, aged: 1, over_limit: 1, all: 4 });
    expect(overLimit(ROWS[2] as AgingRow)).toBe(true);
  });

  it("search by name words or phone digits (also the last digits)", () => {
    expect(matchesSearch(ROWS[0] as AgingRow, "botir")).toBe(true);
    expect(matchesSearch(ROWS[0] as AgingRow, "aliyev bot")).toBe(true);
    expect(matchesSearch(ROWS[0] as AgingRow, "112 233")).toBe(true);
    expect(matchesSearch(ROWS[0] as AgingRow, "999")).toBe(false);
  });

  it("aging cards: amount, count and share of the total per bucket", () => {
    const cards = bucketCards({
      total: "800000.00",
      count: 3,
      buckets: [
        { bucket: "0-30", count: 2, amount: "500000.00" },
        { bucket: "60+", count: 1, amount: "300000.00" },
      ],
    });
    expect(cards.map((c) => [c.bucket, c.count, c.amount, c.share])).toEqual([
      ["0-30", 2, "500000.00", "62.5"],
      ["31-60", 0, "0.00", "0.0"],
      ["60+", 1, "300000.00", "37.5"],
    ]);
  });
});

describe("BO-06 page model (debts-aging → tabs, search, pages, selection)", () => {
  it("loads the aging for the topbar branch, filters client-side and re-reads after a bank payment", async () => {
    const calls: AgingRequest[] = [];
    const answer: DebtsAgingOut = {
      as_of: TODAY,
      direction: "receivable",
      summary: { total: "2960000.00", count: 4, buckets: [] },
      rows: ROWS,
    };
    const s = fork({
      values: [[$activeBranchId, "b-1"]],
      handlers: [
        [
          loadAgingFx,
          (req: AgingRequest) => {
            calls.push(req);
            return answer;
          },
        ],
        [submitBankPaymentFx, () => ({ id: "p-1" })],
      ],
    });
    await allSettled(pageMounted, {
      scope: s,
      params: { today: TODAY, direction: "receivable", tab: "all" },
    });
    expect(calls).toEqual([{ direction: "receivable", branchId: "b-1" }]);
    expect(s.getState($rows)).toHaveLength(4);
    expect(s.getState($counts)).toEqual({ due: 2, aged: 1, over_limit: 1, all: 4 });

    await allSettled(tabChanged, { scope: s, params: "due" });
    expect(s.getState($visible).map((r) => r.counterparty_id)).toEqual(["a", "b"]);
    expect(s.getState($visibleTotal)).toBe("1690000.00");
    await allSettled(searchChanged, { scope: s, params: "malika" });
    expect(s.getState($pageRows).map((r) => r.counterparty_id)).toEqual(["b"]);
    expect(s.getState($page)).toBe(1);

    await allSettled(rowSelected, { scope: s, params: "b" });
    expect(s.getState($selected)?.name).toBe("Karimova Malika");

    await allSettled(submitBankPaymentFx, {
      scope: s,
      params: toBankPaymentRequest("b", {
        amount: "100000.00",
        docDate: TODAY,
        branchId: "b-1",
        promiseDate: "",
        comment: "",
      }),
    });
    expect(calls).toHaveLength(2);

    // US-M08-11: «Men qarzdorman» asks the payable direction and drops the selection
    await allSettled(directionChanged, { scope: s, params: "payable" });
    expect(calls[2]).toEqual({ direction: "payable", branchId: "b-1" });
    expect(s.getState($selected)).toBeNull();
  });

  it("pages of 20 rows", async () => {
    const many = Array.from({ length: 45 }, (_, i) => row(`r${i}`));
    const s = fork({
      handlers: [
        [
          loadAgingFx,
          () => ({
            as_of: TODAY,
            direction: "receivable",
            summary: { total: "0.00", count: 45, buckets: [] },
            rows: many,
          }),
        ],
      ],
    });
    await allSettled(pageMounted, {
      scope: s,
      params: { today: TODAY, direction: "receivable", tab: "all" },
    });
    expect(s.getState($pageRows)).toHaveLength(20);
    await allSettled(pageChanged, { scope: s, params: 3 });
    expect(s.getState($pageRows)).toHaveLength(5);
  });

  it("test_web06_counterparty_param_selects_row", async () => {
    const rows = [row("a"), row("b"), row("c")];
    const answer = (): DebtsAgingOut => ({
      as_of: TODAY,
      direction: "receivable",
      summary: { total: "0.00", count: rows.length, buckets: [] },
      rows,
    });
    // `?counterparty=b&tab=due` → «Barchasi» + row b after the load
    const s = fork({ handlers: [[loadAgingFx, answer]] });
    await allSettled(pageMounted, {
      scope: s,
      params: { today: TODAY, direction: "receivable", tab: "due", counterparty: "b" },
    });
    expect(s.getState($selected)?.counterparty_id).toBe("b");
    expect(s.getState($tab)).toBe("all");
    // only once: a later reload keeps the user's own choice
    await allSettled(rowSelected, { scope: s, params: null });
    await allSettled(reloadRequested, { scope: s });
    expect(s.getState($selected)).toBeNull();

    // an unknown id is ignored (tab from the URL kept, nothing selected)
    const u = fork({ handlers: [[loadAgingFx, answer]] });
    await allSettled(pageMounted, {
      scope: u,
      params: { today: TODAY, direction: "receivable", tab: "due", counterparty: "zzz" },
    });
    expect(u.getState($selected)).toBeNull();
    expect(u.getState($tab)).toBe("due");
  });
});

describe("BO-06 forms (18 §12.3–§12.6, 11.4)", () => {
  it("bank payment: amount > 0 and ≤ debt (qaror #45), date ≤ today, branch required", () => {
    const base = { amount: "100000.00", docDate: TODAY, branchId: "b-1", promiseDate: "", comment: "" };
    expect(validateBankPayment(base, m("450000.00"), TODAY)).toEqual({});
    expect(validateBankPayment({ ...base, amount: "500000.00" }, m("450000.00"), TODAY)).toEqual({
      amount: "debts:payment.exceedsBalance",
    });
    expect(
      validateBankPayment({ ...base, amount: "", docDate: "2026-10-17", branchId: null }, m("1.00"), TODAY),
    ).toEqual({
      amount: "validation.required",
      docDate: "validation.date_in_future",
      branchId: "validation.required",
    });
    expect(toBankPaymentRequest("c-1", { ...base, comment: "  bank  " })).toEqual({
      counterpartyId: "c-1",
      branchId: "b-1",
      amount: "100000.00",
      docDate: TODAY,
      promiseDate: null,
      comment: "bank",
    });
  });

  it("opening: a new customer needs name + phone; the request carries counterparty{} or counterparty_id", () => {
    const form = {
      counterpartyId: null,
      name: "Aliyev Botir",
      phone: "901234567",
      amount: "350000.00",
      dueDate: "",
      docDate: TODAY,
      comment: "",
    };
    expect(validateOpening(form, TODAY)).toEqual({});
    expect(validateOpening({ ...form, phone: "", name: " " }, TODAY)).toEqual({
      name: "validation.required",
      phone: "validation.required",
    });
    expect(validateOpening({ ...form, phone: "" }, TODAY, "payable")).toEqual({});
    expect(toOpeningRequest(form, "receivable", "b-1").body).toEqual({
      counterparty: { name: "Aliyev Botir", phone: "+998901234567", kind: "person" },
      amount: "350000.00",
      direction: "receivable",
      due_date: null,
      doc_date: TODAY,
      branch_id: "b-1",
      comment: null,
    });
    expect(toOpeningRequest({ ...form, counterpartyId: "c-9" }, "payable", null).body).toMatchObject({
      counterparty_id: "c-9",
      direction: "payable",
    });
  });

  it("write-off: amount ≤ debt, reason required", () => {
    const f = {
      amount: "100.00",
      reason: "vafot",
      accountChoice: "9430" as const,
      taxBasis: "death" as const,
      comment: "",
    };
    expect(validateWriteoff(f, m("100.00"))).toEqual({});
    expect(validateWriteoff({ ...f, amount: "100.01", reason: " " }, m("100.00"))).toEqual({
      amount: "validation.debt_writeoff_exceeds_balance",
      reason: "validation.required",
    });
  });

  it("customer card: only changed fields + version; limit empty = no limit", () => {
    const card: CounterpartyOut = {
      id: "c-1",
      kind: "person",
      name: "Aliyev Botir",
      phone: "+998901234567",
      stir: null,
      legal_address: null,
      bank_account: null,
      bank_mfo: null,
      vat_payer: null,
      is_customer: true,
      is_supplier: false,
      credit_limit: "1000000.00",
      standing_discount_pct: null,
      notify_consent: false,
      notify_consent_at: null,
      note: null,
      archived_at: null,
      created_at: "2026-10-01T00:00:00Z",
      updated_at: "2026-10-01T00:00:00Z",
      version: 3,
    };
    const form = toCardForm(card);
    expect(form.phone).toBe("901234567");
    expect(toCardPatch(form, card)).toEqual({ version: 3 });
    expect(toCardPatch({ ...form, creditLimit: "", discountPct: "2.00", notifyConsent: true }, card)).toEqual(
      {
        version: 3,
        credit_limit: null,
        standing_discount_pct: "2.00",
        notify_consent: true,
      },
    );
    expect(validateCard({ ...form, phone: "90", discountPct: "120.00" })).toEqual({
      phone: "validation.phone_uz",
      discountPct: "validation.invalid_format",
    });
  });

  it("overpayments: only unreviewed debt_overpayment_offline rows (qaror #67)", () => {
    const base: SyncExceptionOut = {
      id: "x1",
      kind: "debt_overpayment_offline",
      device_id: "d-1",
      branch_id: "b-1",
      client_event_id: null,
      doc_type: "debt_payments",
      doc_id: "p-1",
      details: { counterparty_id: "c-1", amount: "350000.00", unallocated_amount: "50000.00" },
      created_at: "2026-10-13T08:00:00Z",
      reviewed_at: null,
      reviewed_by: null,
      review_note: null,
    };
    expect(
      toOverpayments([
        base,
        { ...base, id: "x2", kind: "price_mismatch" },
        { ...base, id: "x3", reviewed_at: "x" },
      ]),
    ).toEqual([
      {
        id: "x1",
        counterpartyId: "c-1",
        amount: "350000.00",
        unallocated: "50000.00",
        createdAt: "2026-10-13T08:00:00Z",
        deviceId: "d-1",
        docId: "p-1",
      },
    ]);
  });
});

describe("debt ledger (US-M08-06, QT-M08-09)", () => {
  it("opens newest first and appends the next cursor page", async () => {
    const page = (cursor: string | null) => ({
      counterparty: {
        id: "c-1",
        name: "Aliyev Botir",
        phone: null,
        kind: "person",
        is_customer: true,
        is_supplier: false,
        credit_limit: null,
        receivable_balance: "230000.00",
        payable_balance: "0.00",
        debt_due_date: null,
        doubtful_flag: null,
      },
      direction: "receivable" as const,
      balance: "230000.00",
      entries: [
        {
          id: cursor ? "e2" : "e1",
          doc_type: cursor ? "sales" : "debt_payments",
          doc_id: "d",
          number: null,
          doc_date: TODAY,
          amount: cursor ? "330000.00" : "-100000.00",
          direction: "receivable" as const,
          kind: cursor ? ("debt" as const) : ("payment" as const),
          running_balance: "230000.00",
          due_date: null,
          promise_date: null,
          comment: null,
          status: null,
          open_amount: null,
          created_by: null,
          created_by_name: "Dilnoza",
          paid_amount: null,
          products: [],
          allocations: [],
        },
      ],
      next_cursor: cursor ? null : "c2",
    });
    const s = fork({ handlers: [[loadLedgerFx, ({ cursor }: { cursor: string | null }) => page(cursor)]] });
    await allSettled(ledgerOpened, { scope: s, params: { counterpartyId: "c-1", direction: "receivable" } });
    await allSettled(ledgerMoreRequested, { scope: s });
    expect(s.getState($ledger)?.entries.map((e) => e.id)).toEqual(["e1", "e2"]);
    expect(s.getState($ledger)?.next_cursor).toBeNull();
  });

  it("row presentation: document label, goods in the UI language, signed tone", () => {
    expect(entryDocKey({ doc_type: "debt_openings", kind: "debt" })).toBe("debt_openings");
    expect(entryDocKey({ doc_type: "ledger_adjustments", kind: "payment" })).toBe("payment");
    const goods = [
      { product_id: "1", name: "Non", name_ru: "Хлеб", qty: "1.000", line_total: "4000.00" },
      { product_id: "2", name: "Sut", name_ru: null, qty: "1.000", line_total: "13500.00" },
    ];
    expect(productsText(goods, "uz")).toBe("Non, Sut");
    expect(productsText(goods, "ru")).toBe("Хлеб, Sut");
    expect(productsText(goods, "uz", 1)).toBe("Non +1");
    expect([amountTone("-1.00"), amountTone("0.00"), amountTone("5.00")]).toEqual([
      "payment",
      "zero",
      "debt",
    ]);
  });
});
