/**
 * «Qarzni kechish» (BO-06; Owner): amount (≤ current debt), reason (required), account (9430 other expenses —
 * default, or 4910 doubtful-debt reserve), tax basis, comment; the warning «Bu amal provodka yaratadi».
 */
import { useUnit } from "effector-react";
import { CircleAlert, TriangleAlert } from "lucide-react";
import { useState } from "react";

import { useTranslation } from "@shared/i18n";
import { formatMoney } from "@shared/lib/format";
import type { Money } from "@shared/lib/money";
import {
  Banner,
  Button,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  FormField,
  MoneyInput,
  NativeSelect,
  Textarea,
  toast,
} from "@shared/ui";

import { errorText, fieldError } from "#/shared/lib/errors.ts";

import {
  ACCOUNT_CHOICES,
  TAX_BASES,
  submitWriteoffFx,
  validateWriteoff,
  type AccountChoice,
  type TaxBasis,
  type WriteoffErrors,
  type WriteoffForm,
} from "../model/index.ts";

export interface WriteoffDialogProps {
  counterparty: { id: string; name: string };
  balance: Money;
  branchId: string | null;
  onClose: () => void;
}

export function WriteoffDialog({ counterparty, balance, branchId, onClose }: WriteoffDialogProps) {
  const { t } = useTranslation("debts");
  const pending = useUnit(submitWriteoffFx.pending);
  const [form, setForm] = useState<WriteoffForm>({
    amount: balance,
    reason: "",
    accountChoice: "9430",
    taxBasis: "none",
    comment: "",
  });
  const [errors, setErrors] = useState<WriteoffErrors>({});
  const [serverError, setServerError] = useState<string | null>(null);
  const set = (patch: Partial<WriteoffForm>) => setForm((f) => ({ ...f, ...patch }));

  const submit = async () => {
    const found = validateWriteoff(form, balance);
    setErrors(found);
    setServerError(null);
    if (Object.keys(found).length > 0) return;
    try {
      await submitWriteoffFx({ counterpartyId: counterparty.id, branchId, form });
      toast.success(t("writeoff.done"));
      onClose();
    } catch (e) {
      setServerError(errorText(e));
    }
  };

  return (
    <Dialog open onOpenChange={(open) => (open ? undefined : onClose())}>
      <DialogContent data-testid="writeoff-dialog">
        <form
          className="flex flex-col gap-4"
          onSubmit={(e) => {
            e.preventDefault();
            void submit();
          }}
        >
          <DialogHeader>
            <DialogTitle>{t("writeoff.title")}</DialogTitle>
            <DialogDescription>
              {t("writeoff.description", { name: counterparty.name, amount: formatMoney(balance) })}
            </DialogDescription>
          </DialogHeader>
          <FormField label={t("writeoff.amount")} required error={fieldError(errors.amount)}>
            <MoneyInput
              value={form.amount}
              onChange={(amount) => set({ amount })}
              data-testid="writeoff-amount"
            />
          </FormField>
          <FormField label={t("writeoff.reason")} required error={fieldError(errors.reason)}>
            <Textarea
              rows={2}
              maxLength={1000}
              value={form.reason}
              onChange={(e) => set({ reason: e.target.value })}
              data-testid="writeoff-reason"
            />
          </FormField>
          <div className="grid grid-cols-2 gap-3">
            <FormField label={t("writeoff.account")}>
              <NativeSelect
                value={form.accountChoice}
                onChange={(e) => set({ accountChoice: e.target.value as AccountChoice })}
                options={ACCOUNT_CHOICES.map((a) => ({ value: a, label: t(`writeoff.accounts.${a}`) }))}
              />
            </FormField>
            <FormField label={t("writeoff.taxBasis")}>
              <NativeSelect
                value={form.taxBasis}
                onChange={(e) => set({ taxBasis: e.target.value as TaxBasis })}
                options={TAX_BASES.map((b) => ({ value: b, label: t(`writeoff.bases.${b}`) }))}
              />
            </FormField>
          </div>
          <FormField label={t("writeoff.comment")} optional>
            <Textarea
              rows={2}
              maxLength={1000}
              value={form.comment}
              onChange={(e) => set({ comment: e.target.value })}
            />
          </FormField>
          <Banner tone="warning" icon={TriangleAlert}>
            {t("writeoff.posting")}
          </Banner>
          {serverError ? (
            <Banner tone="destructive" icon={CircleAlert} live="assertive">
              <span data-testid="writeoff-error">{serverError}</span>
            </Banner>
          ) : null}
          <DialogFooter>
            <Button type="button" variant="secondary" onClick={onClose}>
              {t("actions.cancel")}
            </Button>
            <Button type="submit" variant="destructive" disabled={pending} data-testid="writeoff-submit">
              {t("writeoff.submit")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
