/**
 * BO-06 debtor table (07 BO-06 «Joylashuv»): customer (phone), debt, limit (+ «oshgan (offline)»), last payment
 * (amount, date), promise date chip (bugun / o'tdi / sana / belgilanmagan), days overdue, doubtful flag.
 * Client-side pages of 20 with «ko'rsatilganlar jami».
 */
import { useUnit } from "effector-react";
import { Flag } from "lucide-react";

import { useTranslation } from "@shared/i18n";
import { formatDate, formatMoney, formatPhone } from "@shared/lib/format";
import type { AgingRow } from "@shared/models";
import { DataTable, Icon, StatusChip, type DataTableColumn, type Tone } from "@shared/ui";

import { overLimit, promiseOf, promiseState, type PromiseState } from "#/entities/debtor/index.ts";
import { errorText } from "#/shared/lib/errors.ts";

import {
  $direction,
  $error,
  $page,
  $pageRows,
  $selectedId,
  $status,
  $today,
  $visible,
  $visibleTotal,
  PAGE_SIZE,
  pageChanged,
  reloadRequested,
  rowSelected,
} from "../../model/index.ts";

const PROMISE_TONE: Record<PromiseState, Tone> = {
  today: "warning",
  overdue: "destructive",
  future: "neutral",
  none: "neutral",
};

function PromiseChip({ row, today }: { row: AgingRow; today: string }) {
  const { t } = useTranslation("debts");
  const state = promiseState(row, today);
  const date = promiseOf(row);
  return (
    <StatusChip tone={PROMISE_TONE[state]}>
      {state === "none"
        ? t("table.promiseNone")
        : t(`table.promise.${state}`, { date: date ? formatDate(date) : "" })}
    </StatusChip>
  );
}

export function DebtorsTable() {
  const { t } = useTranslation("debts");
  const [rows, visible, total, page, status, error, selectedId, today, direction, select, setPage, reload] =
    useUnit([
      $pageRows,
      $visible,
      $visibleTotal,
      $page,
      $status,
      $error,
      $selectedId,
      $today,
      $direction,
      rowSelected,
      pageChanged,
      reloadRequested,
    ]);
  const payable = direction === "payable";
  const columns: DataTableColumn<AgingRow>[] = [
    {
      id: "name",
      header: payable ? t("table.supplier") : t("table.customer"),
      cell: (r) => (
        <div className="flex min-w-0 flex-col">
          <span className="flex items-center gap-1.5 font-bold" data-testid="debtor-name">
            {r.name}
            {r.doubtful_flag ? (
              <span title={t("table.doubtful")}>
                <Icon as={Flag} size="sm" className="text-destructive" />
              </span>
            ) : null}
          </span>
          <span className="text-[12px] text-muted-foreground">{r.phone ? formatPhone(r.phone) : "—"}</span>
        </div>
      ),
    },
    {
      id: "balance",
      header: t("table.debt"),
      numeric: true,
      cell: (r) => (
        <span data-testid="debtor-balance">{formatMoney(r.balance, { withCurrency: false })}</span>
      ),
    },
    ...(payable
      ? []
      : [
          {
            id: "limit",
            header: t("table.limit"),
            numeric: true,
            cell: (r: AgingRow) => (
              <span className="flex flex-col items-end">
                {r.credit_limit ? formatMoney(r.credit_limit, { withCurrency: false }) : t("table.noLimit")}
                {r.limit_exceeded_offline || overLimit(r) ? (
                  <StatusChip tone="destructive">
                    {r.limit_exceeded_offline ? t("table.overOffline") : t("table.over")}
                  </StatusChip>
                ) : null}
              </span>
            ),
          } satisfies DataTableColumn<AgingRow>,
        ]),
    {
      id: "lastPayment",
      header: t("table.lastPayment"),
      cell: (r) =>
        r.last_payment_amount ? (
          <span className="flex flex-col text-[13px]">
            <span className="font-bold">{formatMoney(r.last_payment_amount, { withCurrency: false })}</span>
            <span className="text-muted-foreground">
              {r.last_payment_date ? formatDate(r.last_payment_date) : ""}
            </span>
          </span>
        ) : (
          <span className="text-muted-foreground">—</span>
        ),
    },
    { id: "promise", header: t("table.promise.title"), cell: (r) => <PromiseChip row={r} today={today} /> },
    {
      id: "days",
      header: t("table.days"),
      numeric: true,
      cell: (r) => <span data-testid="debtor-days">{r.days_overdue}</span>,
    },
  ];
  return (
    <div className="flex flex-col gap-2">
      <DataTable
        label={t("table.label")}
        columns={columns}
        data={rows}
        getRowId={(r) => r.counterparty_id}
        status={status === "loading" && rows.length > 0 ? "idle" : status}
        errorMessage={error ? errorText(error) : undefined}
        onRetry={() => reload()}
        onRowClick={(r) => select(r.counterparty_id)}
        selectedRowId={selectedId}
        empty={<p className="py-8 text-center text-muted-foreground">{t("table.empty")}</p>}
        pagination={
          visible.length > PAGE_SIZE
            ? { kind: "page", page, size: PAGE_SIZE, total: visible.length, onPageChange: setPage }
            : undefined
        }
        minWidth={720}
      />
      <p className="text-[13px] text-foreground-secondary" data-testid="debtors-footer">
        {t("table.footer", { n: visible.length, amount: formatMoney(total) })}
      </p>
    </div>
  );
}
