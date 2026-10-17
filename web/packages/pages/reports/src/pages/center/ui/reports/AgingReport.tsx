/**
 * «Qarzdorlik muddati» (`/reports/debts-aging`, 20 #21): mijozlar (debitorlik) or «Men qarzdorman»
 * (kreditorlik) as of the chosen date — total, eskirish guruhlari (0–30 / 31–60 / 60+) and one row per
 * counterparty, most overdue first.
 */
import { useUnit } from "effector-react";
import { Users } from "lucide-react";

import { useTranslation } from "@shared/i18n";
import { formatDate, formatMoney, formatPhone } from "@shared/lib/format";
import {
  DataTable,
  EmptyState,
  KpiCard,
  SegmentedControl,
  StatusChip,
  type DataTableColumn,
} from "@shared/ui";

import { $options, agingDirectionChanged, type AgingDirection, type DebtsAging } from "../../model/index.ts";
import { BranchFilter, PeriodFilter } from "../filters/Filters.tsx";
import { KpiGrid, ReportBody, Toolbar } from "./common.tsx";

type Row = DebtsAging["rows"][number];

const BUCKET_TONE = { "0-30": "info", "31-60": "warning", "60+": "destructive" } as const;

function AgingView({ data }: { data: DebtsAging }) {
  const { t } = useTranslation("reports");
  const columns: DataTableColumn<Row>[] = [
    {
      id: "name",
      header: t("aging.columns.counterparty"),
      cell: (r) => (
        <span className="flex flex-col">
          <span className="font-semibold">{r.name}</span>
          {r.phone ? <span className="text-[12px] text-muted-foreground">{formatPhone(r.phone)}</span> : null}
        </span>
      ),
    },
    {
      id: "balance",
      header: t("aging.columns.balance"),
      numeric: true,
      cell: (r) => formatMoney(r.balance, { withCurrency: false }),
    },
    {
      id: "due",
      header: t("aging.columns.due"),
      width: "120px",
      cell: (r) => <span className="tabular-nums">{formatDate(r.overdue_since)}</span>,
    },
    {
      id: "days",
      header: t("aging.columns.days"),
      numeric: true,
      width: "110px",
      cell: (r) => String(r.days_overdue),
    },
    {
      id: "bucket",
      header: t("aging.columns.bucket"),
      width: "110px",
      cell: (r) => <StatusChip tone={BUCKET_TONE[r.bucket]}>{t(`aging.buckets.${r.bucket}`)}</StatusChip>,
    },
    {
      id: "promise",
      header: t("aging.columns.promise"),
      width: "120px",
      cell: (r) =>
        r.promise_date ? <span className="tabular-nums">{formatDate(r.promise_date)}</span> : "—",
    },
    {
      id: "lastPayment",
      header: t("aging.columns.lastPayment"),
      numeric: true,
      cell: (r) =>
        r.last_payment_amount && r.last_payment_date
          ? `${formatMoney(r.last_payment_amount, { withCurrency: false })} · ${formatDate(r.last_payment_date)}`
          : "—",
    },
  ];
  return (
    <>
      <KpiGrid label={t("report.kpiLabel")}>
        <KpiCard
          label={t(`aging.total.${data.direction}`)}
          value={formatMoney(data.summary.total)}
          icon={Users}
          tone="warning"
          note={t("aging.count", { count: data.summary.count })}
        />
        {data.summary.buckets.map((b) => (
          <KpiCard
            key={b.bucket}
            label={t(`aging.buckets.${b.bucket}`)}
            value={formatMoney(b.amount)}
            icon={Users}
            tone={BUCKET_TONE[b.bucket]}
            note={t("aging.count", { count: b.count })}
          />
        ))}
      </KpiGrid>
      <DataTable
        label={t("center.items.debts-aging.title")}
        columns={columns}
        data={data.rows}
        getRowId={(r) => r.counterparty_id}
        minWidth={1000}
        empty={<EmptyState icon={Users} title={t("aging.empty")} />}
      />
    </>
  );
}

export function AgingReport() {
  const { t } = useTranslation("reports");
  const [options, onDirection] = useUnit([$options, agingDirectionChanged]);
  return (
    <div className="flex flex-col gap-3.5">
      <Toolbar>
        <BranchFilter />
        <PeriodFilter asOf />
        <SegmentedControl<AgingDirection>
          label={t("aging.direction.label")}
          value={options.agingDirection}
          onChange={onDirection}
          options={[
            { value: "receivable", label: t("aging.direction.receivable") },
            { value: "payable", label: t("aging.direction.payable") },
          ]}
        />
      </Toolbar>
      <ReportBody kind="debts-aging">{(data) => <AgingView data={data} />}</ReportBody>
    </div>
  );
}
