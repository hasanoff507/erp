/**
 * POS-10 pure logic (07 POS-10, 19 §14): server count lines + the counts recorded on this device
 * (`stock_count.line_recorded` outbox events — absolute numbers, the latest `recorded_at` wins) → table rows,
 * filter tabs (Hammasi / Farqli / Sanalmagan / Mos) and the progress counters. Decimal strings only.
 */
import type { CountLineOut, CountOut } from "@shared/models";

import { compareQty, subtractQty } from "#/features/wh-scan/index.ts";

export const LINE_RECORDED = "stock_count.line_recorded";

export interface LocalCount {
  productId: string | null;
  barcode: string | null;
  counted: string;
  recordedAt: string;
  /** Outbox state of the latest event of this line. */
  sync: "pending" | "accepted" | "rejected";
  name?: string | null;
}

export interface CountRow {
  productId: string;
  name: string;
  barcode: string | null;
  /** System qty the device compares with (`expected`, else `snapshot_qty`). */
  expected: string;
  counted: string | null;
  diff: string | null;
  sync: LocalCount["sync"] | "server" | null;
}

export type CountFilter = "all" | "diff" | "uncounted" | "match";

/** Minimal outbox row (structurally `OutboxRow` of @shared/offline). */
export interface CountEventRow {
  type: string;
  status: string;
  retryable: boolean | null;
  created_at: string;
  payload: Record<string, unknown>;
}

const str = (v: unknown): string | null => (typeof v === "string" && v ? v : null);

function syncOf(row: Pick<CountEventRow, "status">): LocalCount["sync"] {
  if (row.status === "accepted" || row.status === "duplicate") return "accepted";
  if (row.status === "rejected") return "rejected";
  return "pending";
}

const keyOf = (productId: string | null, barcode: string | null): string =>
  productId ? `p:${productId}` : `b:${barcode ?? ""}`;

/** Latest local count per product (or per unknown barcode) of one stock count, from the outbox. */
export function localCountsFromOutbox(
  rows: readonly CountEventRow[],
  countId: string,
): Map<string, LocalCount> {
  const out = new Map<string, LocalCount>();
  for (const row of rows) {
    if (row.type !== LINE_RECORDED || str(row.payload.count_id) !== countId) continue;
    if (row.status === "rejected" && row.retryable !== true) continue; // never applied on the server
    const productId = str(row.payload.product_id);
    const barcode = str(row.payload.barcode);
    const counted = str(row.payload.counted);
    const recordedAt = str(row.payload.recorded_at) ?? row.created_at;
    if (!counted) continue;
    const key = keyOf(productId, barcode);
    const prev = out.get(key);
    if (!prev || prev.recordedAt <= recordedAt) {
      out.set(key, { productId, barcode, counted, recordedAt, sync: syncOf(row) });
    }
  }
  return out;
}

export function upsertLocal(
  map: ReadonlyMap<string, LocalCount>,
  count: LocalCount,
): Map<string, LocalCount> {
  const next = new Map(map);
  next.set(keyOf(count.productId, count.barcode), count);
  return next;
}

export function localFor(map: ReadonlyMap<string, LocalCount>, productId: string): LocalCount | undefined {
  return map.get(keyOf(productId, null));
}

function expectedOf(line: Pick<CountLineOut, "expected" | "snapshot_qty">): string {
  return line.expected || line.snapshot_qty || "0.000";
}

/** Server lines + local counts (local wins — it is newer or not synced yet) + unexpected local products. */
export function buildRows(
  count: Pick<CountOut, "lines"> | null,
  local: ReadonlyMap<string, LocalCount>,
): CountRow[] {
  const rows: CountRow[] = [];
  const seen = new Set<string>();
  for (const line of count?.lines ?? []) {
    seen.add(line.product_id);
    const mine = localFor(local, line.product_id);
    const counted = mine?.counted ?? line.counted;
    const expected = expectedOf(line);
    rows.push({
      productId: line.product_id,
      name: line.product_name,
      barcode: null,
      expected,
      counted,
      diff: counted === null ? null : subtractQty(counted, expected),
      sync: mine ? mine.sync : line.counted !== null ? "server" : null,
    });
  }
  for (const item of local.values()) {
    if (!item.productId || seen.has(item.productId)) continue;
    rows.push({
      productId: item.productId,
      name: item.name ?? item.productId,
      barcode: item.barcode,
      expected: "0.000",
      counted: item.counted,
      diff: item.counted,
      sync: item.sync,
    });
  }
  return rows;
}

export function filterRows(rows: readonly CountRow[], filter: CountFilter): CountRow[] {
  switch (filter) {
    case "diff":
      return rows.filter((r) => r.diff !== null && compareQty(r.diff, "0") !== 0);
    case "uncounted":
      return rows.filter((r) => r.counted === null);
    case "match":
      return rows.filter((r) => r.diff !== null && compareQty(r.diff, "0") === 0);
    default:
      return [...rows];
  }
}

export interface CountProgress {
  total: number;
  counted: number;
  shortage: number;
  surplus: number;
  left: number;
  diff: number;
  match: number;
}

export function progressOf(rows: readonly CountRow[]): CountProgress {
  let counted = 0;
  let shortage = 0;
  let surplus = 0;
  for (const r of rows) {
    if (r.counted === null || r.diff === null) continue;
    counted += 1;
    const c = compareQty(r.diff, "0");
    if (c < 0) shortage += 1;
    if (c > 0) surplus += 1;
  }
  return {
    total: rows.length,
    counted,
    shortage,
    surplus,
    left: rows.length - counted,
    diff: shortage + surplus,
    match: counted - shortage - surplus,
  };
}

/** Events of this count not yet confirmed by the server — finishing must wait for them (19 §14 `review`). */
export function pendingCountEvents(rows: readonly CountEventRow[], countId: string): number {
  return rows.filter(
    (r) =>
      r.type === LINE_RECORDED &&
      str(r.payload.count_id) === countId &&
      (r.status === "pending" || (r.status === "rejected" && r.retryable === true)),
  ).length;
}
