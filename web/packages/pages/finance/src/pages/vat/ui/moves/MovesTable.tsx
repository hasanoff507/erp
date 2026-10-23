/**
 * «QQS registri» — `vat_moves` of the period (20 #2): date, kind (chiquvchi / kiruvchi), document type,
 * base, VAT; filters kind and document type (returns included — US-M10-01); a quarter is paged month by
 * month («Yana yuklash»). Totals of the loaded rows below the table.
 */
import { useUnit } from "effector-react";
import { ListChecks } from "lucide-react";

import { serverErrorText, useTranslation } from "@shared/i18n";
import { formatDateTime, formatMoney } from "@shared/lib/format";
import { DataTable, EmptyState, FormField, SimpleSelect, StatusChip, type DataTableColumn } from "@shared/ui";

import {
  $moves,
  $movesError,
  $movesFilters,
  $movesHasMore,
  $movesMoreLoading,
  $movesStatus,
  $movesTotals,
  MOVE_DOC_TYPES,
  MOVE_KINDS,
  isMoveDocType,
  isMoveKind,
  movesDocTypeChanged,
  movesKindChanged,
  movesMoreRequested,
  movesReloadRequested,
  type VatMove,
} from "../../model/index.ts";

const ALL = "all";

export function MovesTable() {
  const { t } = useTranslation("finance");
  const [moves, status, error, filters, hasMore, moreLoading, totals] = useUnit([
    $moves,
    $movesStatus,
    $movesError,
    $movesFilters,
    $movesHasMore,
    $movesMoreLoading,
    $movesTotals,
  ]);
  const [onKind, onDocType, more, reload] = useUnit([
    movesKindChanged,
    movesDocTypeChanged,
    movesMoreRequested,
    movesReloadRequested,
  ]);
  const docLabel = (docType: string) =>
    isMoveDocType(docType) ? t(`vat.docTypes.${docType}`) : t("vat.docTypes.other");

  const columns: DataTableColumn<VatMove>[] = [
    {
      id: "created",
      header: t("vat.moves.columns.created"),
      width: "150px",
      cell: (m) => <span className="tabular-nums">{formatDateTime(m.created_at)}</span>,
    },
    { id: "period", header: t("vat.moves.columns.period"), width: "90px", cell: (m) => m.period },
    {
      id: "kind",
      header: t("vat.moves.columns.kind"),
      width: "130px",
      cell: (m) => (
        <StatusChip tone={m.kind === "output" ? "info" : "success"}>
          {t(`vat.moves.kinds.${m.kind}`)}
        </StatusChip>
      ),
    },
    { id: "doc", header: t("vat.moves.columns.document"), cell: (m) => docLabel(m.doc_type) },
    {
      id: "base",
      header: t("vat.moves.columns.base"),
      numeric: true,
      width: "150px",
      cell: (m) => formatMoney(m.base_amount, { precision: 2, withCurrency: false }),
    },
    {
      id: "vat",
      header: t("vat.moves.columns.vat"),
      numeric: true,
      width: "140px",
      cell: (m) => formatMoney(m.vat_amount, { precision: 2, withCurrency: false }),
    },
  ];

  return (
    <section aria-labelledby="vat-moves-title" className="flex flex-col gap-3">
      <div className="flex flex-wrap items-end gap-3">
        <div className="min-w-0 flex-1">
          <h2 id="vat-moves-title" className="text-h2">
            {t("vat.moves.title")}
          </h2>
          <p className="text-small text-foreground-secondary">{t("vat.moves.subtitle")}</p>
        </div>
        <FormField label={t("vat.moves.kindFilter")} className="w-44">
          <SimpleSelect
            options={[
              { value: ALL, label: t("vat.moves.allKinds") },
              ...MOVE_KINDS.map((k) => ({ value: k, label: t(`vat.moves.kinds.${k}`) })),
            ]}
            value={filters.kind ?? ALL}
            onValueChange={(v) => onKind(isMoveKind(v) ? v : null)}
          />
        </FormField>
        <FormField label={t("vat.moves.docFilter")} className="w-56">
          <SimpleSelect
            options={[
              { value: ALL, label: t("vat.moves.allDocs") },
              ...MOVE_DOC_TYPES.map((d) => ({ value: d, label: t(`vat.docTypes.${d}`) })),
            ]}
            value={filters.docType ?? ALL}
            onValueChange={(v) => onDocType(isMoveDocType(v) ? v : null)}
          />
        </FormField>
      </div>
      <DataTable
        label={t("vat.moves.title")}
        columns={columns}
        data={moves}
        getRowId={(m) => m.id}
        status={status}
        errorMessage={error ? serverErrorText(error) : undefined}
        onRetry={reload}
        minWidth={820}
        skeletonRows={4}
        empty={<EmptyState icon={ListChecks} title={t("vat.moves.empty")} />}
        pagination={{ kind: "cursor", hasMore, loadingMore: moreLoading, onLoadMore: more }}
      />
      {moves.length > 0 ? (
        <dl
          role="group"
          aria-label={t("vat.moves.totals")}
          className="flex flex-wrap justify-end gap-x-6 gap-y-1 text-[13px]"
        >
          <dt className="text-foreground-secondary">{t("vat.moves.totalBase")}</dt>
          <dd className="font-extrabold tabular-nums">{formatMoney(totals.base, { precision: 2 })}</dd>
          <dt className="text-foreground-secondary">{t("vat.moves.totalVat")}</dt>
          <dd className="font-extrabold tabular-nums">{formatMoney(totals.vat, { precision: 2 })}</dd>
        </dl>
      ) : null}
    </section>
  );
}
