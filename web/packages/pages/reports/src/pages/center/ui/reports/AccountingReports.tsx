/**
 * BO-09 «Moliya» M11 statements (Bosqich 5, US-M11-02):
 * - «Sinov balansi» (`/reports/trial-balance?period=`, 20 #11) — per account: opening, Dt / Kt turnover,
 *   closing (debit-positive in the API; shown unsigned in the Dt / Kt column of its side); totals Σ Dt = Σ Kt.
 * - «Buxgalteriya balansi» (`/reports/balance-sheet?as_of=`, 20 #13) — aktiv / majburiyat / kapital lines,
 *   totals (always equal, QT-M11-12); an unresolved 0000 opening is warned («Boshlang'ich qoldiqlar to'liq
 *   kiritilmagan»).
 * - «Ombor qoldig'i (sana holatiga)» (`/reports/stock-as-of?as_of=`, 20 #13a, ACC-09) — stock by document date
 *   and its comparison with the 2910 / 2920 ledger balance.
 */
import { useUnit } from "effector-react";
import { Landmark, Scale, TriangleAlert } from "lucide-react";

import { useTranslation } from "@shared/i18n";
import { formatMoney, formatQty } from "@shared/lib/format";
import { compareMoney, money } from "@shared/lib/money";
import { Banner, Card, DataTable, FormField, Input, KpiCard, cn, type DataTableColumn } from "@shared/ui";

import {
  $range,
  $today,
  monthRange,
  rangeChanged,
  type BalanceSheet,
  type StockAsOf,
  type TrialBalance,
} from "../../model/index.ts";
import { BranchFilter, PeriodFilter } from "../filters/Filters.tsx";
import { KpiGrid, ReportBody, Strong, Toolbar } from "./common.tsx";

const money2 = (v: string) => formatMoney(v, { precision: 2, withCurrency: false });
const ZERO = money("0");

/** Debit-positive signed balance → the amount in its own column (Dt or Kt), the other one empty. */
function split(signed: string): { dt: string; kt: string } {
  const cmp = compareMoney(money(signed), ZERO);
  if (cmp === 0) return { dt: "", kt: "" };
  return cmp > 0 ? { dt: money2(signed), kt: "" } : { dt: "", kt: money2(signed.replace(/^-/, "")) };
}

function MonthFilter() {
  const { t } = useTranslation("reports");
  const [range, today, onRange] = useUnit([$range, $today, rangeChanged]);
  return (
    <FormField label={t("m11.month")}>
      <Input
        type="month"
        value={range.to.slice(0, 7)}
        max={today.slice(0, 7)}
        className="w-44"
        data-testid="tb-month"
        onChange={(e) => (e.target.value ? onRange(monthRange(e.target.value, today)) : undefined)}
      />
    </FormField>
  );
}

type TbRow = TrialBalance["rows"][number] | { account: "total"; name: string; total: TrialBalance["totals"] };

