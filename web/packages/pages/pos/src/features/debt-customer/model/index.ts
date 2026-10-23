/**
 * Debt customer on the POS (B4, w-debts): pick / quick-create a customer and judge a debt sale against the
 * credit limit — 07 POS-02 «+ Mijoz», POS-03 «Nasiya», POS-06; 18 §11.1 (`counterparty.created`, offline too),
 * 16 §5 (the limit uses the last known balance + this device's unsynced debt sales; offline the sale is not
 * blocked — the cashier confirms, the server flags `debt_limit_exceeded_offline`; online an over-limit debt
 * needs a Manager approval, `debts.approve`). QT-M08-08: a new customer has no limit → no check at all.
 */
import { createEffect } from "effector";

import { addMoney, compareMoney, subtractMoney, toDecimal, type Money } from "@shared/lib/money";
import { isCompleteNationalPhone, toE164 } from "@shared/lib/phone";
import {
  createQuickCustomer,
  customerDebts,
  customers,
  overCreditLimit,
  type CustomerDebtView,
  type CustomerRow,
} from "@shared/offline";

export interface QuickCustomerForm {
  name: string;
  /** National digits from PhoneInput ("901234567"). */
  phone: string;
}

export type QuickCustomerErrors = Partial<Record<"name" | "phone", string>>;

/** 18 §11.1: name and phone are required (the backend `CounterpartyCreatedPayload`). */
export function validateQuickCustomer(form: QuickCustomerForm): QuickCustomerErrors {
  const errors: QuickCustomerErrors = {};
  if (!form.name.trim()) errors.name = "validation.required";
  if (!form.phone) errors.phone = "validation.required";
  else if (!isCompleteNationalPhone(form.phone)) errors.phone = "validation.phone_uz";
  return errors;
}

export const createQuickCustomerFx = createEffect(
  ({ form, actorUserId }: { form: QuickCustomerForm; actorUserId: string }): Promise<CustomerRow> =>
    createQuickCustomer({ name: form.name, phone: toE164(form.phone) }, { actorUserId }),
);

export const searchCustomersFx = createEffect((query: string) => customers.search(query, { limit: 30 }));

export const loadDebtViewFx = createEffect((customerId: string): Promise<CustomerDebtView | undefined> =>
  customerDebts.view(customerId),
);

export interface LimitCheck {
  /** Debt after this sale. */
  after: Money;
  /** The limit would be passed. */
  over: boolean;
  /** Online: a Manager approval is needed (18 §4.3). */
  needsApproval: boolean;
  /** Offline: the cashier must confirm the over-limit debt (the server flags it). */
  needsOfflineConfirm: boolean;
  /** `after / limit` in percent (0–999), null without a limit. */
  usedPct: number | null;
  /** What is left of the limit after the sale (may be negative); null without a limit. */
  left: Money | null;
}

export function limitCheck(
  view: CustomerDebtView | null | undefined,
  amount: Money,
  online: boolean,
): LimitCheck {
  const balance = view?.balance ?? ("0.00" as Money);
  const after = addMoney(balance, amount);
  const limit = view?.creditLimit ?? null;
  const over = view ? overCreditLimit(view, amount) : false;
  let usedPct: number | null = null;
  if (limit !== null && compareMoney(limit, "0.00" as Money) > 0) {
    usedPct = Math.min(999, toDecimal(after).times(100).div(toDecimal(limit)).floor().toNumber());
  }
  return {
    after,
    over,
    needsApproval: over && online,
    needsOfflineConfirm: over && !online,
    usedPct,
    left: limit === null ? null : subtractMoney(limit, after),
  };
}
