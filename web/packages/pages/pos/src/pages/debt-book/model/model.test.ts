/**
 * POS-13 / POS-06 device rules (B4, w-debts): QT-M08-16 / QT-M08-17 device halves (allocation over the local
 * open documents, receipt lines, offline overpayment), qaror #45 (online over-balance refused), the
 * `debt_payment.created` call and the `debt_settlement` receipt; QT-M08-08 quick customer form; 16 §5 limit.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Money } from "@shared/lib/money";
import type { CustomerDebtView, CustomerRow, OpenDebtDocRow } from "@shared/offline";

const enqueueMock = vi.fn();
const attemptGet = vi.fn();
vi.mock("@shared/offline", async (importOriginal) => {
  const real = await importOriginal<Record<string, unknown>>();
  return {
    ...real,
    enqueueDebtPayment: enqueueMock,
    cardAttempts: { ...(real.cardAttempts as object), get: attemptGet },
  };
});

const { customerDebtView } = await import("@shared/offline");
const {
  acceptDebtPaymentFx,
  debtReceiptDoc,
  planPayment,
  receiptLines,
  validateAccept,
  DebtPaymentError,
  GENERAL_LINE_NAME,
} = await import("./index.ts");
const { limitCheck, validateQuickCustomer } = await import("#/features/debt-customer/index.ts");

const m = (v: string) => v as Money;
const SALE_A = "0190a000-0000-7000-8000-0000000000a1";
const SALE_B = "0190a000-0000-7000-8000-0000000000b2";
const OPENING = "0190a000-0000-7000-8000-0000000000c3";

function sale(id: string, open: string, due: string, totals: string[]): OpenDebtDocRow {
  return {
    doc_type: "sales",
    doc_id: id,
    number: `S-${id.slice(-2)}`,
    doc_date: "2026-10-01",
    due_date: due,
    open_amount: open,
    lines: totals.map((t, i) => ({
      sale_line_id: `${id.slice(0, -4)}${id.slice(-2)}1${i}`,
      line_no: i + 1,
      product_id: `p-${i}`,
      name: `Tovar ${i + 1}`,
      name_ru: null,
      unit_code: "dona",
      qty: "2.000",
      price: "1000.0000",
      line_total: t,
      vat_rate: "12.00",
      settled_amount: "0.00",
      marking_code: null,
    })),
  };
}

function view(patch: Partial<CustomerRow> = {}): CustomerDebtView {
  return customerDebtView(
    {
      id: "c-1",
      name: "Botir Aliyev",
      phone: "+998901234567",
      receivable_balance: "500000.00",
      credit_limit: "600000.00",
      open_debt_docs: [
        sale(SALE_A, "300000.00", "2026-10-05", ["300000.00"]),
        sale(SALE_B, "200000.00", "2026-10-09", ["120000.00", "80000.00"]),
      ],
      _pulled_at: "2026-10-14T00:00:00.000Z",
      tokens: [],
      ...patch,
    },
    [],
  );
}

beforeEach(() => {
  enqueueMock.mockReset();
  attemptGet.mockReset();
});

describe("planPayment (POS-13 «To'lov yopadigan sotuvlar»)", () => {
  it("QT-M08-16: 350 000 closes A fully and B partly (rest 150 000); debt after = 150 000", () => {
    const plan = planPayment(view(), "350000.00", false);
    expect(plan.error).toBeNull();
    expect(plan.rows.map((r) => [r.number, r.amount, r.closes, r.left])).toEqual([
      ["S-a1", "300000.00", true, "0.00"],
      ["S-b2", "50000.00", false, "150000.00"],
    ]);
    expect(plan.after).toBe("150000.00");
    expect(plan.allocation?.fiscal_lines.map((l) => l.amount)).toEqual(["300000.00", "30000.00", "20000.00"]);
  });

  it("qaror #45: online above the debt is refused; QT-M08-17 offline it is accepted, the rest unallocated", () => {
    const v = view({
      receivable_balance: "300000.00",
      open_debt_docs: [sale(SALE_A, "300000.00", "2026-10-05", ["300000.00"])],
    });
    expect(planPayment(v, "350000.00", true).error).toBe("debt_payment_exceeds_balance");
    const offline = planPayment(v, "350000.00", false);
    expect(offline.error).toBeNull();
    expect(offline.overpay).toBe("50000.00");
    expect(offline.after).toBe("0.00");
    const general = offline.allocation?.fiscal_lines.find((l) => l.sale_id === null);
    expect(general?.amount).toBe("50000.00");
    expect(planPayment(v, "", true).error).toBe("amount_required");
    expect(planPayment(v, "0.00", true).error).toBe("amount_required");
  });

  it("an opening debt goes to the general receipt line «Qarz to'lovi (boshlang'ich qoldiq)»", () => {
    const v = view({
      receivable_balance: "100000.00",
      open_debt_docs: [
        {
          doc_type: "debt_openings",
          doc_id: OPENING,
          number: null,
          doc_date: "2026-09-30",
          due_date: null,
          open_amount: "100000.00",
        },
      ],
    });
    const plan = planPayment(v, "40000.00", true);
    expect(plan.rows[0]).toMatchObject({ docType: "debt_openings", closes: false, left: "60000.00" });
    const lines = receiptLines(plan.allocation?.fiscal_lines ?? [], {});
    expect(lines).toEqual([
      expect.objectContaining({
        name: GENERAL_LINE_NAME,
        qty: "1.000",
        total: "40000.00",
        vatRate: "0",
        vat: "0.00",
      }),
    ]);
  });
});

describe("acceptDebtPaymentFx (18 §12.2) and the debt_settlement receipt", () => {
  const base = () => {
    const v = view();
    return {
      view: v,
      plan: planPayment(v, "350000.00", false),
      method: "cash" as const,
      device: { branchId: "b-1", cashRegisterId: "cr-1" },
      shiftId: "s-1",
      cashier: { userId: "u-1", permissions: ["debts.payment.accept"] },
      online: false,
      offlineSince: "2026-10-14T03:00:00.000Z",
      fiscalBlocked: false,
      promiseDate: "2026-10-30",
      comment: null,
      cashReceived: m("400000.00"),
    };
  };

  it("validates shift, right, 48 h block, cash received, online-only UzQR", () => {
    expect(() => validateAccept({ ...base(), shiftId: null })).toThrowError("SHIFT_NOT_OPEN");
    expect(() => validateAccept({ ...base(), cashier: { userId: "u", permissions: [] } })).toThrowError(
      "PERMISSION_DENIED",
    );
    expect(() => validateAccept({ ...base(), fiscalBlocked: true })).toThrowError(
      "FISCAL_OFFLINE_48H_BLOCKED",
    );
    expect(() => validateAccept({ ...base(), cashReceived: m("1.00") })).toThrowError("CASH_NOT_ENOUGH");
    expect(() => validateAccept({ ...base(), method: "uzqr" })).toThrowError("PAYMENT_ONLINE_ONLY");
    expect(() => validateAccept({ ...base(), method: "card" })).toThrowError("PAYMENT_NOT_COMPLETE");
    const online = { ...base(), online: true, plan: planPayment(view(), "600000.00", true) };
    expect(() => validateAccept(online)).toThrowError(DebtPaymentError);
  });

  it("writes debt_payment.created with the device allocation, the change in cash and a receipt", async () => {
    enqueueMock.mockResolvedValue({
      clientEventId: "ev-1",
      seq: 9,
      receiptSeq: 4,
      creditReceiptSeq: null,
      createdAt: "2026-10-14T04:00:00.000Z",
      payload: { id: "pay-000123" },
    });
    const done = await acceptDebtPaymentFx(base());
    const [input, opts] = enqueueMock.mock.calls[0] as [Record<string, unknown>, Record<string, unknown>];
    expect(input).toMatchObject({
      counterpartyId: "c-1",
      cashRegisterId: "cr-1",
      shiftId: "s-1",
      amount: "350000.00",
      method: "cash",
      isOffline: true,
      offlineSince: "2026-10-14T03:00:00.000Z",
      promiseDate: "2026-10-30",
    });
    expect((input.allocation as { allocations: unknown[] }).allocations).toHaveLength(2);
    expect(opts).toEqual({ actorUserId: "u-1" });
    expect(done).toMatchObject({ receiptSeq: 4, change: "50000.00", received: "400000.00", overpay: "0.00" });

    const doc = debtReceiptDoc(
      done,
      {},
      { name: "Baraka", stir: null, branchName: null, registerName: "Kassa 1" },
      "Dilnoza",
      214,
    );
    expect(doc.kind).toBe("debt_settlement");
    expect(doc.receiptSeq).toBe(4);
    expect(doc.totals?.total).toBe("350000.00");
    // Σ line VAT (32 142.86 + 3 214.29 + 2 142.86), 08 §13.1
    expect(doc.totals?.vat).toEqual([{ rate: "12.00", amount: "37500.01" }]);
    expect(doc.payments).toMatchObject({ form: "cash", received: "400000.00", change: "50000.00" });
  });

  it("an approved integrated card attempt leaves card_attempts with the event (16 §2.1)", async () => {
    attemptGet.mockResolvedValue({ status: "approved" });
    enqueueMock.mockResolvedValue({
      clientEventId: "ev-c",
      seq: 1,
      receiptSeq: 1,
      creditReceiptSeq: null,
      createdAt: "2026-10-14T04:00:00.000Z",
      payload: { id: "p" },
    });
    await acceptDebtPaymentFx({
      ...base(),
      method: "card",
      cashReceived: null,
      clientEventId: "ev-c",
      card: { mode: "integrated", attemptId: "att-1", cardResult: { status: "approved" } },
    });
    const [input, opts] = enqueueMock.mock.calls[0] as [Record<string, unknown>, Record<string, unknown>];
    expect(input.card).toEqual({ mode: "integrated", cardResult: { status: "approved" } });
    expect(opts).toEqual({ actorUserId: "u-1", clientEventId: "ev-c", removeCardAttemptIds: ["att-1"] });
  });
});

describe("debt customer (POS-02/03/06)", () => {
  it("QT-M08-08: quick customer needs name + a full Uzbek phone", () => {
    expect(validateQuickCustomer({ name: "Malika", phone: "977114022" })).toEqual({});
    expect(validateQuickCustomer({ name: " ", phone: "97" })).toEqual({
      name: "validation.required",
      phone: "validation.phone_uz",
    });
  });

  it("16 §5: over the limit — online an approval, offline the cashier's confirmation; no limit → no check", () => {
    const v = view();
    expect(limitCheck(v, m("100000.00"), true)).toMatchObject({
      over: false,
      after: "600000.00",
      usedPct: 100,
      left: "0.00",
    });
    expect(limitCheck(v, m("100000.01"), true)).toMatchObject({
      over: true,
      needsApproval: true,
      needsOfflineConfirm: false,
    });
    expect(limitCheck(v, m("100000.01"), false)).toMatchObject({
      over: true,
      needsApproval: false,
      needsOfflineConfirm: true,
    });
    const noLimit = view({ credit_limit: null });
    expect(limitCheck(noLimit, m("9999999.00"), true)).toMatchObject({
      over: false,
      usedPct: null,
      left: null,
    });
  });
});
