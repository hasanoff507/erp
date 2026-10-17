/**
 * BO-17 «Xarajatlar» tab (07 BO-17): KPI cards, «toifalar bo'yicha o'tkazilgan» (category, amount, share;
 * total), filters (period, category, source Bank / Karta / Kassa (POS), status incl. «Tasdiq kutmoqda»),
 * the list (date, category + comment, account, branch, source, amount, status, actions: «O'tkazish»,
 * «Bekor qilish»), totals «O'tkazilgan» / «Kutilmoqda» (cancelled excluded — server `totals`).
 */
import { useUnit } from "effector-react";
import { Ban, CheckCircle2, Clock, Inbox, Send, Wallet } from "lucide-react";
import { useState } from "react";

import { useTranslation } from "@shared/i18n";
import { formatDate, formatMoney } from "@shared/lib/format";
import { $branches } from "@shared/state/session";
import {
  Card,
  DataTable,
  EmptyState,
  FormField,
  Input,
  KpiCard,
  SimpleSelect,
  StatusChip,
  type DataTableColumn,
  type DataTableRowAction,
  type Tone,
} from "@shared/ui";

import { errorText } from "#/shared/lib/errors.ts";
import { ReasonDialog } from "#/shared/ui/ReasonDialog.tsx";

import {
  $categories,
  $error,
  $filters,
  $hasMore,
  $moreLoading,
  $rows,
  $shares,
  $status,
  $totals,
  CANCEL_MAX,
  CANCEL_MIN,
  SOURCES,
  STATUS_FILTERS,
  cancelExpenseFx,
  filtersChanged,
  isSource,
  isStatusFilter,
  moreRequested,
  postExpenseFx,
  reloadRequested,
  rowStatus,
  type Expense,
  type RowStatus,
} from "../../model/index.ts";

const ALL = "all";

const STATUS_TONE: Readonly<Record<RowStatus, Tone>> = {
  posted: "success",
  draft: "neutral",
  awaiting: "awaiting-approval",
  cancelled: "destructive",
};

