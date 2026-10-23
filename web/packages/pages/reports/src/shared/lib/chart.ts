/**
 * Chart helpers (08 charts, 07 BO-02 «Savdo — oxirgi 7 kun»): recharts rows and the short «mln so'm»
 * labels. Money stays a decimal string — ratios are computed with
 * decimal.js (`toDecimal`), never with Number() (qaror #57).
 */
import { toDecimal } from "@shared/lib/money";

export interface ChartBarInput {
  key: string;
  label: string;
  /** Decimal string (money). */
  value: string;
  /** The bar drawn in the accent colour (today). */
  highlight?: boolean;
}

export interface ChartPoint extends ChartBarInput {
  /** Plot value (so'm, a display-only float; negative — returns over sales — drawn as 0). */
  amount: number;
}

/** Recharts rows: the money string stays in `value` (labels), `amount` is only the bar height. */
export function chartPoints(input: readonly ChartBarInput[]): ChartPoint[] {
  return input.map((b) => {
    const v = toDecimal(b.value);
    return { ...b, amount: v.greaterThan(0) ? v.toDecimalPlaces(0).toNumber() : 0 };
  });
}

/** «mln so'm» label: "4250000.00" → "4,3"; below 100 000 → "0,1"; zero → "0". */
export function millions(value: string): string {
  const v = toDecimal(value).div(1_000_000);
  if (v.isZero()) return "0";
  const places = v.abs().greaterThanOrEqualTo(100) ? 0 : 1;
  const rounded = v.toDecimalPlaces(places);
  const text = (rounded.isZero() ? toDecimal(v.isNegative() ? "-0.1" : "0.1") : rounded)
    .toFixed(places)
    .replace(".", ",");
  return text.startsWith("-") ? `−${text.slice(1)}` : text;
}

/**
 * Change vs the previous period in percent, one decimal ("12.5", "-3.0"); `null` when the previous
 * value is zero (no base to compare with).
 */
export function percentChange(current: string, previous: string): string | null {
  const prev = toDecimal(previous);
  if (prev.isZero()) return null;
  return toDecimal(current).minus(prev).div(prev.abs()).times(100).toDecimalPlaces(1).toFixed(1);
}

/** Share of `part` in `whole` in percent (0…100) for progress bars; 0 when `whole` is zero. */
export function sharePercent(part: string, whole: string): number {
  const w = toDecimal(whole);
  if (!w.greaterThan(0)) return 0;
  const p = toDecimal(part);
  if (!p.greaterThan(0)) return 0;
  return Math.min(100, p.div(w).times(100).toDecimalPlaces(1).toNumber());
}
