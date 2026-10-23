/**
 * BO-02 body — layout per design/canvas/project/Bo02Dashboard.dc.html; data from
 * `GET /reports/dashboard` (KPIs, top-5, alerts, per-branch figures) and `GET /reports/sales` (7 days).
 * States (07): loading — skeleton cards; error — «Qayta urinish»; offline — «Oxirgi yangilanish: N
 * daqiqa oldin»; `data_complete=false` — «faqat sinxronlangan ma'lumot» (QT-M12-04).
 */
import { useUnit } from "effector-react";
import { BellRing, CloudOff, Sparkles, WifiOff } from "lucide-react";

import { serverErrorText, useTranslation } from "@shared/i18n";
import { $isOnline } from "@shared/state/network";
import { Can } from "@shared/state/permissions";
import { Banner, Button, Card, CardTitle, EmptyState, ErrorState, Icon, Input, Skeleton } from "@shared/ui";

import { AlertList } from "#/entities/alert/index.ts";

import {
  $dashboard,
  $error,
  $loadedAt,
  $period,
  $status,
  minutesSince,
  reloadRequested,
} from "../../model/index.ts";
import { BranchTable } from "../branches/BranchTable.tsx";
import { WeekChart } from "../chart/WeekChart.tsx";
import { Kpis } from "../kpis/Kpis.tsx";
import { TopProducts } from "../top/TopProducts.tsx";

function AiPanel() {
  const { t } = useTranslation("reports");
  return (
    <Can permission="ai.chat.use">
      <section className="flex min-w-0 flex-[1_1_420px] flex-col gap-3 rounded-2xl bg-sidebar p-5 text-sidebar-accent-foreground">
        <div className="flex items-center gap-2">
          <Icon as={Sparkles} size="lg" className="text-sidebar-ring" />
          <h2 className="text-h2 font-extrabold">{t("dashboard.ai.title")}</h2>
        </div>
        <p className="text-[14px] leading-relaxed text-sidebar-foreground">{t("dashboard.ai.pending")}</p>
        <div className="mt-auto flex gap-2">
          <Input
            aria-label={t("dashboard.ai.placeholder")}
            placeholder={t("dashboard.ai.placeholder")}
            disabled
            className="border-sidebar-border bg-sidebar-accent text-sidebar-accent-foreground placeholder:text-sidebar-muted-foreground"
          />
          <Button disabled>{t("dashboard.ai.ask")}</Button>
        </div>
      </section>
    </Can>
  );
}

export function Main() {
  const { t } = useTranslation("reports");
  const [data, status, error, loadedAt, period, online, reload] = useUnit([
    $dashboard,
    $status,
    $error,
    $loadedAt,
    $period,
    $isOnline,
    reloadRequested,
  ]);

  const offlineBanner = online ? null : (
    <Banner tone="warning" icon={WifiOff}>
      {loadedAt
        ? t("dashboard.offline", { minutes: minutesSince(loadedAt, new Date()) })
        : t("dashboard.offlineNoData")}
    </Banner>
  );

  if (!data) {
    if (status === "error" && error) {
      return (
        <>
          {offlineBanner}
          <Card className="p-0">
            <ErrorState title={t("dashboard.error")} message={serverErrorText(error)} onRetry={reload} />
          </Card>
        </>
      );
    }
    return (
      <>
        {offlineBanner}
        <div className="grid grid-cols-[repeat(auto-fit,minmax(210px,1fr))] gap-3.5" aria-busy="true">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-[118px] rounded-2xl" />
          ))}
        </div>
        <Skeleton className="h-[300px] rounded-2xl" />
      </>
    );
  }

  return (
    <>
      {offlineBanner}
      {data.data_complete ? null : (
        <Banner tone="warning" icon={CloudOff}>
          {t("incomplete", { count: data.unsynced_devices })}
        </Banner>
      )}
      <Kpis data={data} period={period} />

      <div className="flex flex-wrap gap-3.5">
        <WeekChart />
        <Card className="flex min-w-0 flex-[1_1_320px] flex-col gap-2.5">
          <CardTitle>{t("dashboard.alerts.title")}</CardTitle>
          {data.alerts.length === 0 ? (
            <EmptyState icon={BellRing} title={t("dashboard.alerts.empty")} />
          ) : (
            <AlertList alerts={data.alerts} label={t("dashboard.alerts.title")} />
          )}
        </Card>
      </div>

      {data.by_branch.length > 1 ? <BranchTable data={data} /> : null}

      <div className="flex flex-wrap gap-3.5">
        <TopProducts items={data.top_products} />
        <AiPanel />
      </div>
    </>
  );
}
