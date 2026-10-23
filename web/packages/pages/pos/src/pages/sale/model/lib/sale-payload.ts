/**
 * `sale.created` payload builder — 18 §4.1 exactly (backend app/modules/sales/application/payloads.py,
 * `extra="forbid"`): lines (frozen price 4 dp, vat_rate 2 dp, line_total / vat_amount by qaror #26, manual
 * discount + ApprovalRef), payments (cash / card integrated|manual / static UzQR / debt). Card details are never
 * sent by the device: an integrated payment carries only `card_result` (the server fills rrn / mask / type);
 * a manual card carries only amount + `manual_reason` (+ `card_manual_approval`). `receipt_seq` is assigned by
 * `enqueueEvent` (`opts.receiptSeq`) when the receipt has a non-debt part; a debt-only sale sends `null`.
 * B5: dynamic UzQR / Click / Payme / Uzum parts carry the confirmed checkout (`checkout_ref` + `provider_tx_id`,
 * 18 §16); in the local-bridge mode the FM-signed `receipt_seq` + `fiscal_result` come in `ctx` (qaror #68).
 */
import type { Money } from "@shared/lib/money";

import type { ApprovalRef, DraftTotals } from "#/entities/receipt-draft/index.ts";
import { isPositive, sumMoney } from "#/entities/receipt-draft/index.ts";

export type PayMethod = "cash" | "card" | "uzqr" | "click" | "payme" | "uzum" | "debt";

/** A confirmed provider checkout (18 §16.3 `confirmed`). */
export interface CheckoutRef {
  checkoutRef: string;
  providerTxId: string;
}

export type CardPart =
  | { mode: "integrated"; attemptId: string; cardResult: Record<string, unknown> }
  | {
      mode: "manual";
      manualReason: "standalone_terminal" | "terminal_offline" | "terminal_error" | "unknown_result";
      approval: ApprovalRef | null;
      attemptId: string | null;
    };

export interface PaymentPart {
  method: PayMethod;
  amount: Money;
  card?: CardPart;
  /** static UzQR — optional payment number from the customer's phone (≤ 40). */
  terminalRef?: string | null;
  /** B5: dynamic UzQR / Click / Payme / Uzum — the confirmed checkout. */
  checkout?: CheckoutRef | null;
  /** debt — promise date (ISO day) and the over-limit approval (online). */
  dueDate?: string | null;
  debtApproval?: ApprovalRef | null;
}

export interface SaleContext {
  saleId: string;
  branchId: string;
  cashRegisterId: string;
  shiftId: string;
  tempNumber: string;
  docDate: string;
  counterpartyId: string | null;
  isOffline: boolean;
  offlineSince: string | null;
  delivery: "printed" | "electronic";
  deliveryReason: "printer_failure" | "customer_request" | null;
  comment?: string | null;
  /** B5 local bridge: the number the FM signed and its answer (else the outbox numbers, server fiscalises). */
  receiptSeq?: number | null;
  fiscalResult?: Record<string, unknown> | null;
}

export type SalePayload = Record<string, unknown> & {
  id: string;
  lines: Record<string, unknown>[];
  payments: Record<string, unknown>[];
};

const approvalJson = (a: ApprovalRef | null | undefined) =>
  a
    ? {
        mode: a.mode,
        approved_by: a.approved_by,
        pin_verified_locally: a.pin_verified_locally,
        approval_request_id: a.approval_request_id,
      }
    : null;

export function nonDebtAmount(parts: readonly PaymentPart[]): Money {
  return sumMoney(parts.filter((p) => p.method !== "debt").map((p) => p.amount));
}

export function debtAmount(parts: readonly PaymentPart[]): Money {
  return sumMoney(parts.filter((p) => p.method === "debt").map((p) => p.amount));
}

/** The receipt issues a fiscal `sale` receipt (and so gets a receipt_seq) unless it is debt-only. */
export function issuesFiscalReceipt(parts: readonly PaymentPart[]): boolean {
  return isPositive(nonDebtAmount(parts));
}

