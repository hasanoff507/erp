/**
 * «Davrni yopish» card (07 BO-08): the oldest open month, its readiness — blockers (`recost_pending`,
 * `fiscal_pending`, `devices_unsynced` with the device list and a link to BO-11 «Qurilmalar») disable the
 * button; warnings (`tax_settlement_missing`, `tax_settlement_stale`, `opening_0000_nonzero`, `open_shifts`,
 * `drafts_in_period`, `devices_not_synced_after_period_end`, `ledger_stock_mismatch`) are listed on the card
 * and again in the confirmation dialog; «{Oy}ni yopish» (`accounting.period.close`) → `POST /period-closings`.
 * «Yopilgan oy qayta ochilmaydi — keyingi tuzatishlar joriy ochiq oyda tuzatuvchi yozuv bilan».
 */
import { useUnit } from "effector-react";
import { CheckCircle2, CircleAlert, Lock, RotateCcw, TriangleAlert, X } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import { serverErrorText, useTranslation } from "@shared/i18n";
import { formatDateTime, formatMoney } from "@shared/lib/format";
import { useCan } from "@shared/state/permissions";
import { Banner, Button, Card, ConfirmDialog, Icon, Skeleton, StatusChip } from "@shared/ui";

import { todayIso } from "#/shared/lib/effect.ts";
import { useMonthLabel } from "#/shared/ui/useMonthLabel.ts";

import {
  $canClose,
  $candidate,
  $closeError,
  $closingError,
  $closingStatus,
  $justClosed,
  $periodNotEnded,
  $readiness,
  closePeriodFx,
  closingMounted,
  closingNoticeDismissed,
  closingReloadRequested,
  type Readiness,
  type Warning,
} from "../model/index.ts";

function BlockerList({ readiness }: { readiness: Readiness }) {
  const { t } = useTranslation("finance");
  return (
    <ul className="flex flex-col gap-1.5" aria-label={t("closing.blockersTitle")} data-testid="closing-blockers">
      {readiness.blockers.map((b) => (
        <li key={b} className="flex flex-col gap-1 rounded-lg bg-destructive-soft px-3 py-2 text-[13px]">
          <span className="font-bold">
            {b === "recost_pending"
              ? t("closing.blockers.recost_pending", { count: readiness.pending_recost_jobs })
              : b === "fiscal_pending"
                ? t("closing.blockers.fiscal_pending", { count: readiness.pending_fiscal_receipts })
                : t("closing.blockers.devices_unsynced", { count: readiness.unsynced_devices.length })}
          </span>
          {b === "devices_unsynced" ? (
            <>
              <ul className="flex flex-col gap-0.5 text-[12px] text-foreground-secondary">
                {readiness.unsynced_devices.map((d) => (
                  <li key={d.device_id}>
                    {t("closing.device", {
                      name: d.cash_register_name ?? t("closing.deviceUnnamed"),
                      count: d.outbox_pending_count,
                      since: d.outbox_oldest_pending_at ? formatDateTime(d.outbox_oldest_pending_at) : "—",
                    })}
                  </li>
                ))}
              </ul>
              <Link to="/app/settings/users?tab=devices" className="text-[12px] font-semibold underline">
                {t("closing.devicesLink")}
              </Link>
            </>
          ) : null}
        </li>
      ))}
    </ul>
  );
}

export function WarningList({ readiness }: { readiness: Readiness }) {
  const { t } = useTranslation("finance");
  const detail = (w: Warning): ReactNode => {
    switch (w) {
      case "tax_settlement_stale":
        return readiness.stale_tax_settlements.map((s) => (
          <li key={s.id}>
            {t("closing.stale", {
              kind: t(`vat.settlement.kinds.${s.tax_kind}`),
              amount: formatMoney(s.amount, { precision: 2 }),
              current: formatMoney(s.current_amount, { precision: 2 }),
            })}
          </li>
        ));
      case "ledger_stock_mismatch":
        return readiness.ledger_stock_mismatches.map((m) => (
          <li key={m.account}>
            {t("closing.mismatch", {
              account: m.account,
              ledger: formatMoney(m.ledger_balance, { precision: 2 }),
              stock: formatMoney(m.stock_value, { precision: 2 }),
              difference: formatMoney(m.difference, { precision: 2 }),
            })}
          </li>
        ));
      case "opening_0000_nonzero":
        return <li>{t("closing.opening", { amount: formatMoney(readiness.opening_0000_balance, { precision: 2 }) })}</li>;
      default:
        return null;
    }
  };
  return (
    <ul className="flex flex-col gap-1.5" aria-label={t("closing.warningsTitle")} data-testid="closing-warnings">
      {readiness.warnings.map((w) => (
        <li key={w} className="flex flex-col gap-0.5 rounded-lg bg-warning-soft px-3 py-2 text-[13px]">
          <span className="font-semibold">{t(`closing.warnings.${w}`)}</span>
          <ul className="flex flex-col gap-0.5 text-[12px] text-foreground-secondary">{detail(w)}</ul>
        </li>
      ))}
    </ul>
  );
}

