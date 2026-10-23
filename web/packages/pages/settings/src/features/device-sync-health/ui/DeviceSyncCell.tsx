import { useTranslation } from "@shared/i18n";
import { formatDateTime } from "@shared/lib/date";
import { StatusChip, type StatusChipProps } from "@shared/ui";

import { deviceSyncHealth, type SyncHealth, type SyncHealthInput } from "../model/index.ts";

const TONE: Record<Exclude<SyncHealth, "none">, NonNullable<StatusChipProps["tone"]>> = {
  ok: "success",
  warning: "warning",
  critical: "destructive",
  never: "neutral",
};

/**
 * «Oxirgi sinxron» cell of BO-11 «Qurilmalar»: the last sync time, a health chip (text, not colour
 * only — 08 §10) and, when events wait, the age of the oldest one (`devices.outbox_oldest_pending_at`).
 */
export function DeviceSyncCell({ device, now }: { device: SyncHealthInput; now?: Date }) {
  const { t } = useTranslation("settings");
  const health = deviceSyncHealth(device, now);
  const pending = device.outbox_pending_count ?? 0;
  return (
    <div className="flex min-w-0 flex-col items-start gap-1">
      <span className="text-[13px]">
        {device.last_sync_at ? formatDateTime(device.last_sync_at) : t("devices.neverSynced")}
      </span>
      {health === "none" ? null : (
        <StatusChip tone={TONE[health]} dot>
          {t(`devices.health.${health}`)}
        </StatusChip>
      )}
      {pending > 0 && device.outbox_oldest_pending_at ? (
        <span className="text-[12px] text-muted-foreground">
          {t("devices.oldestPending", { at: formatDateTime(device.outbox_oldest_pending_at) })}
        </span>
      ) : null}
      {device.last_seen_at && health !== "none" ? (
        <span className="text-[12px] text-muted-foreground">
          {t("devices.lastSeen", { at: formatDateTime(device.last_seen_at) })}
        </span>
      ) : null}
    </div>
  );
}
