/**
 * BO-17 model (07 BO-17; 20 #41–#51; US-M15-01, US-M15-02; QT-M15-01/-02/-04/-05/-06 web parts).
 */
import { allSettled, fork } from "effector";
import { describe, expect, it } from "vitest";

import {
  $dueRules,
  $expenses,
  $filters,
  $notice,
  $rows,
  $shares,
  $totals,
  categoryShares,
  confirmRuleFx,
  createExpenseFx,
  dueRules,
  emptyForm,
  filtersChanged,
  listCategoriesFx,
  listExpensesFx,
  listRulesFx,
  pageMounted,
  parseDay,
  postExpenseFx,
  ruleSnoozed,
  rowStatus,
  toListParams,
  toSaveRequest,
  validateExpenseForm,
  visibleRows,
  type Category,
  type Expense,
  type ListRequest,
  type Rule,
  type SaveRequest,
} from "./index.ts";

const TODAY = "2026-10-17";

function cat(
  id: string,
  account: Category["default_account"] = "9410",
  patch: Partial<Category> = {},
): Category {
  return {
    id,
    code: null,
    name: `Cat ${id}`,
    default_account: account,
    source_ref: null,
    is_system: false,
    archived_at: null,
    version: 1,
    ...patch,
  };
}

function expense(id: string, patch: Partial<Expense> = {}): Expense {
  return {
    id,
    number: null,
    branch_id: "b-1",
    doc_date: "2026-10-05",
    status: "posted",
    category_id: "c-rent",
    category_name: "Ijara",
    account: "9410",
    amount: "3000000.00",
    source: "bank",
    tax_type: null,
    cash_register_id: null,
    shift_id: null,
    attachment_id: null,
    recurring_rule_id: null,
    comment: null,
    created_by: "u-1",
    created_at: null,
    posted_at: null,
    cancelled_at: null,
    cancel_reason: null,
    device_id: null,
    approval_request_id: null,
    approval_status: null,
    ...patch,
  };
}

function rule(id: string, patch: Partial<Rule> = {}): Rule {
  return {
    id,
    name: "Ijara",
    branch_id: "b-1",
    category_id: "c-rent",
    amount: "3000000.00",
    period: "month",
    day_of_month: 5,
    source: "bank",
    cash_register_id: null,
    next_due_date: "2026-10-05",
    last_triggered_at: null,
    is_active: true,
    is_due: true,
    version: 1,
    ...patch,
  };
}

function scope(post: "posted" | "approval" = "posted") {
  const listCalls: ListRequest[] = [];
  const saved: SaveRequest[] = [];
  const posted: string[] = [];
  const s = fork({
    handlers: [
      [
        listExpensesFx,
        (req: ListRequest) => {
          listCalls.push(req);
          return {
            items: [
              expense("e1"),
              expense("e2", { status: "draft", approval_status: "pending", amount: "1850000.00" }),
              expense("e3", {
                status: "draft",
                category_id: "c-tr",
                category_name: "Transport",
                amount: "1000000.00",
              }),
            ],
            next_cursor: null,
            totals: { posted: "3000000.00", draft: "2850000.00" },
          };
        },
      ],
      [listCategoriesFx, () => [cat("c-rent"), cat("c-tax", "6410")]],
      [
        listRulesFx,
        () => ({ items: [rule("r1"), rule("r2", { is_due: false })], total: 2, page: 1, size: 100 }),
      ],
      [
        createExpenseFx,
        (req: SaveRequest) => {
          saved.push(req);
          return { expense: expense("new", { status: "draft" }), rule: null };
        },
      ],
      [
        postExpenseFx,
        (id: string) => {
          posted.push(id);
          return post === "posted"
            ? { id, status: "posted", number: "XR-01-2026-000007", posted_at: "2026-10-17T10:00:00Z" }
            : { id, status: "draft", approval_request_id: "ar-1" };
        },
      ],
      [
        confirmRuleFx,
        (id: string) => ({ expense_id: `x-${id}`, status: "draft", approval_request_id: "ar-2" }),
      ],
    ],
  });
  return { s, listCalls, saved, posted };
}

