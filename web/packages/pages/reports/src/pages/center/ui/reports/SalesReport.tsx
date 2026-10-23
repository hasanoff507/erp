/**
 * «Kunlik savdo» (`/reports/sales?group_by=day`, US-M12-01, QT-M12-01) and «Kassirlar bo'yicha savdo»
 * (`group_by=cashier`): KPI (savdo, cheklar, o'rtacha chek, qaytarishlar), the daily chart, the table
 * with the «Jami» row. Branch filter «Barcha filiallar» = consolidated; one branch = that branch only.
 */
import { ChartColumn, Receipt, Undo2, Wallet } from "lucide-react";

import { useTranslation } from "@shared/i18n";
import { formatDate, formatMoney } from "@shared/lib/format";
import { DataTable, EmptyState, KpiCard, type DataTableColumn } from "@shared/ui";

import { millions } from "#/shared/lib/chart.ts";
import { BarChart } from "#/shared/ui/BarChart.tsx";

import type { SalesReport as Data } from "../../model/index.ts";
import { BranchFilter, IncompleteBanner, PeriodFilter } from "../filters/Filters.tsx";
import { KpiGrid, ReportBody, Strong, Toolbar } from "./common.tsx";

type Row = Data["rows"][number] & { isTotal: boolean };

function SalesView({ data, byCashier }: { data: Data; byCashier: boolean }) {
  const { t } = useTranslation("reports");
  const label = (r: Row) =>
    r.isTotal
      ? t("report.total")
      : byCashier
        ? (r.group_label ?? t("sales.unknownCashier"))
        : formatDate(r.group_key);
  const rows: Row[] = [
    ...data.rows.map((r) => ({ ...r, isTotal: false })),
    ...(data.rows.length > 0 ? [{ ...data.total, isTotal: true }] : []),
  ];
  const columns: DataTableColumn<Row>[] = [
    {
      id: "group",
      header: byCashier ? t("sales.columns.cashier") : t("sales.columns.day"),
      cell: (r) => <Strong on={r.isTotal}>{label(r)}</Strong>,
    },
    {
      id: "gross",
      header: t("sales.columns.gross"),
      numeric: true,
      cell: (r) => formatMoney(r.gross_sales, { withCurrency: false }),
    },
    {
      id: "returns",
      header: t("sales.columns.returns"),
      numeric: true,
      cell: (r) => formatMoney(r.returns_total, { withCurrency: false }),
    },
    {
      id: "total",
      header: t("sales.columns.total"),
      numeric: true,
      cell: (r) => formatMoney(r.total_sales, { withCurrency: false }),
    },
    {
      id: "receipts",
      header: t("sales.columns.receipts"),
      numeric: true,
      cell: (r) => String(r.receipt_count),
    },
    {
      id: "avg",
      header: t("sales.columns.avg"),
      numeric: true,
      cell: (r) => formatMoney(r.avg_receipt, { withCurrency: false }),
    },
  ];
  return (
    <>
      <IncompleteBanner complete={data.data_complete} count={data.unsynced_devices} />
      <KpiGrid label={t("report.kpiLabel")}>
        <KpiCard
          label={t("sales.kpi.total")}
          value={formatMoney(data.total.total_sales)}
          icon={ChartColumn}
          tone="primary"
        />
        <KpiCard
          label={t("sales.kpi.receipts")}
          value={String(data.total.receipt_count)}
          icon={Receipt}
          tone="info"
        />
        <KpiCard
          label={t("sales.kpi.avg")}
          value={formatMoney(data.total.avg_receipt)}
          icon={Wallet}
          tone="success"
        />
        <KpiCard
          label={t("sales.kpi.returns")}
          value={formatMoney(data.total.returns_total)}
          icon={Undo2}
          tone="warning"
        />
      </KpiGrid>
      {!byCashier && data.rows.length > 1 && data.rows.length <= 62 ? (
        <section aria-label={t("sales.chart")} className="flex flex-col gap-2">
          <p className="text-small text-muted-foreground">{t("sales.chartUnit")}</p>
          <BarChart
            label={t("sales.chart")}
            bars={data.rows.map((r) => ({
              key: r.group_key,
              label: formatDate(r.group_key).slice(0, 5),
              value: r.total_sales,
            }))}
            formatValue={millions}
            formatFull={(v) => formatMoney(v)}
          />
        </section>
      ) : null}
      <DataTable
        label={t(byCashier ? "center.items.cashier-sales.title" : "center.items.daily-sales.title")}
        columns={columns}
        data={rows}
        getRowId={(r) => (r.isTotal ? "total" : r.group_key)}
        minWidth={760}
        empty={<EmptyState icon={ChartColumn} title={t("sales.empty")} />}
      />
    </>
  );
}

export function SalesReport({ byCashier }: { byCashier: boolean }) {
  return (
    <div className="flex flex-col gap-3.5">
      <Toolbar>
        <BranchFilter />
        <PeriodFilter />
      </Toolbar>
      <ReportBody kind="sales">{(data) => <SalesView data={data} byCashier={byCashier} />}</ReportBody>
    </div>
  );
}
