/**
 * The tiyin boundary of the web POS (21 §1, §16.1; qaror #12, #26, #68) — the ONLY place where decimal strings
 * become integers: amounts → tiyin (`ROUND_HALF_UP` to the tiyin, safe-integer checked), qty → milli-units.
 * Mirrors the backend `fiscal/domain/boundary.py::port_payload` and `sales/domain/calc.py::fiscal_shares`, so
 * the receipt the FM signs on the device is the receipt the server would have built:
 * - item name `"{name} / {name_ru}"` (qaror #29), MXIK, PackageCode, unit, marking codes as scanned;
 * - a mixed sale with a debt part (18 §4.5): `ratio = non_debt / total`, `amt_i = ROUND_HALF_UP(line_total_i ×
 *   ratio, 2)` with the rounding rest on the largest line (ties — the later line), `qty_i = ROUND_HALF_UP(qty_i ×
 *   ratio, 3)` (≥ 0.001), `vat_i = ROUND_HALF_UP(amt_i × r / (100 + r), 2)`;
 * - payments: cash / card / qr (uzqr, click, payme, uzum) tiyin; card type / mask / RRN only from an integrated
 *   terminal result, never typed (qaror #64/#71, 26 #178).
 */
import Decimal from "decimal.js";

import { InvalidMoneyError, toDecimal, type Money } from "#/money/index.ts";

import type {
  CashRegisterRef,
  FiscalCardType,
  FiscalItem,
  FiscalKind,
  FiscalPayments,
  FiscalReceiptPayload,
  PaymentForm,
  RefundInfo,
} from "./types.ts";

const D = Decimal.clone({ precision: 40, rounding: Decimal.ROUND_HALF_UP });

/** Decimal string → integer tiyin (`ROUND_HALF_UP`, 4-place prices included); throws outside int53. */
export function tiyinOf(value: string): number {
  const n = new D(toDecimal(value).toString()).times(100).toDecimalPlaces(0, D.ROUND_HALF_UP).toNumber();
  if (!Number.isSafeInteger(n)) throw new InvalidMoneyError(value);
  return n;
}

/** Qty string → milli-units (`"2.000"` → `2000`). */
export function milliOf(qty: string): number {
  const n = new D(toDecimal(qty).toString()).times(1000).toDecimalPlaces(0, D.ROUND_HALF_UP).toNumber();
  if (!Number.isSafeInteger(n)) throw new InvalidMoneyError(qty);
  return n;
}

/** A receipt line in the POS's decimal form. */
export interface FiscalLineInput {
  name: string;
  nameRu?: string | null;
  mxik: string | null;
  packageCode?: string | null;
  unitCode: string | null;
  qty: string;
  /** Unit price with VAT (4 places allowed). */
  price: string;
  lineTotal: Money;
  vatRate: string;
  vatAmount: Money;
  markingCode: string | null;
}

export interface FiscalShare {
  amount: Money;
  qty: string;
  vat: Money;
}

const money2 = (d: Decimal): Money => d.toDecimalPlaces(2, D.ROUND_HALF_UP).toFixed(2) as Money;
const vatFromGross = (amount: Decimal, rate: string): Money => {
  const r = new D(toDecimal(rate).toString());
  return money2(amount.times(r).div(r.plus(100)));
};

/** 18 §4.5 shares of the `sale` receipt (backend `fiscal_shares`). `nonDebt = total` → the lines unchanged. */
export function fiscalShares(lines: readonly FiscalLineInput[], nonDebt: Money): FiscalShare[] {
  const totals = lines.map((l) => new D(toDecimal(l.lineTotal).toString()));
  const whole = totals.reduce((a, b) => a.plus(b), new D(0));
  const part = new D(toDecimal(nonDebt).toString());
  if (part.eq(whole)) {
    return lines.map((l, i) => ({
      amount: money2(totals[i] ?? new D(0)),
      qty: new D(toDecimal(l.qty).toString()).toFixed(3),
      vat: vatFromGross(totals[i] ?? new D(0), l.vatRate),
    }));
  }
  let amounts: Decimal[];
  if (whole.isZero()) {
    amounts = totals.map(() => new D(0));
    if (amounts.length) amounts[amounts.length - 1] = part;
  } else {
    amounts = totals.map((w) => new D(money2(part.times(w).div(whole))));
    let biggest = 0;
    totals.forEach((w, i) => {
      if (w.gte(totals[biggest] ?? new D(0))) biggest = i; // ties — the later line
    });
    const rest = part.minus(amounts.reduce((a, b) => a.plus(b), new D(0)));
    amounts[biggest] = (amounts[biggest] ?? new D(0)).plus(rest);
  }
  const ratio = whole.isZero() ? new D(0) : part.div(whole);
  return lines.map((l, i) => {
    const amount = amounts[i] ?? new D(0);
    const q = D.max(
      new D(toDecimal(l.qty).toString()).times(ratio).toDecimalPlaces(3, D.ROUND_HALF_UP),
      new D("0.001"),
    );
    return { amount: money2(amount), qty: q.toFixed(3), vat: vatFromGross(amount, l.vatRate) };
  });
}

