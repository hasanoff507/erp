/**
 * «Ombor qoldig'i» / «Kam qolgan tovarlar» (`/reports/stock`, US-M04-03, QT-M04-03, US-M14-01): over
 * «Barcha filiallar» every branch separately and the total — per-branch totals table, per-product
 * quantity of each branch, total quantity and value at cost. One branch — that branch only.
 * The whole report comes in one answer (20 §20); the table pages on the client.
 */
import { useUnit } from "effector-react";
import { Package, PackageOpen, TriangleAlert } from "lucide-react";
import { useState } from "react";

import { useTranslation } from "@shared/i18n";
import { formatMoney } from "@shared/lib/format";
import { DataTable, EmptyState, KpiCard, SearchInput, StatusChip, type DataTableColumn } from "@shared/ui";

import { formatUnitQty, unitLabel } from "#/shared/lib/units.ts";

import { $options, CLIENT_PAGE, stockSearchChanged, type StockReport as Data } from "../../model/index.ts";
import { BranchFilter } from "../filters/Filters.tsx";
import { KpiGrid, ReportBody, Strong, Toolbar } from "./common.tsx";

type Item = Data["items"][number];
type BranchRow = Data["branches"][number] & { isTotal: boolean };

function BranchTotals({ data }: { data: Data }) {
  const { t } = useTranslation("reports");
  const rows: BranchRow[] = [
    ...data.branches.map((b) => ({ ...b, isTotal: false })),
    {
      branch_id: "total",
      name: t("report.total"),
      value: data.total.value,
      positions: data.total.positions,
      below_min_count: data.total.below_min_count,
      isTotal: true,
    },
  ];
  const columns: DataTableColumn<BranchRow>[] = [
    { id: "name", header: t("stock.columns.branch"), cell: (r) => <Strong on={r.isTotal}>{r.name}</Strong> },
    {
      id: "positions",
      header: t("stock.columns.positions"),
      numeric: true,
      cell: (r) => String(r.positions),
    },
    { id: "low", header: t("stock.columns.belowMin"), numeric: true, cell: (r) => String(r.below_min_count) },
    {
      id: "value",
      header: t("stock.columns.value"),
      numeric: true,
      cell: (r) => formatMoney(r.value, { withCurrency: false }),
    },
  ];
  return (
    <DataTable
      label={t("stock.byBranch")}
      columns={columns}
      data={rows}
      getRowId={(r) => r.branch_id}
      minWidth={560}
    />
  );
}

function StockView({ data }: { data: Data }) {
  const { t } = useTranslation("reports");
  const [shown, setShown] = useState(CLIENT_PAGE);
  const perBranch = data.consolidated && data.branches.length > 1;
  const columns: DataTableColumn<Item>[] = [
    {
      id: "product",
      header: t("stock.columns.product"),
      cell: (p) => {
        const meta = [
          unitLabel(p.unit_code),
          p.category_name,
          p.barcode,
          p.is_marked ? t("stock.marked") : null,
        ]
          .filter(Boolean)
          .join(" · ");
        return (
          <span className="flex flex-col">
            <span className="font-semibold">{p.name}</span>
            {meta ? <span className="text-[12px] text-muted-foreground">{meta}</span> : null}
          </span>
        );
      },
    },
    ...(perBranch
      ? data.branches.map((b): DataTableColumn<Item> => ({
          id: `branch-${b.branch_id}`,
          header: b.name,
          numeric: true,
          width: "120px",
          cell: (p) => {
            const q = p.by_branch.find((x) => x.branch_id === b.branch_id);
            return q ? formatUnitQty(q.qty, p.unit_code) : "—";
          },
        }))
      : []),
    {
      id: "qty",
      header: perBranch ? t("stock.columns.qtyTotal") : t("stock.columns.qty"),
      numeric: true,
      width: "120px",
      cell: (p) => formatUnitQty(p.qty, p.unit_code),
    },
    {
      id: "min",
      header: t("stock.columns.min"),
      numeric: true,
      width: "90px",
      cell: (p) => (p.min_stock ? formatUnitQty(p.min_stock, p.unit_code) : "—"),
    },
    {
      id: "value",
      header: t("stock.columns.value"),
      numeric: true,
      width: "140px",
      cell: (p) => formatMoney(p.value, { withCurrency: false }),
    },
    {
      id: "status",
      header: t("stock.columns.status"),
      width: "120px",
      cell: (p) =>
        p.below_min ? (
          <StatusChip tone="destructive">{t("stock.low")}</StatusChip>
        ) : (
          <StatusChip tone="success">{t("stock.ok")}</StatusChip>
        ),
    },
  ];
  const page = data.items.slice(0, shown);
  return (
    <>
      <KpiGrid label={t("report.kpiLabel")}>
        <KpiCard
          label={t("stock.kpi.value")}
          value={formatMoney(data.total.value)}
          icon={Package}
          tone="primary"
          note={t("stock.kpi.positions", { count: data.total.positions })}
        />
        <KpiCard
          label={t("stock.kpi.low")}
          value={String(data.total.below_min_count)}
          icon={TriangleAlert}
          tone="destructive"
        />
      </KpiGrid>
      {perBranch ? <BranchTotals data={data} /> : null}
      <DataTable
        label={t("stock.tableLabel")}
        columns={columns}
        data={page}
        getRowId={(p) => p.product_id}
        minWidth={perBranch ? 900 + data.branches.length * 120 : 900}
        empty={<EmptyState icon={PackageOpen} title={t("stock.empty")} />}
        pagination={{
          kind: "cursor",
          hasMore: data.items.length > shown,
          onLoadMore: () => setShown((n) => n + CLIENT_PAGE),
        }}
      />
    </>
  );
}

export function StockReport() {
  const { t } = useTranslation("reports");
  const [options, onSearch] = useUnit([$options, stockSearchChanged]);
  return (
    <div className="flex flex-col gap-3.5">
      <Toolbar>
        <BranchFilter />
        <SearchInput
          className="w-72"
          value={options.stockSearch}
          onSearch={onSearch}
          maxLength={64}
          aria-label={t("stock.search")}
          placeholder={t("stock.searchPlaceholder")}
        />
      </Toolbar>
      <ReportBody kind="stock">{(data) => <StockView data={data} />}</ReportBody>
    </div>
  );
}
