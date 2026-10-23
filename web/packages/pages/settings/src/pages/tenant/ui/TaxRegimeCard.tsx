import { useUnit } from "effector-react";
import { CalendarClock, TriangleAlert } from "lucide-react";
import { useState } from "react";

import { useTranslation } from "@shared/i18n";
import { formatDate } from "@shared/lib/date";
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
  Icon,
  RadioCard,
  RadioGroup,
  StatusChip,
  toast,
} from "@shared/ui";

import { errorText } from "#/shared/lib/errors.ts";
import { useOnline } from "#/shared/ui/hooks.ts";

import { createTaxRegimeFx, nextMonthStart, type TaxRegime, type TenantSettings } from "../model/index.ts";

/** «Soliq rejimi» (07 BO-14 `taxRegime`, 20 #40c): the change takes effect from the 1st of next month. */
export function TaxRegimeCard({ settings }: { settings: TenantSettings }) {
  const { t } = useTranslation("settings");
  const online = useOnline();
  const [open, setOpen] = useState(false);
  const { current, history } = settings.tax_regime;
  const today = new Date().toISOString().slice(0, 10);
  const scheduled = history.filter((h) => h.valid_from > today);

  return (
    <Card className="flex flex-col gap-3">
      <div className="flex flex-wrap items-start gap-3">
        <div className="min-w-0 flex-1">
          <h3 className="text-[15px] font-bold">{t("tenant.taxRegime.title")}</h3>
          <p className="mt-1 text-[14px]">
            {current ? (
              <strong>{t(`tenant.taxRegime.regime.${current}`)}</strong>
            ) : (
              t("tenant.taxRegime.notSet")
            )}
          </p>
        </div>
        <Button size="sm" variant="secondary" disabled={!online} onClick={() => setOpen(true)}>
          <Icon as={CalendarClock} size="sm" />
          {t("tenant.taxRegime.change")}
        </Button>
      </div>
      {scheduled.map((h) => (
        <StatusChip key={h.valid_from} tone="info" className="self-start">
          {t("tenant.taxRegime.scheduled", {
            regime: t(`tenant.taxRegime.regime.${h.regime}`),
            date: formatDate(h.valid_from),
          })}
        </StatusChip>
      ))}
      <p className="text-small text-foreground-secondary">{t("tenant.taxRegime.hint")}</p>
      {history.length > 0 ? (
        <ul className="flex flex-col gap-1 text-[13px]" aria-label={t("tenant.taxRegime.history")}>
          {history.map((h) => (
            <li key={`${h.valid_from}-${h.regime}`} className="flex gap-2">
              <span className="w-24 tabular-nums text-muted-foreground">{formatDate(h.valid_from)}</span>
              <span>{t(`tenant.taxRegime.regime.${h.regime}`)}</span>
            </li>
          ))}
        </ul>
      ) : null}
      {open ? <TaxRegimeDialog current={current} onClose={() => setOpen(false)} /> : null}
    </Card>
  );
}

function TaxRegimeDialog({ current, onClose }: { current: TaxRegime | null; onClose: () => void }) {
  const { t } = useTranslation("settings");
  const { t: tc } = useTranslation("common");
  const [create, pending] = useUnit([createTaxRegimeFx, createTaxRegimeFx.pending]);
  const [regime, setRegime] = useState<TaxRegime>(current === "vat" ? "turnover" : "vat");
  const [error, setError] = useState<string | null>(null);
  const validFrom = nextMonthStart();

  const submit = async () => {
    setError(null);
    try {
      await create({ regime, validFrom });
      toast.success(t("tenant.taxRegime.saved", { date: formatDate(validFrom) }));
      onClose();
    } catch (e) {
      setError(errorText(e));
    }
  };

  return (
    <Dialog open onOpenChange={(o) => (o ? undefined : onClose())}>
      <DialogContent size="sm">
        <DialogHeader>
          <DialogTitle>{t("tenant.taxRegime.changeTitle")}</DialogTitle>
          <DialogDescription>
            {t("tenant.taxRegime.changeHint", { date: formatDate(validFrom) })}
          </DialogDescription>
        </DialogHeader>
        <RadioGroup
          aria-label={t("tenant.taxRegime.title")}
          value={regime}
          onValueChange={(v) => setRegime(v === "turnover" ? "turnover" : "vat")}
          className="grid gap-2"
        >
          <RadioCard value="vat" title={t("tenant.taxRegime.regime.vat")} />
          <RadioCard value="turnover" title={t("tenant.taxRegime.regime.turnover")} />
        </RadioGroup>
        {error ? (
          <Banner tone="destructive" icon={TriangleAlert} live="assertive">
            {error}
          </Banner>
        ) : null}
        <DialogFooter>
          <Button variant="secondary" onClick={onClose}>
            {tc("actions.cancel")}
          </Button>
          <Button disabled={pending} onClick={() => void submit()}>
            {t("tenant.taxRegime.confirm", { date: formatDate(validFrom) })}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
