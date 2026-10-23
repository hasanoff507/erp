/**
 * Trial-balance helpers (20 #11): balances are **debit-positive** (`Σ Dt − Σ Kt`; a liability is negative).
 * Screens show the amount without a sign and name the side («debet qoldiq» / «kredit qoldiq»), 07 BO-07.
 */
import { compareMoney, money, type Money } from "@shared/lib/money";

export type BalanceSide = "debit" | "credit" | "zero";

export interface SidedBalance {
  side: BalanceSide;
  /** The unsigned amount (decimal string). */
  amount: Money;
}

export function sidedBalance(signed: string): SidedBalance {
  const value = money(signed);
  const cmp = compareMoney(value, money("0"));
  if (cmp === 0) return { side: "zero", amount: money("0.00") };
  return { side: cmp > 0 ? "debit" : "credit", amount: money(signed.replace(/^-/, "")) };
}
