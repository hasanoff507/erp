/** A confirm dialog with a mandatory reason (07 BO-15: «Rad etish», «Bekor qilish» — sabab majburiy). */
import { useState } from "react";

import { useTranslation } from "@shared/i18n";
import { ConfirmDialog, FormField, Textarea } from "@shared/ui";

export interface ReasonDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  confirmLabel: string;
  pending: boolean;
  onSubmit: (reason: string) => void;
}

export function ReasonDialog({
  open,
  onOpenChange,
  title,
  confirmLabel,
  pending,
  onSubmit,
}: ReasonDialogProps) {
  const { t } = useTranslation("edocs");
  const [reason, setReason] = useState("");
  const [touched, setTouched] = useState(false);
  const empty = reason.trim().length === 0;
  return (
    <ConfirmDialog
      open={open}
      onOpenChange={(next) => {
        if (!next) {
          setReason("");
          setTouched(false);
        }
        onOpenChange(next);
      }}
      title={title}
      confirmLabel={confirmLabel}
      tone="destructive"
      pending={pending}
      onConfirm={() => {
        setTouched(true);
        if (empty) return;
        onSubmit(reason.trim());
        setReason("");
        setTouched(false);
        onOpenChange(false);
      }}
    >
      <FormField label={t("reason.label")} required error={touched && empty ? t("reason.required") : null}>
        <Textarea value={reason} maxLength={1000} onChange={(e) => setReason(e.target.value)} />
      </FormField>
    </ConfirmDialog>
  );
}
