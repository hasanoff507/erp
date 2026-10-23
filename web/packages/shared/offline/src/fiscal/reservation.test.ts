import { afterEach, beforeEach, describe, expect, it } from "vitest";

import type { Money } from "@shared/lib/money";

import { enqueueEvent } from "../outbox/enqueue.ts";
import { debtPaymentPayload, enqueueDebtPayment } from "../repos/debts.ts";
import { posDb } from "../runtime.ts";
import { CASHIER, DEVICE, SHIFT_ID, setupOffline, teardownOffline } from "../testing/setup.ts";
import { fiscalReservations, rememberFiscalResult, releaseReservation, reserveReceiptSeq } from "./reservation.ts";

const REG = DEVICE.cashRegisterId ?? "";
const RESULT = {
  fm_terminal_id: "ZZ000000000001",
  fm_receipt_seq: 5,
  fiscal_sign: "123456789012",
  qr_url: "https://ofd.soliq.uz/check?t=ZZ000000000001&r=5&c=20261018120000&s=123456789012",
  fiscal_at: "2026-10-18T07:00:00Z",
};

describe("B5 local-bridge receipt_seq reservation (21 §16, 18 §4.1, qaror #68)", () => {
  beforeEach(async () => {
    await setupOffline();
  });
  afterEach(teardownOffline);

  it("shares the per-shift counter with enqueueEvent; same request → same number; signed + changed → refused", async () => {
    await enqueueEvent(
      "sale.created",
      { id: "s0", shift_id: SHIFT_ID, payments: [], lines: [] },
      { actorUserId: CASHIER, receiptSeq: { cashRegisterId: REG, shiftId: SHIFT_ID } },
    );
    const a = await reserveReceiptSeq({ ref: "draft-1", cashRegisterId: REG, shiftId: SHIFT_ID, request: "A" });
    expect(a.receipt_seq).toBe(2);
    const again = await reserveReceiptSeq({ ref: "draft-1", cashRegisterId: REG, shiftId: SHIFT_ID, request: "A" });
    expect(again.receipt_seq).toBe(2);
    // not signed yet and the cart changed → a fresh number (a gap is allowed, a double signature is not)
    const changed = await reserveReceiptSeq({ ref: "draft-1", cashRegisterId: REG, shiftId: SHIFT_ID, request: "B" });
    expect(changed.receipt_seq).toBe(3);
    await rememberFiscalResult("draft-1", RESULT);
    expect((await fiscalReservations.get("draft-1"))?.result).toEqual(RESULT);
    await expect(
      reserveReceiptSeq({ ref: "draft-1", cashRegisterId: REG, shiftId: SHIFT_ID, request: "C" }),
    ).rejects.toMatchObject({ code: "FISCAL_RESULT_PENDING", params: { receipt_seq: 3 } });
    // the event written with the reserved number: enqueueEvent keeps it and the counter moves on
    const res = await enqueueEvent(
      "sale.created",
      { id: "s1", shift_id: SHIFT_ID, receipt_seq: 3, fiscal_result: RESULT, payments: [], lines: [] },
      { actorUserId: CASHIER },
    );
    expect(res.receiptSeq).toBe(3);
    const row = await posDb().outbox.where("client_event_id").equals(res.clientEventId).first();
    expect(row).toMatchObject({ fiscal: true, fiscal_unacked: 1, receipt_seq: 3 });
    await releaseReservation("draft-1");
    expect(await fiscalReservations.get("draft-1")).toBeUndefined();
    const next = await enqueueEvent(
      "sale.created",
      { id: "s2", shift_id: SHIFT_ID, payments: [], lines: [] },
      { actorUserId: CASHIER, receiptSeq: { cashRegisterId: REG, shiftId: SHIFT_ID } },
    );
    expect(next.receiptSeq).toBe(4);
  });

  it("POS-13 checkout methods and a reserved local-bridge number in debt_payment.created (18 §12.2)", async () => {
    const base = {
      counterpartyId: "0190a000-0000-7000-8000-0000000000k1",
      branchId: DEVICE.branchId,
      cashRegisterId: REG,
      shiftId: SHIFT_ID,
      amount: "30000.00" as Money,
      isOffline: false,
      offlineSince: null,
      promiseDate: null,
      comment: null,
      allocation: { allocations: [], unallocated_amount: "30000.00" as Money, fiscal_lines: [] },
    };
    expect(
      debtPaymentPayload({ ...base, method: "click", checkout: { checkoutRef: "c-1", providerTxId: "77" } }),
    ).toMatchObject({ method: "click", checkout_ref: "c-1", provider_tx_id: "77" });
    const dyn = debtPaymentPayload({
      ...base,
      method: "uzqr",
      checkout: { checkoutRef: "c-2", providerTxId: "q-1" },
    });
    expect(dyn).toMatchObject({ qr_type: "dynamic", checkout_ref: "c-2", provider_tx_id: "q-1" });
    expect(dyn).not.toHaveProperty("terminal_ref");
    const res = await enqueueDebtPayment(
      { ...base, method: "cash", receiptSeq: 7, fiscalResult: RESULT },
      { actorUserId: CASHIER },
    );
    expect(res.receiptSeq).toBe(7);
    expect(res.payload).toMatchObject({ receipt_seq: 7, fiscal_result: RESULT });
  });
});