function TrialBalanceView({ data }: { data: TrialBalance }) {
  const { t } = useTranslation("reports");
  const rows: TbRow[] = [...data.rows, { account: "total", name: t("m11.total"), total: data.totals }];
  const isTotal = (r: TbRow): r is Extract<TbRow, { account: "total" }> => r.account === "total";
  const columns: DataTableColumn<TbRow>[] = [
    {
      id: "account",
      header: t("m11.tb.account"),
      cell: (r) =>
        isTotal(r) ? (
          <Strong on>{r.name}</Strong>
        ) : (
          <span className="flex flex-col">
            <span className="font-extrabold tabular-nums">{r.account}</span>
            <span className="text-[12px] text-muted-foreground">{r.name}</span>
          </span>
        ),
    },
    {
      id: "openDt",
      header: t("m11.tb.openingDt"),
      numeric: true,
      cell: (r) => (isTotal(r) ? "" : split(r.opening_balance).dt),
    },
    {
      id: "openKt",
      header: t("m11.tb.openingKt"),
      numeric: true,
      cell: (r) => (isTotal(r) ? "" : split(r.opening_balance).kt),
    },
    {
      id: "dt",
      header: t("m11.tb.debit"),
      numeric: true,
      cell: (r) => <Strong on={isTotal(r)}>{money2(isTotal(r) ? r.total.debit_turnover : r.debit_turnover)}</Strong>,
    },
    {
      id: "kt",
      header: t("m11.tb.credit"),
      numeric: true,
      cell: (r) => (
        <Strong on={isTotal(r)}>{money2(isTotal(r) ? r.total.credit_turnover : r.credit_turnover)}</Strong>
      ),
    },
    {
      id: "closeDt",
      header: t("m11.tb.closingDt"),
      numeric: true,
      cell: (r) => (isTotal(r) ? "" : split(r.closing_balance).dt),
    },
    {
      id: "closeKt",
      header: t("m11.tb.closingKt"),
      numeric: true,
      cell: (r) => (isTotal(r) ? "" : split(r.closing_balance).kt),
    },
  ];
  const balanced = data.totals.debit_turnover === data.totals.credit_turnover;
  return (
    <>
      <KpiGrid label={t("report.kpiLabel")}>
        <KpiCard
          label={t("m11.tb.turnover")}
          value={formatMoney(data.totals.debit_turnover, { precision: 2 })}
          icon={Scale}
          tone={balanced ? "success" : "destructive"}
          note={balanced ? t("m11.tb.balanced") : t("m11.tb.unbalanced")}
        />
      </KpiGrid>
      <DataTable
        label={t("center.items.trial-balance.title")}
        columns={columns}
        data={rows}
        getRowId={(r) => r.account}
        minWidth={980}
      />
    </>
  );
}

function StatementSection({
  title,
  lines,
  total,
  testId,
}: {
  title: string;
  lines: BalanceSheet["assets"];
  total?: { label: string; value: string };
  testId: string;
}) {
  return (
    <Card className="flex flex-col gap-1" data-testid={testId}>
      <h3 className="text-[15px] font-bold">{title}</h3>
      <dl aria-label={title}>
        {lines.map((l) => (
          <div
            key={l.account}
            className="flex items-baseline justify-between gap-3 border-b border-divider py-2 text-[14px] last:border-0"
          >
            <dt>
              <span className="font-bold tabular-nums">{l.account}</span> {l.name}
            </dt>
            <dd className="font-semibold tabular-nums">{money2(l.amount)}</dd>
          </div>
        ))}
        {total ? (
          <div className="flex items-baseline justify-between gap-3 pt-2 text-[14px]">
            <dt className="font-extrabold">{total.label}</dt>
            <dd className="font-extrabold tabular-nums">{money2(total.value)}</dd>
          </div>
        ) : null}
      </dl>
    </Card>
  );
}

function BalanceSheetView({ data }: { data: BalanceSheet }) {
  const { t } = useTranslation("reports");
  return (
    <>
      {data.opening_balance_unresolved || data.warnings.length > 0 ? (
        <Banner tone="warning" icon={TriangleAlert}>
          <span data-testid="bs-opening-warning">
            {t("m11.bs.openingWarning", { amount: formatMoney(data.opening_0000_balance, { precision: 2 }) })}
          </span>
        </Banner>
      ) : null}
      <KpiGrid label={t("report.kpiLabel")}>
        <KpiCard
          label={t("m11.bs.totalAssets")}
          value={formatMoney(data.total_assets, { precision: 2 })}
          icon={Landmark}
          tone="primary"
        />
        <KpiCard
          label={t("m11.bs.totalLiabilitiesEquity")}
          value={formatMoney(data.total_liabilities_and_equity, { precision: 2 })}
          icon={Scale}
          tone="info"
        />
      </KpiGrid>
      <div className="grid gap-3.5 lg:grid-cols-2">
        <StatementSection
          title={t("m11.bs.assets")}
          lines={data.assets}
          total={{ label: t("m11.bs.totalAssets"), value: data.total_assets }}
          testId="bs-assets"
        />
        <div className="flex flex-col gap-3.5">
          <StatementSection title={t("m11.bs.liabilities")} lines={data.liabilities} testId="bs-liabilities" />
          <StatementSection
            title={t("m11.bs.equity")}
            lines={data.equity}
            total={{ label: t("m11.bs.totalLiabilitiesEquity"), value: data.total_liabilities_and_equity }}
            testId="bs-equity"
          />
        </div>
      </div>
    </>
  );
}

