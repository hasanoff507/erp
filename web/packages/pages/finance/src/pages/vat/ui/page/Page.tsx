/**
 * BO-07 — QQS ichki hisob-kitobi (07, route /app/tax/vat, `tax.vat.view`). The «QQS ichki hisobi» tab
 * of the «QQS va davlat hisoboti» section (06 §1.9; the neighbouring «Davlat hisoboti bilan solishtirish»
 * tab is BO-10). Bosqich 3 part: period (month or quarter, summed on the client), tax-regime chip,
 * KPI cards from `GET /reports/vat-summary` (20 #1) and the «QQS registri» from `GET /vat-moves` (20 #2).
 * Bosqich 4: the «Soliq hisob-kitobi (ST)» card (tax-settlement/, 20 #8a–#8d). Risky inbound e-invoices and
 * the BO-10 difference banner are later stages (e-invoices, state reports).
 * Offline: view only. useEffect only fires pageMounted (24 §2).
 */
import { useUnit } from "effector-react";
import { Hourglass, Inbox, WifiOff } from "lucide-react";
import { useEffect } from "react";
import { NavLink } from "react-router-dom";

import { serverErrorText, useTranslation } from "@shared/i18n";
import { dayjs } from "@shared/lib/date";
import { formatPercent } from "@shared/lib/format";
import { $isOnline } from "@shared/state/network";
import { Can, useCan } from "@shared/state/permissions";
import {
  Banner,
  Card,
  EmptyState,
  ErrorState,
  FormField,
  NoPermissionState,
  SimpleSelect,
  Skeleton,
  StatusChip,
  cn,
} from "@shared/ui";

import {
  $period,
  $summary,
  $summaryError,
  $summaryStatus,
  $today,
  isEmptySummary,
  isPeriodKey,
  pageMounted,
  periodChanged,
  periodOptions,
  summaryReloadRequested,
} from "../../model/index.ts";
import { SummaryCards } from "../kpis/SummaryCards.tsx";
import { MovesTable } from "../moves/MovesTable.tsx";
import { TaxSettlementCard } from "../../tax-settlement/ui/TaxSettlementCard.tsx";

const MONTH_KEYS = ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12"] as const;

function SectionTabs() {
  const { t } = useTranslation("finance");
  const tab = (active: boolean) =>
    cn(
      "inline-flex h-9 items-center rounded-full px-4 text-[13px] font-bold transition-colors",
      "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
      active
        ? "bg-foreground text-background"
        : "text-foreground-secondary hover:bg-accent hover:text-foreground",
    );
  return (
    <nav aria-label={t("vat.sectionLabel")}>
      <ul className="flex flex-wrap gap-1">
        <li>
          <NavLink to="/app/tax/vat" className={({ isActive }) => tab(isActive)}>
            {t("vat.tabs.internal")}
          </NavLink>
        </li>
        <Can anyOf={["tax.compare.review"]}>
          <li>
            <NavLink to="/app/tax/reconciliation" className={({ isActive }) => tab(isActive)}>
              {t("vat.tabs.reconciliation")}
            </NavLink>
          </li>
        </Can>
      </ul>
    </nav>
  );
}

function VatPage() {
  const { t } = useTranslation("finance");
  const canView = useCan({ permission: "tax.vat.view" });
  const [mounted, onPeriod, reload] = useUnit([pageMounted, periodChanged, summaryReloadRequested]);
  const [today, period, summary, status, error, online] = useUnit([
    $today,
    $period,
    $summary,
    $summaryStatus,
    $summaryError,
    $isOnline,
  ]);

  useEffect(() => {
    if (canView) mounted({ today: dayjs().format("YYYY-MM-DD") });
  }, [mounted, canView]);

  if (!canView || error?.status === 403) return <NoPermissionState />;

  const { months, quarters } = periodOptions(today);
  const monthLabel = (m: string) => {
    const key = MONTH_KEYS.find((k) => k === m.slice(5, 7)) ?? "01";
    return t("vat.periodMonth", { month: t(`vat.months.${key}`), year: m.slice(0, 4) });
  };
  const quarterLabel = (q: string) => t("vat.periodQuarter", { year: q.slice(0, 4), quarter: q.slice(6) });
  const currentMonth = today.slice(0, 7);

  return (
    <div className="flex flex-col gap-[18px]">
      <SectionTabs />
      <p className="text-small text-foreground-secondary">{t("vat.subtitle")}</p>
      {online ? null : (
        <Banner tone="warning" icon={WifiOff}>
          {t("vat.offline")}
        </Banner>
      )}
      <div className="flex flex-wrap items-end gap-3">
        <FormField label={t("vat.period")} className="w-64">
          <SimpleSelect
            options={[
              ...months.map((m) => ({
                value: m,
                label: m === currentMonth ? t("vat.currentMonth", { label: monthLabel(m) }) : monthLabel(m),
              })),
              ...quarters.map((q) => ({ value: q, label: quarterLabel(q) })),
            ]}
            value={period}
            onValueChange={(v) => (isPeriodKey(v) ? onPeriod(v) : undefined)}
          />
        </FormField>
        {summary ? (
          <StatusChip tone="primary">
            {summary.regime === "vat"
              ? t("vat.regime.vat")
              : t("vat.regime.turnover", {
                  rate: summary.turnoverRatePct === null ? "—" : formatPercent(summary.turnoverRatePct),
                })}
          </StatusChip>
        ) : null}
      </div>

      {status === "loading" ? (
        <div className="grid gap-3.5 sm:grid-cols-3" aria-busy="true">
          <Skeleton className="h-28 w-full" />
          <Skeleton className="h-28 w-full" />
          <Skeleton className="h-28 w-full" />
        </div>
      ) : status === "error" && error ? (
        <ErrorState message={serverErrorText(error)} onRetry={reload} />
      ) : summary && isEmptySummary(summary) ? (
        <EmptyState icon={Inbox} title={t("vat.empty.title")} description={t("vat.empty.description")} />
      ) : (
        <>
          {summary?.mixedRegime ? (
            <Banner tone="info" icon={Hourglass}>
              {t("vat.mixedRegime")}
            </Banner>
          ) : null}
          <SummaryCards />
        </>
      )}

      <TaxSettlementCard monthLabel={monthLabel} />

      <Card>
        <MovesTable />
      </Card>
    </div>
  );
}

export const Vat = {
  route: "tax/vat",
  titleKey: "finance:vat.title",
  Page: VatPage,
} as const;
