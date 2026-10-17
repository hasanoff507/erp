/* eslint-disable @typescript-eslint/require-await -- in-memory fakes of async collaborators */
/**
 * POS-05 (07; 18 §7.1; US-M02-01…03; QT-M02-01…04 client side): refund amounts (ROUND_HALF_UP, last
 * return takes the rest), VAT of the refund, approval need (no receipt always, expired → unlimited only,
 * over own limit), exact `return.created` payload, sources (server / local history), card refund via the
 * Fake terminal (approved / declined / no answer stays unknown).
 */
import { describe, expect, it } from "vitest";

import { createFakeCardTerminalClient, type TerminalInfo } from "@shared/lib/card-terminal";
import type { Money } from "@shared/lib/money";
import type { SaleOut } from "@shared/models";

import { runCardRefund, manualPolicyNeed, manualReasonFor, type CardRefundDeps } from "./card.ts";
import {
  defaultRefundMethod,
  fromLocalHistory,
  fromServerSale,
  localReturnedQty,
  qtyValid,
  refundLine,
  returnApprovalNeed,
  returnPayload,
  returnTotals,
  returnsEscape,
  type LineState,
  type SourceLine,
} from "./index.ts";

const SALE: SaleOut = {
  id: "sale-1",
  number: "K-01-2026-000471",
  temp_number: null,
  doc_date: "2026-10-15",
  status: "posted",
  branch_id: "b-1",
  shift_id: "s-0",
  cash_register_id: "cr-1",
  counterparty_id: null,
  total_amount: "85000.00",
  is_offline: false,
  debt_limit_exceeded: false,
  created_by: "u-1",
  created_at: "2026-10-15T13:20:00Z",
  posted_at: "2026-10-15T13:20:01Z",
  device_id: "d-1",
  comment: null,
  lines: [
    {
      id: "l-1",
      sale_line_id: "sl-1",
      line_no: 1,
      product_id: "p-cola",
      product_name: "Coca-Cola 1.5L",
      unit_code: "pcs",
      qty: "3.000",
      returned_qty: "1.000",
      price: "12000.0000",
      discount_amount: "0.00",
      discount_pct: null,
      discount_source: null,
      discount_rule_id: null,
      vat_rate: "12.00",
      vat_exemption_code: null,
      vat_amount: "3857.14",
      line_total: "36000.00",
      marking_code: null,
      settled_amount: "0.00",
    },
    {
      id: "l-2",
      sale_line_id: "sl-2",
      line_no: 2,
      product_id: "p-cig",
      product_name: "Sigaret",
      unit_code: "pcs",
      qty: "1.000",
      returned_qty: "0.000",
      price: "49000.0000",
      discount_amount: "0.00",
      discount_pct: null,
      discount_source: null,
      discount_rule_id: null,
      vat_rate: "12.00",
      vat_exemption_code: null,
      vat_amount: "5250.00",
      line_total: "49000.00",
      marking_code: "0104600000000000\u001d21abc",
      settled_amount: "0.00",
    },
  ],
  payments: [
    {
      id: "pay-1",
      method: "cash",
      amount: "85000.00",
      card_entry_mode: null,
      manual_reason: null,
      card_type: null,
      card_mask: null,
      rrn: null,
      approval_code: null,
      card_scheme: null,
      terminal_ref: null,
      qr_type: null,
      provider_tx_id: null,
      due_date: null,
    },
  ],
  fiscal_receipts: [],
};

const sel = (lines: SourceLine[], picks: Record<number, Partial<LineState>>): LineState[] =>
  lines.map((_l, i) => ({
    key: String(i),
    selected: false,
    qty: "1.000",
    restock: true,
    expired: false,
    ...picks[i],
  }));

