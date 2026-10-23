/**
 * «Boshlang'ich qarz» (US-M08-07, 18 §12.4): old paper-book debts into the system without goods —
 * `POST /debt-openings {counterparty_id | counterparty:{name, phone}, amount, direction, due_date?, doc_date?,
 * branch_id?, comment?}` → `POST /debt-openings/{id}/post` (13 §2.13, `entry_date = go_live_date − 1`;
 * `422 validation.go_live_date_missing` without a go-live date). Permission `stock.opening.manage` or
 * `debts.limit.manage`. Used by BO-06 and by BO-21 step ④ (same API — billing has its own copy of the
 * row rules, page packages never import each other). A draft whose post failed is cancelled (best effort).
 */
import { api } from "@shared/api";
import { compareMoney, isMoney, money, type Money } from "@shared/lib/money";
import { isCompleteNationalPhone, toE164 } from "@shared/lib/phone";
import type { DebtOpeningOut } from "@shared/models";

import type { Direction } from "#/entities/debtor/index.ts";
import { apiFx } from "#/shared/lib/effect.ts";

export interface OpeningForm {
  /** Existing counterparty, else a new one from name + phone. */
  counterpartyId: string | null;
  name: string;
  /** National digits from PhoneInput ("901234567"). */
  phone: string;
  amount: string;
  dueDate: string;
  docDate: string;
  comment: string;
}

export type OpeningField = "name" | "phone" | "amount" | "dueDate" | "docDate";
export type OpeningErrors = Partial<Record<OpeningField, string>>;

/** A new customer needs a phone (18 §11.2: `phone` is required on a customer row); a supplier may omit it. */
export function validateOpening(
  form: OpeningForm,
  today: string,
  direction: Direction = "receivable",
): OpeningErrors {
  const errors: OpeningErrors = {};
  if (!form.counterpartyId) {
    if (!form.name.trim()) errors.name = "validation.required";
    if (!form.phone && direction === "receivable") errors.phone = "validation.required";
    else if (form.phone && !isCompleteNationalPhone(form.phone)) errors.phone = "validation.phone_uz";
  }
  if (!form.amount || !isMoney(form.amount) || compareMoney(money(form.amount), "0.00" as Money) <= 0) {
    errors.amount = "validation.required";
  }
  if (form.docDate && form.docDate > today) errors.docDate = "validation.date_in_future";
  if (form.dueDate && form.docDate && form.dueDate < form.docDate)
    errors.dueDate = "debts:opening.dueBeforeDate";
  return errors;
}

export interface OpeningRequest {
  body: Parameters<typeof api.debts.createDebtOpening>[0];
}

export function toOpeningRequest(
  form: OpeningForm,
  direction: Direction,
  branchId: string | null,
): OpeningRequest {
  const who = form.counterpartyId
    ? { counterparty_id: form.counterpartyId }
    : {
        counterparty: {
          name: form.name.trim(),
          phone: form.phone ? toE164(form.phone) : null,
          kind: "person" as const,
        },
      };
  return {
    body: {
      ...who,
      amount: money(form.amount),
      direction,
      due_date: form.dueDate || null,
      doc_date: form.docDate || null,
      branch_id: branchId,
      comment: form.comment.trim() ? form.comment.trim() : null,
    },
  };
}

export const submitOpeningFx = apiFx<OpeningRequest, DebtOpeningOut>(async ({ body }) => {
  const draft = await api.debts.createDebtOpening(body);
  try {
    return await api.debts.postDebtOpening(draft.id);
  } catch (error) {
    await api.debts.cancelDebtOpening(draft.id, { reason: "post failed" }).catch(() => undefined);
    throw error;
  }
});
