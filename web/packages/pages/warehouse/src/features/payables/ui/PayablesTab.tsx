/**
 * BO-04 «Men qarzdorman» (07 BO-04 fifth tab; US-M08-11 / QT-M08-14): «Jami kreditorlik (6010)», the
 * suppliers we owe — whom, how much, when (due chip), days overdue, open documents — row → the supplier's
 * book (Sheet), «To'lash» → the supplier payment form (`purchases.pay`).
 */
import { useUnit } from "effector-react";
import { BookOpen, HandCoins } from "lucide-react";

import { useTranslation } from "@shared/i18n";
import { dayjs } from "@shared/lib/date";
import { formatDate, formatMoney } from "@shared/lib/format";
import type { AgingRow } from "@shared/models";
import {
  Button,
  DataTable,
  ErrorState,
  Icon,
  Sheet,
  SheetBody,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  Skeleton,
  StatusChip,
  cn,
  type DataTableColumn,
  type Tone,
} from "@shared/ui";

import { errorText } from "#/shared/lib/errors.ts";

import {
  $payableLedger,
  $payableLedgerError,
  $payableLedgerId,
  $payables,
  $payablesError,
  $payablesStatus,
  $payablesSummary,
  dueState,
  payableLedgerClosed,
  payableLedgerOpened,
  payablesReloadRequested,
  totalOf,
  type DueState,
} from "../model/index.ts";

const DUE_TONE: Record<DueState, Tone> = {
  overdue: "destructive",
  today: "warning",
  soon: "warning",
  later: "neutral",
  none: "neutral",
};

type DocKey = "goods_receipts" | "supplier_payments" | "supplier_returns" | "debt_openings" | "other";
const DOC_KEYS: readonly string[] = [
  "goods_receipts",
  "supplier_payments",
  "supplier_returns",
  "debt_openings",
];
const docKey = (t: string): DocKey => (DOC_KEYS.includes(t) ? (t as DocKey) : "other");

function LedgerSheet() {
  const { t } = useTranslation("warehouse");
  const [id, ledger, error, close, open] = useUnit([
    $payableLedgerId,
    $payableLedger,
    $payableLedgerError,
    payableLedgerClosed,
    payableLedgerOpened,
  ]);
  return (
    <Sheet open={id !== null} onOpenChange={(o) => (o ? undefined : close())}>
      <SheetContent wide data-testid="payable-ledger">
        <SheetHeader>
          <SheetTitle className="flex items-center gap-2">
            <Icon as={BookOpen} size="lg" />
            {t("payables.ledgerTitle")}
          </SheetTitle>
          <SheetDescription>{ledger?.counterparty.name ?? ""}</SheetDescription>
        </SheetHeader>
        <SheetBody>
          {error ? <ErrorState message={errorText(error)} onRetry={() => id && open(id)} /> : null}
          {!ledger && !error ? <Skeleton className="h-40" /> : null}
          {ledger ? (
            <>
              <div className="rounded-xl bg-muted p-3">
                <span className="block text-[13px] text-muted-foreground">{t("payables.owe")}</span>
                <span
                  className="text-[22px] font-extrabold tabular-nums"
                  data-testid="payable-ledger-balance"
                >
                  {formatMoney(ledger.balance)}
                </span>
              </div>
              <ul className="flex flex-col">
                {ledger.entries.map((e) => (
                  <li
                    key={e.id}
                    className="grid grid-cols-[88px_1fr_auto_auto] gap-x-3 border-b border-border py-2.5"
                    data-testid="payable-ledger-row"
                  >
                    <span className="text-[13px] tabular-nums text-muted-foreground">
                      {e.doc_date ? formatDate(e.doc_date) : "—"}
                    </span>
                    <span className="flex min-w-0 flex-col">
                      <span className="font-bold">
                        {t(`payables.doc.${docKey(e.doc_type)}`)}
                        {e.number ? ` ${e.number}` : ""}
                      </span>
                      {e.status ? (
                        <span className="text-[12px] text-foreground-secondary">
                          {t(`payables.status.${e.status}`)}
                          {e.status === "partially_paid" && e.open_amount
                            ? ` · ${formatMoney(e.open_amount, { withCurrency: false })}`
                            : ""}
                        </span>
                      ) : null}
                    </span>
                    <span
                      className={cn(
                        "text-right font-extrabold tabular-nums",
                        e.amount.startsWith("-") ? "text-success-strong" : "text-destructive-strong",
                      )}
                    >
                      {e.amount.startsWith("-") ? "" : "+"}
                      {formatMoney(e.amount, { withCurrency: false })}
                    </span>
                    <span className="w-[110px] text-right font-bold tabular-nums">
                      {formatMoney(e.running_balance, { withCurrency: false })}
                    </span>
                  </li>
                ))}
              </ul>
            </>
          ) : null}
        </SheetBody>
      </SheetContent>
    </Sheet>
  );
}

