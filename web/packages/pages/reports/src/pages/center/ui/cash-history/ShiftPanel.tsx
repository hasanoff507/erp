/**
 * Shift panel of «Kassa / smena tarixi»: Z-report of a closed shift (payment methods, card split
 * «integratsiyalangan / terminalsiz» — 03 US-M16-01, terminal settlements, sales / returns / discounts /
 * VAT) or the running totals of an open one, and the shift's cash movements (direction, reason, comment,
 * time — US-M16-03 «qo'yilgan/olingan, nega»).
 */
import { useUnit } from "effector-react";
import { X } from "lucide-react";

import { serverErrorText, useTranslation } from "@shared/i18n";
import { formatDateTime, formatMoney } from "@shared/lib/format";
import { compareMoney, money } from "@shared/lib/money";
import { Button, Card, ErrorState, Icon, Skeleton, StatusChip, cn } from "@shared/ui";

import {
  $movements,
  $shift,
  $shiftError,
  $shiftId,
  $shiftStatus,
  shiftReloadRequested,
  shiftSelected,
  type CashMovement,
} from "../../model/index.ts";

const METHODS = ["cash", "card", "uzqr", "click", "payme", "uzum", "debt"] as const;
const REASONS = ["collection", "deposit", "owner_withdrawal", "other"] as const;

function nonZero(value: string): boolean {
  return compareMoney(money(value), money("0")) !== 0;
}

function Row({ label, value, strong }: { label: string; value: string; strong?: boolean }) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-0.5 text-[13px]">
      <dt className="text-foreground-secondary">{label}</dt>
      <dd className={cn("tabular-nums", strong ? "font-extrabold" : "font-semibold")}>{value}</dd>
    </div>
  );
}

