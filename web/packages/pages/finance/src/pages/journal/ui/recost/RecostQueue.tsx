/**
 * «Qayta hisoblash navbati» (07 BO-08, qaror #56c, 19 §18): recost jobs — tovar, ombor, sanadan, holat,
 * urinish, navbatga qo'yilgan, tugagan, xato; «Qayta urinish» for a failed job (`accounting.post`).
 */
import { useUnit } from "effector-react";
import { ListRestart, RotateCcw, TriangleAlert } from "lucide-react";

import { serverErrorText, useTranslation } from "@shared/i18n";
import { formatDate, formatDateTime } from "@shared/lib/format";
import {
  Banner,
  Button,
  Card,
  DataTable,
  EmptyState,
  FormField,
  Icon,
  SimpleSelect,
  StatusChip,
  type DataTableColumn,
  type Tone,
} from "@shared/ui";

import {
  $productNames,
  $recostCursor,
  $recostError,
  $recostFilter,
  $recostJobs,
  $recostMoreLoading,
  $recostStatus,
  $retryError,
  $retrying,
  $warehouseNames,
  ALL,
  RECOST_STATUSES,
  isRecostStatus,
  isRetryable,
  recostFilterChanged,
  recostMoreRequested,
  recostReloadRequested,
  recostRetryDismissed,
  recostRetryRequested,
  type RecostJob,
} from "../../model/index.ts";

const STATUS_TONE: Readonly<Record<string, Tone>> = {
  queued: "info",
  running: "primary",
  done: "success",
  failed: "destructive",
  rejected_period_closed: "neutral",
};

export function RecostQueue({ canRetry, online }: { canRetry: boolean; online: boolean }) {
  const { t } = useTranslation("finance");
  const { t: tc } = useTranslation("common");
  const [jobs, status, error, cursor, moreLoading, filter, retrying, retryError, products, warehouses] =
    useUnit([
      $recostJobs,
      $recostStatus,
      $recostError,
      $recostCursor,
      $recostMoreLoading,
      $recostFilter,
      $retrying,
      $retryError,
      $productNames,
      $warehouseNames,
    ]);
  const [onFilter, more, reload, retry, dismiss] = useUnit([
    recostFilterChanged,
    recostMoreRequested,
    recostReloadRequested,
    recostRetryRequested,
    recostRetryDismissed,
  ]);
  const productName = (job: RecostJob) => products[job.product_id] ?? t("recost.unknown");
  const statusLabel = (value: string) => (isRecostStatus(value) ? t(`recost.status.${value}`) : value);

  const columns: DataTableColumn<RecostJob>[] = [
    { id: "product", header: t("recost.columns.product"), cell: (j) => productName(j) },
    {
      id: "warehouse",
      header: t("recost.columns.warehouse"),
      width: "140px",
      cell: (j) => warehouses[j.warehouse_id] ?? t("recost.unknown"),
    },
    {
      id: "from",
      header: t("recost.columns.from"),
      width: "105px",
      cell: (j) => <span className="tabular-nums">{formatDate(j.from_date)}</span>,
    },
    {
      id: "status",
      header: t("recost.columns.status"),
      width: "140px",
      cell: (j) => <StatusChip tone={STATUS_TONE[j.status] ?? "neutral"}>{statusLabel(j.status)}</StatusChip>,
    },
    {
      id: "attempts",
      header: t("recost.columns.attempts"),
      numeric: true,
      width: "80px",
      cell: (j) => j.attempts,
    },
    {
      id: "created",
      header: t("recost.columns.created"),
      width: "140px",
      cell: (j) => <span className="tabular-nums">{formatDateTime(j.created_at)}</span>,
    },
    {
      id: "finished",
      header: t("recost.columns.finished"),
      width: "140px",
      cell: (j) =>
        j.finished_at ? <span className="tabular-nums">{formatDateTime(j.finished_at)}</span> : "—",
    },
    {
      id: "error",
      header: t("recost.columns.error"),
      // last_error is raw backend exception text (19 §18): never shown, not even as a tooltip (08 §11).
      cell: (j) =>
        j.last_error ? (
          <span className="text-[12px] text-destructive-strong">{t("recost.failedGeneric")}</span>
        ) : (
          "—"
        ),
    },
    ...(canRetry
      ? [
          {
            id: "action",
            header: t("recost.columns.action"),
            hideHeader: true,
            width: "150px",
            cell: (j: RecostJob) =>
              isRetryable(j) ? (
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={!online || retrying.includes(j.id)}
                  aria-busy={retrying.includes(j.id) || undefined}
                  aria-label={t("recost.retryFor", { name: productName(j) })}
                  onClick={() => retry(j.id)}
                >
                  <Icon as={RotateCcw} size="sm" />
                  {t("recost.retry")}
                </Button>
              ) : null,
          } satisfies DataTableColumn<RecostJob>,
        ]
      : []),
  ];

  return (
    <Card role="region" className="flex flex-col gap-3" aria-labelledby="recost-title">
      <div className="flex flex-wrap items-end gap-3">
        <div className="min-w-0 flex-1">
          <h2 id="recost-title" className="text-h2">
            {t("recost.title")}
          </h2>
          <p className="text-small text-foreground-secondary">{t("recost.subtitle")}</p>
        </div>
        <FormField label={t("recost.filter")} className="w-56">
          <SimpleSelect
            options={[
              { value: ALL, label: t("recost.allStatuses") },
              ...RECOST_STATUSES.map((s) => ({ value: s, label: statusLabel(s) })),
            ]}
            value={filter ?? ALL}
            onValueChange={(v) => onFilter(isRecostStatus(v) ? v : null)}
          />
        </FormField>
      </div>
      {retryError ? (
        <Banner
          tone="destructive"
          icon={TriangleAlert}
          live="assertive"
          action={
            <Button size="sm" variant="secondary" onClick={() => dismiss()}>
              {tc("actions.close")}
            </Button>
          }
        >
          {serverErrorText(retryError)}
        </Banner>
      ) : null}
      <DataTable
        label={t("recost.tableLabel")}
        columns={columns}
        data={jobs}
        getRowId={(j) => j.id}
        status={status}
        errorMessage={error ? serverErrorText(error) : undefined}
        onRetry={reload}
        minWidth={1040}
        skeletonRows={3}
        empty={
          <EmptyState
            icon={ListRestart}
            title={t("recost.empty.title")}
            description={t("recost.empty.description")}
          />
        }
        pagination={{ kind: "cursor", hasMore: cursor !== null, loadingMore: moreLoading, onLoadMore: more }}
      />
    </Card>
  );
}
