/**
 * Per-branch figures and the total (US-M14-01, QT-M14-01): shown when the dashboard covers more than
 * one branch («Barcha filiallar»). Profit / low-stock columns only when the API sends them.
 */
import { useTranslation } from "@shared/i18n";
import { formatMoney } from "@shared/lib/format";
import { Card, CardTitle, DataTable, cn, type DataTableColumn } from "@shared/ui";

import type { Dashboard } from "../../model/index.ts";

interface Row {
  id: string;
  name: string;
  sales: string;
  receipts: number;
  avg: string;
  profit: string | null;
  cash: string;
  low: number | null;
  total: boolean;
}

export function BranchTable({ data }: { data: Dashboard }) {
  const { t } = useTranslation("reports");
  const rows: Row[] = [
    ...data.by_branch.map((b) => ({
      id: b.branch_id,
      name: b.name,
      sales: b.sales,
      receipts: b.receipt_count,
      avg: b.avg_receipt,
      profit: b.profit,
      cash: b.cash_on_hand,
      low: b.low_stock_count,
      total: false,
    })),
    {
      id: "total",
      name: t("dashboard.branches.total"),
      sales: data.total_sales,
      receipts: data.receipt_count,
      avg: data.avg_receipt,
      profit: data.net_profit,
      cash: data.cash_on_hand,
      low: data.stock?.low_stock_count ?? null,
      total: true,
    },
  ];
  const strong = (r: Row, text: string) => <span className={cn(r.total && "font-extrabold")}>{text}</span>;
  const columns: DataTableColumn<Row>[] = [
    { id: "name", header: t("dashboard.branches.branch"), cell: (r) => strong(r, r.name) },
    {
      id: "sales",
      header: t("dashboard.branches.sales"),
      numeric: true,
      cell: (r) => formatMoney(r.sales),
    },
    {
      id: "receipts",
      header: t("dashboard.branches.receipts"),
      numeric: true,
      cell: (r) => String(r.receipts),
    },
    {
      id: "avg",
      header: t("dashboard.branches.avgReceipt"),
      numeric: true,
      cell: (r) => formatMoney(r.avg),
    },
    ...(data.net_profit !== null
      ? [
          {
            id: "profit",
            header: t("dashboard.branches.profit"),
            numeric: true,
            cell: (r: Row) => (r.profit === null ? "—" : formatMoney(r.profit)),
          },
        ]
      : []),
    {
      id: "cash",
      header: t("dashboard.branches.cash"),
      numeric: true,
      cell: (r) => formatMoney(r.cash),
    },
    ...(data.stock !== null
      ? [
          {
            id: "low",
            header: t("dashboard.branches.lowStock"),
            numeric: true,
            cell: (r: Row) => (r.low === null ? "—" : String(r.low)),
          },
        ]
      : []),
  ];
  return (
    <Card className="flex flex-col gap-3">
      <CardTitle>{t("dashboard.branches.title")}</CardTitle>
      <DataTable
        label={t("dashboard.branches.title")}
        columns={columns}
        data={rows}
        getRowId={(r) => r.id}
        minWidth={760}
      />
    </Card>
  );
}
