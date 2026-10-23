/**
 * POS-15 — naqd sanash (07 POS-15; 18 §3.2; US-M16-02; QT-M01-06/-07): denominations are only a counting
 * aid (Σ nominal × count → counted cash); otherwise the counted cash is typed. Variance = counted −
 * expected; a non-zero variance needs a note (≤ 200) — nothing is sent from here.
 */
import { compareMoney, money, type Money } from "@shared/lib/money";

import { cashVariance, denominationsTotal } from "#/entities/pos-session/index.ts";

export const COUNT_NOTE_MAX = 200;
export const MAX_PIECES = 9999;

export interface CountView {
  counted: Money | null;
  fromDenominations: boolean;
  pieces: number;
  variance: Money | null;
  varianceKind: "match" | "short" | "over";
}

export function countView(
  counts: Readonly<Record<string, number>>,
  manual: string,
  expected: Money,
): CountView {
  const pieces = Object.values(counts).reduce((a, n) => a + (Number.isInteger(n) && n > 0 ? n : 0), 0);
  const fromDenominations = pieces > 0;
  let counted: Money | null = null;
  if (fromDenominations) counted = denominationsTotal(counts);
  else if (manual !== "") {
    try {
      counted = money(manual);
    } catch {
      counted = null;
    }
  }
  const variance = counted === null ? null : cashVariance(counted, expected);
  const sign = variance === null ? 0 : compareMoney(variance, "0.00" as Money);
  return {
    counted,
    fromDenominations,
    pieces,
    variance,
    varianceKind: sign < 0 ? "short" : sign > 0 ? "over" : "match",
  };
}

/** 07 POS-15: a variance without a note is not saved. */
export const noteRequired = (view: CountView): boolean =>
  view.variance !== null && view.varianceKind !== "match";
