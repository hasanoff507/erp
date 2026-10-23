/**
 * BO-20 — Telegram va bildirishnomalar (07, route /app/settings/telegram; `telegram.link` — own account,
 * `notifications.manage` — alert toggles, daily report time, log). Telegram is linked here only (qaror
 * #56 d): one-time link → «Start» in the bot → the page polls the status (20 #66–#68). Settings are per
 * user (20 #69/#70). Offline: the screen does not open (linking needs the network, 07).
 * useEffect only fires the mount / unmount events (24 §2).
 */
import { useUnit } from "effector-react";
import { CircleCheck, Save, TriangleAlert, WifiOff } from "lucide-react";
import { useEffect } from "react";

import { serverErrorText, useTranslation } from "@shared/i18n";
import { useCan } from "@shared/state/permissions";
import { Banner, Button, EmptyState, Icon, NoPermissionState } from "@shared/ui";

import { PageHeader } from "#/shared/ui/PageHeader.tsx";
import { useOnline } from "#/shared/ui/hooks.ts";

import {
  $dirty,
  $saveError,
  $savedAt,
  $saving,
  draftReset,
  pageMounted,
  pageUnmounted,
  saveRequested,
} from "../../model/index.ts";
import { AccountCard } from "../account/AccountCard.tsx";
import { AlertsCard } from "../alerts/AlertsCard.tsx";
import { DailyReportCard } from "../daily/DailyReportCard.tsx";
import { LogCard } from "../log/LogCard.tsx";

function TelegramPage() {
  const { t } = useTranslation("settings");
  const canLink = useCan({ permission: "telegram.link" });
  const canManage = useCan({ permission: "notifications.manage" });
  const online = useOnline();
  const [mounted, unmounted, dirty, saving, saveError, savedAt, reset, save] = useUnit([
    pageMounted,
    pageUnmounted,
    $dirty,
    $saving,
    $saveError,
    $savedAt,
    draftReset,
    saveRequested,
  ]);

  useEffect(() => {
    if (!canLink && !canManage) return;
    mounted({ canLink, canManage });
    return () => unmounted();
  }, [mounted, unmounted, canLink, canManage]);

  if (!canLink && !canManage) return <NoPermissionState />;

  const actions = canManage ? (
    <>
      {savedAt && !dirty ? (
        <span role="status" className="flex items-center gap-1.5 self-center text-small text-success-strong">
          <Icon as={CircleCheck} size="sm" />
          {t("telegram.saved")}
        </span>
      ) : null}
      <Button variant="secondary" disabled={!dirty || saving} onClick={() => reset()}>
        {t("telegram.cancel")}
      </Button>
      <Button disabled={!dirty || saving || !online} onClick={() => save()}>
        <Icon as={Save} size="sm" />
        {t("telegram.save")}
      </Button>
    </>
  ) : null;

  return (
    <div className="flex flex-col gap-[18px]">
      <PageHeader title={t("telegram.title")} description={t("telegram.description")} actions={actions} />
      {online ? (
        <>
          {saveError ? (
            <Banner tone="destructive" icon={TriangleAlert}>
              {serverErrorText(saveError)}
            </Banner>
          ) : null}
          <div className="grid gap-3.5 xl:grid-cols-2">
            <div className="flex flex-col gap-3.5">
              {canLink ? <AccountCard online={online} /> : null}
              {canManage ? <DailyReportCard online={online} /> : null}
            </div>
            {canManage ? <AlertsCard online={online} /> : null}
          </div>
          {canManage ? <LogCard /> : null}
        </>
      ) : (
        <EmptyState icon={WifiOff} title={t("telegram.offline")} />
      )}
    </div>
  );
}

export const Telegram = {
  route: "settings/telegram",
  titleKey: "settings:telegram.title",
  Page: TelegramPage,
} as const;
