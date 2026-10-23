/**
 * Quantity / value helpers — decimal STRINGS only (qaror #26, #57; 32 §3.3). Arithmetic goes through
 * `toDecimal` (decimal.js) of @shared/lib/money; nothing here becomes a JS number.
 *
 * API shapes (17 §3): qty `decimal(3dp)` ("12.000"), unit cost 4 dp, money 2 dp.
 */
import { addMoney, money, toDecimal, type Money } from "@shared/lib/money";

/** Canonical 3-place quantity for request bodies ("12" → "12.000"). Invalid → "". */
export function qty3(value: string): string {
  if (!isDecimal(value)) return "";
  return toDecimal(value).toFixed(3);
}

/** Any decimal string → 4-place unit cost / price ("12000" → "12000.0000"). Invalid → "". */
export function price4(value: string): string {
  if (!isDecimal(value)) return "";
  return toDecimal(value).toFixed(4);
}

export function isDecimal(value: string | null | undefined): value is string {
  if (value === null || value === undefined || value === "") return false;
  try {
    toDecimal(value);
    return true;
  } catch {
    return false;
  }
}

/** Display/edit form without trailing zeros ("10.000" → "10", "1.250" → "1.25"). */
export function trimQty(value: string): string {
  return isDecimal(value) ? toDecimal(value).toFixed() : value;
}

/** `a − b`, 3 places. */
export function subtractQty(a: string, b: string): string {
  return toDecimal(a).minus(toDecimal(b)).toFixed(3);
}

/** Σ quantities, 3 places ("0.000" for none). */
export function sumQty(values: readonly string[]): string {
  return values.reduce((acc, v) => acc.plus(toDecimal(v)), toDecimal("0")).toFixed(3);
}

export function compareQty(a: string, b: string): -1 | 0 | 1 {
  return toDecimal(a).comparedTo(toDecimal(b)) as -1 | 0 | 1;
}

export function isZero(value: string): boolean {
  return toDecimal(value).isZero();
}

export function isPositive(value: string): boolean {
  return isDecimal(value) && toDecimal(value).greaterThan(0);
}

export function isNegative(value: string): boolean {
  return toDecimal(value).isNegative() && !toDecimal(value).isZero();
}

/** `qty × unitCost` rounded HALF_UP to tiyin (value of a line at cost). */
export function lineValue(qty: string, unitCost: string): Money {
  return money(toDecimal(qty).times(toDecimal(unitCost)).toFixed(6));
}

/** `ROUND_HALF_UP(amount × ratePct / 100, 2)` — VAT on top of a net amount (19 §8 receipt lines). */
export function percentOf(amount: string, ratePct: string): Money {
  return money(toDecimal(amount).times(toDecimal(ratePct)).div(100).toFixed(6));
}

/** Σ of money strings (2 places). */
export function sumMoney(values: readonly string[]): Money {
  return addMoney(...values.map((v) => money(v)));
}

/** |value| of a money string (shortage amounts come signed). */
export function absMoney(value: string): Money {
  return money(toDecimal(value).abs().toFixed(2));
}
