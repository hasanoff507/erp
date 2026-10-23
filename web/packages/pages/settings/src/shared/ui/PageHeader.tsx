import { CloudOff, Hourglass } from "lucide-react";
import type { ReactNode } from "react";

import { useUnit } from "effector-react";

import { useTranslation } from "@shared/i18n";
import { $isOnline } from "@shared/state/network";
import { Banner, Card, StatusChip } from "@shared/ui";

import { SettingsNav } from "./SettingsNav.tsx";

export interface PageHeaderProps {
  title: string;
  description: string;
  actions?: ReactNode;
}

/** Settings screen head (mockups Bo11/Bo12/Bo14): title + hint + actions, the settings tabs below. */
export function PageHeader({ title, description, actions }: PageHeaderProps) {
  const { t } = useTranslation("settings");
  const online = useUnit($isOnline);
  return (
    <div className="flex flex-col gap-3.5">
      <div className="flex flex-wrap items-start gap-3">
        <div className="min-w-0 flex-1">
          <h2 className="text-h1">{title}</h2>
          <p className="mt-1 text-small text-foreground-secondary">{description}</p>
        </div>
        {actions ? <div className="flex flex-wrap gap-2">{actions}</div> : null}
      </div>
      <SettingsNav />
      {online ? null : (
        <Banner tone="warning" icon={CloudOff}>
          {t("offline.readOnly")}
        </Banner>
      )}
    </div>
  );
}

/** A 07 section that belongs to a later stage: visible, disabled, with an explicit note. */
export function NextStageCard({ title, description }: { title: string; description: string }) {
  const { t } = useTranslation("settings");
  return (
    <Card className="flex flex-col gap-2 opacity-80" aria-disabled="true">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="text-[15px] font-bold">{title}</h3>
        <StatusChip tone="neutral" icon={Hourglass}>
          {t("nextStage.chip")}
        </StatusChip>
      </div>
      <p className="text-small text-foreground-secondary">{description}</p>
    </Card>
  );
}
