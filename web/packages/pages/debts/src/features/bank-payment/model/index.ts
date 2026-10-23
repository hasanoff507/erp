/**
 * BO-06 «To'lov qabul qilish» — bank transfer only (qaror #67, D3; 18 §12.3): `POST /debt-payments`
 * `{counterparty_id, branch_id, amount, method:"bank", doc_date, promise_date?, comment?}` (draft) →
 * `POST /debt-payments/{id}/post` — no cash register, no fiscal receipt, `Dt 5110 / Kt 4010`. The amount may
 * not exceed the current debt (`debt_payment_exceeds_balance`, qaror #45); cash / card / QR debt payments are
 * POS-13 only. A draft whose post failed is cancelled (best effort) so no orphan draft is left behind.
 */
import { api } from "@shared/api";
import { compareMoney, isMoney, money, type Money } from "@shared/lib/money";
import type { DebtPaymentOut } from "@shared/models";

import { apiFx } from "#/shared/lib/effect.ts";

export interface BankPaymentForm {
  amount: string;
  docDate: string;
  branchId: string | null;
  promiseDate: string;
  comment: string;
}

export type BankPaymentField = "amount" | "docDate" | "branchId" | "promiseDate";
export type BankPaymentErrors = Partial<Record<BankPaymentField, string>>;

export interface BankPaymentRequest {
  counterpartyId: string;
  branchId: string;
  amount: Money;
  docDate: string;
  promiseDate: string | null;
  comment: string | null;
}

/** Field errors as i18n keys (`validation.*` in common, `debts:*` for the screen-specific ones). */
export function validateBankPayment(form: BankPaymentForm, balance: Money, today: string): BankPaymentErrors {
  const errors: BankPaymentErrors = {};
  if (!form.amount || !isMoney(form.amount) || compareMoney(money(form.amount), "0.00" as Money) <= 0) {
    errors.amount = "validation.required";
  } else if (compareMoney(money(form.amount), balance) > 0) {
    errors.amount = "debts:payment.exceedsBalance";
  }
  if (!form.docDate) errors.docDate = "validation.required";
  else if (form.docDate > today) errors.docDate = "validation.date_in_future";
  if (!form.branchId) errors.branchId = "validation.required";
  if (form.promiseDate && form.promiseDate < today) errors.promiseDate = "debts:payment.promiseInPast";
  return errors;
}

export function toBankPaymentRequest(counterpartyId: string, form: BankPaymentForm): BankPaymentRequest {
  return {
    counterpartyId,
    branchId: form.branchId ?? "",
    amount: money(form.amount),
    docDate: form.docDate,
    promiseDate: form.promiseDate || null,
    comment: form.comment.trim() ? form.comment.trim() : null,
  };
}

export const submitBankPaymentFx = apiFx<BankPaymentRequest, DebtPaymentOut>(async (r) => {
  const draft = await api.debts.createDebtPayment({
    counterparty_id: r.counterpartyId,
    branch_id: r.branchId,
    amount: r.amount,
    method: "bank",
    doc_date: r.docDate,
    promise_date: r.promiseDate,
    comment: r.comment,
  });
  try {
    return await api.debts.postDebtPayment(draft.id);
  } catch (error) {
    await api.debts.cancelDebtPayment(draft.id, { reason: "post failed" }).catch(() => undefined);
    throw error;
  }
});
