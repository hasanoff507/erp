/**
 * BO-03 KPI cards (07, mockup Bo03Ombor): ombor qiymati, kam qoldiq, muddati yaqin partiyalar,
 * yo'ldagi ko'chirishlar. «Barcha filiallar» (consolidated): value and low stock over every branch —
 * lots and transfers are per warehouse.
 */
import { useUnit } from "effector-react";
import { CalendarClock, Package, Truck, TriangleAlert } from "lucide-react";

import { useTranslation } from "@shared/i18n";
import { formatMoney } from "@shared/lib/format";
import { Card, ErrorState, KpiCard, Skeleton } from "@shared/ui";

import { errorText } from "#/shared/lib/errors.ts";

import {
  $expiring,
  $summary,
  $summaryError,
  $transit,
  EXPIRY_DAYS,
  summaryRefreshRequested,
} from "../../model/index.ts";

export function Kpis({ branchName, consolidated }: { branchName: string; consolidated: boolean }) {
  const { t } = useTranslation("warehouse");
  const [summary, summaryError, expiring, transit, retry] = useUnit([
    $summary,
    $summaryError,
    $expiring,
    $transit,
    summaryRefreshRequested,
  ]);
  if (!summary && summaryError) {
    // WEB-06: a failed summary is said so (not an endless skeleton), with «Qayta urinish».
    return (
      <Card className="p-0">
        <ErrorState
          className="py-5"
          title={t("kpi.error")}
          message={errorText(summaryError)}
          onRetry={() => retry()}
        />
      </Card>
    );
  }
  if (!summary) {
    return (
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4" aria-busy="true">
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-[118px] rounded-2xl" />
        ))}
      </div>
    );
  }
  const lots = expiring?.lots ?? [];
  const lotNames = [...new Set(lots.map((l) => l.product_name))].slice(0, 2).join(", ");
  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4" role="group" aria-label={t("kpi.label")}>
      <KpiCard
        label={consolidated ? t("kpi.valueAll") : t("kpi.value", { branch: branchName })}
        value={formatMoney(summary.value, { withCurrency: false })}
        icon={Package}
        tone="primary"
        note={t("kpi.valueNote", { count: summary.positions })}
      />
      <KpiCard
        label={t("kpi.low")}
        value={String(summary.low)}
        icon={TriangleAlert}
        tone="destructive"
        note={t("kpi.lowNote")}
        noteTone={summary.low > 0 ? "destructive" : "neutral"}
      />
      {consolidated ? null : (
        <>
          <KpiCard
            label={t("kpi.expiring")}
            value={String(lots.length)}
            icon={CalendarClock}
            tone="warning"
            note={
              lots.length > 0
                ? t("kpi.expiringNote", { days: EXPIRY_DAYS, names: lotNames })
                : t("kpi.expiringNone", { days: EXPIRY_DAYS })
            }
            noteTone="warning"
          />
          <KpiCard
            label={t("kpi.transit")}
            value={String(transit?.inTransit ?? 0)}
            icon={Truck}
            tone="info"
            note={t("kpi.transitNote", { overdue: transit?.overdue ?? 0, ettn: transit?.waitingEttn ?? 0 })}
            noteTone="info"
          />
        </>
      )}
    </div>
  );
}
