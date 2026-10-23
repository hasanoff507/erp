/**
 * POS-14 — Kassaga pul qo'yish / kassadan pul olish (07 POS-14; 18 §13.1; US-M16-01; QT-M16-01/-02,
 * QT-PERM-05). `cash_movement.created` goes to the outbox (works offline — not a fiscal document);
 * a withdrawal above the cashier's own `cash.withdraw` limit (default 50 000 so'm) needs an approval:
 * local Manager/Owner PIN (offline too) or a remote request (online only).
 * «Xarajat» (`expense.created`) is Bosqich 4 — the tab is shown disabled.
 */
import { compareMoney, money, type Money } from "@shared/lib/money";
import { enqueueEvent, limits, settings } from "@shared/offline";

import { isOwner, limitCovers, uuidv7, type PosCashier } from "#/entities/pos-session/index.ts";
import type { ApprovalRef } from "#/features/manager-approval/index.ts";

export type Direction = "in" | "out";
export type Reason = "collection" | "deposit" | "owner_withdrawal" | "other";

/** 18 §13.1 reason ↔ direction pairs (POS-14 chips). */
export const REASONS: Record<Direction, Reason[]> = {
  out: ["owner_withdrawal", "collection", "other"],
  in: ["deposit", "other"],
};

export const DEFAULT_WITHDRAW_LIMIT = "50000.00";
export const COMMENT_MAX = 1000;

export interface MovementForm {
  direction: Direction;
  /** Whole so'm digits from the keypad ("150000"). */
  digits: string;
  reason: Reason | null;
  comment: string;
}

export type MovementError = "amount" | "reason" | "comment" | "founder";

/** Whole-so'm keypad digits → Money ("150000" → "150000.00"); "" → null. */
export function digitsToMoney(digits: string): Money | null {
  if (!/^\d+$/.test(digits)) return null;
  return money(digits);
}

/**
 * Field checks of 07 POS-14 / 18 §13.1. `soleProprietor === false` → `owner_withdrawal` needs a founder
 * (`counterparty_id`), which the device has no list of (founders are not pulled) — refused here, done in
 * the back-office.
 */
export function validateMovement(form: MovementForm, soleProprietor: boolean): MovementError[] {
  const errors: MovementError[] = [];
  const amount = digitsToMoney(form.digits);
  if (!amount || compareMoney(amount, "0.00" as Money) <= 0) errors.push("amount");
  if (!form.reason || !REASONS[form.direction].includes(form.reason)) errors.push("reason");
  if (form.reason === "other" && form.comment.trim() === "") errors.push("comment");
  if (form.comment.length > COMMENT_MAX) errors.push("comment");
  if (form.reason === "owner_withdrawal" && !soleProprietor) errors.push("founder");
  return errors;
}

/** QT-PERM-05 / QT-M16-02: `out` above the actor's own `cash.withdraw` limit → approval. */
export function withdrawalNeedsApproval(
  cashier: Pick<PosCashier, "roleCodes">,
  ownLimit: string | null | undefined,
  amount: string,
): boolean {
  if (isOwner(cashier.roleCodes)) return false;
  return !limitCovers(ownLimit, amount);
}

/** 18 §13.1 payload (exactly the documented fields). */
export function cashMovementPayload(input: {
  id: string;
  cashRegisterId: string;
  shiftId: string;
  direction: Direction;
  reason: Reason;
  amount: Money;
  comment: string;
  approval: ApprovalRef | null;
}) {
  return {
    id: input.id,
    cash_register_id: input.cashRegisterId,
    shift_id: input.shiftId,
    direction: input.direction,
    reason: input.reason,
    account: null,
    counterparty_id: null,
    employee_id: null,
    amount: input.amount,
    comment: input.comment.trim() || null,
    approval: input.approval,
  };
}

export interface CashMovementDeps {
  ownLimit(userId: string): Promise<string | null | undefined>;
  soleProprietor(): Promise<boolean>;
  enqueue(
    payload: ReturnType<typeof cashMovementPayload>,
    actorUserId: string,
  ): Promise<{ clientEventId: string }>;
}

export const defaultCashMovementDeps: CashMovementDeps = {
  ownLimit: (userId) => limits.value(userId, "cash.withdraw"),
  soleProprietor: async () => {
    const tenant = (await settings.get()).raw.tenant as { legal_form?: unknown } | undefined;
    return tenant?.legal_form === "sole_proprietor";
  },
  enqueue: async (payload, actorUserId) => {
    const r = await enqueueEvent("cash_movement.created", payload, { actorUserId });
    return { clientEventId: r.clientEventId };
  },
};

export const newMovementId = (): string => uuidv7();
