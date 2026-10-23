/**
 * «Bloklash / Kassirni almashtirish» and «Chiqish» (07 POS-01; 16 §12). Used on POS-01 and by the POS
 * shell (status bar cashier menu).
 */
import { CircleAlert, Download, Lock, LogOut } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { useTranslation } from "@shared/i18n";
import { logoutRequested } from "@shared/state/session";
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
  beginLogout,
  defaultLogoutDeps,
  exportFileName,
  performLogout,
  type LogoutDecision,
  type LogoutDeps,
} from "../model/index.ts";

export interface CashierActionsProps {
  onLock: () => void;
  deviceId: string | null;
  loginPath?: string;
  deps?: LogoutDeps;
  /** Fire `cardRecoveryRequested` of #/features/card-payment (features cannot import each other). */
  onCardBlocked?: () => void;
}

function download(name: string, data: unknown) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

export function CashierActions({
  onLock,
  deviceId,
  loginPath = "/pos/login",
  deps = defaultLogoutDeps,
  onCardBlocked,
}: CashierActionsProps) {
  const { t } = useTranslation("pos");
  const navigate = useNavigate();
  const [decision, setDecision] = useState<LogoutDecision | null>(null);
  const [busy, setBusy] = useState(false);
  const [exported, setExported] = useState(false);

  const finish = (d: LogoutDecision) => {
    if (d.kind === "ok") {
      setDecision(null);
      onLock();
      logoutRequested();
      void navigate(loginPath, { replace: true });
    } else setDecision(d);
  };

  const start = async () => {
    setBusy(true);
    try {
      const d = await beginLogout({ ...deps, cardBlocked: onCardBlocked });
      if (d.kind === "ok") finish(d);
      else setDecision(d);
    } finally {
      setBusy(false);
    }
  };

  const confirmUnsynced = async () => {
    setBusy(true);
    try {
      finish(await performLogout(deps, true));
    } finally {
      setBusy(false);
    }
  };

  const exportNow = async () => {
    download(exportFileName(deviceId ?? "device", new Date().toISOString()), await deps.exportOutbox());
    setExported(true);
  };

  return (
    <>
      <div className="flex flex-wrap gap-2">
        <Button variant="secondary" size="pos" onClick={onLock} data-testid="cashier-lock">
          <Icon as={Lock} size="md" />
          {t("login.actions.lock")}
        </Button>
        <Button
          variant="destructive-outline"
          size="pos"
          disabled={busy}
          onClick={() => void start()}
          data-testid="cashier-logout"
        >
          <Icon as={LogOut} size="md" />
          {t("login.actions.logout")}
        </Button>
      </div>
      {decision && decision.kind !== "ok" ? (
        <Dialog open onOpenChange={(open) => (open ? undefined : setDecision(null))}>
          <DialogContent size="sm" data-testid="logout-dialog">
            <DialogHeader>
              <DialogTitle>{t("login.logout.title")}</DialogTitle>
              <DialogDescription>
                {decision.kind === "blocked_card"
                  ? t("login.logout.blockedCard")
                  : t("login.logout.unsynced", { pending: decision.pending, rejected: decision.rejected })}
              </DialogDescription>
            </DialogHeader>
            {decision.kind === "blocked_card" ? (
              <Banner tone="destructive" icon={CircleAlert}>
                {t("login.logout.blockedCardHint")}
              </Banner>
            ) : (
              <Banner tone="warning" icon={CircleAlert}>
                {t("login.logout.unsyncedHint")}
              </Banner>
            )}
            <DialogFooter>
              <Button variant="secondary" size="lg" onClick={() => setDecision(null)}>
                {t("login.logout.cancel")}
              </Button>
              {decision.kind === "confirm_unsynced" ? (
                <>
                  <Button
                    variant="secondary"
                    size="lg"
                    onClick={() => void exportNow()}
                    data-testid="logout-export"
                  >
                    <Icon as={Download} size="md" />
                    {exported ? t("login.logout.exported") : t("login.logout.export")}
                  </Button>
                  <Button
                    variant="destructive"
                    size="lg"
                    disabled={busy}
                    onClick={() => void confirmUnsynced()}
                  >
                    {t("login.logout.confirm")}
                  </Button>
                </>
              ) : null}
            </DialogFooter>
          </DialogContent>
        </Dialog>
      ) : null}
    </>
  );
}
