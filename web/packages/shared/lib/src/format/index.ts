/**
 * Display formatting — 08-dizayn-tizimi.md §8, 32-kod-qoidalari.md §3.3.
 * Every on-screen number/date goes through this module; components never call
 * `toLocaleString` or build number strings by hand.
 *
 * Output is DISPLAY-ONLY: never send it back to the API and never compute with it.
 */
import Decimal from "decimal.js";

import { toDecimal } from "#/money/index.ts";

export { formatDate, formatDateTime, formatWeekdayDate } from "#/date/index.ts";
export { formatPhone } from "#/phone/index.ts";

const MINUS = "−"; // "−" — 08 §8: minus sign, never parentheses
const SOM = " so'm"; // 08 §8: Latin "so'm" suffix added by hand (currency: "UZS" would print "UZS"/"сум")

const formatters = new Map<number, Intl.NumberFormat>();
function numberFormat(fractionDigits: number): Intl.NumberFormat {
  let f = formatters.get(fractionDigits);
  if (!f) {
    f = new Intl.NumberFormat("uz-UZ", {
      minimumFractionDigits: fractionDigits,
      maximumFractionDigits: fractionDigits,
      useGrouping: true,
    });
    formatters.set(fractionDigits, f);
  }
  return f;
}

const NBSP = " ";

/**
 * Intl.NumberFormat("uz-UZ") output normalised to the Uzbek convention (08 §8: "1 240 000", "94 500,00").
 * Browsers without full ICU data for `uz` fall back to another locale ("99,000"), so the group and
 * decimal separators are forced here: group = NBSP (no line break inside a sum), decimal = comma.
 */
function uzFormat(format: Intl.NumberFormat, value: string): string {
  return format
    .formatToParts(value as `${number}`)
    .map((part) => (part.type === "group" ? NBSP : part.type === "decimal" ? "," : part.value))
    .join("");
}

/** Formats a non-negative, already-rounded decimal with uz-UZ grouping (NBSP) and comma decimals. */
function groupDecimal(abs: Decimal, fractionDigits: number): string {
  return uzFormat(numberFormat(fractionDigits), abs.toFixed(fractionDigits));
}

export interface FormatMoneyOptions {
  /** 0 (default) — whole so'm; 2 — fiscal receipt / VAT / accounting reports (08 §0 band 1). */
  precision?: 0 | 2;
  /** Append " so'm" (default true). Tables with a currency column header pass false. */
  withCurrency?: boolean;
}

/**
 * `formatMoney("1240000.00")` → `"1 240 000 so'm"` (NBSP grouping),
 * `formatMoney("-1240000.4")` → `"−1 240 000 so'm"`,
 * `formatMoney("94500", { precision: 2 })` → `"94 500,00 so'm"`.
 * Rounds ROUND_HALF_UP to `precision` places for display only.
 */
export function formatMoney(value: string, options: FormatMoneyOptions = {}): string {
  const precision = options.precision ?? 0;
  const rounded = toDecimal(value).toDecimalPlaces(precision, Decimal.ROUND_HALF_UP);
  const sign = rounded.isNegative() && !rounded.isZero() ? MINUS : "";
  const body = groupDecimal(rounded.abs(), precision);
  return `${sign}${body}${options.withCurrency === false ? "" : SOM}`;
}

export type QtyUnitKind = "integer" | "fractional";

/**
 * Quantity: piece-like units are whole numbers, weight/volume units 3 decimals with comma
 * (08 §8: `1,250 kg`). The unit label itself is appended by the caller (translated).
 */
export function formatQty(value: string, kind: QtyUnitKind): string {
  const places = kind === "integer" ? 0 : 3;
  const rounded = toDecimal(value).toDecimalPlaces(places, Decimal.ROUND_HALF_UP);
  const sign = rounded.isNegative() && !rounded.isZero() ? MINUS : "";
  return `${sign}${groupDecimal(rounded.abs(), places)}`;
}

/** Percent from an API decimal string: "12.50" → "12,5%" (08 §8 — comma decimal separator). */
export function formatPercent(value: string): string {
  const rounded = toDecimal(value).toDecimalPlaces(2, Decimal.ROUND_HALF_UP);
  const sign = rounded.isNegative() && !rounded.isZero() ? MINUS : "";
  const body = uzFormat(
    new Intl.NumberFormat("uz-UZ", { maximumFractionDigits: 2 }),
    rounded.abs().toFixed(2),
  );
  return `${sign}${body}%`;
}