const MXIK_RE = /^[0-9]{17}$/;
const MASK_RE = /^[0-9]{4}\*+[0-9]{4}$/;

function itemName(l: FiscalLineInput): string {
  const name = l.nameRu ? `${l.name} / ${l.nameRu}` : l.name;
  return name.slice(0, 256);
}

/** One FM item from a line and its share (amount / qty / VAT of this receipt). */
export function fiscalItem(l: FiscalLineInput, share?: FiscalShare): FiscalItem {
  const s = share ?? { amount: l.lineTotal, qty: l.qty, vat: l.vatAmount };
  return {
    name: itemName(l),
    mxik: l.mxik && MXIK_RE.test(l.mxik) ? l.mxik : null,
    package_code: l.packageCode ?? null,
    unit_code: l.unitCode,
    qty_milli: milliOf(s.qty),
    price_tiyin: tiyinOf(l.price),
    amount_tiyin: tiyinOf(s.amount),
    vat_rate: new D(toDecimal(l.vatRate).toString()).toFixed(2),
    vat_tiyin: tiyinOf(s.vat),
    marking_codes: l.markingCode ? [l.markingCode] : [],
  };
}

/** A payment as it appears on the receipt (debt parts are left out by the caller). */
export interface FiscalPaymentInput {
  method: "cash" | "card" | "uzqr" | "click" | "payme" | "uzum";
  amount: Money;
  /** Integrated card: the terminal result (mask already 4+4, `card_type` terminal → BIN table → unknown). */
  card?: { cardType: string | null; cardMask: string | null; rrn: string | null } | null;
}

const formOf = (m: FiscalPaymentInput["method"]): "cash" | "card" | "qr" =>
  m === "cash" ? "cash" : m === "card" ? "card" : "qr";

const CARD_TYPES: ReadonlySet<string> = new Set(["personal", "corporate", "social", "unknown"]);

export function fiscalPayments(parts: readonly FiscalPaymentInput[]): FiscalPayments {
  const forms = new Set(parts.map((p) => formOf(p.method)));
  const out: FiscalPayments = {
    payment_form: (forms.size === 1 ? [...forms][0] : "mixed") as PaymentForm,
    cash_tiyin: 0,
    card_tiyin: 0,
    qr_tiyin: 0,
    card_type: null,
    card_mask: null,
    rrn: null,
  };
  for (const p of parts) {
    const form = formOf(p.method);
    out[`${form}_tiyin`] += tiyinOf(p.amount);
    if (form === "card" && p.card) {
      const type = p.card.cardType ?? "unknown";
      out.card_type = (CARD_TYPES.has(type) ? type : "unknown") as FiscalCardType;
      out.card_mask = p.card.cardMask && MASK_RE.test(p.card.cardMask) ? p.card.cardMask : null;
      out.rrn = p.card.rrn;
    }
  }
  return out;
}

export interface FiscalReceiptInput {
  register: CashRegisterRef;
  receiptSeq: number;
  kind: FiscalKind;
  items: FiscalItem[];
  payments: readonly FiscalPaymentInput[];
  refundInfo?: RefundInfo;
}

/** The 21 §16.1 `FiscalReceiptPayload`; Σ payments must equal Σ items (the agent checks it too). */
export function fiscalReceipt(input: FiscalReceiptInput): FiscalReceiptPayload {
  const payments = fiscalPayments(input.payments);
  const total = input.items.reduce((a, i) => a + i.amount_tiyin, 0);
  const paid = payments.cash_tiyin + payments.card_tiyin + payments.qr_tiyin;
  if (paid !== total) {
    throw new InvalidMoneyError(`payments ${paid} ≠ items ${total}`);
  }
  return {
    cash_register: input.register,
    receipt_seq: input.receiptSeq,
    kind: input.kind,
    items: input.items,
    payments,
    total_tiyin: total,
    ...(input.refundInfo ? { refund_info: input.refundInfo } : {}),
  };
}
