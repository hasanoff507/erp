/**
 * Receipt arithmetic on the device — the same formulas the server re-checks (18 §4.1, §4.4; qaror #26;
 * backend app/modules/sales/domain/calc.py):
 *   gross      = ROUND_HALF_UP(qty × price, 0)
 *   line_total = ROUND_HALF_UP(qty × price − discount, 0)
 *   vat        = ROUND_HALF_UP(line_total × r / (100 + r), 2)
 * A receipt-level manual discount D = ROUND_HALF_UP(Σ gross × pct / 100, 0) is spread over the lines in
 * proportion to their gross (whole so'm), the rounding rest goes to the largest line (ties — the later one).
 * Only decimal strings — never JS numbers for money (qaror #57).
 */
import Decimal from "decimal.js";

import { lineTotal, money, toDecimal, vatIncluded, type Money } from "@shared/lib/money";

import type { DraftDiscount, DraftLine, DraftTotals, PricedLine, VatGroup } from "../types/index.ts";

const D = Decimal.clone({ precision: 40, rounding: Decimal.ROUND_HALF_UP });
const ZERO = "0.00" as Money;

const fixed2 = (d: Decimal): Money => d.toFixed(2) as Money;

export function lineGross(line: Pick<DraftLine, "qty" | "price">): Money {
  return lineTotal(line.qty, line.price);
}

/** Splits a whole-so'm discount over the weights; rest → the largest weight (later index on ties). */
export function allocateDiscount(total: Decimal, weights: readonly Decimal[]): Decimal[] {
  if (weights.length === 0) return [];
  const whole = weights.reduce((acc, w) => acc.plus(w), new D(0));
  if (whole.isZero()) return weights.map(() => new D(0));
  const parts = weights.map((w) => total.times(w).div(whole).toDecimalPlaces(0, D.ROUND_HALF_UP));
  let biggest = 0;
  weights.forEach((w, i) => {
    if (w.greaterThanOrEqualTo(weights[biggest] ?? w)) biggest = i;
  });
  const rest = total.minus(parts.reduce((acc, p) => acc.plus(p), new D(0)));
  parts[biggest] = (parts[biggest] ?? new D(0)).plus(rest);
  return parts;
}

/** Percent ("12.5" / "12.50") → 2 dp string, clamped to 0…100; invalid → null. */
export function normalizePct(value: string): string | null {
  try {
    const d = toDecimal(value.trim().replace(",", "."));
    if (d.isNegative() || d.greaterThan(100)) return null;
    return d.toDecimalPlaces(2, D.ROUND_HALF_UP).toFixed(2);
  } catch {
    return null;
  }
}

export function priceLines(lines: readonly DraftLine[], discount: DraftDiscount | null): DraftTotals {
  const gross = lines.map((l) => toDecimal(lineGross(l)));
  const sumGross = gross.reduce((acc, g) => acc.plus(g), new D(0));
  const pct = discount ? toDecimal(discount.pct) : new D(0);
  const totalDiscount = sumGross.times(pct).div(100).toDecimalPlaces(0, D.ROUND_HALF_UP);
  const shares = pct.isZero() ? gross.map(() => new D(0)) : allocateDiscount(totalDiscount, gross);

  const priced: PricedLine[] = lines.map((line, i) => {
    const disc = fixed2(shares[i] ?? new D(0));
    const total = lineTotal(line.qty, line.price, disc);
    return {
      ...line,
      gross: fixed2(gross[i] ?? new D(0)),
      discount: disc,
      total,
      vat: vatIncluded(total, line.vatRate),
    };
  });

  const vatByRate = new Map<string, Decimal>();
  for (const l of priced) {
    const amount = toDecimal(l.vat);
    if (amount.isZero()) continue;
    vatByRate.set(l.vatRate, (vatByRate.get(l.vatRate) ?? new D(0)).plus(amount));
  }
  const vat: VatGroup[] = [...vatByRate.entries()]
    .sort(([a], [b]) => toDecimal(b).comparedTo(toDecimal(a)))
    .map(([rate, amount]) => ({ rate, amount: fixed2(amount) }));

  const sum = (pick: (l: PricedLine) => Money) =>
    fixed2(priced.reduce((acc, l) => acc.plus(toDecimal(pick(l))), new D(0)));

  return {
    lines: priced,
    subtotal: priced.length ? sum((l) => l.gross) : ZERO,
    discount: priced.length ? sum((l) => l.discount) : ZERO,
    total: priced.length ? sum((l) => l.total) : ZERO,
    vat,
  };
}

/** Effective manual discount percent the server checks: Σ discount / Σ gross × 100 (2 dp). */
export function effectiveDiscountPct(totals: DraftTotals): string {
  const g = toDecimal(totals.subtotal);
  if (g.isZero()) return "0.00";
  return toDecimal(totals.discount).div(g).times(100).toDecimalPlaces(2, D.ROUND_HALF_UP).toFixed(2);
}

/** `limit` null = unlimited; undefined = the permission is missing (nothing allowed). */
export function withinLimit(pct: string, limit: string | null | undefined): boolean {
  if (limit === undefined) return toDecimal(pct).isZero();
  if (limit === null) return true;
  return toDecimal(pct).lessThanOrEqualTo(toDecimal(limit));
}

/** qty ± step for piece goods; never below 1 (07: `−` does not go under 1 — removing is BEKOR). */
export function stepQty(qty: string, delta: 1 | -1): string {
  const next = toDecimal(qty).plus(delta);
  return (next.lessThan(1) ? new D(1) : next).toFixed(3);
}

/** Qty from user input: > 0, whole for non-fractional units, 3 dp, ≤ 99 999 (07 POS-02 `lines[].qty`). */
export function parseQty(value: string, fractional: boolean): string | null {
  try {
    const d = toDecimal(value.trim().replace(",", "."));
    if (!d.greaterThan(0) || d.greaterThan(99_999)) return null;
    if (!fractional && !d.isInteger()) return null;
    if (d.decimalPlaces() > 3) return null;
    return d.toFixed(3);
  } catch {
    return null;
  }
}

/** Price as delivered (NUMERIC 18,4) → exactly 4 dp ("8500" → "8500.0000"). */
export function price4(value: string): string {
  return toDecimal(value).toDecimalPlaces(4, D.ROUND_HALF_UP).toFixed(4);
}

export function addQty(a: string, b: string): string {
  return toDecimal(a).plus(toDecimal(b)).toFixed(3);
}

/** Change for cash: received − due (never negative → null when not enough). */
export function changeOf(received: string, due: Money): Money | null {
  try {
    const diff = toDecimal(received).minus(toDecimal(due));
    return diff.isNegative() ? null : money(diff.toFixed(2));
  } catch {
    return null;
  }
}

export function sumMoney(values: readonly string[]): Money {
  return fixed2(values.reduce((acc, v) => acc.plus(toDecimal(v)), new D(0)));
}

export function minusMoney(a: string, b: string): Money {
  return fixed2(toDecimal(a).minus(toDecimal(b)));
}

export function isPositive(value: string): boolean {
  try {
    return toDecimal(value).greaterThan(0);
  } catch {
    return false;
  }
}

export function cmpMoney(a: string, b: string): -1 | 0 | 1 {
  return toDecimal(a).comparedTo(toDecimal(b)) as -1 | 0 | 1;
}
