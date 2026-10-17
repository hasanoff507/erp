/**
 * POS-02/03/04 models: `sale.created` payload exactly per 18 §4.1, payment validation (07 POS-03), the
 * scanner pipeline (weight barcodes US-M09-06 / QT-M09-06, marking duplicate check T08), the void event
 * (QT-M01-11) and the receipt document (two languages, VAT, NUSXA — QT-M01-12, US-M10-01).
 */
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { ProductView } from "@shared/offline";

const catalogMock = {
  byBarcode: vi.fn(),
  byItemCode: vi.fn(),
};
const markingMock = { isUsed: vi.fn(() => Promise.resolve(false)) };

vi.mock("@shared/offline", async (importOriginal) => {
  const real = await importOriginal<Record<string, unknown>>();
  return { ...real, catalog: { ...(real.catalog as object), ...catalogMock }, markingCodes: markingMock };
});

const { priceLines } = await import("#/entities/receipt-draft/index.ts");
const { buildSalePayload, issuesFiscalReceipt, paymentForm } = await import("./lib/sale-payload.ts");
const { resolveScan, toLine, gtinOf, markingCodeValid } = await import("./scan.ts");
const { validateParts, partsFor, SaleError, debtOverLimit, cardPartOf } = await import("./payment.ts");
const { draftVoidPayload } = await import("./void.ts");
const { receiptDoc } = await import("./receipt.ts");

const view = (
  over: Partial<ProductView["product"]> = {},
  price: string | null = "4000.0000",
): ProductView => ({
  product: {
    id: "p-1",
    name: "Non «Patir»",
    name_ru: "Хлеб",
    category_id: null,
    unit_code: "dona",
    vat_rate: "12.00",
    tokens: [],
    ...over,
  },
  price,
});

const ctx = {
  saleId: "0190a000-0000-7000-8000-0000000000a1",
  branchId: "b-1",
  cashRegisterId: "c-1",
  shiftId: "s-1",
  tempNumber: "d-1-7",
  docDate: "2026-10-17",
  counterpartyId: null,
  isOffline: false,
  offlineSince: null,
  delivery: "printed" as const,
  deliveryReason: null,
};

