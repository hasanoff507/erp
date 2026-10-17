/**
 * «Takrorlanuvchi» tab (20 #48–#51): rules with category, amount, period / day, source, next due date,
 * active switch (`PATCH {is_active, version}`), «Tasdiqlash» when due. New rules come from the «Yangi
 * xarajat» form («Takrorlanish davri»).
 */
import { useUnit } from "effector-react";
import { Repeat } from "lucide-react";

import { useTranslation } from "@shared/i18n";
import { formatDate, formatMoney } from "@shared/lib/format";
import { Button, DataTable, EmptyState, StatusChip, Switch, type DataTableColumn } from "@shared/ui";

import {
  $categories,
  $rules,
  $rulesStatus,
  confirmRuleFx,
  ruleTitle,
  rulesReloadRequested,
  updateRuleFx,
  type Rule,
} from "../../model/index.ts";

export function RecurringTab({ canAct }: { canAct: boolean }) {
  const { t } = useTranslation("finance");
  const [rules, status, categories, confirmPending, updatePending] = useUnit([
    $rules,
    $rulesStatus,
    $categories,
    confirmRuleFx.pending,
    updateRuleFx.pending,
  ]);
  const [confirm, update, reload] = useUnit([confirmRuleFx, updateRuleFx, rulesReloadRequested]);

  const columns: DataTableColumn<Rule>[] = [
    {
      id: "name",
      header: t("expenses.recurring.columns.name"),
      cell: (r) => (
        <span className="flex flex-col">
          <span className="font-semibold">{ruleTitle(r, categories)}</span>
          <span className="text-[12px] text-foreground-secondary">
            {categories.find((c) => c.id === r.category_id)?.name ?? ""}
          </span>
        </span>
      ),
    },
    {
      id: "amount",
      header: t("expenses.recurring.columns.amount"),
      numeric: true,
      width: "140px",
      cell: (r) => formatMoney(r.amount, { withCurrency: false }),
    },
    {
      id: "period",
      header: t("expenses.recurring.columns.period"),
      width: "170px",
      cell: (r) =>
        t("expenses.recurring.every", { period: t(`expenses.periods.${r.period}`), day: r.day_of_month }),
    },
    {
      id: "source",
      header: t("expenses.recurring.columns.source"),
      width: "110px",
      cell: (r) => t(`expenses.sources.${r.source}`),
    },
    {
      id: "next",
      header: t("expenses.recurring.columns.next"),
      width: "150px",
      cell: (r) =>
        r.is_due && r.is_active ? (
          <StatusChip tone="warning" dot>
            {t("expenses.recurring.due")}
          </StatusChip>
        ) : (
          <span className="tabular-nums">{formatDate(r.next_due_date)}</span>
        ),
    },
    {
      id: "active",
      header: t("expenses.recurring.columns.active"),
      width: "90px",
      cell: (r) => (
        <Switch
          checked={r.is_active}
          disabled={!canAct || updatePending}
          aria-label={t("expenses.recurring.toggle", { name: ruleTitle(r, categories) })}
          onCheckedChange={(on) =>
            void update({ id: r.id, body: { is_active: on, version: r.version } }).catch(() => undefined)
          }
        />
      ),
    },
    {
      id: "action",
      header: t("expenses.recurring.columns.action"),
      hideHeader: true,
      width: "130px",
      cell: (r) =>
        canAct && r.is_due && r.is_active ? (
          <Button
            size="sm"
            disabled={confirmPending}
            onClick={() => void confirm(r.id).catch(() => undefined)}
          >
            {t("expenses.reminders.confirm")}
          </Button>
        ) : null,
    },
  ];

  return (
    <DataTable
      label={t("expenses.recurring.title")}
      columns={columns}
      data={rules}
      getRowId={(r) => r.id}
      status={status}
      onRetry={reload}
      minWidth={860}
      skeletonRows={3}
      empty={
        <EmptyState
          icon={Repeat}
          title={t("expenses.recurring.empty")}
          description={t("expenses.recurring.emptyHint")}
        />
      }
    />
  );
}
