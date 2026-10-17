/**
 * «Qarz daftari» Sheet (BO-06 → «Qarz daftari», US-M08-06 / QT-M08-09): the paper-book view — date,
 * document (+ goods, who wrote it, comment), signed amount, balance after the row, status chip of debt rows
 * (ochiq / qisman · qoldiq N / to'langan / kechilgan) and, on payments, the documents they closed.
 * Newest first; «Yana yuklash» reads the next cursor page.
 */
import { useUnit } from "effector-react";
import { BookOpen, Flag } from "lucide-react";

import { useTranslation } from "@shared/i18n";
import { formatDate, formatMoney, formatPhone } from "@shared/lib/format";
import type { LedgerEntry } from "@shared/models";
import {
  Banner,
  Button,
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
  type Tone,
} from "@shared/ui";

import { errorText } from "#/shared/lib/errors.ts";

import {
  $ledger,
  $ledgerError,
  $ledgerStatus,
  $ledgerTarget,
  amountTone,
  entryDocKey,
  ledgerClosed,
  ledgerMoreRequested,
  ledgerReloadRequested,
  loadLedgerFx,
  productsText,
} from "../model/index.ts";

const STATUS_TONE: Record<string, Tone> = {
  open: "warning",
  partially_paid: "info",
  paid: "success",
  written_off: "neutral",
};

function EntryRow({ entry }: { entry: LedgerEntry }) {
  const { t, i18n } = useTranslation("debts");
  const tone = amountTone(entry.amount);
  const goods = productsText(entry.products, i18n.language);
  return (
    <li
      data-testid="ledger-row"
      className="grid grid-cols-[88px_1fr_auto_auto] gap-x-3 gap-y-1 border-b border-border py-3"
    >
      <span className="text-[13px] tabular-nums text-muted-foreground">
        {entry.doc_date ? formatDate(entry.doc_date) : "—"}
      </span>
      <div className="flex min-w-0 flex-col gap-0.5">
        <span className="text-[14px] font-bold">
          {t(`ledger.doc.${entryDocKey(entry)}`)}
          {entry.number ? ` ${entry.number}` : ""}
        </span>
        {goods ? <span className="truncate text-[13px] text-foreground-secondary">{goods}</span> : null}
        {entry.allocations.length > 0 ? (
          <span className="text-[12px] text-foreground-secondary" data-testid="ledger-allocations">
            {t("ledger.closes", {
              list: entry.allocations
                .map(
                  (a) =>
                    `${a.target_number ?? t(`ledger.doc.${entryDocKey({ doc_type: a.target_doc_type, kind: "debt" })}`)} ${formatMoney(a.amount, { withCurrency: false })}`,
                )
                .join(", "),
            })}
          </span>
        ) : null}
        <span className="text-[12px] text-muted-foreground">
          {[
            entry.created_by_name ? t("ledger.by", { name: entry.created_by_name }) : null,
            entry.comment,
            entry.promise_date && entry.kind === "debt"
              ? t("ledger.promise", { date: formatDate(entry.promise_date) })
              : null,
          ]
            .filter(Boolean)
            .join(" · ")}
        </span>
        {entry.status ? (
          <span className="flex flex-wrap items-center gap-1.5">
            <StatusChip tone={STATUS_TONE[entry.status] ?? "neutral"}>
              <span data-testid="ledger-status">{t(`ledger.status.${entry.status}`)}</span>
            </StatusChip>
            {entry.status === "partially_paid" && entry.open_amount ? (
              <span className="text-[12px] text-foreground-secondary">
                {t("ledger.openLeft", { amount: formatMoney(entry.open_amount, { withCurrency: false }) })}
              </span>
            ) : null}
          </span>
        ) : null}
      </div>
      <span
        data-testid="ledger-amount"
        className={cn(
          "text-right text-[15px] font-extrabold tabular-nums",
          tone === "debt" && "text-destructive-strong",
          tone === "payment" && "text-success-strong",
        )}
      >
        {tone === "debt" ? "+" : ""}
        {formatMoney(entry.amount, { withCurrency: false })}
        {entry.paid_amount && tone === "zero" ? (
          <span className="block text-[12px] font-semibold text-muted-foreground">
            {t("ledger.paid", { amount: formatMoney(entry.paid_amount, { withCurrency: false }) })}
          </span>
        ) : null}
      </span>
      <span className="w-[110px] text-right text-[14px] font-bold tabular-nums" data-testid="ledger-running">
        {formatMoney(entry.running_balance, { withCurrency: false })}
      </span>
    </li>
  );
}