describe("refund amounts and VAT (18 §7.1, US-M02-03)", () => {
  const src = fromServerSale(SALE);
  const cola = src.lines[0] as SourceLine;

  it("test_qt_m02_01: one 12 000 Coca-Cola → 12 000 refund, VAT 12% inside = 1 285.71", () => {
    expect(refundLine(cola, "1.000")).toBe("12000.00");
    const t = returnTotals(src, src.lines, sel(src.lines, { 0: { selected: true } }));
    expect(t).toMatchObject({
      amount: "12000.00",
      vat: "1285.71",
      moneyPart: "12000.00",
      debtPart: "0.00",
      count: 1,
    });
  });

  it("the last return of a line takes the rest; qty limited to the not-yet-returned rest", () => {
    const odd = { ...cola, lineTotal: "10000.00" as Money, qty: "3.000", returnedQty: "1.000" };
    expect(refundLine(odd, "1.000")).toBe("3333.00");
    expect(refundLine(odd, "2.000")).toBe("6667.00"); // 10 000 − round(10 000 × 1/3)
    expect(qtyValid(cola, "2.000")).toBe(true);
    expect(qtyValid(cola, "3.000")).toBe(false);
    expect(qtyValid(cola, "0.5")).toBe(false);
    expect(qtyValid(cola, "0")).toBe(false);
  });

  it("a debt sale: the open debt is reduced first, only the rest is money (receipt part)", () => {
    const debt = {
      ...src,
      payments: [{ method: "debt", amount: "5000.00" as Money, cardEntryMode: null, rrn: null }],
    };
    const t = returnTotals(debt, src.lines, sel(src.lines, { 0: { selected: true } }));
    expect(t).toMatchObject({ amount: "12000.00", debtPart: "5000.00", moneyPart: "7000.00" });
  });

  it("local returns not yet synced are added to the server's returned qty", () => {
    const events = [
      {
        type: "return.created",
        status: "pending",
        retryable: null,
        payload: { sale_id: "sale-1", lines: [{ sale_line_id: "sl-1", qty: "1.000" }] },
      },
      {
        type: "return.created",
        status: "accepted",
        retryable: null,
        payload: { sale_id: "sale-1", lines: [{ sale_line_id: "sl-1", qty: "1.000" }] },
      },
    ];
    expect(localReturnedQty(events, "sale-1", true)).toEqual({ "sl-1": "1.000" });
    expect(localReturnedQty(events, "sale-1", false)).toEqual({ "sl-1": "2.000" });
    expect(fromServerSale(SALE, { "sl-1": "1.000" }).lines[0]?.returnedQty).toBe("2.000");
  });
});

describe("approval need (QT-M02-02/-03/-04, 18 §7.1)", () => {
  const cashier = { roleCodes: ["cashier"] };
  it("test_qt_m02_03: 100 000 within the cashier's 100 000 returns.approve limit → no approval", () => {
    expect(
      returnApprovalNeed({
        cashier,
        ownLimit: "100000.0000",
        amount: "100000.00" as Money,
        noReceipt: false,
        expired: false,
      }),
    ).toEqual({
      needed: false,
    });
  });
  it("test_qt_m02_04: 150 000 above the limit → return_over_limit", () => {
    expect(
      returnApprovalNeed({
        cashier,
        ownLimit: "100000.0000",
        amount: "150000.00" as Money,
        noReceipt: false,
        expired: false,
      }),
    ).toEqual({
      needed: true,
      kind: "return_over_limit",
      amount: "150000.00",
      reason: "over_limit",
    });
  });
  it("test_qt_m02_02: no receipt → return_no_receipt for any amount", () => {
    expect(
      returnApprovalNeed({
        cashier,
        ownLimit: null,
        amount: "1000.00" as Money,
        noReceipt: true,
        expired: false,
      }),
    ).toMatchObject({
      needed: true,
      kind: "return_no_receipt",
    });
  });
  it("expired goods → only an unlimited returns.approve covers (amount null); owner never asks", () => {
    expect(
      returnApprovalNeed({
        cashier,
        ownLimit: "100000.0000",
        amount: "1000.00" as Money,
        noReceipt: false,
        expired: true,
      }),
    ).toMatchObject({
      needed: true,
      amount: null,
      reason: "expired",
    });
    expect(
      returnApprovalNeed({
        cashier,
        ownLimit: null,
        amount: "1000.00" as Money,
        noReceipt: false,
        expired: true,
      }),
    ).toEqual({ needed: false });
    expect(
      returnApprovalNeed({
        cashier: { roleCodes: ["owner"] },
        ownLimit: undefined,
        amount: "1.00" as Money,
        noReceipt: true,
        expired: true,
      }),
    ).toEqual({
      needed: false,
    });
  });
});

describe("return.created payload (18 §7.1)", () => {
  it("has exactly the documented fields; expired line → restock false; no card block for cash", () => {
    const src = fromServerSale(SALE);
    const p = returnPayload({
      id: "r-1",
      branchId: "b-1",
      shiftId: "s-1",
      cashRegisterId: "cr-1",
      source: src,
      lines: src.lines,
      state: sel(src.lines, { 0: { selected: true, expired: true } }),
      reason: "defective",
      refundMethod: defaultRefundMethod(src),
      refundCard: null,
      approval: {
        mode: "local_pin",
        approved_by: "u-m",
        pin_verified_locally: true,
        approval_request_id: null,
      },
      isOffline: false,
      counterpartyId: null,
    });
    expect(Object.keys(p).sort()).toEqual(
      [
        "approval",
        "branch_id",
        "cash_register_id",
        "counterparty_id",
        "fiscal_result",
        "id",
        "is_offline",
        "lines",
        "reason",
        "receipt_seq",
        "refund_card",
        "refund_method",
        "sale_id",
        "shift_id",
      ].sort(),
    );
    expect(p.refund_method).toBe("cash");
    expect(p.refund_card).toBeNull();
    expect(p.lines).toEqual([
      {
        sale_line_id: "sl-1",
        product_id: "p-cola",
        qty: "1.000",
        price: "12000.0000",
        vat_rate: "12.00",
        vat_exemption_code: null,
        marking_code: null,
        restock: false,
      },
    ]);
  });

  it("local history row without line details cannot be a source", () => {
    expect(fromLocalHistory({ id: "x", created_at: "t", summary: {} })).toBeNull();
    const src = fromLocalHistory({
      id: "sale-9",
      number: null,
      created_at: "t",
      summary: {
        temp_number: "d-1-17",
        lines: [
          {
            id: "sl-9",
            product_id: "p",
            name: "Non",
            unit_code: "pcs",
            qty: "2.000",
            price: "3000.0000",
            line_total: "6000.00",
            vat_rate: "0.00",
          },
        ],
        payments: [{ method: "card", amount: "6000.00", card_entry_mode: "integrated" }],
      },
    });
    expect(src).toMatchObject({ saleId: "sale-9", number: "d-1-17", origin: "local" });
    expect(defaultRefundMethod(src)).toBe("card");
  });
});

