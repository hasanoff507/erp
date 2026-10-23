/**
 * Import result (20 #55g): drafts created, duplicates skipped, outgoing lines ignored; «Qoralamalarni
 * ko'rish» (list filter: drafts from statements); «Mos kelmagan qatorlar» — lines that made no draft
 * (date, amount, payer, purpose, reason) and integrated card purchases missing from the acquirer registry.
 */
import { useUnit } from "effector-react";
import { FileCheck2, X } from "lucide-react";
import { useState } from "react";

import { useTranslation } from "@shared/i18n";
import { formatDate, formatMoney } from "@shared/lib/format";
import { Banner, Button, Card, Icon } from "@shared/ui";

import { $importResult, importResultDismissed, importedDraftsShown } from "../../model/index.ts";

const money2 = (v: string) => formatMoney(v, { precision: 2 });

export function ImportResult() {
  const { t } = useTranslation("finance");
  const [result, dismiss, showDrafts] = useUnit([$importResult, importResultDismissed, importedDraftsShown]);
  const [details, setDetails] = useState(false);
  if (!result) return null;
  const unmatched = result.unmatched_lines.length + result.unmatched_card_transactions.length;
  return (
    <div className="flex flex-col gap-2" data-testid="import-result">
      <Banner
        tone={unmatched > 0 ? "warning" : "success"}
        icon={FileCheck2}
        action={
          <span className="flex flex-wrap items-center gap-1.5">
            {result.drafts_created > 0 ? (
              <Button size="sm" variant="outline" onClick={showDrafts}>
                {t("bank.import.showDrafts")}
              </Button>
            ) : null}
            {unmatched > 0 ? (
              <Button size="sm" variant="outline" onClick={() => setDetails((v) => !v)}>
                {t("bank.import.showUnmatched", { count: unmatched })}
              </Button>
            ) : null}
            <Button variant="ghost" size="icon" aria-label={t("shared.close")} onClick={dismiss}>
              <Icon as={X} size="sm" />
            </Button>
          </span>
        }
      >
        {t("bank.import.summary", {
          drafts: result.drafts_created,
          duplicates: result.duplicates,
          unmatched: result.unmatched_lines.length,
          ignored: result.ignored_outgoing,
        })}
      </Banner>
      {details ? (
        <Card className="flex flex-col gap-2.5">
          {result.unmatched_lines.length > 0 ? (
            <>
              <h3 className="text-[14px] font-bold">
                {t("bank.import.unmatchedTitle", { count: result.unmatched_lines.length })}
              </h3>
              <ul className="flex flex-col gap-1.5 text-[13px]" data-testid="unmatched-lines">
                {result.unmatched_lines.map((l) => (
                  <li
                    key={l.line_no}
                    className="flex flex-wrap justify-between gap-2 border-t border-border pt-1.5"
                  >
                    <span className="min-w-0 flex-1">
                      <span className="font-semibold">
                        №{l.number} · {formatDate(l.date)} · {l.payer_name ?? "—"}
                      </span>
                      <span className="block text-[12px] text-foreground-secondary">{l.purpose}</span>
                      <span className="block text-[12px] text-warning-strong">
                        {t(`bank.import.reasons.${l.reason}`)}
                      </span>
                    </span>
                    <span className="font-bold tabular-nums">{money2(l.amount)}</span>
                  </li>
                ))}
              </ul>
            </>
          ) : null}
          {result.unmatched_card_transactions.length > 0 ? (
            <>
              <h3 className="text-[14px] font-bold">
                {t("bank.import.cardTitle", { count: result.unmatched_card_transactions.length })}
              </h3>
              <ul className="flex flex-col gap-1.5 text-[13px]">
                {result.unmatched_card_transactions.map((c) => (
                  <li
                    key={c.card_terminal_transaction_id}
                    className="flex justify-between gap-2 border-t border-border pt-1.5"
                  >
                    <span>
                      RRN {c.rrn} · {formatDate(c.business_date)}
                    </span>
                    <span className="font-bold tabular-nums">{money2(c.amount)}</span>
                  </li>
                ))}
              </ul>
            </>
          ) : null}
          <p className="text-[12px] text-foreground-secondary">{t("bank.import.unmatchedHint")}</p>
        </Card>
      ) : null}
    </div>
  );
}
