/**
 * «Kassa / smena tarixi» (07 BO-09, US-M16-03, QT-M16-04; 20 #55): register + period (Bugun / Hafta / Oy /
 * Dan–Gacha) → one row per shift: opening cash, cash sales, put in / taken out, expected and counted cash,
 * variance (with the cashier's note), counted card total; totals below. A row opens the shift panel.
 */
import { useUnit } from "effector-react";
import { Wallet } from "lucide-react";

import { serverErrorText, useTranslation } from "@shared/i18n";
import { formatDateTime, formatMoney } from "@shared/lib/format";
import { compareMoney, money } from "@shared/lib/money";
import {
  Button,
  DataTable,
  EmptyState,
  ErrorState,
  FormField,
  Input,
  SimpleSelect,
  StatusChip,
  cn,
  type DataTableColumn,
} from "@shared/ui";

import {
  $history,
  $historyError,
  $historyStatus,
  $historyTotals,
  $range,
  $rangeInvalid,
  $registerId,
  $registers,
  $registersError,
  $shiftId,
  $today,
  QUICK_RANGES,
  historyReloadRequested,
  matchQuickRange,
  quickRange,
  rangeChanged,
  registerChanged,
  reportOpened,
  shiftSelected,
  type ShiftRow,
} from "../../model/index.ts";
import { ShiftPanel } from "./ShiftPanel.tsx";

const m = (v: string | null) => (v === null ? "—" : formatMoney(v, { withCurrency: false }));

function Variance({ value }: { value: string | null }) {
  if (value === null) return <span>—</span>;
  const sign = compareMoney(money(value), money("0"));
  return (
    <span className={cn("font-extrabold", sign < 0 && "text-destructive", sign > 0 && "text-warning-strong")}>
      {formatMoney(value, { withCurrency: false })}
    </span>
  );
}

