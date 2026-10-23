/**
 * Draft receipt store (07 POS-02). Kept per tab in sessionStorage so a reload does not lose an unpaid
 * receipt; the sale itself only exists once `sale.created` is in the outbox.
 */
import { createEvent, createStore } from "effector";

import { newAttemptId as newId } from "@shared/lib/card-terminal";

import { addQty, stepQty } from "../lib/calc.ts";
import type { Draft, DraftDiscount, DraftLine } from "../types/index.ts";

const STORAGE_KEY = "erp-pos.draft";

export function emptyDraft(): Draft {
  return { ref: newId(), lines: [], selectedLineId: null, customerId: null, discount: null };
}

function restore(): Draft {
  try {
    const raw = globalThis.sessionStorage?.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as Draft;
      if (parsed && typeof parsed.ref === "string" && Array.isArray(parsed.lines)) return parsed;
    }
  } catch {
    /* storage unavailable — start empty */
  }
  return emptyDraft();
}

/** New line; piece goods of the same product (no marking, not weighed) merge into one line. */
export const lineAdded = createEvent<DraftLine>();
export const qtyChanged = createEvent<{ lineId: string; qty: string }>();
export const qtyStepped = createEvent<{ lineId: string; delta: 1 | -1 }>();
export const lineSelected = createEvent<string | null>();
export const selectionMoved = createEvent<1 | -1>();
export const lineRemoved = createEvent<string>();
export const discountSet = createEvent<DraftDiscount | null>();
export const customerSet = createEvent<string | null>();
/** After a sale (or a whole-receipt void): a fresh draft with a new ref. */
export const draftReset = createEvent();
/** Tests / bootstrap. */
export const draftReplaced = createEvent<Draft>();

const mergeable = (line: DraftLine) => line.kind === "piece" && line.markingCode === null;

export const $draft = createStore<Draft>(restore())
  .on(lineAdded, (d, line) => {
    const same = mergeable(line)
      ? d.lines.find((l) => mergeable(l) && l.productId === line.productId && l.price === line.price)
      : undefined;
    if (same) {
      return {
        ...d,
        selectedLineId: same.id,
        lines: d.lines.map((l) => (l.id === same.id ? { ...l, qty: addQty(l.qty, line.qty) } : l)),
      };
    }
    return { ...d, lines: [...d.lines, line], selectedLineId: line.id };
  })
  .on(qtyChanged, (d, { lineId, qty }) => ({
    ...d,
    lines: d.lines.map((l) => (l.id === lineId && l.markingCode === null ? { ...l, qty } : l)),
  }))
  .on(qtyStepped, (d, { lineId, delta }) => ({
    ...d,
    lines: d.lines.map((l) =>
      l.id === lineId && l.kind === "piece" && l.markingCode === null
        ? { ...l, qty: stepQty(l.qty, delta) }
        : l,
    ),
  }))
  .on(lineSelected, (d, id) => ({ ...d, selectedLineId: id }))
  .on(selectionMoved, (d, delta) => {
    if (d.lines.length === 0) return d;
    const at = d.lines.findIndex((l) => l.id === d.selectedLineId);
    const next = at < 0 ? d.lines.length - 1 : Math.min(d.lines.length - 1, Math.max(0, at + delta));
    return { ...d, selectedLineId: d.lines[next]?.id ?? null };
  })
  .on(lineRemoved, (d, id) => {
    const lines = d.lines.filter((l) => l.id !== id);
    return {
      ...d,
      lines,
      selectedLineId: d.selectedLineId === id ? (lines[lines.length - 1]?.id ?? null) : d.selectedLineId,
      discount: lines.length ? d.discount : null,
    };
  })
  .on(discountSet, (d, discount) => ({ ...d, discount }))
  .on(customerSet, (d, customerId) => ({ ...d, customerId }))
  .on(draftReset, () => emptyDraft())
  .on(draftReplaced, (_, d) => d);

$draft.watch((d) => {
  try {
    globalThis.sessionStorage?.setItem(STORAGE_KEY, JSON.stringify(d));
  } catch {
    /* ignore */
  }
});
