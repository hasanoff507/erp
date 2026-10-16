import { useUnit } from "effector-react";

import { useTranslation, type UiLanguage } from "@shared/i18n";
import { formatWeekdayDate } from "@shared/lib/format";
import { $user } from "@shared/state/session";
import { SegmentedControl } from "@shared/ui";

import { $period, DASHBOARD_PERIODS, periodChanged } from "../../model/index.ts";

/** BO-02 greeting (date + «Xayrli kun, {ism}») and the period switch (Bugun / Hafta / Oy). */
export function Header() {
  const { t, i18n } = useTranslation("reports");
  const [user, period, onPeriodChange] = useUnit([$user, $period, periodChanged]);
  const firstName = user?.full_name.trim().split(" ")[0] ?? "";
  const lang: UiLanguage = i18n.resolvedLanguage === "ru" ? "ru" : "uz";

  return (
    <div className="flex flex-wrap items-center gap-2.5">
      <div>
        <p className="text-small text-foreground-secondary">{formatWeekdayDate(new Date(), lang)}</p>
        <p className="text-h1">{t("dashboard.greeting", { name: firstName })}</p>
      </div>
      <div className="grow" />
      <SegmentedControl
        label={t("dashboard.period.label")}
        value={period}
        onChange={onPeriodChange}
        options={DASHBOARD_PERIODS.map((p) => ({ value: p, label: t(`dashboard.period.${p}`) }))}
      />
    </div>
  );
}