function paymentJson(part: PaymentPart): Record<string, unknown> {
  const out: Record<string, unknown> = { method: part.method, amount: part.amount };
  if (part.method === "card" && part.card) {
    if (part.card.mode === "integrated") {
      out.card_entry_mode = "integrated";
      out.card_result = part.card.cardResult;
    } else {
      out.card_entry_mode = "manual";
      out.manual_reason = part.card.manualReason;
      out.card_manual_approval = approvalJson(part.card.approval);
    }
  }
  if (part.method === "uzqr" && !part.checkout) {
    out.qr_type = "static";
    out.terminal_ref = part.terminalRef?.trim() ? part.terminalRef.trim() : null;
  }
  if (part.checkout && part.method !== "cash" && part.method !== "card" && part.method !== "debt") {
    if (part.method === "uzqr") out.qr_type = "dynamic";
    out.checkout_ref = part.checkout.checkoutRef;
    out.provider_tx_id = part.checkout.providerTxId;
  }
  if (part.method === "debt") {
    out.due_date = part.dueDate ?? null;
    out.debt_approval = approvalJson(part.debtApproval);
  }
  return out;
}

export function buildSalePayload(
  totals: DraftTotals,
  parts: readonly PaymentPart[],
  discountApproval: ApprovalRef | null,
  discountPct: string | null,
  ctx: SaleContext,
): SalePayload {
  let approvalPlaced = false;
  const lines = totals.lines.map((l) => {
    const discounted = isPositive(l.discount);
    const approval = discounted && !approvalPlaced ? approvalJson(discountApproval) : null;
    if (approval) approvalPlaced = true;
    return {
      id: l.id,
      product_id: l.productId,
      unit_code: l.unitCode,
      qty: l.qty,
      price: l.price,
      vat_rate: l.vatRate,
      vat_exemption_code: l.vatExemptionCode,
      discount_pct: discounted && discountPct ? discountPct : null,
      discount_amount: discounted ? l.discount : null,
      discount_source: discounted ? "manual" : null,
      discount_rule_id: null,
      discount_approval: approval,
      marking_code: l.markingCode,
      marking_offline: l.markingCode ? ctx.isOffline : null,
      line_total: l.total,
      vat_amount: l.vat,
    };
  });
  const fiscalReceipt = issuesFiscalReceipt(parts);
  return {
    id: ctx.saleId,
    branch_id: ctx.branchId,
    cash_register_id: ctx.cashRegisterId,
    shift_id: ctx.shiftId,
    // local bridge: the FM-signed number; else enqueueEvent writes it (opts.receiptSeq) for a non-debt part
    receipt_seq: ctx.receiptSeq ?? null,
    credit_receipt_seq: null,
    // local bridge: the FM answer (qaror #68); else null — server-side (fake / partner cloud) fiscalisation
    fiscal_result: ctx.fiscalResult ?? null,
    delivery: fiscalReceipt ? ctx.delivery : "printed",
    delivery_reason: fiscalReceipt && ctx.delivery === "electronic" ? ctx.deliveryReason : null,
    temp_number: ctx.tempNumber,
    doc_date: ctx.docDate,
    counterparty_id: ctx.counterpartyId,
    lines,
    payments: parts.map(paymentJson),
    comment: ctx.comment ?? null,
    is_offline: ctx.isOffline,
    offline_since: ctx.isOffline ? ctx.offlineSince : null,
  };
}

/** `payment_form` of the fiscal receipt (18 §4.5): cash | card | qr | mixed (debt part excluded). */
export function paymentForm(parts: readonly PaymentPart[]): "cash" | "card" | "qr" | "mixed" {
  const forms = new Set(
    parts
      .filter((p) => p.method !== "debt")
      .map((p) => (p.method === "cash" ? "cash" : p.method === "card" ? "card" : "qr")),
  );
  if (forms.size === 1) return [...forms][0] as "cash" | "card" | "qr";
  return "mixed";
}