describe("sale.created payload (18 §4.1)", () => {
  it("cash sale: frozen 4 dp price, 2 dp rate, line_total / vat_amount, receipt_seq left to enqueue", () => {
    const totals = priceLines([toLine(view(), "2.000")], null);
    const p = buildSalePayload(totals, [{ method: "cash", amount: totals.total }], null, null, ctx);
    expect(p).toMatchObject({
      id: ctx.saleId,
      branch_id: "b-1",
      cash_register_id: "c-1",
      shift_id: "s-1",
      receipt_seq: null,
      credit_receipt_seq: null,
      fiscal_result: null,
      delivery: "printed",
      delivery_reason: null,
      temp_number: "d-1-7",
      doc_date: "2026-10-17",
      counterparty_id: null,
      is_offline: false,
      offline_since: null,
      comment: null,
    });
    expect(p.lines[0]).toEqual({
      id: totals.lines[0]?.id,
      product_id: "p-1",
      unit_code: "dona",
      qty: "2.000",
      price: "4000.0000",
      vat_rate: "12.00",
      vat_exemption_code: null,
      discount_pct: null,
      discount_amount: null,
      discount_source: null,
      discount_rule_id: null,
      discount_approval: null,
      marking_code: null,
      marking_offline: null,
      line_total: "8000.00",
      vat_amount: "857.14",
    });
    expect(p.payments).toEqual([{ method: "cash", amount: "8000.00" }]);
  });

  it("manual discount carries source + approval on the first discounted line only", () => {
    const lines = [toLine(view(), "1.000"), toLine(view({ id: "p-2" }), "1.000")];
    const approval = {
      mode: "local_pin" as const,
      approved_by: "m-1",
      pin_verified_locally: true,
      approval_request_id: null,
    };
    const totals = priceLines(lines, { pct: "10.00", approval });
    const p = buildSalePayload(totals, [{ method: "cash", amount: totals.total }], approval, "10.00", ctx);
    expect(p.lines[0]).toMatchObject({
      discount_source: "manual",
      discount_amount: "400.00",
      discount_pct: "10.00",
      discount_approval: approval,
    });
    expect(p.lines[1]).toMatchObject({ discount_source: "manual", discount_approval: null });
  });

  it("integrated card sends only card_result; manual card only amount + reason (PCI, 18 §4.1)", () => {
    const totals = priceLines([toLine(view(), "1.000")], null);
    const integrated = buildSalePayload(
      totals,
      [
        {
          method: "card",
          amount: totals.total,
          card: {
            mode: "integrated",
            attemptId: "a-1",
            cardResult: { attempt_id: "a-1", status: "approved" },
          },
        },
      ],
      null,
      null,
      ctx,
    );
    expect(integrated.payments[0]).toEqual({
      method: "card",
      amount: "4000.00",
      card_entry_mode: "integrated",
      card_result: { attempt_id: "a-1", status: "approved" },
    });
    const manual = buildSalePayload(
      totals,
      [
        {
          method: "card",
          amount: totals.total,
          card: { mode: "manual", manualReason: "standalone_terminal", approval: null, attemptId: null },
        },
      ],
      null,
      null,
      { ...ctx, isOffline: true, offlineSince: "2026-10-17T05:00:00.000Z" },
    );
    expect(manual.payments[0]).toEqual({
      method: "card",
      amount: "4000.00",
      card_entry_mode: "manual",
      manual_reason: "standalone_terminal",
      card_manual_approval: null,
    });
    expect(Object.keys(manual.payments[0] ?? {})).not.toContain("card_mask");
    expect(manual).toMatchObject({ is_offline: true, offline_since: "2026-10-17T05:00:00.000Z" });
  });

  it("static UzQR and debt parts; debt-only sale issues no fiscal receipt (qaror #30)", () => {
    const totals = priceLines([toLine(view(), "1.000")], null);
    const mixed = [
      { method: "uzqr" as const, amount: "1000.00" as never, terminalRef: " 77 " },
      { method: "debt" as const, amount: "3000.00" as never, dueDate: "2026-10-24", debtApproval: null },
    ];
    const p = buildSalePayload(totals, mixed, null, null, { ...ctx, counterpartyId: "cp-1" });
    expect(p.payments).toEqual([
      { method: "uzqr", amount: "1000.00", qr_type: "static", terminal_ref: "77" },
      { method: "debt", amount: "3000.00", due_date: "2026-10-24", debt_approval: null },
    ]);
    expect(issuesFiscalReceipt(mixed)).toBe(true);
    expect(issuesFiscalReceipt([{ method: "debt", amount: "4000.00" as never }])).toBe(false);
    const debtOnly = buildSalePayload(totals, [{ method: "debt", amount: totals.total }], null, null, {
      ...ctx,
      delivery: "electronic",
      deliveryReason: "customer_request",
    });
    expect(debtOnly).toMatchObject({ delivery: "printed", delivery_reason: null });
  });

  it("payment form follows 18 §4.5", () => {
    expect(paymentForm([{ method: "cash", amount: "1.00" as never }])).toBe("cash");
    expect(paymentForm([{ method: "uzqr", amount: "1.00" as never }])).toBe("qr");
    expect(
      paymentForm([
        { method: "cash", amount: "1.00" as never },
        { method: "card", amount: "1.00" as never },
      ]),
    ).toBe("mixed");
    expect(
      paymentForm([
        { method: "card", amount: "1.00" as never },
        { method: "debt", amount: "1.00" as never },
      ]),
    ).toBe("card");
  });
});

