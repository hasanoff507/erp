import { useUnit } from "effector-react";

import { useTranslation } from "@shared/i18n";
import { StatusChip, StepProgress } from "@shared/ui";

import { LanguageToggle } from "#/shared/ui/LanguageToggle.tsx";

import { $step, STEP_IDS, stepIndex } from "../../model/index.ts";

/** Right panel header: «N-bosqich / 6» + progress, step heading, trial chip, UZ · RU. */
export function Header() {
  const { t } = useTranslation("onboarding");
  const step = useUnit($step);
  return (
    <div className="flex flex-col gap-2.5">
      <div className="flex flex-wrap items-center gap-4">
        <div className="min-w-0 grow">
          <h1 className="text-[26px] font-extrabold leading-tight">{t(`wizard.headings.${step}`)}</h1>
        </div>
        <StatusChip tone="success">{t("wizard.trialChip")}</StatusChip>
        <LanguageToggle />
      </div>
      <StepProgress current={stepIndex(step) + 1} total={STEP_IDS.length} label={t("wizard.progressLabel")} />
    </div>
  );
}
