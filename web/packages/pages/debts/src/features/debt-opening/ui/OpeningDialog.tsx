/**
 * «Boshlang'ich qarz» dialog (BO-06; US-M08-07): for the selected counterparty, or a new one from name + phone
 * (the paper-book row). Amount, due date (optional), document date (≤ today; the posting goes to
 * `go_live_date − 1`, 13 §2.13), comment. Creates and posts in one go.
 */
import { useUnit } from "effector-react";
import { CircleAlert } from "lucide-react";
import { useState } from "react";

import { useTranslation } from "@shared/i18n";
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
  Input,
  MoneyInput,
  PhoneInput,
  Textarea,
  toast,
} from "@shared/ui";

import type { Direction } from "#/entities/debtor/index.ts";
import { todayIso } from "#/shared/lib/effect.ts";
import { errorText, fieldError } from "#/shared/lib/errors.ts";

import {
  submitOpeningFx,
  toOpeningRequest,
  validateOpening,
  type OpeningErrors,
  type OpeningForm,
} from "../model/index.ts";

export interface OpeningDialogProps {
  onClose: () => void;
  direction: Direction;
  counterparty: { id: string; name: string } | null;
  branchId: string | null;
}

export function OpeningDialog({ onClose, direction, counterparty, branchId }: OpeningDialogProps) {
  const { t } = useTranslation("debts");
  const pending = useUnit(submitOpeningFx.pending);
  const today = todayIso();
  const [form, setForm] = useState<OpeningForm>({
    counterpartyId: counterparty?.id ?? null,
    name: "",
    phone: "",
    amount: "",
    dueDate: "",
    docDate: today,
    comment: "",
  });
  const [errors, setErrors] = useState<OpeningErrors>({});
  const [serverError, setServerError] = useState<string | null>(null);
  const set = (patch: Partial<OpeningForm>) => setForm((f) => ({ ...f, ...patch }));

  const submit = async () => {
    const found = validateOpening(form, today, direction);
    setErrors(found);
    setServerError(null);
    if (Object.keys(found).length > 0) return;
    try {
      await submitOpeningFx(toOpeningRequest(form, direction, branchId));
      toast.success(t("opening.done"));
      onClose();
    } catch (e) {
      setServerError(errorText(e));
    }
  };

  return (
    <Dialog open onOpenChange={(open) => (open ? undefined : onClose())}>
      <DialogContent data-testid="opening-dialog">
        <form
          className="flex flex-col gap-4"
          onSubmit={(e) => {
            e.preventDefault();
            void submit();
          }}
        >
          <DialogHeader>
            <DialogTitle>
              {direction === "payable" ? t("opening.titlePayable") : t("opening.title")}
            </DialogTitle>
            <DialogDescription>{t("opening.description")}</DialogDescription>
          </DialogHeader>
          {counterparty ? (
            <FormField label={direction === "payable" ? t("opening.supplier") : t("opening.customer")}>
              <Input value={counterparty.name} readOnly disabled />
            </FormField>
          ) : (
            <div className="grid grid-cols-2 gap-3">
              <FormField label={t("opening.name")} required error={fieldError(errors.name)}>
                <Input
                  value={form.name}
                  maxLength={255}
                  onChange={(e) => set({ name: e.target.value })}
                  data-testid="opening-name"
                  autoFocus
                />
              </FormField>
              <FormField
                label={t("opening.phone")}
                required={direction === "receivable"}
                error={fieldError(errors.phone)}
              >
                <PhoneInput
                  value={form.phone}
                  onChange={(phone) => set({ phone })}
                  data-testid="opening-phone"
                />
              </FormField>
            </div>
          )}
          <FormField label={t("opening.amount")} required error={fieldError(errors.amount)}>
            <MoneyInput
              value={form.amount}
              onChange={(amount) => set({ amount })}
              data-testid="opening-amount"
            />
          </FormField>
          <div className="grid grid-cols-2 gap-3">
            <FormField
              label={t("opening.docDate")}
              error={fieldError(errors.docDate)}
              hint={t("opening.docDateHint")}
            >
              <Input
                type="date"
                max={today}
                value={form.docDate}
                onChange={(e) => set({ docDate: e.target.value })}
              />
            </FormField>
            <FormField label={t("opening.dueDate")} optional error={fieldError(errors.dueDate)}>
              <Input type="date" value={form.dueDate} onChange={(e) => set({ dueDate: e.target.value })} />
            </FormField>
          </div>
          <FormField label={t("opening.comment")} optional>
            <Textarea
              rows={2}
              maxLength={1000}
              value={form.comment}
              onChange={(e) => set({ comment: e.target.value })}
            />
          </FormField>
          {serverError ? (
            <Banner tone="destructive" icon={CircleAlert} live="assertive">
              <span data-testid="opening-error">{serverError}</span>
            </Banner>
          ) : null}
          <DialogFooter>
            <Button type="button" variant="secondary" onClick={onClose}>
              {t("actions.cancel")}
            </Button>
            <Button type="submit" disabled={pending} data-testid="opening-submit">
              {t("opening.submit")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
