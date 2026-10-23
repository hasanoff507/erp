/** `YYYY-MM` → «Oktyabr 2026» / «Октябрь 2026» (the `finance:vat.months.*` names). */
import { useTranslation } from "@shared/i18n";

const MONTH_KEYS = ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12"] as const;

export function useMonthLabel(): (period: string) => string {
  const { t } = useTranslation("finance");
  return (period: string) => {
    const key = MONTH_KEYS.find((k) => k === period.slice(5, 7));
    if (!key) return period;
    return t("vat.periodMonth", { month: t(`vat.months.${key}`), year: period.slice(0, 4) });
  };
}
