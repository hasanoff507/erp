/**
 * BO-04 «Yetkazib beruvchiga to'lov» (19 §11; 13 §2.16; qaror #47; US-M07-04, US-M08-11; QT-M07-05 web part).
 */
import { allSettled, fork } from "effector";
import { describe, expect, it } from "vitest";

import type { Money } from "@shared/lib/money";

import {
  $lastCreated,
  $openDocs,
  $paymentFormOpen,
  $payments,
  advanceOf,
  autoAllocation,
  checkManual,
  createPaymentFx,
  debtPart,
  listPaymentsFx,
  openDocsFx,
  openShiftsFx,
  paymentFormOpened,
  paymentsOpened,
  supplierChosen,
  toPaymentBody,
  validatePayment,
  type OpenDocs,
  type PaymentForm,
} from "./index.ts";

const m = (v: string) => v as Money;

const docs: OpenDocs = {
  supplier_id: "s-1",
  payable_balance: "1500000.00",
  advance_balance: "0.00",
  items: [
    {
      target_doc_type: "debt_openings",
      target_doc_id: "do-1",
      number: "DO-1",
      doc_date: "2026-08-01",
      due_date: null,
      total: "500000.00",
      outstanding: "500000.00",
      einvoice_id: null,
      einvoice_risk_flag: null,
      vat_pending: "0.00",
    },
    {
      target_doc_type: "goods_receipts",
      target_doc_id: "gr-1",
      number: "KR-01-2026-000001",
      doc_date: "2026-09-10",
      due_date: "2026-10-10",
      total: "1120000.00",
      outstanding: "1000000.00",
      einvoice_id: "e-1",
      einvoice_risk_flag: "red",
      vat_pending: "120000.00",
    },
  ],
};

const form = (patch: Partial<PaymentForm> = {}): PaymentForm => ({
  supplierId: "s-1",
  method: "bank",
  shiftId: "",
  amount: "700000.00",
  docDate: "2026-10-17",
  manual: false,
  split: {},
  comment: "",
  ...patch,
});

describe("BO-04 supplier payment lib", () => {
  it("test_qt_m08_11 web: oldest first — debt opening, then the receipt", () => {
    expect(autoAllocation(m("700000.00"), docs)).toEqual({ "do-1": "500000.00", "gr-1": "200000.00" });
    expect(advanceOf(m("700000.00"), docs)).toBe("0.00");
  });

  it("qaror #47: overpay → advance (Dt 4310) = amount − debt part", () => {
    expect(debtPart(m("1800000.00"), docs)).toBe("1500000.00");
    expect(advanceOf(m("1800000.00"), docs)).toBe("300000.00");
    // an advance balance (payable < 0) — everything is an advance
    expect(advanceOf(m("100.00"), { payable_balance: "-50.00", items: [] })).toBe("100.00");
  });

  it("manual split: each line ≤ outstanding, Σ = debt part", () => {
    expect(checkManual({ "do-1": "200000.00", "gr-1": "500000.00" }, m("700000.00"), docs)).toMatchObject({
      lines: {},
      sumOk: true,
    });
    expect(checkManual({ "do-1": "600000.00", "gr-1": "100000.00" }, m("700000.00"), docs).lines).toEqual({
      "do-1": "exceeds",
    });
    expect(
      validatePayment(form({ manual: true, split: { "do-1": "100000.00" } }), docs, "2026-10-17"),
    ).toEqual({ allocations: "validation.allocation_sum_mismatch" });
  });

  it("test_qt_m07_05 web: bank body without allocations (server allocates); cash needs an open shift", () => {
    expect(toPaymentBody(form(), docs, null)).toEqual({
      supplier_id: "s-1",
      amount: "700000.00",
      method: "bank",
      doc_date: "2026-10-17",
      comment: null,
    });
    expect(validatePayment(form({ method: "cash" }), docs, "2026-10-17")).toEqual({
      shiftId: "validation.required",
    });
    const shift = {
      id: "sh-1",
      shift_no: 214,
      cash_register_id: "cr-1",
      branch_id: "b-1",
      status: "open" as const,
      opening_cash: "0.00",
      opened_at: "2026-10-17T03:00:00Z",
      closed_at: null,
    };
    expect(
      toPaymentBody(
        form({ method: "cash", shiftId: "sh-1", manual: true, split: { "gr-1": "700000.00" } }),
        docs,
        shift,
      ),
    ).toEqual({
      supplier_id: "s-1",
      amount: "700000.00",
      method: "cash",
      doc_date: "2026-10-17",
      cash_register_id: "cr-1",
      shift_id: "sh-1",
      allocations: [{ target_doc_type: "goods_receipts", target_doc_id: "gr-1", amount: "700000.00" }],
      comment: null,
    });
    expect(validatePayment(form({ amount: "", supplierId: "" }), null, "2026-10-17")).toEqual({
      supplierId: "validation.required",
      amount: "validation.required",
    });
  });
});

describe("BO-04 supplier payment model", () => {
  it("open tab → list; form → shifts + supplier's open documents; created → form closed, list reloaded", async () => {
    let listCalls = 0;
    const s = fork({
      handlers: [
        [
          listPaymentsFx,
          () => {
            listCalls += 1;
            return { items: [], next_cursor: null };
          },
        ],
        [openShiftsFx, () => []],
        [openDocsFx, () => docs],
        [
          createPaymentFx,
          () => ({
            id: "p-1",
            number: "SP-01-2026-000001",
            amount: "1800000.00",
            advance_amount: "300000.00",
            warnings: [],
          }),
        ],
      ],
    });
    await allSettled(paymentsOpened, { scope: s });
    expect(listCalls).toBe(1);
    expect(s.getState($payments)).toEqual([]);
    await allSettled(paymentFormOpened, { scope: s, params: { supplierId: null } });
    expect(s.getState($paymentFormOpen)).toBe(true);
    await allSettled(supplierChosen, { scope: s, params: "s-1" });
    expect(s.getState($openDocs)?.items).toHaveLength(2);
    await allSettled(createPaymentFx, {
      scope: s,
      params: toPaymentBody(form({ amount: "1800000.00" }), docs, null),
    });
    expect(s.getState($paymentFormOpen)).toBe(false);
    expect(s.getState($lastCreated)?.advance_amount).toBe("300000.00");
    expect(listCalls).toBe(2);
  });
});
