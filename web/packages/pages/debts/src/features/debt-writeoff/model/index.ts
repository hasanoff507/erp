/**
 * «Qarzni kechish» (hisobdan chiqarish) — Owner only (`debts.forgive`; 18 §12.5, 13 §2.15):
 * `POST /debt-writeoffs {counterparty_id, amount, reason, account_choice ("9430" default | "4910"),
 * tax_writeoff_basis?, doc_date?, branch_id?, comment?}` → `POST /debt-writeoffs/{id}/post`
 * (`Dt 9430|4910 / Kt 4010`, allocated oldest-first to open documents). Errors: `DEBT_ALREADY_PAID`,
 * `validation.debt_writeoff_exceeds_balance`, `validation.reserve_4910_insufficient`. Online only (16 §2).
 */
import { api } from "@shared/api";
import { compareMoney, isMoney, money, type Money } from "@shared/lib/money";
import type { DebtWriteoffOut } from "@shared/models";

import { apiFx } from "#/shared/lib/effect.ts";

export const ACCOUNT_CHOICES = ["9430", "4910"] as const;
export type AccountChoice = (typeof ACCOUNT_CHOICES)[number];
export const TAX_BASES = ["none", "court", "bankruptcy", "liquidation", "death", "limitation"] as const;
export type TaxBasis = (typeof TAX_BASES)[number];

export interface WriteoffForm {
  amount: string;
  reason: string;
  accountChoice: AccountChoice;
  taxBasis: TaxBasis;
  comment: string;
}

export type WriteoffErrors = Partial<Record<"amount" | "reason", string>>;

export function validateWriteoff(form: WriteoffForm, balance: Money): WriteoffErrors {
  const errors: WriteoffErrors = {};
  if (!form.amount || !isMoney(form.amount) || compareMoney(money(form.amount), "0.00" as Money) <= 0) {
    errors.amount = "validation.required";
  } else if (compareMoney(money(form.amount), balance) > 0) {
    errors.amount = "validation.debt_writeoff_exceeds_balance";
  }
  if (!form.reason.trim()) errors.reason = "validation.required";
  return errors;
}

export interface WriteoffRequest {
  counterpartyId: string;
  branchId: string | null;
  form: WriteoffForm;
}

export const submitWriteoffFx = apiFx<WriteoffRequest, DebtWriteoffOut>(
  async ({ counterpartyId, branchId, form }) => {
    const draft = await api.debts.createDebtWriteoff({
      counterparty_id: counterpartyId,
      amount: money(form.amount),
      reason: form.reason.trim(),
      account_choice: form.accountChoice,
      tax_writeoff_basis: form.taxBasis,
      branch_id: branchId,
      comment: form.comment.trim() ? form.comment.trim() : null,
    });
    try {
      return await api.debts.postDebtWriteoff(draft.id);
    } catch (error) {
      await api.debts.cancelDebtWriteoff(draft.id, { reason: "post failed" }).catch(() => undefined);
      throw error;
    }
  },
);
