/**
 * «Chegirmalar va marja» (`/reports/discounts`, US-M03-03, QT-M03-03): given discounts and the margin
 * they cost — margin with and without discounts, by day / branch / cashier / product, with the total.
 */
import { useUnit } from "effector-react";
import { BadgePercent, TrendingDown, TrendingUp } from "lucide-react";

import { useTranslation } from "@shared/i18n";
import { formatDate, formatMoney, formatPercent } from "@shared/lib/format";
import { DataTable, EmptyState, KpiCard, SegmentedControl, type DataTableColumn } from "@shared/ui";

import {
  $options,
  DISCOUNT_GROUPS,
  discountsGroupByChanged,
  lostMargin,
  type DiscountReport,
  type DiscountsGroupBy,
} from "../../model/index.ts";
import { BranchFilter, IncompleteBanner, PeriodFilter } from "../filters/Filters.tsx";
import { KpiGrid, ReportBody, Strong, Toolbar } from "./common.tsx";

type Row = DiscountReport["rows"][number] & { isTotal: boolean };

function DiscountsView({ data, groupBy }: { data: DiscountReport; groupBy: DiscountsGroupBy }) {
  const { t } = useTranslation("reports");
  const rows: Row[] = [
    ...data.rows.map((r) => ({ ...r, isTotal: false })),
    ...(data.rows.length > 0 ? [{ ...data.total, isTotal: true }] : []),
  ];
  const label = (r: Row) =>
    r.isTotal ? t("report.total") : groupBy === "day" ? formatDate(r.group_key) : (r.group_label ?? "—");
  const pct = (v: string | null) => (v === null ? "—" : formatPercent(v));
  const m = (v: string) => formatMoney(v, { withCurrency: false });
  const columns: DataTableColumn<Row>[] = [
    {
      id: "group",
      header: t(`discounts.groupBy.${groupBy}`),
      cell: (r) => <Strong on={r.isTotal}>{label(r)}</Strong>,
    },
    { id: "sales", header: t("discounts.columns.sales"), numeric: true, cell: (r) => m(r.sales_total) },
    {
      id: "discount",
      header: t("discounts.columns.discount"),
      numeric: true,
      cell: (r) => m(r.discount_total),
    },
    { id: "revenue", header: t("discounts.columns.revenue"), numeric: true, cell: (r) => m(r.revenue_net) },
    { id: "cost", header: t("discounts.columns.cost"), numeric: true, cell: (r) => m(r.cost) },
    { id: "margin", header: t("discounts.columns.margin"), numeric: true, cell: (r) => m(r.margin) },
    {
      id: "marginNoDiscount",
      header: t("discounts.columns.marginWithout"),
      numeric: true,
      cell: (r) => m(r.margin_without_discounts),
    },
    { id: "lost", header: t("discounts.columns.lost"), numeric: true, cell: (r) => m(lostMargin(r)) },
    {
      id: "pct",
      header: t("discounts.columns.marginPct"),
      numeric: true,
      cell: (r) => `${pct(r.margin_pct)} / ${pct(r.margin_pct_without_discounts)}`,
    },
  ];
  return (
    <>
      <IncompleteBanner complete={data.data_complete} count={data.unsynced_devices} />
      <KpiGrid label={t("report.kpiLabel")}>
        <KpiCard
          label={t("discounts.kpi.discounts")}
          value={formatMoney(data.total.discount_total)}
          icon={BadgePercent}
          tone="warning"
        />
        <KpiCard
          label={t("discounts.kpi.margin")}
          value={formatMoney(data.total.margin)}
          icon={TrendingUp}
          tone="primary"
          note={t("discounts.kpi.marginWithout", {
            amount: formatMoney(data.total.margin_without_discounts),
          })}
        />
        <KpiCard
          label={t("discounts.kpi.lost")}
          value={formatMoney(lostMargin(data.total))}
          icon={TrendingDown}
          tone="destructive"
        />
      </KpiGrid>
      <DataTable
        label={t("center.items.discounts.title")}
        columns={columns}
        data={rows}
        getRowId={(r) => (r.isTotal ? "total" : r.group_key)}
        minWidth={1100}
        empty={<EmptyState icon={BadgePercent} title={t("discounts.empty")} />}
      />
    </>
  );
}

export function DiscountsReport() {
  const { t } = useTranslation("reports");
  const [options, onGroup] = useUnit([$options, discountsGroupByChanged]);
  return (
    <div className="flex flex-col gap-3.5">
      <Toolbar>
        <BranchFilter />
        <PeriodFilter />
        <SegmentedControl<DiscountsGroupBy>
          label={t("discounts.groupBy.label")}
          value={options.discountsGroupBy}
          onChange={onGroup}
          options={DISCOUNT_GROUPS.map((g) => ({ value: g, label: t(`discounts.groupBy.${g}`) }))}
        />
      </Toolbar>
      <ReportBody kind="discounts">
        {(data) => <DiscountsView data={data} groupBy={options.discountsGroupBy} />}
      </ReportBody>
    </div>
  );
}
