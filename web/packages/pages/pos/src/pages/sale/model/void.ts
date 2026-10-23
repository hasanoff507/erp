/**
 * BEKOR (07 POS-02, 18 §5): voiding a line or the whole unpaid receipt is audit-only — `sale.draft_voided`
 * goes to the outbox (offline too), no register and no fiscal receipt is touched (QT-M01-11).
 */
import { createEffect, createEvent, sample } from "effector";

import { enqueueEvent } from "@shared/offline";

import {
  $draft,
  draftReset,
  lineRemoved,
  type Draft,
  type DraftLine,
} from "#/entities/receipt-draft/index.ts";
import { $posCashier } from "#/entities/pos-session/index.ts";

export interface VoidInput {
  draft: Draft;
  /** null → the whole receipt. */
  lineId: string | null;
  actorUserId: string;
  reason?: string | null;
}

const lineJson = (l: DraftLine) => ({
  line_id: l.id,
  product_id: l.productId,
  qty: l.qty,
  price: l.price,
  marking_code: l.markingCode,
});

/** 18 §5 payload: `voided_lines: null` = the whole receipt. */
export function draftVoidPayload(input: Omit<VoidInput, "actorUserId">): Record<string, unknown> {
  const lines =
    input.lineId === null ? null : input.draft.lines.filter((l) => l.id === input.lineId).map(lineJson);
  return { draft_ref: input.draft.ref, voided_lines: lines, reason: input.reason ?? null };
}

export const voidFx = createEffect(async (input: VoidInput) => {
  await enqueueEvent("sale.draft_voided", draftVoidPayload(input), { actorUserId: input.actorUserId });
  return input.lineId;
});

export const voidRequested = createEvent<{ lineId: string | null; reason?: string | null }>();

sample({
  clock: voidRequested,
  source: { draft: $draft, cashier: $posCashier },
  filter: ({ draft, cashier }) => cashier !== null && draft.lines.length > 0,
  fn: ({ draft, cashier }, x): VoidInput => ({
    draft,
    lineId: x.lineId,
    reason: x.reason ?? null,
    actorUserId: cashier?.userId ?? "",
  }),
  target: voidFx,
});

sample({ clock: voidFx.doneData, filter: (id): id is string => id !== null, target: lineRemoved });
sample({ clock: voidFx.doneData, filter: (id) => id === null, target: draftReset });
