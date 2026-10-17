/**
 * BO-08 «Provodkalar» (07): sana, hujjat (raqam + filial), mazmun, Dt, Kt, summa (2 dp — buxgalteriya
 * hisoboti, 08 §8); jami qatori «Dt oboroti = Kt oboroti»; cursor «Yana yuklash» (17 §4).
 */
import { useUnit } from "effector-react";
import { BookOpen } from "lucide-react";

import { serverErrorText, useTranslation } from "@shared/i18n";
import { formatDate, formatMoney } from "@shared/lib/format";
import { $branches } from "@shared/state/session";
import { DataTable, EmptyState, StatusChip, type DataTableColumn } from "@shared/ui";

import {
  $cursor,
  $entries,
  $error,
  $filters,
  $moreLoading,
  $status,
  $turnover,
  isAccountCode,
  isDocType,
  moreRequested,
  reloadRequested,
  type LedgerEntry,
} from "../../model/index.ts";

function Account({ code }: { code: string }) {
  const { t } = useTranslation("finance");
  return (
    <span className="flex flex-col">
      <span className="font-extrabold tabular-nums">{code}</span>
      {isAccountCode(code) ? (
        <span className="text-[11px] font-normal text-muted-foreground">{t(`accounts.${code}`)}</span>
      ) : null}
    </span>
  );
}

export function JournalTable() {
  const { t } = useTranslation("finance");
  const [entries, status, error, cursor, moreLoading, turnover, filters, branches] = useUnit([
    $entries,
    $status,
    $error,
    $cursor,
    $moreLoading,
    $turnover,
    $filters,
    $branches,
  ]);
  const [more, retry] = useUnit([moreRequested, reloadRequested]);
  const branchName = (id: string | null) =>
    id === null ? t("journal.table.allBranches") : (branches.find((b) => b.id === id)?.name ?? "—");
  const docTypeLabel = (type: string) => (isDocType(type) ? t(`docTypes.${type}`) : type);

  const columns: DataTableColumn<LedgerEntry>[] = [
    {
      id: "date",
      header: t("journal.table.date"),
      width: "110px",
      cell: (e) => <span className="tabular-nums">{formatDate(e.entry_date)}</span>,
    },
    {
      id: "doc",
      header: t("journal.table.doc"),
      width: "190px",
      cell: (e) => (
        <span className="flex flex-col">
          <span className="font-semibold">{e.doc_number ?? t("journal.table.noNumber")}</span>
          <span className="text-[12px] text-muted-foreground">{branchName(e.branch_id)}</span>
        </span>
      ),
    },
    {
      id: "content",
      header: t("journal.table.content"),
      cell: (e) => (
        <span className="flex flex-wrap items-center gap-1.5">
          {docTypeLabel(e.doc_type)}
          {e.reversal_of_id ? <StatusChip tone="warning">{t("journal.table.reversal")}</StatusChip> : null}
        </span>
      ),
    },
    { id: "dt", header: t("journal.table.dt"), width: "150px", cell: (e) => <Account code={e.account_dt} /> },
    { id: "kt", header: t("journal.table.kt"), width: "150px", cell: (e) => <Account code={e.account_kt} /> },
    {
      id: "amount",
      header: t("journal.table.amount"),
      numeric: true,
      width: "160px",
      cell: (e) => formatMoney(e.amount, { precision: 2, withCurrency: false }),
    },
  ];

  return (
    <section className="flex flex-col gap-2.5" aria-labelledby="journal-table-title">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h2 id="journal-table-title" className="text-h2">
          {t("journal.table.title")}
        </h2>
        {filters.dateFrom && filters.dateTo ? (
          <p className="text-small text-foreground-secondary">
            {t("journal.table.caption", {
              from: formatDate(filters.dateFrom),
              to: formatDate(filters.dateTo),
              count: entries.length,
            })}
          </p>
        ) : null}
      </div>
      <DataTable
        label={t("journal.table.label")}
        columns={columns}
        data={entries}
        getRowId={(e) => e.id}
        status={status}
        errorMessage={error ? serverErrorText(error) : undefined}
        onRetry={retry}
        minWidth={860}
        empty={
          <EmptyState
            icon={BookOpen}
            title={t("journal.table.empty.title")}
            description={t("journal.table.empty.description")}
          />
        }
        pagination={{ kind: "cursor", hasMore: cursor !== null, loadingMore: moreLoading, onLoadMore: more }}
      />
      {entries.length > 0 ? (
        <div
          className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-lg border border-border bg-muted px-4 py-3"
          aria-label={t("journal.table.turnover")}
          role="group"
        >
          <span className="text-[14px] font-bold">{t("journal.table.total")}</span>
          <span className="text-small text-foreground-secondary">
            {t("journal.table.turnover")} · {t("journal.table.totalHint", { count: entries.length })}
          </span>
          <span className="grow" />
          <span className="text-[16px] font-extrabold tabular-nums" data-testid="journal-turnover">
            {formatMoney(turnover, { precision: 2 })}
          </span>
        </div>
      ) : null}
    </section>
  );
}
