/**
 * «Hisob qoldiqlari» (07 BO-08 right panel; 20 #11): the trial balance of the journal's month — per account
 * the closing balance with its side (debet / kredit), the period's Dt and Kt turnover; totals Σ Dt = Σ Kt.
 */
import { useUnit } from "effector-react";
import { CircleAlert, Scale } from "lucide-react";

import { serverErrorText, useTranslation } from "@shared/i18n";
import { formatMoney } from "@shared/lib/format";
import { Banner, Card, Icon, Skeleton } from "@shared/ui";

import { sidedBalance } from "#/shared/lib/balances.ts";
import { useMonthLabel } from "#/shared/ui/useMonthLabel.ts";

import {
  $balances,
  $balancesError,
  $balancesPeriod,
  $balancesStatus,
  balancesReloadRequested,
} from "../model/index.ts";

export function BalancesPanel() {
  const { t } = useTranslation("finance");
  const monthLabel = useMonthLabel();
  const [tb, status, error, period, reload] = useUnit([
    $balances,
    $balancesStatus,
    $balancesError,
    $balancesPeriod,
    balancesReloadRequested,
  ]);
  const money2 = (v: string) => formatMoney(v, { precision: 2, withCurrency: false });

  return (
    <Card role="region" aria-labelledby="balances-title" className="flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <Icon as={Scale} size="md" />
        <h2 id="balances-title" className="text-[15px] font-bold">
          {t("balances.title")}
        </h2>
      </div>
      {period ? (
        <p className="text-small text-foreground-secondary">{t("balances.period", { period: monthLabel(period) })}</p>
      ) : null}
      {status === "error" && error ? (
        <Banner tone="destructive" icon={CircleAlert}>
          {serverErrorText(error)}{" "}
          <button type="button" className="font-semibold underline" onClick={reload}>
            {t("closing.retry")}
          </button>
        </Banner>
      ) : !tb ? (
        <Skeleton className="h-32 w-full" />
      ) : tb.rows.length === 0 ? (
        <p className="text-small text-foreground-secondary">{t("balances.empty")}</p>
      ) : (
        <>
          <ul className="flex flex-col divide-y divide-divider" aria-label={t("balances.title")} data-testid="balances">
            {tb.rows.map((row) => {
              const closing = sidedBalance(row.closing_balance);
              return (
                <li key={row.account} className="flex items-start justify-between gap-3 py-2 text-[13px]">
                  <span className="flex min-w-0 flex-col">
                    <span className="font-extrabold tabular-nums">{row.account}</span>
                    <span className="text-[11px] text-muted-foreground">{row.name}</span>
                    <span className="text-[11px] text-muted-foreground tabular-nums">
                      {t("balances.turnover", {
                        dt: money2(row.debit_turnover),
                        kt: money2(row.credit_turnover),
                      })}
                    </span>
                  </span>
                  <span className="flex flex-col items-end">
                    <span className="font-extrabold tabular-nums">{money2(closing.amount)}</span>
                    <span className="text-[11px] text-muted-foreground">{t(`balances.side.${closing.side}`)}</span>
                  </span>
                </li>
              );
            })}
          </ul>
          <p className="text-[12px] font-semibold tabular-nums" data-testid="balances-totals">
            {t("balances.totals", {
              dt: money2(tb.totals.debit_turnover),
              kt: money2(tb.totals.credit_turnover),
            })}
          </p>
        </>
      )}
    </Card>
  );
}
