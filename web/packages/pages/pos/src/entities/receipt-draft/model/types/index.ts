/**
 * The open (unpaid) receipt of POS-02 (07 POS-02; 18 §4.1 `lines[]`). Money / qty / price are decimal
 * strings: qty 3 dp ("1.250"), price 4 dp as delivered by the price list ("8500.0000" — frozen into the line,
 * 16 §5), money 2 dp. The cashier never edits a price (US-M09-03).
 */
import type { Money } from "@shared/lib/money";

/** Product kind shown as a chip on the tile/line (07 POS-02): piece, scale (weighed), marked. */
export type LineKind = "piece" | "weighed" | "marked";

export interface DraftLine {
  /** `sale_lines.id` (UUIDv7, given by the device). */
  id: string;
  productId: string;
  name: string;
  nameRu: string | null;
  unitCode: string;
  /** `units.is_fractional` — false → only whole quantities (18 §2.3). */
  fractional: boolean;
  kind: LineKind;
  /** "1.000" … — 3 dp. */
  qty: string;
  /** Frozen current price, 4 dp. */
  price: string;
  /** "12.00" / "0.00". */
  vatRate: string;
  vatExemptionCode: string | null;
  mxik: string | null;
  barcode: string | null;
  /** DataMatrix raw value (GS separators kept) — marked goods only, qty is always "1.000". */
  markingCode: string | null;
  /** Online precheck said the code is not valid / CRPT did not answer (warn policy, 18 §4.2). */
  markingWarning: boolean;
}

/** Receipt-level manual discount (07 POS-02 `discountPercent`, 18 §4.4). */
export interface DraftDiscount {
  /** "0.00" … "100.00". */
  pct: string;
  /** ApprovalRef (18 §2.4) when the percent is above the cashier's `discount.give` limit. */
  approval: ApprovalRef | null;
}

export interface ApprovalRef {
  mode: "local_pin" | "remote_request";
  approved_by: string | null;
  pin_verified_locally: boolean | null;
  approval_request_id: string | null;
}

export interface Draft {
  /** Local receipt identifier (`sale.draft_voided.draft_ref`, and later the sale id). */
  ref: string;
  lines: DraftLine[];
  selectedLineId: string | null;
  customerId: string | null;
  discount: DraftDiscount | null;
}

/** A line with its computed amounts (18 §4.1: line_total, vat_amount; §4.4 discount). */
export interface PricedLine extends DraftLine {
  /** ROUND_HALF_UP(qty × price, 0). */
  gross: Money;
  /** Manual discount of this line, whole so'm ("0.00" when none). */
  discount: Money;
  /** ROUND_HALF_UP(qty × price − discount, 0). */
  total: Money;
  /** ROUND_HALF_UP(total × r / (100 + r), 2). */
  vat: Money;
}

export interface VatGroup {
  rate: string;
  amount: Money;
}

export interface DraftTotals {
  lines: PricedLine[];
  /** Σ gross. */
  subtotal: Money;
  /** Σ discount. */
  discount: Money;
  /** Σ total — what the customer pays. */
  total: Money;
  /** "Shu jumladan QQS" by rate (only rates with a non-zero amount). */
  vat: VatGroup[];
}
