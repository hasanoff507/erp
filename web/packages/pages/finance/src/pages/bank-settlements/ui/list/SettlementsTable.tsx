/**
 * «Bank tushumi hujjatlari» (20 #55a): date, number (+ bank ref), branch · method, period, gross, commission,
 * variance, net, status (+ «Importdan»); footer «O'tkazilgan jami» over the loaded posted rows.
 */
import { useUnit } from "effector-react";
import { Landmark } from "lucide-react";

import { serverErrorText, useTranslation } from "@shared/i18n";
import { formatDate, formatMoney } from "@shared/lib/format";
import { $branches } from "@shared/state/session";
import { DataTable, EmptyState, StatusChip, type DataTableColumn, type Tone } from "@shared/ui";

import {
  $error,
  $hasMore,
  $moreLoading,
  $openedId,
  $postedTotals,
  $settlements,
  $status,
  moreRequested,
  reloadRequested,
  type Settlement,
} from "../../model/index.ts";

const STATUS_TONE: Readonly<Record<Settlement["status"], Tone>> = {
  draft: "neutral",
  posted: "success",
  cancelled: "destructive",
};

const money2 = (v: string) => formatMoney(v, { precision: 2, withCurrency: false });

export function SettlementsTable({ onOpen }: { onOpen: (id: string) => void }) {
  const { t } = useTranslation("finance");
  const [rows, status, error, hasMore, moreLoading, totals, openedId, branches] = useUnit([
    $settlements,
    $status,
    $error,
    $hasMore,
    $moreLoading,
    $postedTotals,
    $openedId,
    $branches,
  ]);
  const [more, reload] = useUnit([moreRequested, reloadRequested]);
  const branchName = (id: string) => branches.find((b) => b.id === id)?.name ?? "—";

  const columns: DataTableColumn<Settlement>[] = [
    { id: "date", header: t("bank.list.columns.date"), width: "100px", cell: (s) => formatDate(s.doc_date) },
    {
      id: "number",
      header: t("bank.list.columns.number"),
      width: "170px",
      cell: (s) => (
        <span className="flex flex-col">
          <span className="font-semibold tabular-nums">{s.number ?? t("bank.list.noNumber")}</span>
          {s.bank_ref ? <span className="text-[11px] text-foreground-secondary">№ {s.bank_ref}</span> : null}
        </span>
      ),
    },
    {
      id: "method",
      header: t("bank.list.columns.method"),
      width: "150px",
      cell: (s) => (
        <span className="flex flex-col">
          <span className="font-semibold">{t(`bank.methods.${s.method}`)}</span>
          <span className="text-[11px] text-foreground-secondary">{branchName(s.branch_id)}</span>
        </span>
      ),
    },
    {
      id: "period",
      header: t("bank.list.columns.period"),
      width: "130px",
      cell: (s) => `${formatDate(s.settled_from)}–${formatDate(s.settled_to)}`,
    },
    {
      id: "gross",
      header: t("bank.list.columns.gross"),
      numeric: true,
      width: "130px",
      cell: (s) => money2(s.gross_amount),
    },
    {
      id: "commission",
      header: t("bank.list.columns.commission"),
      numeric: true,
      width: "110px",
      cell: (s) => money2(s.commission_amount),
    },
    {
      id: "variance",
      header: t("bank.list.columns.variance"),
      numeric: true,
      width: "100px",
      cell: (s) => money2(s.variance_amount),
    },
    {
      id: "net",
      header: t("bank.list.columns.net"),
      numeric: true,
      width: "130px",
      cell: (s) => money2(s.net_amount),
    },
    {
      id: "status",
      header: t("bank.list.columns.status"),
      width: "170px",
      cell: (s) => (
        <span className="flex flex-wrap gap-1">
          <StatusChip tone={STATUS_TONE[s.status]} dot>
            {t(`bank.status.${s.status}`)}
          </StatusChip>
          {s.source === "statement_import" ? (
            <StatusChip tone="info">{t("bank.list.imported")}</StatusChip>
          ) : null}
        </span>
      ),
    },
  ];

  return (
    <section aria-labelledby="bank-list-title" className="flex flex-col gap-2.5">
      <div className="flex flex-wrap items-baseline gap-2">
        <h2 id="bank-list-title" className="text-h2">
          {t("bank.list.title")}
        </h2>
        <span className="text-[12px] text-foreground-secondary">{t("bank.list.formula")}</span>
      </div>
      <DataTable
        label={t("bank.list.title")}
        columns={columns}
        data={rows}
        getRowId={(s) => s.id}
        status={status}
        errorMessage={error ? serverErrorText(error) : undefined}
        onRetry={reload}
        onRowClick={(s) => onOpen(s.id)}
        selectedRowId={openedId}
        minWidth={1080}
        skeletonRows={4}
        empty={
          <EmptyState icon={Landmark} title={t("bank.list.empty")} description={t("bank.list.emptyHint")} />
        }
        pagination={{ kind: "cursor", hasMore, loadingMore: moreLoading, onLoadMore: more }}
      />
      {totals.count > 0 ? (
        <dl
          role="group"
          aria-label={t("bank.list.postedTotal")}
          className="flex flex-wrap justify-end gap-x-5 gap-y-1 text-[13px]"
        >
          <dt className="text-foreground-secondary">
            {t("bank.list.postedTotalCount", { count: totals.count })}
          </dt>
          <dd className="sr-only">{totals.count}</dd>
          <dt className="text-foreground-secondary">{t("bank.list.columns.gross")}</dt>
          <dd className="font-bold tabular-nums">{money2(totals.gross)}</dd>
          <dt className="text-foreground-secondary">{t("bank.list.columns.commission")}</dt>
          <dd className="font-bold tabular-nums">{money2(totals.commission)}</dd>
          <dt className="text-foreground-secondary">{t("bank.list.columns.net")}</dt>
          <dd className="font-extrabold tabular-nums" data-testid="posted-net-total">
            {money2(totals.net)}
          </dd>
        </dl>
      ) : null}
    </section>
  );
}
