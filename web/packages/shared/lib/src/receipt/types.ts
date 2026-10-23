/**
 * Receipt document model — 08 §13.1 (template, two languages, qaror #29), 18 §4.5/§4.9/§4.10 (fiscal block,
 * payment form, card requisites), 21 §1 (payment form map). Money = decimal strings ("12000.00"),
 * quantities = decimal strings ("1.250"); this module only formats them, never computes totals.
 */
import type { Money } from "#/money/index.ts";

export type ReceiptKind = "sale" | "return" | "debt_settlement" | "z_report" | "test";
export type PaperWidth = 58 | 80;

export interface ReceiptStore {
  name: string;
  address?: string | null;
  phone?: string | null;
  stir?: string | null;
  branchName?: string | null;
}

export interface ReceiptLine {
  name: string;
  /** `products.name_ru`; empty → only the Uzbek line (qaror #29). */
  nameRu?: string | null;
  qty: string;
  qtyKind: "integer" | "fractional";
  unitPrice: string;
  /** Catalog unit label as printed ("dona", "kg"). */
  unitLabel: string;
  /** Line discount (Money), printed only when non-zero. */
  discount?: Money | null;
  /** Line total after discount. */
  total: Money;
  mxik?: string | null;
  barcode?: string | null;
  /** VAT rate in percent ("12"); null → exempt line. */
  vatRate: string | null;
  vat: Money;
  vatExemptCode?: string | null;
  markingCodes?: readonly string[];
}

export type ReceiptPaymentMethod = "cash" | "card" | "uzqr" | "click" | "payme" | "uzum" | "debt";

export interface ReceiptCardDetails {
  /** `integrated` → card type / mask / RRN from the terminal; `manual` → only the payment form (26 #178). */
  entryMode: "integrated" | "manual";
  cardType?: "personal" | "corporate" | "social" | "unknown" | null;
  cardMask?: string | null;
  rrn?: string | null;
  approvalCode?: string | null;
  scheme?: string | null;
  tid?: string | null;
}

export interface ReceiptPayment {
  method: ReceiptPaymentMethod;
  amount: Money;
  card?: ReceiptCardDetails | null;
}

export interface ReceiptPayments {
  /** `fiscal_receipts.payment_form`. */
  form: "cash" | "card" | "qr" | "mixed";
  items: readonly ReceiptPayment[];
  received?: Money | null;
  change?: Money | null;
}

export interface ReceiptFiscal {
  fmTerminalId: string;
  fmReceiptSeq: string | number;
  fiscalSign: string;
  qrUrl: string;
  fiscalAt?: string | null;
}

export interface ReceiptTotals {
  total: Money;
  discount: Money;
  /** One row per VAT rate (Σ line VAT, 08 §13.1). */
  vat: readonly { rate: string; amount: Money }[];
}

export interface ReceiptDoc {
  kind: ReceiptKind;
  /** Reprint → «NUSXA / КОПИЯ» (POS-04). */
  copy?: boolean;
  store: ReceiptStore;
  /** Display number, e.g. "K-01-2026-000154". */
  number: string;
  /** ISO instant; printed in Asia/Tashkent. */
  issuedAt: string;
  cashierName: string;
  shiftNo?: number | null;
  registerNo?: string | null;
  receiptSeq?: number | null;
  lines: readonly ReceiptLine[];
  totals: ReceiptTotals | null;
  payments: ReceiptPayments | null;
  /** null → not fiscalized yet («Fiskal belgi kutilmoqda»). */
  fiscal: ReceiptFiscal | null;
  /** Credit-type receipts carry neither QR nor fiscal sign (08 §13.1). */
  noQr?: boolean;
  slipText?: string | null;
  /** Free text lines (test receipt body). */
  extraLines?: readonly string[];
  /** Z-report figures (`kind: "z_report"`, 18 §3.2 `z_report`). */
  zReport?: ReceiptZReport | null;
  /**
   * `z_report` only: true → «Fiskal belgi kutilmoqda» while `fiscal` is null (Z queued to the FM/OFD);
   * false/absent → no fiscal block at all.
   */
  fiscalPending?: boolean;
}

/** Z-report (shift close) figures — 18 §3.2 `z_report`, 24 §6.5 (card integrated / terminal-less apart). */
export interface ReceiptZReport {
  openedAt?: string | null;
  closedAt?: string | null;
  salesCount: number;
  returnsCount: number;
  /** `totals_by_method` — only non-null methods are printed. */
  totalsByMethod: Partial<Record<ReceiptPaymentMethod, Money>>;
  cardSplit?: { integrated: Money; manual: Money } | null;
  cardSettlements?: readonly {
    /** Printed terminal name / TID. */
    terminal: string;
    netTotal: Money;
    expectedTotal: Money;
    variance: Money;
    /** `card_settlements[].status`; `matched` | `mismatch` | `failed` (12 card_terminal_settlements). */
    status: string;
  }[];
  returnsTotal: Money;
  discountTotal: Money;
  vatTotal: Money;
  expectedCash: Money;
  countedCash: Money;
  variance: Money;
  /** FM Z number when the fiscal module returned it. */
  zNumber?: string | number | null;
}

export type TextSize = "normal" | "small" | "large";

export interface TextBlock {
  type: "text";
  left: string;
  /** Right-aligned part on the same line (amounts). */
  right?: string;
  align: "left" | "center" | "right";
  bold?: boolean;
  size: TextSize;
}

export type ReceiptBlock =
  TextBlock | { type: "rule" } | { type: "qr"; data: string } | { type: "feed"; lines: number };

export interface ReceiptLayout {
  paperWidth: PaperWidth;
  /** Characters per line for `normal` text (Font A). */
  columns: number;
  /** Characters per line for `small` text (Font B). */
  smallColumns: number;
  blocks: ReceiptBlock[];
}
