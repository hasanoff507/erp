/**
 * «Kiruvchi» tab (07 BO-15, 19 §19): filters — xavf darajasi (Barchasi / Yashil / Qizil / Noma'lum) and
 * holat (Barchasi / Imzo kutmoqda / Qabul qilingan / Rad etilgan); columns — faktura · yetkazib beruvchi,
 * sana, summa, QQS, xavf chipi, holat. Below — the deferred VAT credit note (VM 830) and the «Kiruvchi e-TTN»
 * short block (the full list is the E-TTN tab).
 */
import { useUnit } from "effector-react";
import { Info } from "lucide-react";

import { formatDate, formatMoney } from "@shared/lib/format";
import { Banner, DataTable, SegmentedControl, type DataTableColumn } from "@shared/ui";

import { errorText } from "#/shared/lib/effect.ts";
import { useTx } from "#/shared/lib/i18n.ts";

import {
  $hasMore,
  $inFilters,
  $inbound,
  $inboundError,
  $inboundStatus,
  $selectedId,
  IN_STATUS_FILTERS,
  RISK_FILTERS,
  einvoiceSelected,
  moreRequested,
  reloadRequested,
  riskFilterChanged,
  statusFilterChanged,
  type EInvoice,
} from "../../model/index.ts";
import { DocStatusChip, RiskChip } from "../shared/chips.tsx";

const m = (v: string | null) => (v === null ? "—" : formatMoney(v, { precision: 2, withCurrency: false }));

export function InboundTab() {
  const { t } = useTx();
  const [rows, status, error, filters, selected, hasMore] = useUnit([
    $inbound,
    $inboundStatus,
    $inboundError,
    $inFilters,
    $selectedId,
    $hasMore,
  ]);
  const [onRisk, onStatus, select, more, reload] = useUnit([
    riskFilterChanged,
    statusFilterChanged,
    einvoiceSelected,
    moreRequested,
    reloadRequested,
  ]);

  const columns: DataTableColumn<EInvoice>[] = [
    {
      id: "doc",
      header: t("columns.invoiceSupplier"),
      cell: (e) => (
        <span className="flex flex-col">
          <span className="font-bold">{e.number ?? e.operator_doc_id ?? "—"}</span>
          <span className="text-[13px] text-foreground-secondary">{e.counterparty.name ?? "—"}</span>
        </span>
      ),
    },
    {
      id: "date",
      header: t("columns.date"),
      width: "120px",
      cell: (e) => (e.doc_date ? formatDate(e.doc_date) : "—"),
    },
    {
      id: "total",
      header: t("columns.total"),
      numeric: true,
      width: "140px",
      cell: (e) => m(e.total_amount),
    },
    { id: "vat", header: t("columns.vat"), numeric: true, width: "120px", cell: (e) => m(e.vat_amount) },
    { id: "risk", header: t("columns.risk"), width: "130px", cell: (e) => <RiskChip flag={e.risk_flag} /> },
    {
      id: "status",
      header: t("columns.status"),
      width: "150px",
      cell: (e) => <DocStatusChip status={e.status} scope="in" />,
    },
  ];

  return (
    <div className="flex flex-col gap-3.5">
      <div className="flex flex-wrap items-center gap-3">
        <SegmentedControl
          label={t("filters.risk")}
          variant="soft"
          options={RISK_FILTERS.map((v) => ({ value: v, label: t(`filters.riskOptions.${v}`) }))}
          value={filters.risk}
          onChange={onRisk}
        />
        <SegmentedControl
          label={t("filters.status")}
          variant="soft"
          options={IN_STATUS_FILTERS.map((v) => ({ value: v, label: t(`filters.statusOptions.${v}`) }))}
          value={filters.status}
          onChange={onStatus}
        />
      </div>
      <DataTable
        label={t("tabs.in")}
        columns={columns}
        data={rows}
        getRowId={(e) => e.id}
        status={status}
        errorMessage={error ? errorText(error) : undefined}
        onRetry={() => reload("in")}
        onRowClick={(e) => select(e.id)}
        selectedRowId={selected}
        pagination={{ kind: "cursor", hasMore: hasMore.in, onLoadMore: () => more("in") }}
      />
      <Banner tone="info" icon={Info}>
        {t("deferredNote")}
      </Banner>
    </div>
  );
}
