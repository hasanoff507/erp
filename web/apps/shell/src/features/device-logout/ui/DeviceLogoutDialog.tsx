/**
 * SEC-07 dialog of the back-office logout on a POS device browser — the POS logout texts
 * (pos:login.logout.*): unresolved card payment → refuse; unsynced events → export + «Baribir chiqish».
 */
import { useUnit } from "effector-react";
import { Download, TriangleAlert } from "lucide-react";

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
  Icon,
} from "@shared/ui";

import {
  $deviceLogoutDialog,
  $deviceLogoutError,
  $deviceLogoutPending,
  $exported,
  deviceLogoutConfirmed,
  deviceLogoutDismissed,
  deviceLogoutExportRequested,
} from "../model/index.ts";

export function DeviceLogoutDialog() {
  const { t } = useTranslation("pos");
  const { t: tc } = useTranslation();
  const [dialog, error, pending, exported, confirm, dismiss, exportOutbox] = useUnit([
    $deviceLogoutDialog,
    $deviceLogoutError,
    $deviceLogoutPending,
    $exported,
    deviceLogoutConfirmed,
    deviceLogoutDismissed,
    deviceLogoutExportRequested,
  ]);

  return (
    <Dialog open={dialog !== null} onOpenChange={(open) => (open || pending ? undefined : dismiss())}>
      <DialogContent size="sm" role="alertdialog">
        <DialogHeader>
          <DialogTitle>{t("login.logout.title")}</DialogTitle>
          {dialog?.kind === "blocked_card" ? (
            <DialogDescription>
              {t("login.logout.blockedCard")} {t("login.logout.blockedCardHint")}
            </DialogDescription>
          ) : null}
          {dialog?.kind === "needs_confirm" ? (
            <DialogDescription>
              {t("login.logout.unsynced", { pending: dialog.pending, rejected: dialog.rejected })}{" "}
              {t("login.logout.unsyncedHint")}
            </DialogDescription>
          ) : null}
        </DialogHeader>
        {error ? (
          <Banner tone="destructive" icon={TriangleAlert} live="assertive">
            {tc("errors.internal_error")}
          </Banner>
        ) : null}
        <DialogFooter>
          <Button variant="outline" onClick={() => dismiss()} disabled={pending}>
            {t("login.logout.cancel")}
          </Button>
          {dialog?.kind === "needs_confirm" ? (
            <>
              <Button variant="outline" onClick={() => exportOutbox()} disabled={pending}>
                <Icon as={Download} size="md" />
                {exported ? t("login.logout.exported") : t("login.logout.export")}
              </Button>
              <Button variant="destructive" onClick={() => confirm()} disabled={pending}>
                {t("login.logout.confirm")}
              </Button>
            </>
          ) : null}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
