/**
 * Money helpers of the finance forms (qaror #57: decimal strings via @shared/lib/money only, never
 * Number()/parseFloat). A typed amount is the MoneyInput's normalised string ("" when empty).
 */
import { compareMoney, isMoney, money, type Money } from "@shared/lib/money";

export const ZERO = "0.00" as Money;

/** A typed amount as Money, or null when empty / not a number. */
export function typedMoney(value: string): Money | null {
  const v = value.trim();
  if (v === "" || !isMoney(v)) return null;
  return money(v);
}

/** `> 0`. */
export function isPositiveMoney(value: string): boolean {
  const m = typedMoney(value);
  return m !== null && compareMoney(m, ZERO) > 0;
}

/** Smaller of two amounts. */
export function minMoney(a: Money, b: Money): Money {
  return compareMoney(a, b) <= 0 ? a : b;
}

/** Larger of two amounts. */
export function maxMoney(a: Money, b: Money): Money {
  return compareMoney(a, b) >= 0 ? a : b;
}
