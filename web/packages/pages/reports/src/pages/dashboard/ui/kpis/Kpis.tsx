/**
 * BO-02 KPI cards (07, mockup Bo02Dashboard): savdo (kecha / o'tgan davr bilan), cheklar (o'rtacha
 * chek), mijozlar qarzi (qarzdorlar, muddati o'tganlar), ombor qiymati (kam qolgan tovarlar) and
 * «Sof foyda» (US-M15-03: tushum − tannarx − xarajatlar; `reports.finance.view`). A card the user has
 * no right to (the API sends `null`) is not shown; each card opens its screen.
 */
import { ChartColumn, Package, Receipt, TrendingUp, Users } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { useTranslation } from "@shared/i18n";
import { formatMoney, formatPercent } from "@shared/lib/format";
import { KpiCard, type KpiCardProps } from "@shared/ui";

import { percentChange } from "#/shared/lib/chart.ts";

import type { Dashboard, DashboardPeriod } from "../../model/index.ts";

function CardLink({ to, children }: { to: string; children: ReactNode }) {
  return (
    <Link
      to={to}
      className="rounded-2xl transition-shadow hover:shadow-dialog focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      {children}
    </Link>
  );
}

type Card = KpiCardProps & { key: string; to: string };

export function Kpis({ data, period }: { data: Dashboard; period: DashboardPeriod }) {
  const { t } = useTranslation("reports");
  const change = percentChange(data.total_sales, data.previous_total_sales);
  const up = change !== null && !change.startsWith("-");
  const salesNote =
    change === null
      ? t(`dashboard.kpi.noPrevious.${period}`)
      : t(`dashboard.kpi.change.${period}`, {
          sign: up ? "↑" : "↓",
          value: formatPercent(change.replace("-", "")),
        });

  const cards: Card[] = [
    {
      key: "sales",
      to: "/app/reports?report=daily-sales",
      label: t(`dashboard.kpi.sales.${period}`),
      value: formatMoney(data.total_sales),
      icon: ChartColumn,
      tone: "primary",
      note: salesNote,
      noteTone: change === null ? "neutral" : up ? "success" : "destructive",
    },
    {
      key: "receipts",
      to: "/app/reports?report=daily-sales",
      label: t("dashboard.kpi.receipts"),
      value: String(data.receipt_count),
      icon: Receipt,
      tone: "info",
      note: t("dashboard.kpi.avgReceipt", { amount: formatMoney(data.avg_receipt) }),
    },
  ];
  if (data.receivables) {
    cards.push({
      key: "debt",
      to: "/app/debts",
      label: t("dashboard.kpi.customerDebt"),
      value: formatMoney(data.receivables.total),
      icon: Users,
      tone: "warning",
      note: t("dashboard.kpi.debtNote", {
        debtors: data.receivables.debtors_count,
        overdue: data.receivables.overdue_count,
      }),
      noteTone: data.receivables.overdue_count > 0 ? "warning" : "neutral",
    });
  }
  if (data.stock) {
    cards.push({
      key: "stock",
      to: "/app/warehouse/stock",
      label: t("dashboard.kpi.stockValue"),
      value: formatMoney(data.stock.value),
      icon: Package,
      tone: "destructive",
      note: t("dashboard.kpi.stockNote", { low: data.stock.low_stock_count }),
      noteTone: data.stock.low_stock_count > 0 ? "destructive" : "neutral",
    });
  }
  if (data.net_profit !== null) {
    cards.push({
      key: "profit",
      to: "/app/reports?report=profit-and-loss",
      label: t("dashboard.kpi.netProfit"),
      value: formatMoney(data.net_profit),
      icon: TrendingUp,
      tone: "success",
      note: t("dashboard.kpi.netProfitNote"),
    });
  }

  return (
    <div
      role="group"
      aria-label={t("dashboard.kpi.label")}
      className="grid grid-cols-[repeat(auto-fit,minmax(210px,1fr))] gap-3.5"
    >
      {cards.map(({ key, to, ...card }) => (
        <CardLink key={key} to={to}>
          <KpiCard {...card} className="h-full" />
        </CardLink>
      ))}
    </div>
  );
}
