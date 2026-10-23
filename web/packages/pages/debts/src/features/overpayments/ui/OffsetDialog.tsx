/**
 * «Keyingi qarzga hisoblash» (07 BO-06 «Ortiqcha to'lovlar» bloki, `accounting.post`): the excess on Kt 6310
 * is set off against the customer's debt — `POST /ledger-adjustments` Dt 6310 / Kt 4010 (13 §2.14 (b)), no
 * cash moves. Confirmation «{summa} keyingi qarzga hisoblanadi». Amount ≤ the row's unallocated excess; the
 * server also caps it by the 6310 balance and the open receivable (`params.available` is shown).
 */
import { useUnit } from "effector-react";
import { CircleAlert } from "lucide-react";
import { useState } from "react";

import { toApiError } from "@shared/api";
import { useTranslation } from "@shared/i18n";
import { formatMoney } from "@shared/lib/format";
import { isMoney, type Money } from "@shared/lib/money";
import { $activeBranchId, $branches, ALL_BRANCHES } from "@shared/state/session";
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
  SimpleSelect,
  Textarea,
  toast,
} from "@shared/ui";

import { todayIso } from "#/shared/lib/effect.ts";
import { errorText, fieldError } from "#/shared/lib/errors.ts";

import {
  offsetAvailable,
  submitOffsetFx,
  validateOffset,
  type OffsetErrors,
  type OffsetForm,
  type Overpayment,
} from "../model/index.ts";

export interface OffsetDialogProps {
  row: Overpayment;
  customer: string;
  onClose: () => void;
  onDone: () => void;
}

export function OffsetDialog({ row, customer, onClose, onDone }: OffsetDialogProps) {
  const { t } = useTranslation("debts");
  const [pending, branches, activeBranch] = useUnit([submitOffsetFx.pending, $branches, $activeBranchId]);
  const initialBranch =
    activeBranch && activeBranch !== ALL_BRANCHES ? activeBranch : branches.length === 1 ? branches[0]?.id : "";
  const [form, setForm] = useState<OffsetForm>({
    amount: row.unallocated,
    comment: t("overpay.offset.defaultComment"),
    branchId: initialBranch ?? "",
  });
  const [errors, setErrors] = useState<OffsetErrors>({});
  const [serverError, setServerError] = useState<string | null>(null);
  const set = (patch: Partial<OffsetForm>) => setForm((f) => ({ ...f, ...patch }));

  const submit = async () => {
    const found = validateOffset(form, row.unallocated as Money);
    setErrors(found);
    setServerError(null);
    if (Object.keys(found).length > 0) return;
    try {
      const done = await submitOffsetFx({ row, form, today: todayIso() });
      toast.success(t("overpay.offset.done", { number: done.number ?? "" }));
      onDone();
      onClose();
    } catch (e) {
      const error = toApiError(e);
      const available = offsetAvailable(error);
      if (available !== null) {
        setErrors({ amount: t("overpay.offset.available", { amount: formatMoney(available) }) });
        return;
      }
      setServerError(errorText(error));
    }
  };

  return (
    <Dialog open onOpenChange={(open) => (open || pending ? undefined : onClose())}>
      <DialogContent data-testid="offset-dialog">
        <form
          className="flex flex-col gap-4"
          noValidate
          onSubmit={(e) => {
            e.preventDefault();
            void submit();
          }}
        >
          <DialogHeader>
            <DialogTitle>{t("overpay.offset.title")}</DialogTitle>
            <DialogDescription>
              {t("overpay.offset.description", { name: customer, amount: formatMoney(row.unallocated) })}
            </DialogDescription>
          </DialogHeader>
          {branches.length > 1 ? (
            <FormField label={t("overpay.offset.branch")} required error={fieldError(errors.branchId)}>
              <SimpleSelect
                options={branches.map((b) => ({ value: b.id, label: b.name }))}
                value={form.branchId || undefined}
                placeholder={t("overpay.offset.branchPlaceholder")}
                onValueChange={(branchId) => set({ branchId })}
                aria-label={t("overpay.offset.branch")}
              />
            </FormField>
          ) : null}
          <FormField label={t("overpay.offset.amount")} required error={fieldError(errors.amount)}>
            <MoneyInput
              precision={2}
              value={form.amount}
              onChange={(amount) => set({ amount })}
              data-testid="offset-amount"
            />
          </FormField>
          <FormField label={t("overpay.offset.comment")} required error={fieldError(errors.comment)}>
            <Textarea
              rows={2}
              maxLength={1000}
              value={form.comment}
              onChange={(e) => set({ comment: e.target.value })}
              data-testid="offset-comment"
            />
          </FormField>
          <p className="text-[13px] font-semibold" data-testid="offset-confirm">
            {t("overpay.offset.confirm", {
              amount: isMoney(form.amount) ? formatMoney(form.amount) : "—",
            })}
          </p>
          <p className="text-[12px] text-foreground-secondary">{t("overpay.offset.posting")}</p>
          {serverError ? (
            <Banner tone="destructive" icon={CircleAlert} live="assertive">
              <span data-testid="offset-error">{serverError}</span>
            </Banner>
          ) : null}
          <DialogFooter>
            <Button type="button" variant="secondary" onClick={onClose} disabled={pending}>
              {t("actions.cancel")}
            </Button>
            <Button type="submit" disabled={pending} data-testid="offset-submit">
              {t("overpay.offset.submit")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
