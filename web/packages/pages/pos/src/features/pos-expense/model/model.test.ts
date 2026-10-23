/**
 * POS-14 «Xarajat» (07 POS-14; 18 §13.2; US-M15-01; QT-M15-01 web part): payload, `cash.withdraw` limit,
 * categories cache (offline), shift totals count the expense as cash out.
 */
import { describe, expect, it } from "vitest";

import type { Money } from "@shared/lib/money";

import { localShiftTotals } from "#/entities/pos-session/index.ts";

import {
  expenseNeedsApproval,
  expensePayload,
  loadCategories,
  toCached,
  validateExpense,
  type CachedCategories,
} from "./index.ts";

const rent = { id: "c-rent", name: "Ijara", default_account: "9410" };
const tax = { id: "c-tax", name: "Soliqlar", default_account: "6410" };

describe("POS-14 Xarajat", () => {
  it("test_qt_m15_01 web: payload = exactly the 18 §13.2 fields", () => {
    expect(
      expensePayload({
        id: "x-1",
        docDate: "2026-10-17",
        branchId: "b-1",
        cashRegisterId: "cr-1",
        shiftId: "s-1",
        category: rent,
        amount: "35000.00" as Money,
        comment: " Taksi ",
        taxType: "vat",
        approval: null,
      }),
    ).toEqual({
      id: "x-1",
      doc_date: "2026-10-17",
      branch_id: "b-1",
      cash_register_id: "cr-1",
      shift_id: "s-1",
      category_id: "c-rent",
      amount: "35000.00",
      comment: "Taksi",
      tax_type: null,
      approval: null,
    });
  });

  it("validation: amount, category, tax type for a 6410 category", () => {
    expect(validateExpense({ digits: "", categoryId: null, taxType: null, comment: "" }, null)).toEqual([
      "amount",
      "category",
    ]);
    expect(
      validateExpense({ digits: "36000", categoryId: "c-tax", taxType: null, comment: "" }, tax),
    ).toEqual(["taxType"]);
    expect(
      validateExpense({ digits: "36000", categoryId: "c-tax", taxType: "turnover", comment: "" }, tax),
    ).toEqual([]);
  });

  it("cash.withdraw limit: 50 000 passes, 50 001 needs approval, Owner unlimited, no permission → approval", () => {
    const cashier = { roleCodes: ["cashier"] };
    expect(expenseNeedsApproval(cashier, "50000.0000", "50000.00")).toBe(false);
    expect(expenseNeedsApproval(cashier, "50000.0000", "50001.00")).toBe(true);
    expect(expenseNeedsApproval(cashier, undefined, "1.00")).toBe(true);
    expect(expenseNeedsApproval({ roleCodes: ["owner"] }, undefined, "9000000.00")).toBe(false);
  });

  it("categories: online refreshes the device cache (active only); offline / failure reads it", async () => {
    let cache: CachedCategories | undefined;
    const deps = (online: boolean, fail = false) => ({
      isOnline: () => online,
      fetchCategories: () =>
        fail
          ? Promise.reject(new Error("net"))
          : Promise.resolve(
              toCached(
                [
                  { ...rent, archived_at: null },
                  { id: "c-old", name: "Eski", default_account: "9430", archived_at: "2026-01-01T00:00:00Z" },
                ],
                "2026-10-17T08:00:00Z",
              ),
            ),
      readCache: () => Promise.resolve(cache),
      writeCache: (v: CachedCategories) => {
        cache = v;
        return Promise.resolve();
      },
    });
    expect(await loadCategories(deps(false))).toEqual({ categories: null, fromCache: true });
    const online = await loadCategories(deps(true));
    expect(online.fromCache).toBe(false);
    expect(online.categories?.items.map((c) => c.id)).toEqual(["c-rent"]);
    expect((await loadCategories(deps(true, true))).categories?.items).toHaveLength(1);
    expect((await loadCategories(deps(false))).fromCache).toBe(true);
  });

  it("shift totals: an expense.created event is cash out (expected cash at close)", () => {
    const totals = localShiftTotals("500000.00", [
      {
        client_event_id: "e-1",
        type: "expense.created",
        created_at: "2026-10-17T09:00:00Z",
        status: "pending",
        retryable: null,
        payload: { id: "x-1", shift_id: "s-1", amount: "35000.00", comment: "Taksi", approval: null },
      },
    ]);
    expect(totals.cashOut).toBe("35000.00");
    expect(totals.expectedCash).toBe("465000.00");
    expect(totals.movements[0]).toMatchObject({ direction: "out", reason: "expense", amount: "35000.00" });
  });
});
