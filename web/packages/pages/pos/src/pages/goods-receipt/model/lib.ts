/**
 * POS-08 pure logic (07 POS-08, 19 §8): PO lines → receipt lines (default = what is still to come), scanner
 * comparison (first scan of a line switches it to counted units), marking codes (count = qty, GS kept),
 * discrepancy reason rule and the `POST/PATCH /goods-receipts` body. Decimal strings only.
 */
import type { PoOut, ReceiptIn, ReceiptLineInDiscrepancyReason, ReceiptOut } from "@shared/models";

import {
  addQty,
  compareQty,
  isPositiveQty,
  qty3,
  subtractQty,
  type ScannedProduct,
} from "#/features/wh-scan/index.ts";

export type DiscrepancyReason = Exclude<ReceiptLineInDiscrepancyReason, null>;
export const DISCREPANCY_REASONS: readonly DiscrepancyReason[] = [
  "short",
  "excess",
  "damaged",
  "wrong_item",
  "other",
];

export interface ReceiveLine {
  productId: string;
  name: string;
  unitCode: string | null;
  /** Still to come = ordered − already received (PO `received_lines`). */
  remaining: string;
  received: string;
  /** Scanned at least once — then scans count units from zero. */
  scanned: boolean;
  reason: DiscrepancyReason | null;
  /** PO line price; null → `cost` must be typed (19 §8). */
  price: string | null;
  cost: string;
  isMarked: boolean;
  markingCodes: string[];
}

export type LineProblem = "reason_required" | "cost_required" | "marking_mismatch";

export function linesFromOrder(
  po: Pick<PoOut, "lines" | "received_lines">,
  marked: ReadonlySet<string> = new Set(),
): ReceiveLine[] {
  const done = new Map<string, string>();
  for (const r of po.received_lines)
    done.set(r.product_id, addQty(done.get(r.product_id) ?? "0", r.received_qty));
  return po.lines.map((l) => {
    const left = subtractQty(l.qty, done.get(l.product_id) ?? "0");
    const remaining = compareQty(left, "0") < 0 ? "0.000" : left;
    return {
      productId: l.product_id,
      name: l.product_name ?? l.product_id,
      unitCode: l.unit_code,
      remaining,
      received: remaining,
      scanned: false,
      reason: null,
      price: l.price,
      cost: l.price ?? "",
      isMarked: marked.has(l.product_id),
      markingCodes: [],
    };
  });
}

/** A saved draft (PATCH continues it): its quantities, reasons and marking codes replace the defaults. */
export function applyDraft(lines: readonly ReceiveLine[], draft: Pick<ReceiptOut, "lines">): ReceiveLine[] {
  return lines.map((l) => {
    const d = draft.lines.find((x) => x.product_id === l.productId);
    if (!d) return { ...l, received: "0.000", scanned: true };
    return {
      ...l,
      received: d.qty,
      scanned: true,
      reason: d.discrepancy_reason ?? null,
      cost: l.price ?? d.cost,
      isMarked: l.isMarked || d.is_marked,
      markingCodes: [...d.marking_codes],
    };
  });
}

export type ScanOutcome =
  { lines: ReceiveLine[]; error: null } | { lines: null; error: "not_in_order" | "marking_duplicate" };

export function applyScan(lines: readonly ReceiveLine[], item: ScannedProduct): ScanOutcome {
  const i = lines.findIndex((l) => l.productId === item.productId);
  if (i === -1) return { lines: null, error: "not_in_order" };
  const line = lines[i] as ReceiveLine;
  if (item.markingCode && line.markingCodes.includes(item.markingCode)) {
    return { lines: null, error: "marking_duplicate" };
  }
  const next: ReceiveLine = {
    ...line,
    received: line.scanned ? addQty(line.received, item.qty) : qty3(item.qty),
    scanned: true,
    isMarked: line.isMarked || item.isMarked || item.markingCode !== null,
    markingCodes: item.markingCode ? [...line.markingCodes, item.markingCode] : line.markingCodes,
  };
  return { lines: lines.map((l, j) => (j === i ? next : l)), error: null };
}

export function hasDiscrepancy(l: Pick<ReceiveLine, "received" | "remaining">): boolean {
  const received = qty3(l.received) || "0.000";
  return compareQty(received, l.remaining) !== 0;
}

export function lineProblems(l: ReceiveLine): LineProblem[] {
  const out: LineProblem[] = [];
  if (!isPositiveQty(l.received)) return out; // not sent
  if (hasDiscrepancy(l) && !l.reason) out.push("reason_required");
  if (l.price === null && qty3(l.cost) === "") out.push("cost_required");
  if (l.isMarked && compareQty(String(l.markingCodes.length), l.received) !== 0) out.push("marking_mismatch");
  return out;
}

/** «Nomuvofiqlik bilan yakunlaysizmi?» — lines whose received differs from what was still to come. */
export function discrepancyCount(lines: readonly ReceiveLine[]): number {
  return lines.filter(hasDiscrepancy).length;
}

export function receiptBody(
  po: Pick<PoOut, "id" | "warehouse_id" | "supplier_id">,
  lines: readonly ReceiveLine[],
  docDate: string,
  poaNumber: string,
): ReceiptIn {
  return {
    supplier_id: po.supplier_id,
    warehouse_id: po.warehouse_id,
    po_id: po.id,
    doc_date: docDate,
    lines: lines
      .filter((l) => isPositiveQty(l.received))
      .map((l) => ({
        product_id: l.productId,
        qty: qty3(l.received),
        ...(l.price === null ? { cost: l.cost } : {}),
        ...(l.isMarked ? { marking_codes: [...l.markingCodes] } : {}),
        ...(hasDiscrepancy(l) ? { discrepancy_reason: l.reason } : {}),
      })),
    ...(poaNumber.trim() ? { poa_number: poaNumber.trim().slice(0, 64) } : {}),
  };
}
