import { useUnit } from "effector-react";
import { CalendarClock, TriangleAlert } from "lucide-react";
import { useEffect, useState } from "react";

import { useTranslation } from "@shared/i18n";
import { formatDate } from "@shared/lib/date";
import { useCan } from "@shared/state/permissions";
import {
  Banner,
  Button,
  Card,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  ErrorState,
  Icon,
  Skeleton,
  StatusChip,
  toast,
} from "@shared/ui";

import { errorText } from "#/shared/lib/errors.ts";
import { useOnline } from "#/shared/ui/hooks.ts";

import {
  $valuation,
  $valuationError,
  canRequestValuationChange,
  nextYearStart,
  otherMethod,
  updateValuationFx,
  valuationOpened,
  type ValuationMethod,
} from "../model/index.ts";

/**
 * «Zaxira baholash usuli» (07 BO-14 `costingMethod`, 19 §17, US-M04-05): current method + since when,
 * the scheduled change («{sana} dan: FIFO»), «Usulni o'zgartirish» with the «keyingi hisobot yilidan»
 * confirmation. Changing needs `valuation.settings.manage`; without it the card is read-only.
 */
export function ValuationCard() {
  const { t } = useTranslation("settings");
  const online = useOnline();
  const canManage = useCan({ permission: "valuation.settings.manage" });
  const [valuation, error, opened] = useUnit([$valuation, $valuationError, valuationOpened]);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    opened();
  }, [opened]);

  const method = (m: ValuationMethod) => t(`tenant.valuation.method.${m}`);

  return (
    <Card role="region" className="flex flex-col gap-3" aria-labelledby="valuation-title">
      <div className="flex flex-wrap items-start gap-3">
        <div className="min-w-0 flex-1">
          <h3 id="valuation-title" className="text-[15px] font-bold">
            {t("tenant.valuation.title")}
          </h3>
          {valuation ? (
            <p className="mt-1 text-[14px]">
              <strong>{method(valuation.current_method)}</strong>
              {valuation.effective_from ? (
                <span className="text-foreground-secondary">
                  {" · "}
                  {t("tenant.valuation.since", { date: formatDate(valuation.effective_from) })}
                </span>
              ) : null}
            </p>
          ) : null}
        </div>
        {canManage && valuation && canRequestValuationChange(valuation) ? (
          <Button size="sm" variant="secondary" disabled={!online} onClick={() => setOpen(true)}>
            <Icon as={CalendarClock} size="sm" />
            {t("tenant.valuation.change")}
          </Button>
        ) : null}
      </div>

      {!valuation && error ? (
        <ErrorState message={errorText(error)} onRetry={() => opened()} className="py-4" />
      ) : null}
      {!valuation && !error ? <Skeleton className="h-6 w-56" /> : null}

      {valuation?.pending_change ? (
        <div className="flex flex-col gap-1">
          <StatusChip tone="info" className="self-start">
            {t("tenant.valuation.pending", {
              date: formatDate(valuation.pending_change.effective_from),
              method: method(valuation.pending_change.method),
            })}
          </StatusChip>
          <p className="text-small text-foreground-secondary">{t("tenant.valuation.pendingHint")}</p>
        </div>
      ) : null}
      <p className="text-small text-foreground-secondary">{t("tenant.valuation.hint")}</p>
      {canManage ? null : (
        <p className="text-small text-muted-foreground">{t("tenant.valuation.readOnly")}</p>
      )}
      {open && valuation ? (
        <ValuationDialog current={valuation.current_method} onClose={() => setOpen(false)} />
      ) : null}
    </Card>
  );
}

function ValuationDialog({ current, onClose }: { current: ValuationMethod; onClose: () => void }) {
  const { t } = useTranslation("settings");
  const { t: tc } = useTranslation("common");
  const [update, pending] = useUnit([updateValuationFx, updateValuationFx.pending]);
  const [error, setError] = useState<string | null>(null);
  const target = otherMethod(current);
  const from = nextYearStart();
  const method = (m: ValuationMethod) => t(`tenant.valuation.method.${m}`);

  const submit = async () => {
    setError(null);
    try {
      const result = await update(target);
      toast.success(
        result.pending_change
          ? t("tenant.valuation.savedPending", {
              date: formatDate(result.pending_change.effective_from),
              method: method(result.pending_change.method),
            })
          : t("tenant.valuation.savedNow", { method: method(result.current_method) }),
      );
      onClose();
    } catch (e) {
      setError(errorText(e));
    }
  };

  return (
    <Dialog open onOpenChange={(o) => (o ? undefined : onClose())}>
      <DialogContent size="sm">
        <DialogHeader>
          <DialogTitle>{t("tenant.valuation.dialogTitle", { method: method(target) })}</DialogTitle>
          <DialogDescription>
            {t("tenant.valuation.dialogBody", { date: formatDate(from), current: method(current) })}
          </DialogDescription>
        </DialogHeader>
        <p className="text-small text-foreground-secondary">{t("tenant.valuation.dialogNote")}</p>
        {error ? (
          <Banner tone="destructive" icon={TriangleAlert} live="assertive">
            {error}
          </Banner>
        ) : null}
        <DialogFooter>
          <Button variant="secondary" onClick={onClose}>
            {tc("actions.cancel")}
          </Button>
          <Button disabled={pending} aria-busy={pending || undefined} onClick={() => void submit()}>
            {t("tenant.valuation.confirm", { method: method(target) })}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
