/** «Savdo — oxirgi 7 kun» (07 BO-02): column chart in mln so'm, today's column highlighted. */
import { useUnit } from "effector-react";

import { useTranslation, type UiLanguage } from "@shared/i18n";
import { dayjs } from "@shared/lib/date";
import { formatMoney } from "@shared/lib/format";
import { Card, CardTitle, Skeleton } from "@shared/ui";

import { millions } from "#/shared/lib/chart.ts";
import { BarChart } from "#/shared/ui/BarChart.tsx";

import { $today, $week, $weekError, dayBars } from "../../model/index.ts";

const WEEKDAYS: Record<UiLanguage, readonly string[]> = {
  uz: ["Ya", "Du", "Se", "Ch", "Pa", "Ju", "Sh"],
  ru: ["Вс", "Пн", "Вт", "Ср", "Чт", "Пт", "Сб"],
};

export function WeekChart() {
  const { t, i18n } = useTranslation("reports");
  const [week, error, today] = useUnit([$week, $weekError, $today]);
  const lang: UiLanguage = i18n.resolvedLanguage === "ru" ? "ru" : "uz";
  const weekday = (iso: string) => WEEKDAYS[lang][dayjs(iso).day()] ?? iso;

  return (
    <Card className="min-w-0 flex-[2_1_520px]">
      <div className="mb-4 flex items-baseline justify-between">
        <CardTitle>{t("dashboard.salesChart.title")}</CardTitle>
        <span className="text-small text-muted-foreground">{t("dashboard.salesChart.unit")}</span>
      </div>
      {week ? (
        <BarChart
          label={t("dashboard.salesChart.title")}
          bars={dayBars(week, today, weekday)}
          formatValue={millions}
          formatFull={(v) => formatMoney(v)}
        />
      ) : error ? (
        <p className="flex h-[230px] items-center justify-center text-small text-muted-foreground">
          {t("dashboard.salesChart.error")}
        </p>
      ) : (
        <Skeleton className="h-[260px] w-full" />
      )}
    </Card>
  );
}