export function CashHistory() {
  const { t } = useTranslation("reports");
  const [registers, registersError, registerId, range, rangeInvalid, today] = useUnit([
    $registers,
    $registersError,
    $registerId,
    $range,
    $rangeInvalid,
    $today,
  ]);
  const [rows, status, error, totals, shiftId] = useUnit([
    $history,
    $historyStatus,
    $historyError,
    $historyTotals,
    $shiftId,
  ]);
  const [onRegister, onRange, reload, select, reopen] = useUnit([
    registerChanged,
    rangeChanged,
    historyReloadRequested,
    shiftSelected,
    reportOpened,
  ]);
  const quick = matchQuickRange(range, today);

  if (registersError)
    return <ErrorState message={serverErrorText(registersError)} onRetry={() => reopen("cash-history")} />;

  const columns: DataTableColumn<ShiftRow>[] = [
    {
      id: "shift",
      header: t("cashHistory.columns.shift"),
      width: "90px",
      cell: (r) => <span className="font-bold tabular-nums">№{r.shift_no}</span>,
    },
    {
      id: "opened",
      header: t("cashHistory.columns.period"),
      width: "170px",
      cell: (r) => (
        <div className="flex flex-col text-[12px] tabular-nums">
          <span>{formatDateTime(r.opened_at)}</span>
          <span className="text-muted-foreground">
            {r.closed_at ? formatDateTime(r.closed_at) : t("cashHistory.open")}
          </span>
        </div>
      ),
    },
    {
      id: "status",
      header: t("cashHistory.columns.status"),
      width: "100px",
      cell: (r) => (
        <StatusChip tone={r.status === "open" ? "info" : "neutral"}>
          {t(`cashHistory.status.${r.status}`)}
        </StatusChip>
      ),
    },
    {
      id: "opening",
      header: t("cashHistory.columns.opening"),
      numeric: true,
      cell: (r) => m(r.opening_cash),
    },
    { id: "sales", header: t("cashHistory.columns.cashSales"), numeric: true, cell: (r) => m(r.cash_sales) },
    { id: "in", header: t("cashHistory.columns.cashIn"), numeric: true, cell: (r) => m(r.cash_in) },
    { id: "out", header: t("cashHistory.columns.cashOut"), numeric: true, cell: (r) => m(r.cash_out) },
    {
      id: "expected",
      header: t("cashHistory.columns.expected"),
      numeric: true,
      cell: (r) => m(r.expected_cash),
    },
    {
      id: "counted",
      header: t("cashHistory.columns.counted"),
      numeric: true,
      cell: (r) => m(r.counted_cash),
    },
    {
      id: "variance",
      header: t("cashHistory.columns.variance"),
      numeric: true,
      cell: (r) => (
        <div className="flex flex-col items-end">
          <Variance value={r.variance} />
          {r.variance_note ? (
            <span
              className="max-w-[180px] truncate text-[11px] font-normal text-muted-foreground"
              title={r.variance_note}
            >
              «{r.variance_note}»
            </span>
          ) : null}
        </div>
      ),
    },
    {
      id: "card",
      header: t("cashHistory.columns.card"),
      numeric: true,
      cell: (r) => m(r.counted_card_total),
    },
  ];

  return (
    <div className="flex flex-col gap-3.5">
      <div className="flex flex-wrap items-end gap-3">
        <FormField label={t("cashHistory.register")} className="w-56">
          <SimpleSelect
            options={registers.map((r) => ({ value: r.id, label: r.name }))}
            value={registerId ?? undefined}
            placeholder={t("cashHistory.registerPlaceholder")}
            onValueChange={(v) => onRegister(v)}
          />
        </FormField>
        <div role="group" aria-label={t("cashHistory.quickLabel")} className="flex flex-wrap gap-1.5">
          {QUICK_RANGES.map((k) => (
            <Button
              key={k}
              size="sm"
              variant={quick === k ? "default" : "secondary"}
              aria-pressed={quick === k}
              onClick={() => onRange(quickRange(k, today))}
            >
              {t(`cashHistory.quick.${k}`)}
            </Button>
          ))}
        </div>
        <FormField
          label={t("cashHistory.from")}
          error={rangeInvalid ? t("cashHistory.rangeInvalid") : undefined}
        >
          <Input
            type="date"
            value={range.from}
            max={today}
            className="w-40"
            onChange={(e) => onRange({ ...range, from: e.target.value })}
          />
        </FormField>
        <FormField label={t("cashHistory.to")}>
          <Input
            type="date"
            value={range.to}
            max={today}
            className="w-40"
            onChange={(e) => onRange({ ...range, to: e.target.value })}
          />
        </FormField>
      </div>

      <div className="grid gap-3.5 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="flex min-w-0 flex-col gap-2">
          <DataTable
            label={t("cashHistory.tableLabel")}
            columns={columns}
            data={rows}
            getRowId={(r) => r.shift_id}
            status={status}
            errorMessage={error ? serverErrorText(error) : undefined}
            onRetry={reload}
            onRowClick={(r) => select(r.shift_id)}
            selectedRowId={shiftId}
            minWidth={1100}
            skeletonRows={4}
            empty={<EmptyState icon={Wallet} title={t("cashHistory.empty")} />}
          />
          {rows.length > 0 ? (
            <dl
              role="group"
              aria-label={t("cashHistory.totals")}
              className="flex flex-wrap justify-end gap-x-5 gap-y-1 text-[13px]"
            >
              <dt className="text-foreground-secondary">{t("cashHistory.columns.cashSales")}</dt>
              <dd className="font-extrabold tabular-nums">{formatMoney(totals.cashSales)}</dd>
              <dt className="text-foreground-secondary">{t("cashHistory.columns.cashIn")}</dt>
              <dd className="font-extrabold tabular-nums">{formatMoney(totals.cashIn)}</dd>
              <dt className="text-foreground-secondary">{t("cashHistory.columns.cashOut")}</dt>
              <dd className="font-extrabold tabular-nums">{formatMoney(totals.cashOut)}</dd>
              <dt className="text-foreground-secondary">{t("cashHistory.columns.variance")}</dt>
              <dd className="font-extrabold tabular-nums">{formatMoney(totals.variance)}</dd>
            </dl>
          ) : null}
        </div>
        <ShiftPanel />
      </div>
    </div>
  );
}
