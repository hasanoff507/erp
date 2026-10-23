/** WEB-03: BO-06 «Ortiqcha to'lovlar» → «Qaytarish» (real effects, API mocked). */
import { describe, expect, it, vi, beforeEach } from "vitest";

import type * as ApiModule from "@shared/api";

import { ApiError } from "@shared/api";
import type { Money } from "@shared/lib/money";
import type { CashMovementCreated, CashMovementIn, ShiftListItem } from "@shared/models";

import type { Overpayment, RefundForm } from "./index.ts";

const { createCashMovement, reviewSyncException } = vi.hoisted(() => ({
  createCashMovement: vi.fn<(body: CashMovementIn) => Promise<CashMovementCreated>>(),
  reviewSyncException: vi.fn<(id: string, body: { review_note: string }) => Promise<unknown>>(),
}));

vi.mock("@shared/api", async (importOriginal) => {
  const actual = await importOriginal<typeof ApiModule>();
  return {
    ...actual,
    api: {
      ...actual.api,
      cash: { ...actual.api.cash, createCashMovement },
      branches: { ...actual.api.branches, reviewSyncException },
    },
  };
});

const { refundFieldErrors, submitRefundFx, toRefundBody, validateRefund } = await import("./index.ts");

const row: Overpayment = {
  id: "x1",
  counterpartyId: "c-1",
  amount: "350000.00",
  unallocated: "50000.00",
  createdAt: "2026-10-13T08:00:00Z",
  deviceId: "d-1",
  docId: "p-1",
};
const shift: ShiftListItem = {
  id: "sh-1",
  shift_no: 214,
  cash_register_id: "cr-1",
  branch_id: "b-1",
  status: "open",
  opening_cash: "100000.00",
  opened_at: "2026-10-18T03:00:00Z",
  closed_at: null,
};
const form = (patch: Partial<RefundForm> = {}): RefundForm => ({
  amount: "50000.00",
  comment: "Ortiqcha to'lov qaytarildi",
  shiftId: "sh-1",
  ...patch,
});

beforeEach(() => {
  createCashMovement.mockReset();
  reviewSyncException.mockReset();
});

describe("WEB-03 overpayment refund (07 BO-06, 13 §2.18: Dt 6310 / Kt 5010)", () => {
  it("test_web03_refund_posts_6310_cash_movement", async () => {
    expect(toRefundBody(row, form({ comment: "  qaytarildi " }), shift, "2026-10-18")).toEqual({
      reason: "other",
      direction: "out",
      account: "6310",
      counterparty_id: "c-1",
      amount: "50000.00",
      cash_register_id: "cr-1",
      shift_id: "sh-1",
      comment: "qaytarildi",
      doc_date: "2026-10-18",
    });

    createCashMovement.mockResolvedValue({ id: "cm-1", status: "posted", amount: "50000.00" });
    reviewSyncException.mockResolvedValue({});
    const done = await submitRefundFx({ row, form: form(), shift, today: "2026-10-18" });
    expect(createCashMovement).toHaveBeenCalledTimes(1);
    expect(createCashMovement.mock.calls[0]?.[0]).toMatchObject({
      account: "6310",
      counterparty_id: "c-1",
      shift_id: "sh-1",
      cash_register_id: "cr-1",
      direction: "out",
      reason: "other",
    });
    // the whole excess paid back → the exception is closed (no second refund of the same row)
    expect(reviewSyncException.mock.calls[0]?.[0]).toBe("x1");
    expect(reviewSyncException.mock.calls[0]?.[1].review_note).toContain("cm-1");
    expect(done).toEqual({ status: "posted", approvalRequestId: null, reviewed: true });
  });

  it("test_web03_refund_over_limit_goes_to_approval_202", async () => {
    createCashMovement.mockResolvedValue({
      id: "cm-2",
      status: "draft",
      amount: "50000.00",
      approval_request_id: "ar-1",
    });
    const done = await submitRefundFx({ row, form: form(), shift, today: "2026-10-18" });
    expect(done).toEqual({ status: "draft", approvalRequestId: "ar-1", reviewed: false });
    expect(reviewSyncException).not.toHaveBeenCalled();
  });

  it("a partial refund leaves the row open; a failed review does not fail the refund", async () => {
    createCashMovement.mockResolvedValue({ id: "cm-3", status: "posted", amount: "20000.00" });
    const partial = await submitRefundFx({
      row,
      form: form({ amount: "20000" }),
      shift,
      today: "2026-10-18",
    });
    expect(partial.reviewed).toBe(false);
    expect(reviewSyncException).not.toHaveBeenCalled();

    createCashMovement.mockResolvedValue({ id: "cm-4", status: "posted", amount: "50000.00" });
    reviewSyncException.mockRejectedValue(new Error("403"));
    const full = await submitRefundFx({ row, form: form(), shift, today: "2026-10-18" });
    expect(full).toEqual({ status: "posted", approvalRequestId: null, reviewed: false });
  });

  it("test_web03_refund_amount_capped_by_unallocated", () => {
    const cap = "50000.00" as Money;
    expect(validateRefund(form(), cap)).toEqual({});
    expect(validateRefund(form({ amount: "50000.01" }), cap)).toEqual({
      amount: "debts:overpay.refund.exceeds",
    });
    expect(validateRefund(form({ amount: "0" }), cap)).toEqual({ amount: "validation.must_be_positive" });
    expect(validateRefund(form({ amount: "" }), cap)).toEqual({ amount: "validation.required" });
    expect(validateRefund(form({ comment: " ", shiftId: "" }), cap)).toEqual({
      comment: "validation.required",
      shiftId: "validation.required",
    });
  });

  it("server validation keys land on the form fields; the rest goes to the banner", () => {
    const e = new ApiError({
      status: 422,
      code: "VALIDATION_ERROR",
      messageKey: "errors.validation",
      details: [
        { field: "amount", messageKey: "validation.must_be_positive" },
        { field: "cash_register_id", messageKey: "validation.cash_register_not_of_shift" },
        { field: "comment", messageKey: "validation.required" },
        { field: "counterparty_id", messageKey: "validation.required" },
      ],
    });
    expect(refundFieldErrors(e)).toEqual({
      fields: {
        amount: "validation.must_be_positive",
        shiftId: "validation.cash_register_not_of_shift",
        comment: "validation.required",
      },
      rest: true,
    });
    expect(
      refundFieldErrors(
        new ApiError({ status: 409, code: "SHIFT_NOT_OPEN", messageKey: "errors.shift_not_open" }),
      ),
    ).toEqual({ fields: {}, rest: true });
  });
});