describe("payment validation (07 POS-03)", () => {
  const base = () => {
    const draftLines = [toLine(view(), "1.000")];
    return {
      payment: {
        saleId: "s",
        clientEventId: "e",
        mode: "cash" as const,
        parts: [],
        cashReceived: "5000.00",
        dueDate: null,
        debtApproval: null,
        uzqrRef: "",
        electronic: null,
      },
      draft: { ref: "r", lines: draftLines, selectedLineId: null, customerId: null, discount: null },
      totals: priceLines(draftLines, null),
      card: null,
      device: {
        deviceId: "d",
        tenantId: "t",
        branchId: "b",
        cashRegisterId: "c",
        branchName: null,
        cashRegisterName: null,
      },
      shift: {
        id: "s-1",
        cash_register_id: "c",
        shift_no: 3,
        opened_at: "2026-10-17T03:00:00Z",
        opened_by: "u",
        status: "open" as const,
      },
      cashier: {
        userId: "u",
        fullName: "K",
        roleCodes: ["cashier"],
        permissions: ["sales.create"],
        verifiedAt: "",
        via: "local" as const,
      },
      online: true,
      offlineSince: null,
      fiscalBlocked: false,
      fiscalLocked: false,
    };
  };

  it("cash needs enough cash received", () => {
    expect(validateParts(base())).toEqual([{ method: "cash", amount: "4000.00" }]);
    expect(() =>
      validateParts({ ...base(), payment: { ...base().payment, cashReceived: "3000.00" } }),
    ).toThrow(SaleError);
  });

  it("48 h block and fm lock refuse a fiscal receipt (QT-OFFLINE48-03, T07)", () => {
    expect(() => validateParts({ ...base(), fiscalBlocked: true })).toThrowError(
      "FISCAL_OFFLINE_48H_BLOCKED",
    );
    expect(() => validateParts({ ...base(), fiscalLocked: true })).toThrowError("FISCAL_DEVICE_LOCKED");
  });

  it("UzQR only online; debt needs a customer and debts.create", () => {
    const uzqr = { ...base(), payment: { ...base().payment, mode: "uzqr" as const }, online: false };
    expect(() => validateParts(uzqr)).toThrowError("PAYMENT_ONLINE_ONLY");
    const debt = { ...base(), payment: { ...base().payment, mode: "debt" as const } };
    expect(() => validateParts(debt)).toThrowError("CUSTOMER_REQUIRED");
    const withCustomer = { ...debt, draft: { ...debt.draft, customerId: "cp" } };
    expect(() => validateParts(withCustomer)).toThrowError("PERMISSION_DENIED");
  });

  it("mixed must cover the total; card mode needs the card outcome", () => {
    const mixed = {
      ...base(),
      payment: {
        ...base().payment,
        mode: "mixed" as const,
        parts: [{ method: "cash" as const, amount: "1000.00" as never }],
      },
    };
    expect(() => validateParts(mixed)).toThrowError("PAYMENT_NOT_COMPLETE");
    const card = { ...base(), payment: { ...base().payment, mode: "card" as const } };
    expect(() => validateParts(card)).toThrowError("PAYMENT_METHOD_REQUIRED");
    const outcome = cardPartOf({
      mode: "manual",
      manualReason: "terminal_offline",
      approval: null,
      amount: "4000.00" as never,
      attemptId: null,
    });
    expect(partsFor(card.payment, card.totals.total, outcome)).toHaveLength(1);
    expect(validateParts({ ...card, card: outcome })[0]?.card).toMatchObject({
      mode: "manual",
      manualReason: "terminal_offline",
    });
  });

  it("marked goods without a code never close the receipt", () => {
    const b = base();
    const marked = { ...b.draft.lines[0]!, kind: "marked" as const };
    expect(() => validateParts({ ...b, draft: { ...b.draft, lines: [marked] } })).toThrowError(
      "MARKING_CODE_REQUIRED",
    );
  });

  it("debt over the credit limit (18 §4.3)", () => {
    const customer = {
      id: "c",
      name: "A",
      tokens: [],
      credit_limit: "500000.00",
      receivable_balance: "450000.00",
    };
    expect(debtOverLimit(customer, "40000.00" as never)).toBe(false);
    expect(debtOverLimit(customer, "60000.00" as never)).toBe(true);
    expect(debtOverLimit({ ...customer, credit_limit: null }, "60000.00" as never)).toBe(false);
  });
});

