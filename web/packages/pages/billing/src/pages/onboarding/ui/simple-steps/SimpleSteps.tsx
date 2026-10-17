/**
 * BO-21 ④ opening debts (B4: the table / Excel paste of features/opening-debts → posted openings; optional), ⑤ OFD / e-invoice guidance with
 * the Telegram bot link (BO-20 comes later; `connectNow` only reveals the steps), ⑥ device install —
 * `<InstallGuide embedded />` (the same component as /install, UX-INSTALL).
 */
import { useUnit } from "effector-react";
import { Send, Users } from "lucide-react";

import { useTranslation } from "@shared/i18n";
import { telegramBotLink } from "@shared/lib/runtime-config";
import { $isOnline } from "@shared/state/network";
import { Button, Card, CardTitle, Icon, StatusChip, Switch } from "@shared/ui";

import { InstallGuide } from "#/features/install-guide/ui/InstallGuide.tsx";
import { OpeningDebtsForm } from "#/features/opening-debts/ui/OpeningDebtsForm.tsx";

import {
  $connectNow,
  backClicked,
  connectNowToggled,
  finishClicked,
  nextClicked,
  skipClicked,
} from "../../model/index.ts";
import { StepFooter } from "../footer/StepFooter.tsx";

export function DebtsStep() {
  const { t } = useTranslation("onboarding");
  const [back, skip, next, online] = useUnit([backClicked, skipClicked, nextClicked, $isOnline]);
  return (
    <div className="flex flex-col gap-4">
      <p className="text-[14px] text-foreground-secondary">{t("debts.intro")}</p>
      <Card className="flex flex-col gap-3">
        <div className="flex items-center gap-2">
          <Icon as={Users} size="lg" className="text-primary" />
          <CardTitle className="grow">{t("wizard.headings.debts")}</CardTitle>
          <StatusChip tone="neutral">{t("debts.badge")}</StatusChip>
        </div>
        <OpeningDebtsForm disabled={!online} />
      </Card>
      <StepFooter
        onBack={() => back()}
        onSkip={() => skip()}
        primaryType="button"
        onPrimary={() => next()}
        autoFocusPrimary
      />
    </div>
  );
}

export function OfdStep() {
  const { t } = useTranslation("onboarding");
  const [connectNow, toggle, back, skip, next] = useUnit([
    $connectNow,
    connectNowToggled,
    backClicked,
    skipClicked,
    nextClicked,
  ]);
  const bot = telegramBotLink();
  return (
    <div className="flex flex-col gap-4">
      <p className="text-[14px] text-foreground-secondary">{t("ofd.intro")}</p>
      <Card className="flex flex-col gap-3">
        <label className="flex items-center gap-3">
          <Switch checked={connectNow} onCheckedChange={(v) => toggle(v)} />
          <span className="flex flex-col">
            <span className="text-[15px] font-bold">{t("ofd.connectNow")}</span>
            <span className="text-[12px] text-muted-foreground">{t("ofd.connectLater")}</span>
          </span>
        </label>
        {connectNow ? (
          <div className="flex flex-col gap-2 border-t border-border pt-3">
            <span className="text-[14px] font-bold">{t("ofd.stepsTitle")}</span>
            <ol className="flex list-decimal flex-col gap-1.5 pl-5 text-[14px]">
              <li>{t("ofd.steps.fiscal")}</li>
              <li>{t("ofd.steps.einvoice")}</li>
              <li>{t("ofd.steps.tin")}</li>
            </ol>
          </div>
        ) : null}
      </Card>
      <Card className="flex flex-wrap items-center gap-3">
        <Icon as={Send} size="lg" className="text-info" />
        <div className="flex min-w-0 flex-1 flex-col gap-0.5">
          <span className="text-[15px] font-bold">{t("ofd.telegramTitle")}</span>
          <span className="text-[13px] text-foreground-secondary">
            {bot ? t("ofd.telegramText") : `${t("ofd.telegramText")} ${t("ofd.telegramMissing")}`}
          </span>
        </div>
        {bot ? (
          <Button asChild variant="secondary">
            <a href={bot.href} target="_blank" rel="noreferrer">
              {t("ofd.telegramOpen")} · {bot.label}
            </a>
          </Button>
        ) : null}
      </Card>
      <StepFooter
        onBack={() => back()}
        onSkip={() => skip()}
        primaryType="button"
        onPrimary={() => next()}
        autoFocusPrimary
      />
    </div>
  );
}

export function InstallStep() {
  const { t } = useTranslation("onboarding");
  const [back, skip, finish] = useUnit([backClicked, skipClicked, finishClicked]);
  return (
    <div className="flex flex-col gap-4">
      <InstallGuide embedded />
      <StepFooter
        onBack={() => back()}
        onSkip={() => skip()}
        primaryType="button"
        primaryLabel={t("wizard.finish")}
        onPrimary={() => finish()}
      />
    </div>
  );
}
