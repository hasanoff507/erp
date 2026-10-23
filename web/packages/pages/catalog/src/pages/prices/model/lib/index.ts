import { dayjs } from "@shared/lib/date";

import {
  changePct,
  currentPriceOf,
  DEFAULT_PRICE_LIMIT_PCT,
  exceedsLimit,
  isPositiveAmount,
  samePrice,
  scheduledPriceOf,
} from "#/entities/product/index.ts";

import type {
  ApprovalLimit,
  PriceChange,
  PriceDraft,
  PriceHistoryItem,
  ProductOut,
  ProductPrice,
  RowState,
} from "../types/index.ts";

/** Local calendar date `YYYY-MM-DD` (07 BO-05 `effectiveFrom` default "Bugun"). */
export function todayIso(now: Date = new Date()): string {
  return dayjs(now).format("YYYY-MM-DD");
}

/**
 * `lines[].valid_from` (19 §4): `null` = in force from the moment of posting (today); a later date
 * starts at local midnight of that day (sent as UTC ISO).
 */
export function validFromOf(effectiveFrom: string, today: string): string | null {
  return effectiveFrom <= today ? null : dayjs(effectiveFrom).startOf("day").toISOString();
}

/** Branch override first (19 §4 "base = filial narxi, yo'q bo'lsa global narx"), then the global price. */
export function productPriceOf(
  global: readonly PriceHistoryItem[],
  branch: readonly PriceHistoryItem[] | null,
  now: Date = new Date(),
): ProductPrice {
  const current = (branch ? currentPriceOf(branch, now) : null) ?? currentPriceOf(global, now);
  const scheduled = (branch ? scheduledPriceOf(branch, now) : null) ?? scheduledPriceOf(global, now);
  return {
    current: current?.price ?? null,
    scheduled: scheduled ? { price: scheduled.price, validFrom: scheduled.valid_from } : null,
  };
}

/** Edited prices (all pages) that differ from the current price (unchanged / empty drafts are ignored). */
export function collectChanges(
  prices: Readonly<Record<string, ProductPrice>>,
  drafts: Readonly<Record<string, PriceDraft>>,
): PriceChange[] {
  const out: PriceChange[] = [];
  for (const draft of Object.values(drafts)) {
    if (draft.value === "") continue;
    const loaded = prices[draft.product.id];
    const oldPrice = loaded ? loaded.current : draft.oldPrice;
    if (oldPrice !== null && samePrice(oldPrice, draft.value)) continue;
    const pct = changePct(oldPrice, draft.value);
    out.push({ product: draft.product, oldPrice, newPrice: draft.value, pct, overLimit: exceedsLimit(pct) });
  }
  return out;
}

/** `draftChanged` → the stored draft: the product and its current price are snapshotted on first edit. */
export function applyDraft(
  drafts: Readonly<Record<string, PriceDraft>>,
  edit: { productId: string; value: string },
  products: readonly ProductOut[],
  prices: Readonly<Record<string, ProductPrice>>,
): Record<string, PriceDraft> {
  const existing = drafts[edit.productId];
  if (existing) return { ...drafts, [edit.productId]: { ...existing, value: edit.value } };
  const product = products.find((p) => p.id === edit.productId);
  if (!product) return { ...drafts };
  const oldPrice = prices[product.id]?.current ?? null;
  return { ...drafts, [product.id]: { product, oldPrice, value: edit.value } };
}

/**
 * The limit the prediction compares with (19 §4). GET /auth/session exposes permission codes but not
 * `role_permissions.limit_value`, so:
 * - no `prices.approve` grant → the server uses the default 10% — exact;
 * - a grant whose limit is known (`grantedLimit`, `null` = unlimited) → exact;
 * - a grant with an unknown limit → the default 10% as an advisory hint ("may need approval").
 */
export function approvalLimitOf(canApprove: boolean, grantedLimit?: string | null): ApprovalLimit {
  if (!canApprove) return { pct: DEFAULT_PRICE_LIMIT_PCT, exact: true };
  if (grantedLimit !== undefined) return { pct: grantedLimit, exact: true };
  return { pct: DEFAULT_PRICE_LIMIT_PCT, exact: false };
}

/** Row status for the table: over the limit → approval (exact limit) or "may need approval" (advisory). */
export function rowStateOf(change: PriceChange | undefined, limit: ApprovalLimit): RowState {
  if (!change) return "unchanged";
  if (!isPositiveAmount(change.newPrice)) return "invalid";
  if (limit.pct !== null && exceedsLimit(change.pct, limit.pct)) {
    return limit.exact ? "approval" : "approvalMaybe";
  }
  return "changed";
}
