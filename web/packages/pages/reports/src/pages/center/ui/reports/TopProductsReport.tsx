/**
 * «Top tovarlar» (`/reports/top-products`, US-M12-02, QT-M12-02): products by quantity sold (net of
 * returns), most sold first — or least sold («Eng kam sotilgan», `order=bottom`).
 */
import { useUnit } from "effector-react";
import { ShoppingCart } from "lucide-react";

import { useTranslation } from "@shared/i18n";
import { formatMoney } from "@shared/lib/format";
import { DataTable, EmptyState, SegmentedControl, type DataTableColumn } from "@shared/ui";

import { formatUnitQty } from "#/shared/lib/units.ts";

import { $options, topOrderChanged, type TopOrder, type TopProducts } from "../../model/index.ts";
import { BranchFilter, IncompleteBanner, PeriodFilter } from "../filters/Filters.tsx";
import { ReportBody, Toolbar } from "./common.tsx";

type Item = TopProducts["items"][number];

function TopView({ data }: { data: TopProducts }) {
  const { t } = useTranslation("reports");
  const columns: DataTableColumn<Item>[] = [
    {
      id: "rank",
      header: "№",
      width: "60px",
      cell: (_, i) => <span className="font-extrabold text-muted-foreground">{i + 1}</span>,
    },
    {
      id: "name",
      header: t("top.columns.product"),
      cell: (p) => <span className="font-semibold">{p.name}</span>,
    },
    {
      id: "qty",
      header: t("top.columns.qty"),
      numeric: true,
      cell: (p) => formatUnitQty(p.qty_sold, p.unit_code),
    },
    {
      id: "revenue",
      header: t("top.columns.revenue"),
      numeric: true,
      cell: (p) => formatMoney(p.revenue, { withCurrency: false }),
    },
  ];
  return (
    <>
      <IncompleteBanner complete={data.data_complete} count={data.unsynced_devices} />
      <DataTable
        label={t("center.items.top-products.title")}
        columns={columns}
        data={data.items}
        getRowId={(p) => p.product_id}
        minWidth={640}
        empty={<EmptyState icon={ShoppingCart} title={t("top.empty")} />}
      />
    </>
  );
}

export function TopProductsReport() {
  const { t } = useTranslation("reports");
  const [options, onOrder] = useUnit([$options, topOrderChanged]);
  return (
    <div className="flex flex-col gap-3.5">
      <Toolbar>
        <BranchFilter />
        <PeriodFilter />
        <SegmentedControl<TopOrder>
          label={t("top.order.label")}
          value={options.topOrder}
          onChange={onOrder}
          options={[
            { value: "top", label: t("top.order.top") },
            { value: "bottom", label: t("top.order.bottom") },
          ]}
        />
      </Toolbar>
      <ReportBody kind="top-products">{(data) => <TopView data={data} />}</ReportBody>
    </div>
  );
}