export function LedgerSheet() {
  const { t } = useTranslation("debts");
  const [target, ledger, status, error, pending, close, more, reload] = useUnit([
    $ledgerTarget,
    $ledger,
    $ledgerStatus,
    $ledgerError,
    loadLedgerFx.pending,
    ledgerClosed,
    ledgerMoreRequested,
    ledgerReloadRequested,
  ]);
  const cp = ledger?.counterparty ?? null;
  const payable = target?.direction === "payable";
  return (
    <Sheet open={target !== null} onOpenChange={(open) => (open ? undefined : close())}>
      <SheetContent wide data-testid="ledger-sheet">
        <SheetHeader>
          <SheetTitle className="flex items-center gap-2">
            <Icon as={BookOpen} size="lg" />
            {payable ? t("ledger.titlePayable") : t("ledger.title")}
          </SheetTitle>
          <SheetDescription>
            {cp ? `${cp.name}${cp.phone ? ` · ${formatPhone(cp.phone)}` : ""}` : t("ledger.loading")}
          </SheetDescription>
        </SheetHeader>
        <SheetBody className="flex flex-col gap-3">
          {cp ? (
            <div className="grid grid-cols-2 gap-2 rounded-xl bg-muted p-3 text-[13px] sm:grid-cols-3">
              <div className="flex flex-col">
                <span className="text-muted-foreground">{t("ledger.balance")}</span>
                <span className="text-[20px] font-extrabold tabular-nums" data-testid="ledger-balance">
                  {formatMoney(ledger?.balance ?? "0.00")}
                </span>
              </div>
              {!payable ? (
                <div className="flex flex-col">
                  <span className="text-muted-foreground">{t("ledger.limit")}</span>
                  <span className="font-bold">
                    {cp.credit_limit ? formatMoney(cp.credit_limit) : t("table.noLimit")}
                  </span>
                </div>
              ) : null}
              {!payable ? (
                <div className="flex flex-col">
                  <span className="text-muted-foreground">{t("ledger.promiseDate")}</span>
                  <span className="font-bold">{cp.debt_due_date ? formatDate(cp.debt_due_date) : "—"}</span>
                </div>
              ) : null}
            </div>
          ) : null}
          {cp?.doubtful_flag ? (
            <Banner tone="warning" icon={Flag}>
              {t("ledger.doubtful", { reason: cp.doubtful_flag.reason })}
            </Banner>
          ) : null}
          {status === "loading" ? (
            <div className="flex flex-col gap-2">
              <Skeleton className="h-14" />
              <Skeleton className="h-14" />
              <Skeleton className="h-14" />
            </div>
          ) : null}
          {status === "error" && error ? (
            <ErrorState message={errorText(error)} onRetry={() => reload()} />
          ) : null}
          {status === "idle" && ledger && ledger.entries.length === 0 ? (
            <p className="py-6 text-center text-muted-foreground">{t("ledger.empty")}</p>
          ) : null}
          {ledger && ledger.entries.length > 0 ? (
            <>
              <div className="grid grid-cols-[88px_1fr_auto_auto] gap-x-3 border-b border-border pb-2 text-[12px] font-bold text-muted-foreground">
                <span>{t("ledger.columns.date")}</span>
                <span>{t("ledger.columns.doc")}</span>
                <span className="text-right">{t("ledger.columns.amount")}</span>
                <span className="w-[110px] text-right">{t("ledger.columns.balance")}</span>
              </div>
              <ul aria-label={t("ledger.title")}>
                {ledger.entries.map((e) => (
                  <EntryRow key={e.id} entry={e} />
                ))}
              </ul>
              {ledger.next_cursor ? (
                <Button variant="secondary" disabled={pending} onClick={() => more()}>
                  {t("ledger.more")}
                </Button>
              ) : null}
            </>
          ) : null}
        </SheetBody>
      </SheetContent>
    </Sheet>
  );
}
