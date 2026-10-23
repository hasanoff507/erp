/**
 * «Yo'ldagi pul — bankka o'tmagan (5710)» (20 #55b): method rows × branch columns + total; the card row is
 * split into «Karta (integratsiyalangan)» / «Karta (terminalsiz)» when the server sends the breakdown.
 */
import { useUnit } from "effector-react";
import { ArrowRightLeft } from "lucide-react";

import { useTranslation } from "@shared/i18n";
import { formatDate, formatMoney } from "@shared/lib/format";
import { $branches } from "@shared/state/session";
import { Card, EmptyState, ErrorState, Skeleton } from "@shared/ui";

import { $transit, $transitStatus, $transitView, transitReloadRequested } from "../../model/index.ts";

export function TransitPanel() {
  const { t } = useTranslation("finance");
  const [transit, status, view, branches] = useUnit([$transit, $transitStatus, $transitView, $branches]);
  const reload = useUnit(transitReloadRequested);
  const name = (id: string) => branches.find((b) => b.id === id)?.name ?? "—";
  const amount = (v: string | undefined) =>
    v === undefined ? "—" : formatMoney(v, { precision: 2, withCurrency: false });

  return (
    <Card role="region" aria-labelledby="transit-title" className="flex flex-col gap-2.5">
      <div>
        <h2 id="transit-title" className="text-[15px] font-bold">
          {t("bank.transit.title")}
        </h2>
        <p className="text-[12px] text-foreground-secondary">
          {transit ? t("bank.transit.asOf", { date: formatDate(transit.as_of) }) : t("bank.transit.subtitle")}
        </p>
      </div>
      {status === "loading" && !transit ? (
        <Skeleton className="h-24 w-full" />
      ) : status === "error" ? (
        <ErrorState message={t("bank.transit.error")} onRetry={reload} />
      ) : view.rows.length === 0 ? (
        <EmptyState icon={ArrowRightLeft} title={t("bank.transit.empty")} />
      ) : (
        <div className="overflow-x-auto">
          <table
            className="w-full min-w-[480px] text-[13px]"
            aria-label={t("bank.transit.title")}
            data-testid="transit-table"
          >
            <thead>
              <tr className="text-left text-[12px] text-foreground-secondary">
                <th className="py-1.5 pr-3 font-semibold">{t("bank.transit.method")}</th>
                {view.branches.map((b) => (
                  <th key={b} className="py-1.5 pr-3 text-right font-semibold">
                    {name(b)}
                  </th>
                ))}
                <th className="py-1.5 text-right font-semibold">{t("bank.transit.total")}</th>
              </tr>
            </thead>
            <tbody>
              {view.rows.map((r) => (
                <tr key={r.key} className="border-t border-border">
                  <td className="py-1.5 pr-3">
                    <span className="font-semibold">{t(`bank.transitRows.${r.key}`)}</span>
                    {r.oldest ? (
                      <span className="block text-[11px] text-foreground-secondary">
                        {t("bank.transit.oldest", { date: formatDate(r.oldest) })}
                      </span>
                    ) : null}
                  </td>
                  {view.branches.map((b) => (
                    <td key={b} className="py-1.5 pr-3 text-right tabular-nums">
                      {amount(r.byBranch[b])}
                    </td>
                  ))}
                  <td className="py-1.5 text-right font-bold tabular-nums">{amount(r.total)}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="border-t-2 border-border font-extrabold">
                <td className="py-1.5 pr-3">{t("bank.transit.total")}</td>
                {view.branches.map((b) => (
                  <td key={b} className="py-1.5 pr-3 text-right tabular-nums">
                    {amount(view.totals[b])}
                  </td>
                ))}
                <td className="py-1.5 text-right tabular-nums" data-testid="transit-total">
                  {amount(view.total)}
                </td>
              </tr>
            </tfoot>
          </table>
        </div>
      )}
    </Card>
  );
}
