/**
 * BO-07 KPI cards (07 BO-07, mockup Bo07Qqs): VAT payer — output VAT (Kt 6410), input VAT credited
 * (Dt 4410), net VAT (payable / carried forward), «Kutilayotgan QQS krediti» (red e-invoices, share of
 * the period's input VAT, 10% limit); turnover-tax payer — base, rate, tax (Dt 9430 / Kt 6410).
 */
import { useUnit } from "effector-react";
import { ArrowDownLeft, ArrowUpRight, FileWarning, Landmark, Percent, Receipt } from "lucide-react";

import { useTranslation } from "@shared/i18n";
import { formatMoney, formatPercent } from "@shared/lib/format";
import { Banner, Card, KpiCard, StatusChip } from "@shared/ui";

import { $summary, PENDING_CREDIT_LIMIT_PCT, netSign, overCreditLimit } from "../../model/index.ts";

const money2 = (v: string | null) => (v === null ? "—" : formatMoney(v, { precision: 2 }));

export function SummaryCards() {
  const { t } = useTranslation("finance");
  const summary = useUnit($summary);
  if (!summary) return null;

  if (summary.regime === "turnover") {
    return (
      <div className="grid gap-3.5 sm:grid-cols-3">
        <KpiCard
          label={t("vat.kpi.turnoverBase")}
          value={money2(summary.turnoverBase)}
          icon={Receipt}
          tone="info"
          note={t("vat.kpi.turnoverBaseNote")}
        />
        <KpiCard
          label={t("vat.kpi.turnoverRate")}
          value={summary.turnoverRatePct === null ? "—" : formatPercent(summary.turnoverRatePct)}
          icon={Percent}
          tone="neutral"
        />
        <KpiCard
          label={t("vat.kpi.turnoverAmount")}
          value={money2(summary.turnoverAmount)}
          icon={Landmark}
          tone="primary"
          note={t("vat.kpi.turnoverAmountNote")}
        />
      </div>
    );
  }

  const sign = netSign(summary.netVat);
  const overLimit = overCreditLimit(summary.pendingCreditPct, PENDING_CREDIT_LIMIT_PCT);
  return (
    <div className="flex flex-col gap-3.5">
      <div className="grid gap-3.5 sm:grid-cols-3">
        <KpiCard
          label={t("vat.kpi.output")}
          value={money2(summary.outputVat)}
          icon={ArrowUpRight}
          tone="info"
          note={t("vat.kpi.outputNote")}
        />
        <KpiCard
          label={t("vat.kpi.input")}
          value={money2(summary.inputVat)}
          icon={ArrowDownLeft}
          tone="success"
          note={t("vat.kpi.inputNote")}
        />
        <KpiCard
          label={sign < 0 ? t("vat.kpi.carryForward") : t("vat.kpi.payable")}
          value={money2(summary.netVat)}
          icon={Landmark}
          tone={sign > 0 ? "warning" : "primary"}
          note={t("vat.kpi.netNote")}
        />
      </div>
      <Card role="region" aria-labelledby="vat-credit-title" className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <h2 id="vat-credit-title" className="text-[15px] font-bold">
            {t("vat.credit.title")}
          </h2>
          {summary.pendingCreditPct !== null ? (
            <StatusChip tone={overLimit ? "destructive" : "success"} icon={FileWarning}>
              {t("vat.credit.share", {
                pct: formatPercent(summary.pendingCreditPct),
                limit: formatPercent(PENDING_CREDIT_LIMIT_PCT),
              })}
            </StatusChip>
          ) : null}
        </div>
        <p className="text-small text-foreground-secondary">{t("vat.credit.hint")}</p>
        <p className="text-[14px] font-semibold">
          {summary.pendingRedInvoices === null
            ? t("vat.credit.none")
            : t("vat.credit.invoices", { count: summary.pendingRedInvoices })}
        </p>
        {summary.months.length > 1 ? (
          <p className="text-[12px] text-muted-foreground">{t("vat.credit.quarterNote")}</p>
        ) : null}
      </Card>
      {overLimit ? (
        <Banner tone="destructive" icon={FileWarning} live="polite">
          {t("vat.credit.overLimit")}
        </Banner>
      ) : null}
    </div>
  );
}
