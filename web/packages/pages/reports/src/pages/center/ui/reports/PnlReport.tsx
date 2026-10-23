/**
 * «Foyda va zarar» (`/reports/profit-and-loss`, US-M15-03, QT-M15-03): tushum − qaytarishlar −
 * chegirmalar = sof tushum; − tannarx = yalpi foyda (marja %); + boshqa daromad; − xarajatlar
 * (toifalar bo'yicha) = sof foyda. Over several branches — the same figures per branch.
 */
import { TrendingUp } from "lucide-react";

import { useTranslation } from "@shared/i18n";
import { formatMoney, formatPercent } from "@shared/lib/format";
import { Card, DataTable, KpiCard, cn, type DataTableColumn } from "@shared/ui";

import type { ProfitAndLoss } from "../../model/index.ts";
import { BranchFilter, IncompleteBanner, PeriodFilter } from "../filters/Filters.tsx";
import { KpiGrid, ReportBody, Toolbar } from "./common.tsx";

type Branch = ProfitAndLoss["by_branch"][number];

/** Ledger sources of expense lines without a category (20 §12 `source`). */
const KNOWN_SOURCES = [
  "expenses",
  "write_offs",
  "debt_writeoffs",
  "bank_settlements",
  "tax_settlements",
] as const;

function Line({
  label,
  value,
  strong,
  minus,
  indent,
}: {
  label: string;
  value: string;
  strong?: boolean;
  minus?: boolean;
  indent?: boolean;
}) {
  return (
    <div
      className={cn(
        "flex items-baseline justify-between gap-3 border-b border-divider py-2 text-[14px] last:border-0",
        indent && "pl-5 text-[13px] text-foreground-secondary",
      )}
    >
      <dt className={cn(strong && "font-extrabold")}>{label}</dt>
      <dd className={cn("tabular-nums", strong ? "font-extrabold" : "font-semibold")}>
        {minus ? "− " : ""}
        {formatMoney(value)}
      </dd>
    </div>
  );
}

function PnlView({ data }: { data: ProfitAndLoss }) {
  const { t } = useTranslation("reports");
  const expenseLabel = (e: ProfitAndLoss["expenses_by_category"][number]) => {
    if (e.category) return e.category;
    const source = KNOWN_SOURCES.find((s) => s === e.source);
    return source ? t(`pnl.sources.${source}`) : t("pnl.sources.other", { account: e.account });
  };
  const columns: DataTableColumn<Branch>[] = [
    {
      id: "name",
      header: t("pnl.columns.branch"),
      cell: (b) => <span className="font-semibold">{b.name}</span>,
    },
    {
      id: "net",
      header: t("pnl.netRevenue"),
      numeric: true,
      cell: (b) => formatMoney(b.net_revenue, { withCurrency: false }),
    },
    {
      id: "cogs",
      header: t("pnl.cogs"),
      numeric: true,
      cell: (b) => formatMoney(b.cogs, { withCurrency: false }),
    },
    {
      id: "gross",
      header: t("pnl.grossProfit"),
      numeric: true,
      cell: (b) => formatMoney(b.gross_profit, { withCurrency: false }),
    },
    {
      id: "exp",
      header: t("pnl.expensesTotal"),
      numeric: true,
      cell: (b) => formatMoney(b.expenses_total, { withCurrency: false }),
    },
    {
      id: "profit",
      header: t("pnl.netProfit"),
      numeric: true,
      cell: (b) => formatMoney(b.net_profit, { withCurrency: false }),
    },
  ];
  return (
    <>
      <IncompleteBanner complete={data.data_complete} count={data.unsynced_devices} />
      <KpiGrid label={t("report.kpiLabel")}>
        <KpiCard
          label={t("pnl.netProfit")}
          value={formatMoney(data.net_profit)}
          icon={TrendingUp}
          tone="success"
          note={t("pnl.formula")}
        />
        <KpiCard
          label={t("pnl.grossProfit")}
          value={formatMoney(data.gross_profit)}
          icon={TrendingUp}
          tone="primary"
          note={
            data.gross_margin_pct === null
              ? undefined
              : t("pnl.margin", { value: formatPercent(data.gross_margin_pct) })
          }
        />
      </KpiGrid>
      <Card>
        <dl aria-label={t("pnl.statement")}>
          <Line label={t("pnl.revenue")} value={data.revenue} />
          <Line label={t("pnl.returns")} value={data.returns} minus indent />
          <Line label={t("pnl.discounts")} value={data.discounts} minus indent />
          <Line label={t("pnl.netRevenue")} value={data.net_revenue} strong />
          <Line label={t("pnl.cogs")} value={data.cogs} minus />
          <Line label={t("pnl.grossProfit")} value={data.gross_profit} strong />
          <Line label={t("pnl.otherIncome")} value={data.other_income} />
          {data.expenses_by_category.map((e, i) => (
            <Line
              key={`${e.category_id ?? e.source}-${e.account}-${i}`}
              label={expenseLabel(e)}
              value={e.amount}
              minus
              indent
            />
          ))}
          <Line label={t("pnl.expensesTotal")} value={data.expenses_total} minus />
          <Line label={t("pnl.netProfit")} value={data.net_profit} strong />
        </dl>
      </Card>
      {data.by_branch.length > 0 ? (
        <DataTable
          label={t("pnl.byBranch")}
          columns={columns}
          data={data.by_branch}
          getRowId={(b) => b.branch_id}
          minWidth={820}
        />
      ) : null}
    </>
  );
}

export function PnlReport() {
  return (
    <div className="flex flex-col gap-3.5">
      <Toolbar>
        <BranchFilter />
        <PeriodFilter />
      </Toolbar>
      <ReportBody kind="profit-and-loss">{(data) => <PnlView data={data} />}</ReportBody>
    </div>
  );
}
