/**
 * «Ortiqcha to'lovni qaytarish» (07 BO-06, `accounting.post`): amount (≤ the row's unallocated excess),
 * reason / comment, a cash register with its OPEN shift → `POST /cash-movements` on account 6310
 * (Dt 6310 / Kt 5010). No open shift → the form stays closed with the reason. Over the cash.withdraw limit
 * the server answers 202 (draft + approval request, BO-16).
 */
import { useUnit } from "effector-react";
import { CircleAlert, TriangleAlert } from "lucide-react";
import { useEffect, useState } from "react";

import { toApiError } from "@shared/api";
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
  SimpleSelect,
  Textarea,
  toast,
} from "@shared/ui";

import { todayIso } from "#/shared/lib/effect.ts";
import { errorText, fieldError } from "#/shared/lib/errors.ts";

import {
  openShiftsFx,
  refundFieldErrors,
  submitRefundFx,
  validateRefund,
  type OpenShift,
  type Overpayment,
  type RefundErrors,
  type RefundForm,
} from "../model/index.ts";

export interface RefundDialogProps {
  row: Overpayment;
  customer: string;
  onClose: () => void;
  /** The list changed (posted refund). */
  onDone: () => void;
}

export function RefundDialog({ row, customer, onClose, onDone }: RefundDialogProps) {
  const { t } = useTranslation("debts");
  const pending = useUnit(submitRefundFx.pending);
  const [shifts, setShifts] = useState<OpenShift[] | null>(null);
  const [shiftsError, setShiftsError] = useState<string | null>(null);
  const [form, setForm] = useState<RefundForm>({ amount: row.unallocated, comment: "", shiftId: "" });
  const [errors, setErrors] = useState<RefundErrors>({});
  const [serverError, setServerError] = useState<string | null>(null);
  const set = (patch: Partial<RefundForm>) => setForm((f) => ({ ...f, ...patch }));

  useEffect(() => {
    let alive = true;
    openShiftsFx()
      .then((list) => {
        if (!alive) return;
        setShifts(list);
        const only = list.length === 1 ? list[0] : undefined;
        if (only) setForm((f) => (f.shiftId ? f : { ...f, shiftId: only.shift.id }));
      })
      .catch((e: unknown) => {
        if (!alive) return;
        setShifts([]);
        setShiftsError(errorText(e));
      });
    return () => {
      alive = false;
    };
  }, []);

  const noShift = shifts !== null && shifts.length === 0;

  const submit = async () => {
    const found = validateRefund(form, row.unallocated as Money);
    setErrors(found);
    setServerError(null);
    const shift = shifts?.find((s) => s.shift.id === form.shiftId)?.shift;
    if (Object.keys(found).length > 0 || !shift) return;
    try {
      const done = await submitRefundFx({ row, form, shift, today: todayIso() });
      if (done.status === "draft") toast.info(t("overpay.refund.approval"));
      else toast.success(t("overpay.refund.done"));
      onDone();
      onClose();
    } catch (e) {
      const { fields, rest } = refundFieldErrors(toApiError(e));
      setErrors(fields);
      if (rest) setServerError(errorText(e));
    }
  };

  return (
    <Dialog open onOpenChange={(open) => (open ? undefined : onClose())}>
      <DialogContent data-testid="refund-dialog">
        <form
          className="flex flex-col gap-4"
          onSubmit={(e) => {
            e.preventDefault();
            void submit();
          }}
        >
          <DialogHeader>
            <DialogTitle>{t("overpay.refund.title")}</DialogTitle>
            <DialogDescription>
              {t("overpay.refund.description", {
                name: customer,
                amount: formatMoney(row.unallocated),
              })}
            </DialogDescription>
          </DialogHeader>
          {noShift ? (
            <Banner tone="warning" icon={TriangleAlert}>
              <span data-testid="refund-no-shift">{shiftsError ?? t("overpay.refund.noShift")}</span>
            </Banner>
          ) : null}
          <FormField label={t("overpay.refund.shift")} required error={fieldError(errors.shiftId)}>
            <SimpleSelect
              options={(shifts ?? []).map(({ shift: s, register }) => ({
                value: s.id,
                label: t("overpay.refund.shiftOption", {
                  register: register?.name ?? "—",
                  number: s.shift_no,
                }),
              }))}
              value={form.shiftId || undefined}
              placeholder={t("overpay.refund.shiftPlaceholder")}
              onValueChange={(shiftId) => set({ shiftId })}
              disabled={noShift || shifts === null}
              aria-label={t("overpay.refund.shift")}
            />
          </FormField>
          <FormField label={t("overpay.refund.amount")} required error={fieldError(errors.amount)}>
            <MoneyInput
              precision={2}
              value={form.amount}
              onChange={(amount) => set({ amount })}
              data-testid="refund-amount"
            />
          </FormField>
          <FormField label={t("overpay.refund.comment")} required error={fieldError(errors.comment)}>
            <Textarea
              rows={2}
              maxLength={500}
              value={form.comment}
              onChange={(e) => set({ comment: e.target.value })}
              data-testid="refund-comment"
            />
          </FormField>
          <p className="text-[12px] text-foreground-secondary">{t("overpay.refund.posting")}</p>
          {serverError ? (
            <Banner tone="destructive" icon={CircleAlert} live="assertive">
              <span data-testid="refund-error">{serverError}</span>
            </Banner>
          ) : null}
          <DialogFooter>
            <Button type="button" variant="secondary" onClick={onClose}>
              {t("actions.cancel")}
            </Button>
            <Button
              type="submit"
              disabled={pending || noShift || shifts === null}
              data-testid="refund-submit"
            >
              {t("overpay.refund.submit")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
