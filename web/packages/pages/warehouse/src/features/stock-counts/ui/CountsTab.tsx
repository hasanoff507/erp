/**
 * BO-03 «Inventarizatsiyalar» tab (07): `GET /stock-counts?status=review` by default; row → detail
 * (kutilgan / sanalgan / farq / summa), «Farqni tasdiqlash» (`stock.count.post`) and «Bekor qilish».
 */
import { useUnit } from "effector-react";
import { ClipboardList } from "lucide-react";

import { useTranslation } from "@shared/i18n";
import { formatDate, formatDateTime } from "@shared/lib/format";
import { DataTable, EmptyState, FormField, SimpleSelect, type DataTableColumn } from "@shared/ui";

import { errorText } from "#/shared/lib/errors.ts";

import {
  $counts,
  $cursor,
  $error,
  $filter,
  $moreLoading,
  $status,
  COUNT_STATUSES,
  countSelected,
  filterChanged,
  isCountStatus,
  moreRequested,
  reloadRequested,
  type CountSummary,
} from "../model/index.ts";

import { CountStatusChip } from "./chips.tsx";
import { CountDetail, type CountRights } from "./CountDetail.tsx";

const ALL = "all";

export function CountsTab({ rights, online }: { rights: CountRights; online: boolean }) {
  const { t } = useTranslation("warehouse");
  const [items, status, error, cursor, moreLoading, filter] = useUnit([
    $counts,
    $status,
    $error,
    $cursor,
    $moreLoading,
    $filter,
  ]);
  const [onFilter, more, reload, select] = useUnit([
    filterChanged,
    moreRequested,
    reloadRequested,
    countSelected,
  ]);

  const columns: DataTableColumn<CountSummary>[] = [
    {
      id: "doc",
      header: t("counts.columns.doc"),
      width: "170px",
      cell: (c) => (
        <span className="flex flex-col">
          <span className="font-semibold">{c.number ?? t("counts.noNumber")}</span>
          <span className="text-[12px] text-muted-foreground">{formatDate(c.doc_date)}</span>
        </span>
      ),
    },
    {
      id: "started",
      header: t("counts.columns.started"),
      width: "150px",
      cell: (c) =>
        c.started_at ? <span className="tabular-nums">{formatDateTime(c.started_at)}</span> : "—",
    },
    {
      id: "progress",
      header: t("counts.columns.progress"),
      cell: (c) => t("counts.progress", { counted: c.counted_count, total: c.line_count }),
    },
    {
      id: "uncounted",
      header: t("counts.columns.uncounted"),
      numeric: true,
      width: "110px",
      cell: (c) =>
        c.uncounted_count > 0 ? <span className="text-warning-strong">{c.uncounted_count}</span> : "0",
    },
    {
      id: "status",
      header: t("counts.columns.status"),
      width: "170px",
      cell: (c) => <CountStatusChip status={c.status} />,
    },
  ];

  return (
    <section className="flex flex-col gap-3" aria-label={t("tabs.counts")}>
      <div className="flex flex-wrap items-end gap-3">
        <FormField label={t("counts.filter")} className="w-56">
          <SimpleSelect
            options={[
              { value: ALL, label: t("counts.allStatuses") },
              ...COUNT_STATUSES.map((s) => ({ value: s, label: t(`counts.status.${s}`) })),
            ]}
            value={filter ?? ALL}
            onValueChange={(v) => onFilter(isCountStatus(v) ? v : null)}
          />
        </FormField>
      </div>
      <DataTable
        label={t("counts.tableLabel")}
        columns={columns}
        data={items}
        getRowId={(c) => c.id}
        status={status}
        errorMessage={error ? errorText(error) : undefined}
        onRetry={reload}
        onRowClick={(c) => select(c.id)}
        minWidth={760}
        empty={
          <EmptyState
            icon={ClipboardList}
            title={t(filter === "review" ? "counts.empty.reviewTitle" : "counts.empty.title")}
            description={t("counts.empty.description")}
          />
        }
        pagination={{ kind: "cursor", hasMore: cursor !== null, loadingMore: moreLoading, onLoadMore: more }}
      />
      <CountDetail rights={rights} online={online} />
    </section>
  );
}
