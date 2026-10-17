/**
 * «QQS registri (qaytarishlar bilan)» (07 BO-09; 20 #2 `GET /vat-moves?doc_type=returns`, `tax.vat.view`):
 * VAT reversals written by customer returns for the chosen month, totals of the loaded rows.
 */
import { useUnit } from "effector-react";
import { Undo2 } from "lucide-react";

import { serverErrorText, useTranslation } from "@shared/i18n";
import { formatDateTime, formatMoney } from "@shared/lib/format";
import { addMoney, money } from "@shared/lib/money";
import { DataTable, EmptyState, FormField, SimpleSelect, StatusChip, type DataTableColumn } from "@shared/ui";

import {
  $today,
  $vatCursor,
  $vatError,
  $vatMoreLoading,
  $vatMoves,
  $vatPeriod,
  $vatStatus,
  lastMonths,
  vatMoreRequested,
  vatPeriodChanged,
  vatReloadRequested,
  type VatMove,
} from "../../model/index.ts";

export function VatReturns() {
  const { t } = useTranslation("reports");
  const [today, period, moves, status, error, cursor, moreLoading] = useUnit([
    $today,
    $vatPeriod,
    $vatMoves,
    $vatStatus,
    $vatError,
    $vatCursor,
    $vatMoreLoading,
  ]);
  const [onPeriod, more, reload] = useUnit([vatPeriodChanged, vatMoreRequested, vatReloadRequested]);
  const totalBase = addMoney(...moves.map((m) => money(m.base_amount)));
  const totalVat = addMoney(...moves.map((m) => money(m.vat_amount)));

  const columns: DataTableColumn<VatMove>[] = [
    {
      id: "created",
      header: t("vatReturns.columns.created"),
      width: "160px",
      cell: (m) => <span className="tabular-nums">{formatDateTime(m.created_at)}</span>,
    },
    {
      id: "kind",
      header: t("vatReturns.columns.kind"),
      width: "140px",
      cell: (m) => <StatusChip tone="info">{t(`vatReturns.kinds.${m.kind}`)}</StatusChip>,
    },
    {
      id: "base",
      header: t("vatReturns.columns.base"),
      numeric: true,
      cell: (m) => formatMoney(m.base_amount, { precision: 2, withCurrency: false }),
    },
    {
      id: "vat",
      header: t("vatReturns.columns.vat"),
      numeric: true,
      cell: (m) => formatMoney(m.vat_amount, { precision: 2, withCurrency: false }),
    },
  ];

  return (
    <div className="flex flex-col gap-3.5">
      <FormField label={t("vatReturns.period")} className="w-48">
        <SimpleSelect
          options={lastMonths(today).map((m) => ({ value: m, label: m }))}
          value={period}
          onValueChange={(v) => onPeriod(v)}
        />
      </FormField>
      <DataTable
        label={t("vatReturns.tableLabel")}
        columns={columns}
        data={moves}
        getRowId={(m) => m.id}
        status={status}
        errorMessage={error ? serverErrorText(error) : undefined}
        onRetry={reload}
        minWidth={640}
        skeletonRows={4}
        empty={<EmptyState icon={Undo2} title={t("vatReturns.empty")} />}
        pagination={{ kind: "cursor", hasMore: cursor !== null, loadingMore: moreLoading, onLoadMore: more }}
      />
      {moves.length > 0 ? (
        <dl
          role="group"
          aria-label={t("vatReturns.totals")}
          className="flex flex-wrap justify-end gap-x-5 gap-y-1 text-[13px]"
        >
          <dt className="text-foreground-secondary">{t("vatReturns.columns.base")}</dt>
          <dd className="font-extrabold tabular-nums">{formatMoney(totalBase, { precision: 2 })}</dd>
          <dt className="text-foreground-secondary">{t("vatReturns.columns.vat")}</dt>
          <dd className="font-extrabold tabular-nums">{formatMoney(totalVat, { precision: 2 })}</dd>
        </dl>
      ) : null}
    </div>
  );
}