describe("scanner pipeline", () => {
  beforeEach(() => {
    catalogMock.byBarcode.mockReset();
    catalogMock.byItemCode.mockReset();
    markingMock.isUsed.mockReset();
    markingMock.isUsed.mockResolvedValue(false);
  });
  const input = (code: string, extra: Partial<Parameters<typeof resolveScan>[0]> = {}) => ({
    code,
    awaiting: null,
    templates: [],
    precheck: "warn" as const,
    online: true,
    usedInDraft: [],
    ...extra,
  });

  it("QT-M09-06: a weight label adds the product with the weight from the code", async () => {
    catalogMock.byItemCode.mockResolvedValue(
      view({ id: "beef", name: "Mol go'shti", unit_code: "kg", is_weighed: true }, "95000.0000"),
    );
    const r = await resolveScan(input("2212345012503"));
    expect(catalogMock.byItemCode).toHaveBeenCalledWith("12345");
    expect(r).toMatchObject({
      kind: "line",
      line: { productId: "beef", qty: "1.250", price: "95000.0000", fractional: true },
    });
    const totals = priceLines(
      [(r as unknown as { line: Parameters<typeof priceLines>[0][number] }).line],
      null,
    );
    expect(totals.total).toBe("118750.00");
  });

  it("ordinary barcode adds pack quantity; weighed product by plain barcode asks for the weight", async () => {
    catalogMock.byBarcode.mockResolvedValueOnce({
      ...view(),
      barcode: { barcode: "478", id: "x", product_id: "p-1", units_per_barcode: "6.000" },
      unitsPerBarcode: "6.000",
    });
    expect(await resolveScan(input("4780000000001"))).toMatchObject({ kind: "line", line: { qty: "6.000" } });
    catalogMock.byBarcode.mockResolvedValueOnce({
      ...view({ is_weighed: true }),
      barcode: {},
      unitsPerBarcode: "1.000",
    });
    expect(await resolveScan(input("4780000000002"))).toMatchObject({ kind: "weigh" });
  });

  it("no price → refused; unknown code → PRODUCT_NOT_FOUND", async () => {
    catalogMock.byBarcode.mockResolvedValueOnce({ ...view({}, null), barcode: {}, unitsPerBarcode: "1.000" });
    expect(await resolveScan(input("4780000000003"))).toMatchObject({
      kind: "error",
      error: { code: "PRICE_UNKNOWN" },
    });
    catalogMock.byBarcode.mockResolvedValue(null);
    expect(await resolveScan(input("ABC123"))).toMatchObject({
      kind: "error",
      error: { code: "PRODUCT_NOT_FOUND" },
    });
  });

  it("T08: marked product waits for its DataMatrix; duplicates are refused locally", async () => {
    const marked = view({ is_marked: true });
    catalogMock.byBarcode.mockResolvedValueOnce({ ...marked, barcode: {}, unitsPerBarcode: "1.000" });
    expect(await resolveScan(input("4780000000004"))).toMatchObject({ kind: "await_marking" });
    const dm = "0104780000000004215abcdefgh\u001d93ZZZZ";
    expect(gtinOf(dm)).toBe("04780000000004");
    expect(markingCodeValid(dm)).toBe(true);
    expect(await resolveScan(input(dm, { awaiting: marked }))).toMatchObject({
      kind: "line",
      line: { markingCode: dm, qty: "1.000" },
    });
    expect(await resolveScan(input(dm, { awaiting: marked, usedInDraft: [dm] }))).toMatchObject({
      error: { code: "MARKING_CODE_ALREADY_SOLD" },
    });
    markingMock.isUsed.mockResolvedValueOnce(true);
    expect(await resolveScan(input(dm, { awaiting: marked }))).toMatchObject({
      error: { code: "MARKING_CODE_ALREADY_SOLD" },
    });
    expect(await resolveScan(input("4780000000004", { awaiting: marked }))).toMatchObject({
      error: { code: "MARKING_SCAN_REQUIRED" },
    });
    expect(await resolveScan(input(dm, { awaiting: marked, precheck: "block" }))).toMatchObject({
      error: { code: "MARKING_VERIFY_UNAVAILABLE" },
    });
    expect(await resolveScan(input(dm, { awaiting: view({ is_marked: true }, null) }))).toMatchObject({
      error: { code: "MARKING_PRICE_UNKNOWN_OFFLINE" },
    });
  });
});

