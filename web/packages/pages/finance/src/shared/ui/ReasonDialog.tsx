/**
 * «Bekor qilish» with a required reason (BO-17: 3–500, BO-24: 10–500, ST / supplier payment: 1–1000).
 * The dialog stays open on a server error and shows it.
 */
import { useState, type ReactNode } from "react";

import { toApiError } from "@shared/api";
import { serverErrorText, useTranslation } from "@shared/i18n";
import { ConfirmDialog, FormField, Textarea, withParams } from "@shared/ui";

export interface ReasonDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: ReactNode;
  confirmLabel?: string;
  minLength?: number;
  maxLength?: number;
  onConfirm: (reason: string) => Promise<unknown>;
}

export function reasonProblem(reason: string, min: number, max: number): string | null {
  const v = reason.trim();
  if (v === "") return "validation.required";
  if (v.length < min) return withParams("validation.min_length", { min });
  if (v.length > max) return withParams("validation.max_length", { max });
  return null;
}

export function ReasonDialog(props: ReasonDialogProps) {
  return props.open ? <ReasonForm {...props} /> : null;
}

function ReasonForm({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel,
  minLength = 1,
  maxLength = 1000,
  onConfirm,
}: ReasonDialogProps) {
  const { t } = useTranslation("finance");
  const [reason, setReason] = useState("");
  const [touched, setTouched] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const problem = reasonProblem(reason, minLength, maxLength);

  const confirm = async () => {
    setTouched(true);
    if (problem) throw new Error("invalid reason");
    setError(null);
    try {
      await onConfirm(reason.trim());
    } catch (e) {
      setError(serverErrorText(toApiError(e)));
      throw e;
    }
  };

  return (
    <ConfirmDialog
      open={open}
      onOpenChange={onOpenChange}
      title={title}
      description={description}
      tone="destructive"
      confirmLabel={confirmLabel ?? t("shared.cancelDoc")}
      cancelLabel={t("shared.back")}
      onConfirm={confirm}
      error={error}
    >
      <FormField label={t("shared.cancelReason")} required error={touched ? problem : null}>
        <Textarea
          value={reason}
          maxLength={maxLength}
          rows={3}
          data-testid="cancel-reason"
          onChange={(e) => setReason(e.target.value)}
          onBlur={() => setTouched(true)}
        />
      </FormField>
    </ConfirmDialog>
  );
}
