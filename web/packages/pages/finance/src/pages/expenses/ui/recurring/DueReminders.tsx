/**
 * Due recurring expenses (US-M15-02, QT-M15-02): «{Nom} to'lash vaqti — {summa}» with period, source,
 * branch; «Keyinroq» (hidden for this visit) / «Tasdiqlash va yozish» (one click, `POST /confirm`;
 * never automatic). A 202 answer → the notice «Egasi tasdig'iga yuborildi».
 */
import { useUnit } from "effector-react";
import { BellRing } from "lucide-react";

import { useTranslation } from "@shared/i18n";
import { formatMoney } from "@shared/lib/format";
import { $branches } from "@shared/state/session";
import { Button, Icon } from "@shared/ui";

import { $categories, $dueRules, confirmRuleFx, ruleSnoozed, ruleTitle } from "../../model/index.ts";

export function DueReminders({ canAct }: { canAct: boolean }) {
  const { t } = useTranslation("finance");
  const [rules, categories, branches, pending] = useUnit([
    $dueRules,
    $categories,
    $branches,
    confirmRuleFx.pending,
  ]);
  const [confirm, snooze] = useUnit([confirmRuleFx, ruleSnoozed]);
  if (rules.length === 0) return null;
  return (
    <ul className="flex flex-col gap-2" aria-label={t("expenses.reminders.label")}>
      {rules.map((r) => (
        <li
          key={r.id}
          data-testid="due-reminder"
          className="flex flex-wrap items-center gap-3 rounded-xl border border-warning-border bg-warning-soft px-4 py-3"
        >
          <Icon as={BellRing} size="md" className="shrink-0 text-warning-strong" />
          <div className="min-w-0 flex-1">
            <p className="text-[14px] font-bold">
              {t("expenses.reminders.title", {
                name: ruleTitle(r, categories),
                amount: formatMoney(r.amount),
              })}
            </p>
            <p className="text-[12px] text-foreground-secondary">
              {t("expenses.reminders.meta", {
                period: t(`expenses.periods.${r.period}`),
                day: r.day_of_month,
                source: t(`expenses.sources.${r.source}`),
                branch: branches.find((b) => b.id === r.branch_id)?.name ?? "—",
              })}
            </p>
          </div>
          <Button variant="ghost" onClick={() => snooze(r.id)}>
            {t("expenses.reminders.later")}
          </Button>
          {canAct ? (
            <Button disabled={pending} onClick={() => void confirm(r.id).catch(() => undefined)}>
              {t("expenses.reminders.confirm")}
            </Button>
          ) : null}
        </li>
      ))}
    </ul>
  );
}