describe("BO-17 expenses model", () => {
  it("mount: current month list, totals, rows, category shares, due reminders", async () => {
    const { s, listCalls } = scope();
    await allSettled(pageMounted, { scope: s, params: { today: TODAY, branchId: "b-1" } });
    expect(listCalls[0]).toEqual({
      filters: { from: "2026-10-01", to: TODAY, categoryId: null, source: null, status: null },
      cursor: null,
    });
    expect(s.getState($expenses)).toHaveLength(3);
    expect(s.getState($totals)).toEqual({ posted: "3000000.00", draft: "2850000.00" });
    expect(s.getState($shares).total).toBe("3000000.00");
    expect(s.getState($dueRules).map((r) => r.id)).toEqual(["r1"]);
    await allSettled(ruleSnoozed, { scope: s, params: "r1" });
    expect(s.getState($dueRules)).toEqual([]);
  });

  it("«Tasdiq kutmoqda» filter = server draft + pending approval on the client", async () => {
    const { s, listCalls } = scope();
    await allSettled(pageMounted, { scope: s, params: { today: TODAY, branchId: null } });
    await allSettled(filtersChanged, { scope: s, params: { status: "awaiting" } });
    expect(toListParams(listCalls.at(-1)!).status).toBe("draft");
    expect(s.getState($rows).map((e) => e.id)).toEqual(["e2"]);
    await allSettled(filtersChanged, { scope: s, params: { status: "draft" } });
    expect(s.getState($rows).map((e) => e.id)).toEqual(["e3"]);
    // an inverted period is swapped
    await allSettled(filtersChanged, { scope: s, params: { from: "2026-10-20" } });
    expect(s.getState($filters)).toMatchObject({ from: TODAY, to: "2026-10-20" });
  });

  it("test_qt_m15_05 web: «Saqlash va o'tkazish» → create then post; 202 → «Egasi tasdig'iga yuborildi»", async () => {
    const { s, saved, posted, listCalls } = scope("approval");
    await allSettled(pageMounted, { scope: s, params: { today: TODAY, branchId: "b-1" } });
    const before = listCalls.length;
    const form = { ...emptyForm(TODAY, "b-1"), amount: "1850000.00", categoryId: "c-rent" };
    await allSettled(createExpenseFx, { scope: s, params: toSaveRequest(form, cat("c-rent"), true) });
    expect(saved[0]?.body).toMatchObject({ amount: "1850000.00", source: "bank", tax_type: null });
    expect(posted).toEqual(["new"]);
    expect(s.getState($notice)).toEqual({ kind: "approval" });
    expect(listCalls.length).toBeGreaterThan(before);
  });

  it("posted answer carries the number; draft save → «Qoralama saqlandi»", async () => {
    const { s, posted } = scope("posted");
    await allSettled(pageMounted, { scope: s, params: { today: TODAY, branchId: "b-1" } });
    const form = { ...emptyForm(TODAY, "b-1"), amount: "1000.00", categoryId: "c-rent" };
    await allSettled(createExpenseFx, { scope: s, params: toSaveRequest(form, cat("c-rent"), false) });
    expect(posted).toEqual([]);
    expect(s.getState($notice)).toEqual({ kind: "draft" });
    await allSettled(postExpenseFx, { scope: s, params: "e3" });
    expect(s.getState($notice)).toEqual({ kind: "posted", number: "XR-01-2026-000007" });
  });

  it("test_qt_m15_02 web: one-click confirm of a due reminder (202 → approval notice)", async () => {
    const { s } = scope();
    await allSettled(pageMounted, { scope: s, params: { today: TODAY, branchId: "b-1" } });
    await allSettled(confirmRuleFx, { scope: s, params: "r1" });
    expect(s.getState($notice)).toEqual({ kind: "approval" });
  });
});

describe("BO-17 lib", () => {
  it("row status, visible rows, shares", () => {
    expect(rowStatus({ status: "draft", approval_status: "pending" })).toBe("awaiting");
    expect(rowStatus({ status: "draft", approval_status: "rejected" })).toBe("draft");
    const list = [
      expense("a", { amount: "300.00" }),
      expense("b", { category_id: "c2", category_name: "Kommunal", amount: "100.00" }),
      expense("c", { status: "cancelled", amount: "999.00" }),
    ];
    expect(visibleRows(list, null)).toHaveLength(3);
    expect(categoryShares(list)).toEqual({
      total: "400.00",
      items: [
        { categoryId: "c-rent", name: "Ijara", amount: "300.00", pct: "75.0" },
        { categoryId: "c2", name: "Kommunal", amount: "100.00", pct: "25.0" },
      ],
    });
  });

  it("test_qt_m15_06 web: a 6410 category needs tax_type and never becomes a recurring rule", () => {
    const tax = cat("c-tax", "6410");
    const base = { ...emptyForm(TODAY, "b-1"), amount: "36000.00", categoryId: "c-tax" };
    expect(validateExpenseForm(base, tax, TODAY)).toEqual({ taxType: "validation.required" });
    const req = toSaveRequest({ ...base, taxType: "turnover", period: "month", dayOfMonth: "5" }, tax, true);
    expect(req.body.tax_type).toBe("turnover");
    expect(req.rule).toBeNull();
  });

  it("field checks: amount, category, archived, date, branch, day of month", () => {
    const form = emptyForm(TODAY, null);
    expect(validateExpenseForm(form, null, TODAY)).toEqual({
      amount: "validation.required",
      categoryId: "validation.required",
      branchId: "validation.required",
    });
    expect(
      validateExpenseForm(
        { ...form, amount: "0.00", docDate: "2026-10-18", branchId: "b", period: "month", dayOfMonth: "29" },
        cat("x", "9410", { archived_at: "2026-01-01T00:00:00Z" }),
        TODAY,
      ),
    ).toEqual({
      amount: "validation.must_be_positive",
      categoryId: "validation.archived",
      docDate: "validation.doc_date_in_future",
      dayOfMonth: "validation.range",
    });
    expect(parseDay("5")).toBe(5);
    expect(parseDay("28")).toBe(28);
    expect(parseDay("0")).toBeNull();
  });

  it("US-M15-02: a monthly rule is created with the expense", () => {
    const req = toSaveRequest(
      {
        ...emptyForm(TODAY, "b-1"),
        amount: "3000000.00",
        categoryId: "c-rent",
        comment: " Ijara ",
        period: "month",
        dayOfMonth: "5",
        source: "card",
      },
      cat("c-rent"),
      false,
    );
    expect(req.rule).toEqual({
      name: "Ijara",
      category_id: "c-rent",
      amount: "3000000.00",
      day_of_month: 5,
      period: "month",
      source: "card",
      branch_id: "b-1",
    });
    expect(req.body).toEqual({
      doc_date: TODAY,
      branch_id: "b-1",
      category_id: "c-rent",
      amount: "3000000.00",
      source: "card",
      attachment_id: null,
      comment: "Ijara",
      tax_type: null,
    });
    expect(dueRules([rule("a"), rule("b", { is_active: false })], [])).toHaveLength(1);
  });
});