describe("sale.draft_voided (18 §5, QT-M01-11)", () => {
  it("whole receipt → voided_lines null; one line → that line only", () => {
    const lines = [toLine(view(), "1.000"), toLine(view({ id: "p-2" }), "2.000")];
    const draft = { ref: "draft-1", lines, selectedLineId: null, customerId: null, discount: null };
    expect(draftVoidPayload({ draft, lineId: null })).toEqual({
      draft_ref: "draft-1",
      voided_lines: null,
      reason: null,
    });
    const one = draftVoidPayload({ draft, lineId: lines[1]!.id });
    expect(one.voided_lines).toEqual([
      { line_id: lines[1]!.id, product_id: "p-2", qty: "2.000", price: "4000.0000", marking_code: null },
    ]);
  });
});

describe("receipt document (08 §13, QT-M01-12, US-M10-01)", () => {
  it("bilingual lines, VAT by rate, fiscal block, NUSXA copy flag", () => {
    const totals = priceLines([toLine(view(), "2.000")], null);
    const sale = {
      saleId: "s",
      clientEventId: "e",
      receiptSeq: 7,
      createdAt: "2026-10-17T10:00:00.000Z",
      tempNumber: "d-1",
      fiscal: true,
      totals,
      parts: [{ method: "cash" as const, amount: totals.total }],
      form: "cash" as const,
      received: "10000.00" as never,
      change: "2000.00" as never,
      delivery: "printed" as const,
      deliveryReason: null,
      cashierName: "Akmal",
      shiftNo: 3,
      customerName: null,
      isOffline: false,
    };
    const store = { name: "Baraka", stir: "123456789", branchName: "Chilonzor", registerName: "Kassa 1" };
    const fiscalView = {
      status: "fiscalized" as const,
      fiscalReceiptId: "fr-1",
      fiscalSign: "123456",
      qrUrl: "https://ofd.soliq.uz/check?t=1",
      fmTerminalId: "FM1",
      fmReceiptSeq: 55,
      fiscalAt: null,
      number: "K-01-2026-000154",
      syncStatus: "accepted" as const,
      errorCode: null,
    };
    const doc = receiptDoc(sale, store, fiscalView, true);
    expect(doc.copy).toBe(true);
    expect(doc.number).toBe("K-01-2026-000154");
    expect(doc.lines[0]).toMatchObject({ name: "Non «Patir»", nameRu: "Хлеб", vatRate: "12", vat: "857.14" });
    expect(doc.totals?.vat).toEqual([{ rate: "12.00", amount: "857.14" }]);
    expect(doc.fiscal).toMatchObject({ fiscalSign: "123456", qrUrl: "https://ofd.soliq.uz/check?t=1" });
    expect(doc.payments).toMatchObject({ form: "cash", received: "10000.00", change: "2000.00" });
    expect(receiptDoc(sale, store, { ...fiscalView, status: "pending" }, false).fiscal).toBeNull();
  });
});

describe("credit_type receipt numbers (SYNC-09, 18 §4.1)", () => {
  it("sale + debt under credit_type → two numbers; debt-only → one into credit_receipt_seq", async () => {
    const { receiptSeqOption, creditTypeOf } = await import("./payment.ts");
    const cash = { method: "cash" as const, amount: "1000.00" as never };
    const debt = { method: "debt" as const, amount: "3000.00" as never };
    expect(receiptSeqOption([cash, debt], true, "c", "s")).toEqual({
      cashRegisterId: "c",
      shiftId: "s",
      count: 2,
    });
    expect(receiptSeqOption([debt], true, "c", "s")).toEqual({
      cashRegisterId: "c",
      shiftId: "s",
      target: "credit_receipt_seq",
    });
    expect(receiptSeqOption([cash, debt], false, "c", "s")).toEqual({ cashRegisterId: "c", shiftId: "s" });
    expect(receiptSeqOption([debt], false, "c", "s")).toBeNull();
    expect(creditTypeOf({ tenant_settings: { fiscal_policy: { credit_sale_receipt: "credit_type" } } })).toBe(
      true,
    );
    expect(creditTypeOf({ tenant_settings: {} })).toBe(false);
  });
});
