/**
 * Quantity helpers of the warehouse screens (POS-08/09/10) — decimal STRINGS only (qaror #26, #57); every
 * operation goes through decimal.js (`toDecimal`), nothing becomes a JS number. API qty = 3 dp ("12.000").
 */
import { toDecimal } from "@shared/lib/money";

export function isQty(value: string | null | undefined): value is string {
  if (value === null || value === undefined || value.trim() === "") return false;
  try {
    toDecimal(value);
    return true;
  } catch {
    return false;
  }
}

/** Canonical 3-place quantity ("12" → "12.000"); invalid → "". */
export function qty3(value: string): string {
  return isQty(value) ? toDecimal(value).toFixed(3) : "";
}

/** Display form without trailing zeros ("10.000" → "10", "1.250" → "1.25"). */
export function trimQty(value: string): string {
  return isQty(value) ? toDecimal(value).toFixed() : value;
}

export function addQty(a: string, b: string): string {
  return toDecimal(a).plus(toDecimal(b)).toFixed(3);
}

export function subtractQty(a: string, b: string): string {
  return toDecimal(a).minus(toDecimal(b)).toFixed(3);
}

export function sumQty(values: readonly string[]): string {
  return values.reduce((acc, v) => acc.plus(toDecimal(v)), toDecimal("0")).toFixed(3);
}

export function compareQty(a: string, b: string): -1 | 0 | 1 {
  return toDecimal(a).comparedTo(toDecimal(b)) as -1 | 0 | 1;
}

export function isPositiveQty(value: string): boolean {
  return isQty(value) && toDecimal(value).greaterThan(0);
}

/** `value − 1` but never below zero (the `−` button). */
export function decrementQty(value: string, step = "1"): string {
  const next = toDecimal(isQty(value) ? value : "0").minus(toDecimal(step));
  return (next.isNegative() ? toDecimal("0") : next).toFixed(3);
}
