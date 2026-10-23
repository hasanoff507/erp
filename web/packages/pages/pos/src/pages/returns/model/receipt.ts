/**
 * Return receipt print document (08 §13, 18 §4.9/§4.10): kind `return`, the returned lines with the
 * refund amounts, the refund payment; the fiscal block arrives later (fake/partner fiscalisation →
 * «Fiskal belgi kutilmoqda»).
 */
import { money, vatIncluded, type Money } from "@shared/lib/money";
import type { ReceiptDoc, ReceiptPaymentMethod } from "@shared/lib/receipt";

import {
  refundLine,
  returnTotals,
  type LineState,
  type RefundMethod,
  type ReturnSource,
  type SourceLine,
} from "./index.ts";

const RECEIPT_METHODS: Record<RefundMethod, ReceiptPaymentMethod | null> = {
  cash: "cash",
  card: "card",
  uzqr: "uzqr",
  click: "click",
  payme: "payme",
  uzum: "uzum",
  debt_adjustment: null,
};

export function returnReceiptDoc(input: {
  storeName: string;
  branchName: string | null;
  registerName: string | null;
  cashierName: string;
  shiftNo: number;
  receiptSeq: number | null;
  number: string;
  at: string;
  lines: readonly SourceLine[];
  state: readonly LineState[];
  source: ReturnSource | null;
  method: RefundMethod;
  moneyPart: Money;
  total: Money;
  vat: Money;
}): ReceiptDoc {
  const docLines = input.lines.flatMap((line, i) => {
    const s = input.state[i];
    if (!s?.selected) return [];
    const total = input.source ? refundLine(line, s.qty) : returnTotals(null, [line], [s]).amount;
    const rate = money(line.vatRate);
    const taxed = rate !== "0.00";
    return [
      {
        name: line.name,
        qty: s.qty,
        qtyKind: line.fractional ? ("fractional" as const) : ("integer" as const),
        unitPrice: line.price,
        unitLabel: line.unitCode,
        total,
        vatRate: taxed ? rate.replace(/\.00$/, "") : null,
        vat: taxed ? vatIncluded(total, rate) : ("0.00" as Money),
        vatExemptCode: line.vatExemptionCode,
        markingCodes: line.markingCode ? [line.markingCode] : [],
      },
    ];
  });
  const method = RECEIPT_METHODS[input.method];
  return {
    kind: "return",
    store: { name: input.storeName, branchName: input.branchName },
    number: input.number,
    issuedAt: input.at,
    cashierName: input.cashierName,
    shiftNo: input.shiftNo,
    registerNo: input.registerName,
    receiptSeq: input.receiptSeq,
    lines: docLines,
    totals: {
      total: input.total,
      discount: "0.00" as Money,
      vat: input.vat === "0.00" ? [] : [{ rate: "12", amount: input.vat }],
    },
    payments: method
      ? {
          form: input.method === "cash" ? "cash" : input.method === "card" ? "card" : "qr",
          items: [{ method, amount: input.moneyPart }],
        }
      : null,
    fiscal: null,
  };
}
