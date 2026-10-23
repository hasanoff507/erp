/**
 * «Mijoz kartasi» Sheet (07 BO-06; 18 §11.4): `GET /counterparties/{id}` → `PATCH /counterparties/{id}` with
 * `version` (409 VERSION_CONFLICT when someone saved meanwhile — LWW is never silent, 16 §5). Fields: name,
 * phone, kind, STIR, legal address, bank account, MFO, credit limit (empty = no limit), standing discount
 * (0–100), notify consent. Only changed fields are sent. Permission `debts.limit.manage`.
 */
import { api } from "@shared/api";
import { compareMoney, isMoney, money, type Money } from "@shared/lib/money";
import { isCompleteNationalPhone, nationalDigits, toE164 } from "@shared/lib/phone";
import type { CounterpartyOut, CounterpartyUpdate } from "@shared/models";

import { apiFx } from "#/shared/lib/effect.ts";

export interface CardForm {
  name: string;
  phone: string;
  kind: "person" | "company";
  stir: string;
  legalAddress: string;
  bankAccount: string;
  bankMfo: string;
  creditLimit: string;
  discountPct: string;
  notifyConsent: boolean;
}

export type CardErrors = Partial<Record<"name" | "phone" | "stir" | "creditLimit" | "discountPct", string>>;

export function toCardForm(c: CounterpartyOut): CardForm {
  return {
    name: c.name,
    phone: c.phone ? nationalDigits(c.phone) : "",
    kind: c.kind === "company" ? "company" : "person",
    stir: c.stir ?? "",
    legalAddress: c.legal_address ?? "",
    bankAccount: c.bank_account ?? "",
    bankMfo: c.bank_mfo ?? "",
    creditLimit: c.credit_limit ?? "",
    discountPct: c.standing_discount_pct ?? "",
    notifyConsent: c.notify_consent,
  };
}

export function validateCard(form: CardForm): CardErrors {
  const errors: CardErrors = {};
  if (!form.name.trim()) errors.name = "validation.required";
  if (!form.phone) errors.phone = "validation.required";
  else if (!isCompleteNationalPhone(form.phone)) errors.phone = "validation.phone_uz";
  if (form.stir && !/^\d{9}$|^\d{14}$/.test(form.stir)) errors.stir = "validation.invalid_format";
  if (
    form.creditLimit &&
    (!isMoney(form.creditLimit) || compareMoney(money(form.creditLimit), "0.00" as Money) < 0)
  ) {
    errors.creditLimit = "validation.invalid_format";
  }
  if (form.discountPct) {
    if (!isMoney(form.discountPct)) errors.discountPct = "validation.invalid_format";
    else {
      const pct = money(form.discountPct);
      if (compareMoney(pct, "0.00" as Money) < 0 || compareMoney(pct, "100.00" as Money) > 0) {
        errors.discountPct = "validation.invalid_format";
      }
    }
  }
  return errors;
}

const orNull = (v: string): string | null => (v.trim() ? v.trim() : null);

/** Only the fields that changed against the loaded card (+ `version`). */
export function toCardPatch(form: CardForm, original: CounterpartyOut): CounterpartyUpdate {
  const before = toCardForm(original);
  const patch: CounterpartyUpdate = { version: original.version };
  if (form.name.trim() !== before.name) patch.name = form.name.trim();
  if (form.phone !== before.phone) patch.phone = toE164(form.phone);
  if (form.kind !== before.kind) patch.kind = form.kind;
  if (form.stir !== before.stir) patch.stir = orNull(form.stir);
  if (form.legalAddress !== before.legalAddress) patch.legal_address = orNull(form.legalAddress);
  if (form.bankAccount !== before.bankAccount) patch.bank_account = orNull(form.bankAccount);
  if (form.bankMfo !== before.bankMfo) patch.bank_mfo = orNull(form.bankMfo);
  if (form.creditLimit !== before.creditLimit)
    patch.credit_limit = form.creditLimit ? money(form.creditLimit) : null;
  if (form.discountPct !== before.discountPct) {
    patch.standing_discount_pct = form.discountPct ? money(form.discountPct) : null;
  }
  if (form.notifyConsent !== before.notifyConsent) patch.notify_consent = form.notifyConsent;
  return patch;
}

export const loadCardFx = apiFx<string, CounterpartyOut>((id) => api.debts.getCounterparty(id));
export const saveCardFx = apiFx<{ id: string; patch: CounterpartyUpdate }, CounterpartyOut>(({ id, patch }) =>
  api.debts.updateCounterparty(id, patch),
);