export function ShiftPanel() {
  const { t } = useTranslation("reports");
  const [shiftId, shift, movements, status, error] = useUnit([
    $shiftId,
    $shift,
    $movements,
    $shiftStatus,
    $shiftError,
  ]);
  const [select, reload] = useUnit([shiftSelected, shiftReloadRequested]);

  if (!shiftId) {
    return (
      <Card className="hidden text-small text-muted-foreground xl:block">{t("cashHistory.panel.hint")}</Card>
    );
  }

  const reason = (mv: CashMovement) => {
    const r = REASONS.find((x) => x === mv.reason);
    return r ? t(`cashHistory.reasons.${r}`) : t("cashHistory.reasons.other");
  };
  const z = shift?.z_report ?? null;
  const running = shift?.running_totals ?? null;
  const totals = z?.totals_by_method ?? running?.totals_by_method ?? null;

  return (
    <Card role="region" aria-labelledby="shift-panel-title" className="flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <h2 id="shift-panel-title" className="min-w-0 flex-1 text-[15px] font-bold">
          {shift ? t("cashHistory.panel.title", { no: shift.shift_no }) : t("cashHistory.panel.loading")}
        </h2>
        <Button
          size="icon"
          variant="outline"
          className="h-8 w-8"
          aria-label={t("cashHistory.panel.close")}
          onClick={() => select(null)}
        >
          <Icon as={X} size="sm" />
        </Button>
      </div>

      {status === "loading" ? (
        <div className="flex flex-col gap-2" aria-busy="true">
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
        </div>
      ) : status === "error" && error ? (
        <ErrorState message={serverErrorText(error)} onRetry={reload} />
      ) : shift ? (
        <>
          <p className="text-[12px] text-muted-foreground tabular-nums">
            {formatDateTime(shift.opened_at)} —{" "}
            {shift.closed_at ? formatDateTime(shift.closed_at) : t("cashHistory.open")}
          </p>
          {totals ? (
            <section aria-labelledby="shift-methods" className="flex flex-col">
              <h3 id="shift-methods" className="text-[13px] font-bold">
                {z ? t("cashHistory.panel.zReport") : t("cashHistory.panel.running")}
              </h3>
              <dl>
                {METHODS.filter((k) => k === "cash" || nonZero(totals[k])).map((k) => (
                  <Row key={k} label={t(`cashHistory.methods.${k}`)} value={formatMoney(totals[k])} />
                ))}
              </dl>
            </section>
          ) : null}
          {z ? (
            <>
              <section aria-labelledby="shift-card-split" className="flex flex-col">
                <h3 id="shift-card-split" className="text-[13px] font-bold">
                  {t("cashHistory.panel.cardSplit")}
                </h3>
                <dl>
                  <Row
                    label={t("cashHistory.panel.cardIntegrated")}
                    value={formatMoney(z.card_split.integrated)}
                  />
                  <Row label={t("cashHistory.panel.cardManual")} value={formatMoney(z.card_split.manual)} />
                </dl>
                {z.card_settlements.length > 0 ? (
                  <ul className="mt-1 flex flex-col gap-1">
                    {z.card_settlements.map((s) => (
                      <li
                        key={s.card_terminal_id}
                        className="flex items-center justify-between gap-2 text-[12px]"
                      >
                        <span>{t("cashHistory.panel.settlement", { total: formatMoney(s.net_total) })}</span>
                        <StatusChip tone={s.status === "matched" ? "success" : "warning"}>
                          {t(`cashHistory.panel.settlementStatus.${s.status}`)}
                        </StatusChip>
                      </li>
                    ))}
                  </ul>
                ) : null}
              </section>
              <dl>
                <Row label={t("cashHistory.panel.salesCount")} value={String(z.sales_count)} />
                <Row
                  label={t("cashHistory.panel.returns", { count: z.returns_count })}
                  value={formatMoney(z.returns_total)}
                />
                <Row label={t("cashHistory.panel.vat")} value={formatMoney(z.vat_total)} />
                <Row label={t("cashHistory.panel.discounts")} value={formatMoney(z.discount_total)} />
                <Row label={t("cashHistory.columns.expected")} value={formatMoney(z.expected_cash)} strong />
                <Row
                  label={t("cashHistory.columns.counted")}
                  value={z.counted_cash === null ? "—" : formatMoney(z.counted_cash)}
                />
                <Row
                  label={t("cashHistory.columns.variance")}
                  value={z.variance === null ? "—" : formatMoney(z.variance)}
                  strong
                />
              </dl>
            </>
          ) : running ? (
            <dl>
              <Row label={t("cashHistory.columns.cashIn")} value={formatMoney(running.cash_in)} />
              <Row label={t("cashHistory.columns.cashOut")} value={formatMoney(running.cash_out)} />
              <Row
                label={t("cashHistory.columns.expected")}
                value={formatMoney(running.expected_cash)}
                strong
              />
            </dl>
          ) : null}

          <section aria-labelledby="shift-movements" className="flex flex-col gap-1.5">
            <h3 id="shift-movements" className="text-[13px] font-bold">
              {t("cashHistory.panel.movements")}
            </h3>
            {movements.length === 0 ? (
              <p className="text-[12px] text-muted-foreground">{t("cashHistory.panel.noMovements")}</p>
            ) : (
              <ul
                aria-label={t("cashHistory.panel.movements")}
                className="flex flex-col divide-y divide-divider"
              >
                {movements.map((mv) => (
                  <li
                    key={mv.id}
                    className={cn("flex flex-col gap-0.5 py-1.5", mv.status === "cancelled" && "opacity-60")}
                  >
                    <div className="flex items-center gap-2 text-[13px]">
                      <StatusChip tone={mv.direction === "in" ? "success" : "warning"}>
                        {t(`cashHistory.direction.${mv.direction}`)}
                      </StatusChip>
                      <span className="min-w-0 flex-1 truncate">{reason(mv)}</span>
                      <span
                        className={cn(
                          "font-extrabold tabular-nums",
                          mv.status === "cancelled" && "line-through",
                        )}
                      >
                        {formatMoney(mv.amount)}
                      </span>
                    </div>
                    <div className="flex flex-wrap gap-x-2 text-[12px] text-muted-foreground">
                      <span className="tabular-nums">{formatDateTime(mv.created_at)}</span>
                      {mv.number ? <span>{mv.number}</span> : null}
                      {mv.status !== "posted" ? (
                        <span>{t(`cashHistory.movementStatus.${mv.status}`)}</span>
                      ) : null}
                      {mv.comment ? <span className="break-words">«{mv.comment}»</span> : null}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      ) : null}
    </Card>
  );
}