const TERMINAL: TerminalInfo = {
  id: "t-1",
  name: "T1",
  adapter: "fake",
  driver: "fake",
  local_id: null,
  tid: "T0000001",
  is_default: true,
  status: "active",
  capabilities: {},
};

function cardDeps(client = createFakeCardTerminalClient({ sleep: () => Promise.resolve() })) {
  const attempts = new Map<string, Record<string, unknown>>();
  const recorded: unknown[] = [];
  const d: CardRefundDeps = {
    terminals: async () => [TERMINAL],
    client: () => client,
    fallbackPolicy: async () => "manager_approval",
    putAttempt: async (a) => void attempts.set(a.attempt_id, a),
    updateAttempt: async (id, patch) => void attempts.set(id, { ...attempts.get(id), ...patch }),
    removeAttempt: async (id) => void attempts.delete(id),
    recordTx: async (b) => void recorded.push(b),
    isOnline: () => true,
    now: () => "2026-10-17T10:00:00Z",
    sleep: () => Promise.resolve(),
  };
  return { d, attempts, recorded, client };
}

describe("card refund (18 §7.1 refund_card, 16 §2.1)", () => {
  const input = {
    terminal: TERMINAL,
    amount: "12000.00" as Money,
    cashRegisterId: "cr-1",
    shiftId: "s-1",
    originalRrn: "123456789012",
  };

  it("approved refund → integrated card_result (kind=refund), attempt kept approved for the event", async () => {
    const { d, attempts, recorded } = cardDeps();
    const r = await runCardRefund(d, input);
    expect(r.status).toBe("approved");
    if (r.status !== "approved") return;
    expect(r.cardResult).toMatchObject({
      kind: "refund",
      status: "approved",
      amount: "12000.00",
      card_terminal_id: "t-1",
    });
    expect(attempts.get(r.attemptId)?.status).toBe("approved");
    expect(recorded).toHaveLength(1);
  });

  it("no answer → the attempt stays unknown (blocks, never a second refund)", async () => {
    const { d, attempts, client } = cardDeps();
    client.refund = () => Promise.reject(new Error("lost"));
    client.getStatus = () => Promise.reject(new Error("lost"));
    const r = await runCardRefund(d, input);
    expect(r.status).toBe("unknown");
    if (r.status === "unknown") expect(attempts.get(r.attemptId)?.status).toBe("unknown");
  });

  it("manual policy: standalone needs nothing; forbid refuses; manager_approval asks", () => {
    expect(manualPolicyNeed({ kind: "standalone" }, "forbid")).toBe("none");
    expect(manualPolicyNeed({ kind: "integrated", terminal: TERMINAL }, "forbid")).toBe("forbidden");
    expect(manualPolicyNeed({ kind: "integrated", terminal: TERMINAL }, "manager_approval")).toBe("approval");
    expect(manualReasonFor({ kind: "standalone" }, null)).toBe("standalone_terminal");
    expect(manualReasonFor({ kind: "integrated", terminal: TERMINAL }, { status: "unavailable" })).toBe(
      "terminal_offline",
    );
  });
});

describe("UX-03: keys during a card refund", () => {
  it("Esc does nothing while the refund is on the terminal; otherwise closes panels, then goes back", () => {
    expect(returnsEscape({ cardPending: true, approvalOpen: true, manualOpen: false })).toBe("none");
    expect(returnsEscape({ cardPending: false, approvalOpen: true, manualOpen: false })).toBe(
      "close_approval",
    );
    expect(returnsEscape({ cardPending: false, approvalOpen: false, manualOpen: true })).toBe("close_manual");
    expect(returnsEscape({ cardPending: false, approvalOpen: false, manualOpen: false })).toBe("back");
  });
});
