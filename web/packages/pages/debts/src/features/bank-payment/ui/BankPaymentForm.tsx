/**
 * BO-06 right panel «To'lov qabul qilish» (07 BO-06; mockup Bo06Qarzdorlar): amount (≤ current debt), date,
 * method «Bank o'tkazmasi» (the only one here — qaror #67), branch, optional new promise date, and the note
 * «Kassasiz, fiskal chek chiqmaydi · Dt 5110 / Kt 4010. Naqd, karta yoki QR bilan qarz to'lovi — kassada».
 */
import { useUnit } from "effector-react";
import { CircleAlert, Landmark } from "lucide-react";
import { useState } from "react";

import { useTranslation } from "@shared/i18n";
import { formatMoney } from "@shared/lib/format";
import type { Money } from "@shared/lib/money";
import {
  Banner,
  Button,
  FormField,
  Icon,
  Input,
  MoneyInput,
  NativeSelect,
  Textarea,
  toast,
} from "@shared/ui";

import { todayIso } from "#/shared/lib/effect.ts";
import { errorText, fieldError } from "#/shared/lib/errors.ts";

import {
  submitBankPaymentFx,
  toBankPaymentRequest,
  validateBankPayment,
  type BankPaymentErrors,
  type BankPaymentForm as Form,
} from "../model/index.ts";

export interface BankPaymentFormProps {
  counterpartyId: string;
  balance: Money;
  branches: readonly { id: string; name: string }[];
  defaultBranchId: string | null;
  disabled?: boolean;
}

export function BankPaymentForm({
  counterpartyId,
  balance,
  branches,
  defaultBranchId,
  disabled,
}: BankPaymentFormProps) {
  const { t } = useTranslation("debts");
  const pending = useUnit(submitBankPaymentFx.pending);
  const today = todayIso();
  const [form, setForm] = useState<Form>({
    amount: "",
    docDate: today,
    branchId: defaultBranchId ?? branches[0]?.id ?? null,
    promiseDate: "",
    comment: "",
  });
  const [errors, setErrors] = useState<BankPaymentErrors>({});
  const [serverError, setServerError] = useState<string | null>(null);
  const set = (patch: Partial<Form>) => setForm((f) => ({ ...f, ...patch }));

  const submit = async () => {
    const found = validateBankPayment(form, balance, today);
    setErrors(found);
    setServerError(null);
    if (Object.keys(found).length > 0) return;
    try {
      await submitBankPaymentFx(toBankPaymentRequest(counterpartyId, form));
      toast.success(t("payment.done"));
      setForm((f) => ({ ...f, amount: "", promiseDate: "", comment: "" }));
    } catch (e) {
      setServerError(errorText(e));
    }
  };

  return (
    <form
      className="flex flex-col gap-3 rounded-2xl border border-border bg-card p-4"
      data-testid="bank-payment"
      onSubmit={(e) => {
        e.preventDefault();
        void submit();
      }}
    >
      <h3 className="flex items-center gap-2 text-[15px] font-extrabold">
        <Icon as={Landmark} size="md" />
        {t("payment.title")}
      </h3>
      <FormField
        label={t("payment.amount")}
        required
        error={fieldError(errors.amount)}
        hint={t("payment.amountHint", { amount: formatMoney(balance) })}
      >
        <MoneyInput
          value={form.amount}
          onChange={(amount) => set({ amount })}
          disabled={disabled}
          data-testid="bank-amount"
        />
      </FormField>
      <div className="grid grid-cols-2 gap-2">
        <FormField label={t("payment.date")} required error={fieldError(errors.docDate)}>
          <Input
            type="date"
            max={today}
            value={form.docDate}
            onChange={(e) => set({ docDate: e.target.value })}
            disabled={disabled}
          />
        </FormField>
        <FormField label={t("payment.method")}>
          <Input value={t("payment.bank")} readOnly disabled />
        </FormField>
      </div>
      <FormField label={t("payment.branch")} required error={fieldError(errors.branchId)}>
        <NativeSelect
          value={form.branchId ?? ""}
          onChange={(e) => set({ branchId: e.target.value || null })}
          options={[
            { value: "", label: t("payment.branchPick") },
            ...branches.map((b) => ({ value: b.id, label: b.name })),
          ]}
          disabled={disabled}
          data-testid="bank-branch"
        />
      </FormField>
      <FormField label={t("payment.promiseDate")} optional error={fieldError(errors.promiseDate)}>
        <Input
          type="date"
          min={today}
          value={form.promiseDate}
          onChange={(e) => set({ promiseDate: e.target.value })}
          disabled={disabled}
        />
      </FormField>
      <FormField label={t("payment.comment")} optional>
        <Textarea
          rows={2}
          maxLength={1000}
          value={form.comment}
          onChange={(e) => set({ comment: e.target.value })}
          disabled={disabled}
        />
      </FormField>
      <p className="text-[12px] text-foreground-secondary">{t("payment.note")}</p>
      {serverError ? (
        <Banner tone="destructive" icon={CircleAlert} live="assertive">
          <span data-testid="bank-error">{serverError}</span>
        </Banner>
      ) : null}
      <Button type="submit" disabled={disabled || pending} data-testid="bank-submit">
        {t("payment.submit")}
      </Button>
    </form>
  );
}
