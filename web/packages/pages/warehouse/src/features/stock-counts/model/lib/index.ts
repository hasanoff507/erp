import type { ListStockCountsParams } from "@shared/models";

import { absMoney, compareQty, isDecimal, isNegative, isZero, qty3, sumMoney } from "#/shared/lib/decimal.ts";

import {
  COUNT_PAGE_SIZE,
  COUNT_STATUSES,
  type CountLine,
  type CountLineIn,
  type CountStatus,
  type CountTotals,
  type ExtraLine,
  type LineFilter,
  type ListRequest,
} from "../types/index.ts";

export function toQuery({ warehouseId, status, cursor }: ListRequest): ListStockCountsParams {
  return {
    ...(warehouseId ? { warehouse_id: warehouseId } : {}),
    ...(status ? { status } : {}),
    ...(cursor ? { cursor } : {}),
    limit: COUNT_PAGE_SIZE,
  };
}

export function isCountStatus(value: string | null): value is CountStatus {
  return value !== null && (COUNT_STATUSES as readonly string[]).includes(value);
}

/**
 * «Kamomad X so'm, ortiqcha Y so'm hisobga olinadi» (07 BO-03): Σ of the estimated difference values
 * (`amount`, 2 dp) — shortage lines have a negative diff. Uncounted lines carry no amount yet.
 */
export function countTotals(lines: readonly CountLine[]): CountTotals {
  const shortage: string[] = [];
  const surplus: string[] = [];
  let uncounted = 0;
  let diffLines = 0;
  for (const l of lines) {
    if (l.counted === null) {
      uncounted += 1;
      continue;
    }
    if (l.diff === null || isZero(l.diff)) continue;
    diffLines += 1;
    if (l.amount === null) continue;
    if (isNegative(l.diff)) shortage.push(absMoney(l.amount));
    else surplus.push(absMoney(l.amount));
  }
  return { shortage: sumMoney(shortage), surplus: sumMoney(surplus), uncounted, diffLines };
}

export function filterLines(lines: readonly CountLine[], filter: LineFilter, search: string): CountLine[] {
  const q = search.trim().toLowerCase();
  return lines.filter((l) => {
    if (q && !l.product_name.toLowerCase().includes(q)) return false;
    if (filter === "uncounted") return l.counted === null;
    if (filter === "diff") return l.diff !== null && !isZero(l.diff);
    return true;
  });
}

/**
 * Edited counted values (product_id → typed qty) that differ from what the server has → the
 * `POST /stock-counts/{id}/lines` body (19 §14: upsert by product, a new product adds a line).
 */
export function changedLines(
  lines: readonly CountLine[],
  extras: readonly ExtraLine[],
  drafts: Readonly<Record<string, string>>,
): CountLineIn[] {
  const out: CountLineIn[] = [];
  for (const l of lines) {
    const typed = drafts[l.product_id];
    if (typed === undefined || !isDecimal(typed)) continue;
    if (l.counted !== null && compareQty(typed, l.counted) === 0) continue;
    out.push({ product_id: l.product_id, counted: qty3(typed) });
  }
  for (const e of extras) {
    if (lines.some((l) => l.product_id === e.productId)) continue;
    const typed = drafts[e.productId];
    if (typed !== undefined && isDecimal(typed)) out.push({ product_id: e.productId, counted: qty3(typed) });
  }
  return out;
}

/**
 * Drafts left after a save (WEB-12): a value typed while the save was in flight differs from what was
 * sent and survives; one equal to what was sent (or to what the server now has) is dropped.
 */
export function draftsAfterSave(
  drafts: Readonly<Record<string, string>>,
  sent: readonly CountLineIn[],
  lines: readonly CountLine[],
): Record<string, string> {
  const same = (value: string, qty: string | null | undefined) =>
    qty != null && isDecimal(value) && compareQty(value, qty) === 0;
  const out: Record<string, string> = {};
  for (const [productId, value] of Object.entries(drafts)) {
    const wasSent = same(value, sent.find((l) => l.product_id === productId)?.counted);
    const isStored = same(value, lines.find((l) => l.product_id === productId)?.counted);
    if (!wasSent && !isStored) out[productId] = value;
  }
  return out;
}

/** `≥ 0` (07 POS-10 `countedQty`); empty = not counted yet. */
export function isCountedValid(value: string): boolean {
  return value === "" || (isDecimal(value) && compareQty(value, "0") >= 0);
}