export interface PayablesTabProps {
  canPay: boolean;
  online: boolean;
  /** «To'lash» → the supplier payment form of the «Yetkazib beruvchiga to'lov» tab. */
  onPay: (supplierId: string) => void;
}

export function PayablesTab({ canPay, online, onPay }: PayablesTabProps) {
  const { t } = useTranslation("warehouse");
  const [rows, summary, status, error, reload, openLedger] = useUnit([
    $payables,
    $payablesSummary,
    $payablesStatus,
    $payablesError,
    payablesReloadRequested,
    payableLedgerOpened,
  ]);
  const today = dayjs().format("YYYY-MM-DD");
  const columns: DataTableColumn<AgingRow>[] = [
    {
      id: "supplier",
      header: t("payables.supplier"),
      cell: (r) => (
        <span className="font-bold" data-testid="payable-name">
          {r.name}
        </span>
      ),
    },
    {
      id: "amount",
      header: t("payables.amount"),
      numeric: true,
      cell: (r) => (
        <span data-testid="payable-amount">{formatMoney(r.balance, { withCurrency: false })}</span>
      ),
    },
    {
      id: "due",
      header: t("payables.due"),
      cell: (r) => {
        const s = dueState(r.due_date, today);
        return (
          <StatusChip tone={DUE_TONE[s]}>
            <span data-testid="payable-due">
              {r.due_date
                ? t(`payables.dueState.${s}`, { date: formatDate(r.due_date) })
                : t("payables.noDue")}
            </span>
          </StatusChip>
        );
      },
    },
    { id: "days", header: t("payables.days"), numeric: true, cell: (r) => r.days_overdue },
    { id: "docs", header: t("payables.docs"), numeric: true, cell: (r) => r.open_docs },
  ];
  return (
    <div className="flex flex-col gap-3" data-testid="payables-tab">
      <div className="flex flex-wrap items-end gap-3">
        <div className="flex flex-col rounded-2xl border border-border bg-card px-5 py-3 shadow-card">
          <span className="text-[13px] font-semibold text-muted-foreground">{t("payables.total")}</span>
          <span className="text-[24px] font-extrabold tabular-nums" data-testid="payables-total">
            {formatMoney(summary?.total ?? totalOf(rows))}
          </span>
          <span className="text-[12px] text-muted-foreground">
            {t("payables.count", { n: summary?.count ?? rows.length })}
          </span>
        </div>
        <p className="max-w-[520px] text-[13px] text-foreground-secondary">{t("payables.hint")}</p>
      </div>
      <DataTable
        label={t("payables.label")}
        columns={columns}
        data={rows}
        getRowId={(r) => r.counterparty_id}
        status={status === "loading" && rows.length > 0 ? "idle" : status}
        errorMessage={error ? errorText(error) : undefined}
        onRetry={() => reload()}
        onRowClick={(r) => openLedger(r.counterparty_id)}
        rowActions={(r) => [
          {
            id: "ledger",
            label: t("payables.openLedger"),
            icon: BookOpen,
            onSelect: () => openLedger(r.counterparty_id),
          },
          ...(canPay
            ? [
                {
                  id: "pay",
                  label: t("payables.pay"),
                  icon: HandCoins,
                  disabled: !online,
                  onSelect: () => onPay(r.counterparty_id),
                },
              ]
            : []),
        ]}
        empty={<p className="py-8 text-center text-muted-foreground">{t("payables.empty")}</p>}
        minWidth={640}
      />
      {canPay && rows[0] ? (
        <div>
          <Button
            variant="secondary"
            disabled={!online}
            onClick={() => rows[0] && onPay(rows[0].counterparty_id)}
          >
            <Icon as={HandCoins} size="sm" />
            {t("payables.payFirst", { name: rows[0].name })}
          </Button>
        </div>
      ) : null}
      <LedgerSheet />
    </div>
  );
}