export function PeriodClosingCard({ online }: { online: boolean }) {
  const { t } = useTranslation("finance");
  const monthLabel = useMonthLabel();
  const canCloseRight = useCan({ permission: "accounting.period.close" });
  const [candidate, readiness, status, error, closeError, justClosed, canClose, notEnded, pending] = useUnit([
    $candidate,
    $readiness,
    $closingStatus,
    $closingError,
    $closeError,
    $justClosed,
    $canClose,
    $periodNotEnded,
    closePeriodFx.pending,
  ]);
  const [mounted, reload, dismiss, close] = useUnit([
    closingMounted,
    closingReloadRequested,
    closingNoticeDismissed,
    closePeriodFx,
  ]);
  const [confirming, setConfirming] = useState(false);

  useEffect(() => {
    mounted({ today: todayIso() });
  }, [mounted]);

  const label = candidate ? monthLabel(candidate) : "";

  return (
    <Card role="region" aria-labelledby="closing-title" className="flex flex-col gap-3" data-testid="period-closing">
      <div className="flex flex-wrap items-center gap-2">
        <Icon as={Lock} size="md" />
        <h2 id="closing-title" className="text-[15px] font-bold">
          {t("closing.title")}
        </h2>
        {readiness ? (
          <StatusChip tone={readiness.ready ? "success" : "destructive"} dot>
            {readiness.ready ? t("closing.ready") : t("closing.notReady")}
          </StatusChip>
        ) : null}
      </div>
      {candidate ? (
        <p className="text-[14px]">
          {t("closing.oldestOpen")} <span className="font-extrabold" data-testid="closing-period">{label}</span>
        </p>
      ) : null}

      {status === "error" && error ? (
        <Banner tone="destructive" icon={CircleAlert}>
          {serverErrorText(error)}{" "}
          <button type="button" className="font-semibold underline" onClick={reload}>
            {t("closing.retry")}
          </button>
        </Banner>
      ) : !readiness ? (
        <Skeleton className="h-16 w-full" />
      ) : (
        <>
          {readiness.blockers.length > 0 ? <BlockerList readiness={readiness} /> : null}
          {readiness.warnings.length > 0 ? <WarningList readiness={readiness} /> : null}
          {readiness.blockers.length === 0 && readiness.warnings.length === 0 ? (
            <p className="text-small text-foreground-secondary">{t("closing.allClear")}</p>
          ) : null}
        </>
      )}

      {notEnded && candidate ? (
        <p className="text-[12px] text-foreground-secondary" data-testid="closing-not-ended">
          {t("closing.notEnded", { period: label })}
        </p>
      ) : null}
      {justClosed ? (
        <Banner
          tone="success"
          icon={CheckCircle2}
          action={
            <Button variant="ghost" size="icon" aria-label={t("shared.close")} onClick={dismiss}>
              <Icon as={X} size="sm" />
            </Button>
          }
        >
          <span data-testid="closing-done">{t("closing.done", { period: monthLabel(justClosed) })}</span>
        </Banner>
      ) : null}
      {closeError ? (
        <Banner tone="destructive" icon={TriangleAlert} live="assertive">
          <span data-testid="closing-error">{serverErrorText(closeError)}</span>
        </Banner>
      ) : null}

      {canCloseRight ? (
        <div className="flex flex-wrap items-center gap-2">
          <Button
            disabled={!online || !canClose || pending}
            onClick={() => setConfirming(true)}
            data-testid="closing-close"
          >
            <Icon as={Lock} size="sm" />
            {t("closing.close", { period: label })}
          </Button>
          <Button variant="ghost" size="sm" onClick={reload} disabled={status === "loading"}>
            <Icon as={RotateCcw} size="sm" />
            {t("closing.recheck")}
          </Button>
        </div>
      ) : null}
      <p className="text-[12px] text-foreground-secondary">{t("closing.irreversible")}</p>

      <ConfirmDialog
        open={confirming}
        onOpenChange={setConfirming}
        title={t("closing.confirmTitle", { period: label })}
        description={t("closing.confirmDescription", { period: label })}
        confirmLabel={t("closing.close", { period: label })}
        cancelLabel={t("shared.back")}
        tone="destructive"
        onConfirm={async () => {
          if (!candidate) return;
          setConfirming(false);
          await close(candidate).catch(() => undefined);
        }}
      >
        {readiness && readiness.warnings.length > 0 ? (
          <div className="flex flex-col gap-1.5">
            <p className="text-[13px] font-semibold">{t("closing.warningsTitle")}</p>
            <WarningList readiness={readiness} />
          </div>
        ) : null}
      </ConfirmDialog>
    </Card>
  );
}
