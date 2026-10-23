/**
 * Topbar bell (06 §1.9, WEB-12): count badge + popover with the alert list (each alert links to its
 * screen — the list component is BO-02's own, exported by @pages/reports). useEffect only fires the
 * mount / unmount events (24 §2).
 */
import { useUnit } from "effector-react";
import { Bell, BellRing } from "lucide-react";
import { useEffect, useState } from "react";

import { AlertList } from "@pages/reports";
import { useTranslation } from "@shared/i18n";
import { Button, Icon, Popover, PopoverContent, PopoverTrigger, Skeleton, cn } from "@shared/ui";

import {
  $alerts,
  $alertsError,
  bellBadge,
  bellMounted,
  bellOpened,
  bellTone,
  bellUnmounted,
} from "../model/index.ts";

const BADGE = {
  destructive: "bg-destructive text-destructive-foreground",
  warning: "bg-warning text-warning-foreground",
  info: "bg-info text-info-foreground",
} as const;

export function NotificationsBell() {
  const { t } = useTranslation();
  const [alerts, error, mounted, unmounted, opened] = useUnit([
    $alerts,
    $alertsError,
    bellMounted,
    bellUnmounted,
    bellOpened,
  ]);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    mounted();
    return () => unmounted();
  }, [mounted, unmounted]);

  const badge = bellBadge(alerts);
  const tone = bellTone(alerts);
  const label = badge
    ? t("topbar.notificationsCount", { count: alerts?.length ?? 0 })
    : t("topbar.notifications");

  return (
    <Popover
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (next) opened();
      }}
    >
      <PopoverTrigger asChild>
        <Button variant="outline" size="icon" className="relative h-[42px] w-[42px]" aria-label={label}>
          <Icon as={Bell} size="lg" />
          {badge && tone ? (
            <span
              aria-hidden="true"
              className={cn(
                "absolute -right-1.5 -top-1.5 flex h-5 min-w-5 items-center justify-center rounded-full px-1 text-[11px] font-extrabold",
                BADGE[tone],
              )}
              data-testid="bell-badge"
            >
              {badge}
            </span>
          ) : null}
        </Button>
      </PopoverTrigger>
      <PopoverContent
        align="end"
        className="w-[360px] max-w-[calc(100vw-2rem)]"
        aria-label={t("topbar.notifications")}
      >
        <div className="flex flex-col gap-2.5">
          <p className="text-[14px] font-bold">{t("notificationsPanel.title")}</p>
          {alerts === null ? (
            error ? (
              <p className="text-small text-destructive-strong">{t("notificationsPanel.error")}</p>
            ) : (
              <Skeleton className="h-20 w-full" />
            )
          ) : alerts.length === 0 ? (
            <div className="flex flex-col items-center gap-2 py-3 text-center">
              <Icon as={BellRing} size="lg" className="text-muted-foreground" />
              <p className="text-small text-foreground-secondary">{t("notificationsPanel.empty")}</p>
            </div>
          ) : (
            <AlertList
              alerts={alerts}
              dense
              label={t("notificationsPanel.title")}
              onNavigate={() => setOpen(false)}
            />
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}
