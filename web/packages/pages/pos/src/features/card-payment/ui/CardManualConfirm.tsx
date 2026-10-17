/**
 * CardManualConfirm (08 §7.2; qaror #64, 21 §9.2): «Karta terminalsiz (rekvizitsiz)» — the amount, the reason
 * and ONE button «Karta terminalsiz qabul qilindi». There is no card input of any kind (type, mask, RRN,
 * approval code). The approval dialog opens only on a register with a bound terminal under `manager_approval`.
 */
import { CheckCircle2, CircleAlert, ShieldCheck } from "lucide-react";

import { useTranslation } from "@shared/i18n";
import { formatMoney } from "@shared/lib/format";
import type { Money } from "@shared/lib/money";
import { Banner, Button, Icon } from "@shared/ui";

import type { ManualReason } from "../model/types/index.ts";
import { codeText, dyn } from "./i18n.ts";

export interface CardManualConfirmProps {
  amount: Money;
  manualReason: ManualReason;
  requiresApproval: boolean;
  errorCode: string | null;
  onConfirm: () => void;
}

export function CardManualConfirm({
  amount,
  manualReason,
  requiresApproval,
  errorCode,
  onConfirm,
}: CardManualConfirmProps) {
  const { t: tt } = useTranslation("pos");
  const t = dyn(tt);
  return (
    <section
      data-testid="card-manual-confirm"
      aria-labelledby="card-manual-title"
      className="flex flex-col gap-3 rounded-xl border border-border bg-muted/40 p-4"
    >
      <h2 id="card-manual-title" className="text-[17px] font-extrabold">
        {t("cardPayment.manual.title")}
      </h2>
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-[14px]">
        <dt className="text-foreground-secondary">{t("cardPayment.manual.amount")}</dt>
        <dd className="font-extrabold tabular-nums">{formatMoney(amount)}</dd>
        <dt className="text-foreground-secondary">{t("cardPayment.manual.reason")}</dt>
        <dd className="font-semibold">{t(`cardPayment.manual.reasons.${manualReason}`)}</dd>
      </dl>
      <p className="text-[13px] text-foreground-secondary">{t("cardPayment.manual.hint")}</p>
      {errorCode ? (
        <Banner tone="destructive" icon={CircleAlert} live="assertive">
          {codeText(errorCode)}
        </Banner>
      ) : null}
      <Button size="pos-cta" onClick={onConfirm}>
        <Icon as={requiresApproval ? ShieldCheck : CheckCircle2} />
        {t("cardPayment.manual.confirm")}
      </Button>
      {requiresApproval ? (
        <p className="text-[12px] font-semibold text-warning-strong">
          {t("cardPayment.manual.needsApproval")}
        </p>
      ) : null}
    </section>
  );
}
