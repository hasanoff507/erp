/**
 * «Bekor qilish» with a reason — every document cancel of 19 (transfer, count, write-off, purchase
 * order, receipt, supplier return) takes `{reason}` (1…1000 chars). The dialog stays open on error.
 */
import { useState, type ReactNode } from "react";

import { useTranslation } from "@shared/i18n";
import { ConfirmDialog, FormField, Textarea } from "@shared/ui";

import { errorText } from "../lib/errors.ts";

export interface ReasonDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: ReactNode;
  confirmLabel?: string;
  onConfirm: (reason: string) => Promise<unknown>;
}

export function ReasonDialog(props: ReasonDialogProps) {
  return props.open ? <ReasonForm {...props} /> : null;
}

function ReasonForm({ open, onOpenChange, title, description, confirmLabel, onConfirm }: ReasonDialogProps) {
  const { t } = useTranslation("warehouse");
  const [reason, setReason] = useState("");
  const [touched, setTouched] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const empty = reason.trim() === "";

  const confirm = async () => {
    setTouched(true);
    if (empty) throw new Error("reason required");
    setError(null);
    try {
      await onConfirm(reason.trim());
    } catch (e) {
      setError(errorText(e));
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
      confirmLabel={confirmLabel ?? t("actions.cancelDoc")}
      cancelLabel={t("actions.back")}
      onConfirm={confirm}
      error={error}
    >
      <FormField label={t("cancel.reason")} required error={touched && empty ? "validation.required" : null}>
        <Textarea
          value={reason}
          maxLength={1000}
          rows={3}
          onChange={(e) => setReason(e.target.value)}
          onBlur={() => setTouched(true)}
        />
      </FormField>
    </ConfirmDialog>
  );
}
