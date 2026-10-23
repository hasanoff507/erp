/**
 * Price helpers (19 §4, US-M09-01/02). Money stays a decimal string (qaror #57): arithmetic goes
 * through decimal.js via @shared/lib/money `toDecimal`, never JS numbers.
 */
import { isMoney, toDecimal } from "@shared/lib/money";
import type { PriceHistoryItem } from "@shared/models";

/** Who set a history entry (19 §4 `set_by_name`): the viewer, a named user, or no author (system/legacy). */
export type PriceAuthor =
  { kind: "you" } | { kind: "user"; name: string } | { kind: "staff" } | { kind: "system" };

export function priceAuthorOf(
  item: Pick<PriceHistoryItem, "set_by" | "set_by_name">,
  viewerId: string | null,
): PriceAuthor {
  if (item.set_by === null) return { kind: "system" };
  if (viewerId !== null && item.set_by === viewerId) return { kind: "you" };
  const name = item.set_by_name?.trim();
  return name ? { kind: "user", name } : { kind: "staff" };
}

/** Catalog default approval limit when the user has no `prices.approve` grant (26 #5, US-M09-02). */
export const DEFAULT_PRICE_LIMIT_PCT = "10";

function time(value: string): number {
  return new Date(value).getTime();
}

/** The history entry in force at `now` (valid_from ≤ now < valid_to); history is newest first. */
export function currentPriceOf(
  items: readonly PriceHistoryItem[],
  now: Date = new Date(),
): PriceHistoryItem | null {
  const at = now.getTime();
  return (
    items.find(
      (item) => time(item.valid_from) <= at && (item.valid_to === null || time(item.valid_to) > at),
    ) ?? null
  );
}

/** The nearest future entry (a price change posted with a later `valid_from`). */
export function scheduledPriceOf(
  items: readonly PriceHistoryItem[],
  now: Date = new Date(),
): PriceHistoryItem | null {
  const at = now.getTime();
  const future = items.filter((item) => time(item.valid_from) > at);
  return future.length > 0 ? (future[future.length - 1] ?? null) : null;
}

/** API `new_price` is `^-?\d{1,14}\.\d{4}$` (19 §4): "19000.00" → "19000.0000". */
export function toPrice4(value: string): string {
  return toDecimal(value).toFixed(4);
}

export function isPositiveAmount(value: string): boolean {
  return isMoney(value) && toDecimal(value).greaterThan(0);
}

/** Same amount regardless of scale ("19000.00" vs "19000.0000"). */
export function samePrice(a: string, b: string): boolean {
  return isMoney(a) && isMoney(b) && toDecimal(a).equals(toDecimal(b));
}

/**
 * Change in percent (decimal string, 1 place, signed) — `(new − old) / old × 100`, or null when there
 * is no old price (19 §4: no base → no limit check).
 */
export function changePct(oldPrice: string | null, newPrice: string): string | null {
  if (!oldPrice || !isMoney(oldPrice) || !isMoney(newPrice)) return null;
  const base = toDecimal(oldPrice);
  if (base.isZero()) return null;
  return toDecimal(newPrice).minus(base).div(base).times(100).toDecimalPlaces(1).toFixed(1);
}

/** |pct| > limit (19 §4: one line over the limit sends the whole document to approval). */
export function exceedsLimit(pct: string | null, limit: string = DEFAULT_PRICE_LIMIT_PCT): boolean {
  return pct !== null && toDecimal(pct).abs().greaterThan(toDecimal(limit));
}
