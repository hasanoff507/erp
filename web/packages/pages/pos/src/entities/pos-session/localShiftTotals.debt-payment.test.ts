/**
 * WEB-01 (R3): the device's expected cash follows the server rule
 * `expected_cash = opening_cash + Σ cash_moves(shift, method='cash')` (18 §3.2, 13 X-01):
 * cash sale payments +, cash refunds −money_part, cash movements ±, POS cash expense −, cash debt payment +.
 * Card / UzQR / Click / Payme / Uzum debt payments write a non-cash `cash_moves` row and do not count.
 */
import { describe, expect, it } from "vitest";

import { localShiftTotals, type ReturnHistoryRow, type ShiftEventRow } from "./lib/index.ts";

const SHIFT = "shift-1";
let seq = 0;
const ev = (type: string, payload: Record<string, unknown>, extra: Partial<ShiftEventRow> = {}): ShiftEventRow => ({
  client_event_id: `ce-${++seq}`,
  type,
  created_at: "2026-10-17T05:00:00.000Z",
  status: "pending",
  retryable: null,
  payload: { shift_id: SHIFT, ...payload },
  ...extra,
});

describe("localShiftTotals — debt payments (WEB-01)", () => {
  it("test_web01_cash_debt_payment_counts_in_expected_cash", () => {
    const sale = ev("sale.created", { payments: [{ method: "cash", amount: "50000.00" }] });
    const debtCash = ev("debt_payment.created", { method: "cash", amount: "200000.00" });
    const totals = localShiftTotals("100000.00", [sale, debtCash]);
    expect(totals.debtCashIn).toBe("200000.00");
    expect(totals.expectedCash).toBe("350000.00");

    const debtCard = ev("debt_payment.created", {
      method: "card",
      amount: "70000.00",
      card_entry_mode: "integrated",
    });
    const debtQr = ev("debt_payment.created", { method: "uzqr", amount: "15000.00" });
    const withNonCash = localShiftTotals("100000.00", [sale, debtCash, debtCard, debtQr]);
    expect(withNonCash.debtCashIn).toBe("200000.00");
    expect(withNonCash.expectedCash).toBe("350000.00");
    // a debt payment is not a sale: no sales row / count / total change
    expect(withNonCash.salesCount).toBe(1);
    expect(withNonCash.salesTotal).toBe("50000.00");
  });

  it("test_web01_expected_cash_mirrors_server_signed_cash_moves", () => {
    // Every event the server turns into a `cash_moves(method='cash')` row, with the server's sign.
    const events: ShiftEventRow[] = [
      ev("sale.created", {
        payments: [
          { method: "cash", amount: "120000.00" },
          { method: "card", amount: "30000.00", card_entry_mode: "manual" },
          { method: "debt", amount: "40000.00" },
        ],
      }),
      ev("cash_movement.created", { direction: "in", reason: "change_fund", amount: "25000.00" }),
      ev("cash_movement.created", { direction: "out", reason: "collection", amount: "60000.00" }),
      ev("expense.created", { amount: "15000.00", category_id: "cat-1" }),
      ev("debt_payment.created", { method: "cash", amount: "80000.00" }),
      ev("debt_payment.created", { method: "click", amount: "9000.00" }),
      // rejected non-retryable: never posted on the server → no cash_moves row
      ev(
        "debt_payment.created",
        { method: "cash", amount: "500000.00" },
        { status: "rejected", retryable: false },
      ),
    ];
    const ret = ev("return.created", {});
    events.push(ret);
    const returns: ReturnHistoryRow[] = [
      {
        client_event_id: ret.client_event_id,
        kind: "return",
        shift_id: SHIFT,
        total: "20000.00",
        summary: { refund_method: "cash", money_part: "12000.00" },
      },
    ];
    // server-side signed cash_moves(method='cash') rows of this shift
    const serverCashMoves = [120000, 25000, -60000, -15000, 80000, -12000];
    const opening = 100000;
    const serverExpected = (opening + serverCashMoves.reduce((a, b) => a + b, 0)).toFixed(2);

    const totals = localShiftTotals("100000.00", events, returns);
    expect(totals.expectedCash).toBe(serverExpected);
    expect(totals.expectedCash).toBe("238000.00");
    expect(totals.debtCashIn).toBe("80000.00");
    expect(totals.cashIn).toBe("25000.00");
    expect(totals.cashOut).toBe("75000.00");
  });
});
