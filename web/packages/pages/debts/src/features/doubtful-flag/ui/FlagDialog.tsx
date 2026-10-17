/**
 * «Shubhali deb belgilash» (reason required, no posting) and «Belgini olib tashlash» — Owner only (BO-06).
 */
import { useState } from "react";

import { useTranslation } from "@shared/i18n";
import { ConfirmDialog, FormField, Textarea, toast } from "@shared/ui";

import { errorText } from "#/shared/lib/errors.ts";

import { flagDoubtfulFx, unflagDoubtfulFx } from "../model/index.ts";

export interface FlagDialogProps {
  counterparty: { id: string; name: string };
  /** Active flag id → the dialog removes it; null → sets a new flag. */
  flagId: string | null;
  onClose: () => void;
}

export function FlagDialog({ counterparty, flagId, onClose }: FlagDialogProps) {
  const { t } = useTranslation("debts");
  const [reason, setReason] = useState("");
  const [touched, setTouched] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const unflag = flagId !== null;

  const confirm = async () => {
    setTouched(true);
    if (!unflag && !reason.trim()) throw new Error("reason required");
    setError(null);
    try {
      if (flagId) await unflagDoubtfulFx(flagId);
      else await flagDoubtfulFx({ counterpartyId: counterparty.id, reason });
      toast.success(unflag ? t("flag.removed") : t("flag.done"));
      onClose();
    } catch (e) {
      setError(errorText(e));
      throw e;
    }
  };

  return (
    <ConfirmDialog
      open
      onOpenChange={(open) => (open ? undefined : onClose())}
      title={unflag ? t("flag.removeTitle") : t("flag.title")}
      description={
        unflag
          ? t("flag.removeText", { name: counterparty.name })
          : t("flag.text", { name: counterparty.name })
      }
      confirmLabel={unflag ? t("flag.removeConfirm") : t("flag.confirm")}
      cancelLabel={t("actions.cancel")}
      onConfirm={confirm}
      error={error}
    >
      {unflag ? null : (
        <FormField
          label={t("flag.reason")}
          required
          error={touched && !reason.trim() ? "validation.required" : null}
        >
          <Textarea
            rows={3}
            maxLength={1000}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            onBlur={() => setTouched(true)}
            data-testid="flag-reason"
          />
        </FormField>
      )}
    </ConfirmDialog>
  );
}
