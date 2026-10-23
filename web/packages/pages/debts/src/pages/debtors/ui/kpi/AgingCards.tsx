/**
 * BO-06 top: «Jami debitorlik (4010)» (or «Jami kreditorlik (6010)» for «Men qarzdorman») and the aging
 * groups — bucket, debtors, amount, share (`debts-aging.summary`, before the tab filters).
 */
import { useUnit } from "effector-react";

import { useTranslation } from "@shared/i18n";
import { formatDate, formatMoney } from "@shared/lib/format";
import { cn } from "@shared/ui";

import { bucketCards } from "#/entities/debtor/index.ts";

import { $asOf, $direction, $summary } from "../../model/index.ts";

export function AgingCards() {
  const { t } = useTranslation("debts");
  const [summary, direction, asOf] = useUnit([$summary, $direction, $asOf]);
  const cards = bucketCards(summary);
  return (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
      <div className="flex flex-col gap-1 rounded-2xl border border-border bg-card px-5 py-4 shadow-card">
        <span className="text-[13px] font-semibold text-muted-foreground">
          {direction === "payable" ? t("kpi.totalPayable") : t("kpi.totalReceivable")}
        </span>
        <span className="text-[26px] font-extrabold tabular-nums" data-testid="kpi-total">
          {formatMoney(summary?.total ?? "0.00")}
        </span>
        <span className="text-[12px] text-muted-foreground">
          {t("kpi.count", { n: summary?.count ?? 0 })}
          {asOf ? ` · ${t("kpi.asOf", { date: formatDate(asOf) })}` : ""}
        </span>
      </div>
      {cards.map((c) => (
        <div
          key={c.bucket}
          data-testid={`bucket-${c.bucket}`}
          className={cn(
            "flex flex-col gap-1 rounded-2xl border border-border bg-card px-5 py-4 shadow-card",
            c.bucket === "60+" && c.count > 0 && "border-destructive-border",
          )}
        >
          <span className="text-[13px] font-semibold text-muted-foreground">
            {t(`kpi.bucket.${c.bucket}`)}
          </span>
          <span className="text-[20px] font-extrabold tabular-nums">{formatMoney(c.amount)}</span>
          <span className="text-[12px] text-muted-foreground">
            {t("kpi.bucketNote", { n: c.count, share: c.share })}
          </span>
        </div>
      ))}
    </div>
  );
}
