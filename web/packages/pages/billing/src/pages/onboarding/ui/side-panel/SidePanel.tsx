import { useUnit } from "effector-react";

import { useTranslation } from "@shared/i18n";
import { supportLinks } from "@shared/lib/runtime-config";
import { LogoMark, StepList } from "@shared/ui";

import { $completed, $step, stepEditRequested, stepStates, type StepId } from "../../model/index.ts";

/** BO-21 left ink panel (mockup Bo21Royxat): logo, pitch, step list with states, help block. */
export function SidePanel() {
  const { t } = useTranslation("onboarding");
  const { t: tc } = useTranslation();
  const [step, completed, edit] = useUnit([$step, $completed, stepEditRequested]);
  // 25 §12 support channels from the runtime config (24 §3); unset → plain text only.
  const support = supportLinks();
  const steps = stepStates(step, completed, (id) => ({
    title: t(`wizard.steps.${id}.title`),
    description: t(`wizard.steps.${id}.description`),
  }));

  return (
    <aside className="flex w-full shrink-0 flex-col gap-6 bg-sidebar px-6 py-6 text-sidebar-foreground lg:min-h-dvh lg:w-[400px] lg:px-8 lg:py-7">
      <div className="flex items-center gap-2.5">
        <LogoMark size={38} />
        <div>
          <div className="text-[16px] font-extrabold text-sidebar-accent-foreground">{tc("app.name")}</div>
          <div className="text-[12px] text-sidebar-muted-foreground">{tc("app.tagline")}</div>
        </div>
      </div>
      <div>
        <p className="text-[24px] font-extrabold leading-tight text-sidebar-accent-foreground">
          {t("wizard.heading")}
        </p>
        <p className="mt-2 text-[14px] leading-relaxed">{t("wizard.intro")}</p>
      </div>
      <StepList
        tone="dark"
        label={t("wizard.stepsLabel")}
        steps={steps}
        // Only ① can be reopened, and only before the tenant exists (from ②).
        onStepClick={step === "store" ? (id) => edit(id as StepId) : undefined}
        className="hidden lg:flex"
      />
      <div className="mt-auto hidden rounded-lg bg-sidebar-accent p-3.5 text-[13px] leading-normal lg:block">
        <div className="font-bold text-sidebar-accent-foreground">{t("wizard.help.title")}</div>
        <div>
          {support.telegram ? (
            <>
              <a href={support.telegram.href} target="_blank" rel="noreferrer" className="text-sidebar-ring">
                {t("wizard.help.telegram", { handle: support.telegram.label })}
              </a>
              {" · "}
            </>
          ) : null}
          {support.phone ? (
            <>
              <a href={support.phone.href} className="text-sidebar-ring">
                {support.phone.label}
              </a>
              {" · "}
            </>
          ) : null}
          {t("wizard.help.hours")}
        </div>
      </div>
    </aside>
  );
}
