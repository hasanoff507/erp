/**
 * «Kunlik hisobot» (07 BO-20 `dailyReportTime`, US-M18-02): on/off, the time (20:00 / 21:00 / 22:00 /
 * 23:00, Toshkent vaqti; «Smenalar yopilmagan bo'lsa ham shu vaqtgacha bo'lgan savdo yuboriladi») and
 * a sample of the message (savdo, cheklar, o'rtacha chek, to'lov usullari, kecha bilan farq, «Diqqat»).
 */
import { useUnit } from "effector-react";

import { useTranslation } from "@shared/i18n";
import { Card, CardTitle, FormField, Label, SimpleSelect, Switch } from "@shared/ui";

import {
  $draft,
  DAILY_REPORT,
  DEFAULT_DAILY_TIME,
  dailyTimeChanged,
  kindToggled,
  timeOptions,
} from "../../model/index.ts";

const SAMPLE_LINES = ["sales", "receipts", "avg", "methods", "change"] as const;

export function DailyReportCard({ online }: { online: boolean }) {
  const { t } = useTranslation("settings");
  const [draft, toggle, onTime] = useUnit([$draft, kindToggled, dailyTimeChanged]);
  const daily = draft.find((i) => i.kind === DAILY_REPORT);
  if (!daily) return null;
  const time = daily.time ?? DEFAULT_DAILY_TIME;

  return (
    <Card className="flex flex-col gap-3.5">
      <CardTitle>{t("telegram.daily.title")}</CardTitle>
      <div className="flex items-center gap-3">
        <span className="flex min-w-0 flex-1 flex-col">
          <Label htmlFor="tg-daily" className="text-[14px] font-semibold">
            {t("telegram.daily.toggle")}
          </Label>
          <span className="text-[12px] text-foreground-secondary">{t("telegram.daily.toggleHint")}</span>
        </span>
        <Switch
          id="tg-daily"
          checked={daily.enabled}
          disabled={!online}
          onCheckedChange={(on) => toggle({ kind: DAILY_REPORT, enabled: on })}
        />
      </div>
      <FormField label={t("telegram.daily.time")} hint={t("telegram.daily.timeHint")} className="w-56">
        <SimpleSelect
          options={timeOptions(daily.time).map((v) => ({ value: v, label: v }))}
          value={time}
          disabled={!online || !daily.enabled}
          onValueChange={onTime}
        />
      </FormField>
      <section
        aria-label={t("telegram.daily.preview")}
        className="flex flex-col gap-1.5 rounded-xl border border-border bg-muted p-4 text-[13px]"
      >
        <h3 className="text-[13px] font-bold">{t("telegram.daily.preview")}</h3>
        <p className="font-semibold">{t("telegram.daily.sample.head")}</p>
        {SAMPLE_LINES.map((k) => (
          <p key={k}>{t(`telegram.daily.sample.${k}`)}</p>
        ))}
        <p className="text-warning-strong">{t("telegram.daily.sample.attention")}</p>
        <p className="text-right text-[12px] text-muted-foreground">{time}</p>
      </section>
    </Card>
  );
}
