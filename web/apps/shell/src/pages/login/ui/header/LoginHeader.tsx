import { useTranslation } from "@shared/i18n";
import { LogoMark } from "@shared/ui";

import { LanguageSwitcher } from "#/features/language-switcher/index.ts";

/** BO-01 header: 38px logo tile, «ERP» + tagline, «UZ · RU» on the right (mockup Bo01Kirish). */
export function LoginHeader() {
  const { t } = useTranslation();
  return (
    <div className="flex items-center gap-2.5">
      <LogoMark size={38} />
      <div>
        <div className="text-[16px] font-extrabold">{t("app.name")}</div>
        <div className="text-[12px] text-foreground-secondary">{t("app.tagline")}</div>
      </div>
      <div className="grow" />
      <LanguageSwitcher />
    </div>
  );
}
