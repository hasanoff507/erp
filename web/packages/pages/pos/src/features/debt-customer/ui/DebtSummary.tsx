/**
 * Debt summary of the chosen customer for a nasiya sale (mockup Pos06Nasiya): «Joriy qarz», «Shu sotuv»,
 * «Sotuvdan keyin», «Kredit limiti N · X% · qoladi Y» (or «Limitsiz») and the note when the balance includes
 * this device's unsynced documents (16 §5 — the last known balance).
 */
import { useTranslation } from "@shared/i18n";
import { formatMoney } from "@shared/lib/format";
import { compareMoney, type Money } from "@shared/lib/money";
import type { CustomerDebtView } from "@shared/offline";
import { cn } from "@shared/ui";

import type { LimitCheck } from "../model/index.ts";

export interface DebtSummaryProps {
  view: CustomerDebtView | null;
  amount: Money;
  check: LimitCheck;
}

export function DebtSummary({ view, amount, check }: DebtSummaryProps) {
  const { t } = useTranslation("pos");
  const unsynced =
    view !== null &&
    (compareMoney(view.pendingDebt, "0.00" as Money) > 0 ||
      compareMoney(view.pendingPayments, "0.00" as Money) > 0 ||
      view.local);
  return (
    <div className="flex flex-col gap-2" data-testid="debt-summary">
      <dl className="grid grid-cols-3 gap-2 text-[13px]">
        <div className="flex flex-col rounded-xl bg-muted px-3 py-2">
          <dt className="text-muted-foreground">{t("debts.current")}</dt>
          <dd className="text-[18px] font-extrabold tabular-nums" data-testid="debt-current">
            {formatMoney(view?.balance ?? "0.00", { withCurrency: false })}
          </dd>
        </div>
        <div className="flex flex-col rounded-xl bg-muted px-3 py-2">
          <dt className="text-muted-foreground">{t("debts.thisSale")}</dt>
          <dd className="text-[18px] font-extrabold tabular-nums text-warning-strong">
            +{formatMoney(amount, { withCurrency: false })}
          </dd>
        </div>
        <div className="flex flex-col rounded-xl bg-muted px-3 py-2">
          <dt className="text-muted-foreground">{t("debts.afterSale")}</dt>
          <dd className="text-[18px] font-extrabold tabular-nums" data-testid="debt-after">
            {formatMoney(check.after, { withCurrency: false })}
          </dd>
        </div>
      </dl>
      {view?.creditLimit ? (
        <div className="flex flex-col gap-1">
          <div className="flex justify-between text-[13px]">
            <span>{t("debts.limit", { amount: formatMoney(view.creditLimit) })}</span>
            <span
              className={cn("font-bold", check.over && "text-destructive-strong")}
              data-testid="debt-left"
            >
              {check.usedPct ?? 0}% ·{" "}
              {t("debts.left", { amount: formatMoney(check.left ?? "0.00", { withCurrency: false }) })}
            </span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-muted">
            <div
              className={cn(
                "h-full rounded-full",
                check.over ? "bg-destructive" : (check.usedPct ?? 0) >= 80 ? "bg-warning" : "bg-primary",
                WIDTH_CLASS[Math.min(10, Math.floor((check.usedPct ?? 0) / 10))],
              )}
            />
          </div>
        </div>
      ) : (
        <p className="text-[13px] text-muted-foreground" data-testid="debt-no-limit">
          {t("debts.noLimit")}
        </p>
      )}
      {unsynced ? <p className="text-[12px] text-muted-foreground">{t("debts.unsyncedNote")}</p> : null}
    </div>
  );
}

/** CSP: no inline styles — the bar width is one of eleven static classes. */
const WIDTH_CLASS = [
  "w-0",
  "w-[10%]",
  "w-[20%]",
  "w-[30%]",
  "w-[40%]",
  "w-1/2",
  "w-[60%]",
  "w-[70%]",
  "w-[80%]",
  "w-[90%]",
  "w-full",
] as const;
