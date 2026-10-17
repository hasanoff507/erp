/**
 * «Ogohlantirishlar» (07 BO-20 `alertToggles`, US-M18-03, QT-M18-06): one switch per event kind,
 * grouped as in the mockup, «N / M yoqilgan»; default — all on. Saved with «Saqlash» (20 #70).
 */
import { useUnit } from "effector-react";

import { useTranslation } from "@shared/i18n";
import { Card, CardTitle, ErrorState, Label, Skeleton, StatusChip, Switch } from "@shared/ui";

import { errorText } from "#/shared/lib/errors.ts";

import {
  $alertGroups,
  $enabled,
  $settingsError,
  $settingsStatus,
  kindToggled,
  settingsReloadRequested,
} from "../../model/index.ts";
import { useKindText } from "../kind-text.ts";

export function AlertsCard({ online }: { online: boolean }) {
  const { t } = useTranslation("settings");
  const kindText = useKindText();
  const [groups, enabled, status, error, toggle, reload] = useUnit([
    $alertGroups,
    $enabled,
    $settingsStatus,
    $settingsError,
    kindToggled,
    settingsReloadRequested,
  ]);

  return (
    <Card className="flex flex-col gap-3.5">
      <div className="flex flex-wrap items-center gap-2">
        <CardTitle className="min-w-0 flex-1">{t("telegram.alerts.title")}</CardTitle>
        {enabled.all > 0 ? (
          <StatusChip tone="primary">
            {t("telegram.alerts.enabled", { on: enabled.on, all: enabled.all })}
          </StatusChip>
        ) : null}
      </div>
      {status === "error" && error ? (
        <ErrorState message={errorText(error)} onRetry={reload} />
      ) : groups.length === 0 ? (
        <Skeleton className="h-40 w-full" />
      ) : (
        groups.map((g) => (
          <section key={g.group} aria-labelledby={`tg-group-${g.group}`} className="flex flex-col gap-2">
            <h3 id={`tg-group-${g.group}`} className="text-overline text-foreground-secondary">
              {t(`telegram.groups.${g.group}`)}
            </h3>
            <ul className="flex flex-col divide-y divide-divider">
              {g.items.map((item) => {
                const text = kindText(item.kind);
                const id = `tg-kind-${item.kind}`;
                return (
                  <li key={item.kind} className="flex items-center gap-3 py-2.5">
                    <span className="flex min-w-0 flex-1 flex-col">
                      <Label htmlFor={id} className="text-[14px] font-semibold">
                        {text.title}
                      </Label>
                      {text.description ? (
                        <span className="text-[12px] text-foreground-secondary">{text.description}</span>
                      ) : null}
                    </span>
                    <Switch
                      id={id}
                      checked={item.enabled}
                      disabled={!online}
                      onCheckedChange={(on) => toggle({ kind: item.kind, enabled: on })}
                    />
                  </li>
                );
              })}
            </ul>
          </section>
        ))
      )}
    </Card>
  );
}