type StockItem = StockAsOf["items"][number];
type StockAccount = StockAsOf["accounts"][number];

function StockAsOfView({ data }: { data: StockAsOf }) {
  const { t } = useTranslation("reports");
  const accountColumns: DataTableColumn<StockAccount>[] = [
    { id: "account", header: t("m11.stock.account"), cell: (a) => <span className="font-extrabold">{a.account}</span> },
    { id: "stock", header: t("m11.stock.stockValue"), numeric: true, cell: (a) => money2(a.stock_value) },
    {
      id: "ledger",
      header: t("m11.stock.ledgerValue"),
      numeric: true,
      cell: (a) => (a.ledger_value === null ? "—" : money2(a.ledger_value)),
    },
    {
      id: "diff",
      header: t("m11.stock.difference"),
      numeric: true,
      cell: (a) =>
        a.difference === null ? (
          "—"
        ) : (
          <span
            className={cn(compareMoney(money(a.difference), ZERO) !== 0 && "text-destructive-strong")}
            data-testid={`stock-diff-${a.account}`}
          >
            {money2(a.difference)}
          </span>
        ),
    },
  ];
  const itemColumns: DataTableColumn<StockItem>[] = [
    { id: "name", header: t("m11.stock.product"), cell: (i) => <span className="font-semibold">{i.name}</span> },
    { id: "qty", header: t("m11.stock.qty"), numeric: true, cell: (i) => formatQty(i.qty, "fractional") },
    { id: "value", header: t("m11.stock.value"), numeric: true, cell: (i) => money2(i.value) },
  ];
  const mismatch = data.accounts.some(
    (a) => a.difference !== null && compareMoney(money(a.difference), ZERO) !== 0,
  );
  return (
    <>
      <p className="text-small text-foreground-secondary">{t("m11.stock.basis")}</p>
      {mismatch ? (
        <Banner tone="warning" icon={TriangleAlert}>
          {t("m11.stock.mismatch")}
        </Banner>
      ) : null}
      <DataTable
        label={t("m11.stock.accountsTitle")}
        columns={accountColumns}
        data={data.accounts}
        getRowId={(a) => a.account}
        minWidth={620}
      />
      <DataTable
        label={t("m11.stock.itemsTitle")}
        columns={itemColumns}
        data={data.items}
        getRowId={(i) => `${i.warehouse_id}:${i.product_id}`}
        minWidth={620}
      />
    </>
  );
}

export function TrialBalanceReport() {
  return (
    <div className="flex flex-col gap-3.5">
      <Toolbar>
        <BranchFilter />
        <MonthFilter />
      </Toolbar>
      <ReportBody kind="trial-balance">{(data) => <TrialBalanceView data={data} />}</ReportBody>
    </div>
  );
}

export function BalanceSheetReport() {
  return (
    <div className="flex flex-col gap-3.5">
      <Toolbar>
        <BranchFilter />
        <PeriodFilter asOf />
      </Toolbar>
      <ReportBody kind="balance-sheet">{(data) => <BalanceSheetView data={data} />}</ReportBody>
    </div>
  );
}

export function StockAsOfReport() {
  return (
    <div className="flex flex-col gap-3.5">
      <Toolbar>
        <BranchFilter />
        <PeriodFilter asOf />
      </Toolbar>
      <ReportBody kind="stock-as-of">{(data) => <StockAsOfView data={data} />}</ReportBody>
    </div>
  );
}
