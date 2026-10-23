import { useUnit } from "effector-react";
import { useState } from "react";

import { useTranslation } from "@shared/i18n";
import { ConfirmDialog, toast } from "@shared/ui";

import { errorText } from "#/shared/lib/errors.ts";

import { resetPasswordFx, resetPinFx, staffName, updateStaffFx, type Staff } from "../../model/index.ts";

export type StaffActionKind = "block" | "unblock" | "resetPassword" | "resetPin";

export interface PendingStaffAction {
  kind: StaffActionKind;
  staff: Staff;
}

/**
 * Confirmation for the staff row actions (07 BO-11): block «Xodimni bloklaysizmi?» (sessions end at
 * once), unblock, password reset and PIN reset. The reset code goes to the Telegram bot first, SMS
 * as a fallback (qaror #34); a password/PIN is never shown or sent in clear text.
 */
export function StaffActionDialog({
  action,
  onClose,
}: {
  action: PendingStaffAction | null;
  onClose: () => void;
}) {
  const { t } = useTranslation("settings");
  const [update, resetPassword, resetPin] = useUnit([updateStaffFx, resetPasswordFx, resetPinFx]);
  const [error, setError] = useState<string | null>(null);

  if (!action) return null;
  const { kind, staff } = action;

  const run = async () => {
    setError(null);
    try {
      if (kind === "block" || kind === "unblock") {
        const result = await update({
          userId: staff.user_id,
          status: kind === "block" ? "blocked" : "active",
        });
        toast.success(
          kind === "block" ? t("users.actions.blocked") : t("users.actions.unblocked"),
          kind === "block" ? t("users.actions.sessionsEnded", { count: result.sessions_revoked }) : undefined,
        );
      } else {
        const result = await (kind === "resetPassword" ? resetPassword : resetPin)(staff.user_id);
        toast.success(
          kind === "resetPassword" ? t("users.actions.passwordResetDone") : t("users.actions.pinResetDone"),
          t(`users.invite.sentVia.${result.channel_used}`),
        );
      }
    } catch (e) {
      setError(errorText(e));
      throw e;
    }
  };

  return (
    <ConfirmDialog
      open
      onOpenChange={(open) => {
        if (!open) {
          setError(null);
          onClose();
        }
      }}
      title={t(`users.confirm.${kind}.title`)}
      description={t(`users.confirm.${kind}.description`, { name: staffName(staff) })}
      confirmLabel={t(`users.confirm.${kind}.confirm`)}
      tone={kind === "block" ? "destructive" : "default"}
      onConfirm={run}
      error={error}
    />
  );
}
