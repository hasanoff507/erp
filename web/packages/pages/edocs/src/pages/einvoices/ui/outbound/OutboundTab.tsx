/**
 * «Chiquvchi» tab (07 BO-15, 18 §14a): B2B credit-sale drafts (created by the server at sale posting) and
 * e-invoices made from a receipt or by hand — holati: qoralama / imzolangan / yuborildi / qabul qilindi.
 */
import { useUnit } from "effector-react";

import { formatDate, formatMoney } from "@shared/lib/format";
import { DataTable, type DataTableColumn } from "@shared/ui";

import { errorText } from "#/shared/lib/effect.ts";
import { useTx } from "#/shared/lib/i18n.ts";

import {
  $hasMore,
  $outbound,
  $outboundError,
  $outboundStatus,
  $selectedId,
  einvoiceSelected,
  moreRequested,
  reloadRequested,
  type EInvoice,
} from "../../model/index.ts";
import { DocStatusChip } from "../shared/chips.tsx";

export function OutboundTab() {
  const { t } = useTx();
  const [rows, status, error, selected, hasMore] = useUnit([
    $outbound,
    $outboundStatus,
    $outboundError,
    $selectedId,
    $hasMore,
  ]);
  const [select, more, reload] = useUnit([einvoiceSelected, moreRequested, reloadRequested]);

  const columns: DataTableColumn<EInvoice>[] = [
    {
      id: "doc",
      header: t("columns.invoiceBuyer"),
      cell: (e) => (
        <span className="flex flex-col">
          <span className="font-bold">{e.number ?? e.operator_doc_id ?? t("detail.noNumber")}</span>
          <span className="text-[13px] text-foreground-secondary">{e.counterparty.name ?? "—"}</span>
        </span>
      ),
    },
    {
      id: "source",
      header: t("columns.source"),
      width: "170px",
      cell: (e) => (e.related_doc_type === "sales" ? t("source.receipt") : t("source.manual")),
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
      cell: (e) =>
        e.total_amount === null ? "—" : formatMoney(e.total_amount, { precision: 2, withCurrency: false }),
    },
    {
      id: "status",
      header: t("columns.status"),
      width: "150px",
      cell: (e) => <DocStatusChip status={e.status} scope="out" />,
    },
  ];

  return (
    <DataTable
      label={t("tabs.out")}
      columns={columns}
      data={rows}
      getRowId={(e) => e.id}
      status={status}
      errorMessage={error ? errorText(error) : undefined}
      onRetry={() => reload("out")}
      onRowClick={(e) => select(e.id)}
      selectedRowId={selected}
      pagination={{ kind: "cursor", hasMore: hasMore.out, onLoadMore: () => more("out") }}
    />
  );
}