export function ExpensesList({ canAct }: { canAct: boolean }) {
  const { t } = useTranslation("finance");
  const [rows, status, error, filters, hasMore, moreLoading, totals, shares, categories, branches] = useUnit([
    $rows,
    $status,
    $error,
    $filters,
    $hasMore,
    $moreLoading,
    $totals,
    $shares,
    $categories,
    $branches,
  ]);
  const [change, more, reload, post, cancel] = useUnit([
    filtersChanged,
    moreRequested,
    reloadRequested,
    postExpenseFx,
    cancelExpenseFx,
  ]);
  const [cancelling, setCancelling] = useState<Expense | null>(null);
  const branchName = (id: string) => branches.find((b) => b.id === id)?.name ?? "—";

  const columns: DataTableColumn<Expense>[] = [
    {
      id: "date",
      header: t("expenses.list.columns.date"),
      width: "110px",
      cell: (e) => <span className="tabular-nums">{formatDate(e.doc_date)}</span>,
    },
    {
      id: "category",
      header: t("expenses.list.columns.category"),
      cell: (e) => (
        <span className="flex flex-col">
          <span className="font-semibold">{e.category_name}</span>
          {e.comment ? <span className="text-[12px] text-foreground-secondary">{e.comment}</span> : null}
        </span>
      ),
    },
    {
      id: "account",
      header: t("expenses.list.columns.account"),
      width: "90px",
      cell: (e) => (
        <span title={t(`accounts.${e.account}`, { defaultValue: e.account })} className="tabular-nums">
          {e.account}
        </span>
      ),
    },
    {
      id: "branch",
      header: t("expenses.list.columns.branch"),
      width: "140px",
      cell: (e) => branchName(e.branch_id),
    },
    {
      id: "source",
      header: t("expenses.list.columns.source"),
      width: "120px",
      cell: (e) => t(`expenses.sources.${e.source}`),
    },
    {
      id: "amount",
      header: t("expenses.list.columns.amount"),
      numeric: true,
      width: "140px",
      cell: (e) => formatMoney(e.amount, { withCurrency: false }),
    },
    {
      id: "status",
      header: t("expenses.list.columns.status"),
      width: "150px",
      cell: (e) => {
        const s = rowStatus(e);
        return (
          <StatusChip tone={STATUS_TONE[s]} dot>
            {t(`expenses.status.${s}`)}
          </StatusChip>
        );
      },
    },
  ];

  const actions = (e: Expense): DataTableRowAction<Expense>[] => {
    if (!canAct) return [];
    const list: DataTableRowAction<Expense>[] = [];
    if (e.status === "draft" && e.approval_status !== "pending")
      list.push({
        id: "post",
        label: t("expenses.actions.post"),
        icon: Send,
        onSelect: (row) => void post(row.id),
      });
    if (e.status !== "cancelled")
      list.push({
        id: "cancel",
        label: t("expenses.actions.cancel"),
        icon: Ban,
        destructive: true,
        onSelect: setCancelling,
      });
    return list;
  };

  return (
    <div className="flex flex-col gap-[18px]">
      <div className="grid gap-3.5 sm:grid-cols-3">
        <KpiCard
          label={t("expenses.kpi.posted")}
          value={formatMoney(totals.posted)}
          icon={CheckCircle2}
          tone="success"
          note={t("expenses.kpi.postedNote")}
        />
        <KpiCard
          label={t("expenses.kpi.pending")}
          value={formatMoney(totals.draft)}
          icon={Clock}
          tone="warning"
          note={t("expenses.kpi.pendingNote")}
        />
        <KpiCard
          label={t("expenses.kpi.count")}
          value={String(rows.length)}
          icon={Wallet}
          tone="info"
          note={t("expenses.kpi.countNote")}
        />
      </div>

      <Card role="region" aria-labelledby="expense-shares-title" className="flex flex-col gap-2.5">
        <div>
          <h2 id="expense-shares-title" className="text-[15px] font-bold">
            {t("expenses.shares.title")}
          </h2>
          <p className="text-[12px] text-foreground-secondary">{t("expenses.shares.subtitle")}</p>
        </div>
        {shares.items.length === 0 ? (
          <p className="text-small text-foreground-secondary">{t("expenses.shares.empty")}</p>
        ) : (
          <ul className="flex flex-col gap-1.5" data-testid="expense-shares">
            {shares.items.map((s) => (
              <li
                key={s.categoryId}
                className="grid grid-cols-[1fr_auto_56px] items-center gap-3 text-[13px]"
              >
                <span className="truncate font-semibold">{s.name}</span>
                <span className="tabular-nums">{formatMoney(s.amount, { withCurrency: false })}</span>
                <span className="text-right tabular-nums text-foreground-secondary">{s.pct}%</span>
              </li>
            ))}
            <li className="grid grid-cols-[1fr_auto_56px] gap-3 border-t border-border pt-1.5 text-[13px] font-extrabold">
              <span>{t("expenses.shares.total")}</span>
              <span className="tabular-nums">{formatMoney(shares.total)}</span>
              <span />
            </li>
          </ul>
        )}
        <p className="text-[12px] text-foreground-secondary">{t("expenses.shares.posNote")}</p>
      </Card>

      <section aria-labelledby="expense-list-title" className="flex flex-col gap-3">
        <div className="flex flex-wrap items-end gap-3">
          <h2 id="expense-list-title" className="min-w-0 flex-1 text-h2">
            {t("expenses.list.title")}
          </h2>
          <FormField label={t("expenses.filters.from")} className="w-40">
            <Input
              type="date"
              value={filters.from}
              onChange={(e) => e.target.value && change({ from: e.target.value })}
            />
          </FormField>
          <FormField label={t("expenses.filters.to")} className="w-40">
            <Input
              type="date"
              value={filters.to}
              onChange={(e) => e.target.value && change({ to: e.target.value })}
            />
          </FormField>
          <FormField label={t("expenses.filters.category")} className="w-48">
            <SimpleSelect
              options={[
                { value: ALL, label: t("expenses.filters.allCategories") },
                ...categories.map((c) => ({ value: c.id, label: c.name })),
              ]}
              value={filters.categoryId ?? ALL}
              onValueChange={(v) => change({ categoryId: v === ALL ? null : v })}
            />
          </FormField>
          <FormField label={t("expenses.filters.source")} className="w-44">
            <SimpleSelect
              options={[
                { value: ALL, label: t("expenses.filters.allSources") },
                ...SOURCES.map((s) => ({ value: s, label: t(`expenses.sources.${s}`) })),
              ]}
              value={filters.source ?? ALL}
              onValueChange={(v) => change({ source: isSource(v) ? v : null })}
            />
          </FormField>
          <FormField label={t("expenses.filters.status")} className="w-48">
            <SimpleSelect
              options={[
                { value: ALL, label: t("expenses.filters.allStatuses") },
                ...STATUS_FILTERS.map((s) => ({ value: s, label: t(`expenses.status.${s}`) })),
              ]}
              value={filters.status ?? ALL}
              onValueChange={(v) => change({ status: isStatusFilter(v) ? v : null })}
            />
          </FormField>
        </div>
        <DataTable
          label={t("expenses.list.title")}
          columns={columns}
          data={rows}
          getRowId={(e) => e.id}
          status={status}
          errorMessage={error ? errorText(error) : undefined}
          onRetry={reload}
          rowActions={canAct ? actions : undefined}
          minWidth={900}
          skeletonRows={5}
          empty={
            <EmptyState
              icon={Inbox}
              title={t("expenses.list.empty")}
              description={t("expenses.list.emptyHint")}
            />
          }
          pagination={{ kind: "cursor", hasMore, loadingMore: moreLoading, onLoadMore: more }}
        />
        <div className="flex flex-wrap items-center justify-end gap-x-6 gap-y-1 text-[13px]">
          <span className="text-foreground-secondary">{t("expenses.list.cancelledNote")}</span>
          <dl role="group" aria-label={t("expenses.list.totals")} className="flex gap-x-6">
            <div className="flex gap-1.5">
              <dt className="text-foreground-secondary">{t("expenses.list.totalPosted")}</dt>
              <dd className="font-extrabold tabular-nums" data-testid="total-posted">
                {formatMoney(totals.posted)}
              </dd>
            </div>
            <div className="flex gap-1.5">
              <dt className="text-foreground-secondary">{t("expenses.list.totalPending")}</dt>
              <dd className="font-extrabold tabular-nums" data-testid="total-pending">
                {formatMoney(totals.draft)}
              </dd>
            </div>
          </dl>
        </div>
      </section>

      <ReasonDialog
        open={cancelling !== null}
        onOpenChange={(open) => (open ? undefined : setCancelling(null))}
        title={t("expenses.cancel.title")}
        description={
          cancelling
            ? t("expenses.cancel.description", {
                category: cancelling.category_name,
                amount: formatMoney(cancelling.amount),
              })
            : undefined
        }
        minLength={CANCEL_MIN}
        maxLength={CANCEL_MAX}
        onConfirm={async (reason) => {
          if (!cancelling) return;
          await cancel({ id: cancelling.id, reason });
          setCancelling(null);
        }}
      />
    </div>
  );
}
