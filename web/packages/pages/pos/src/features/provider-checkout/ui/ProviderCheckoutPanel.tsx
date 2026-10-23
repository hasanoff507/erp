/**
 * POS-03 / POS-13 dynamic payment panel (07 POS-03 «UzQR — dinamik», Click / Payme / Uzum; 18 §16): the QR /
 * link the customer pays with, «To'lov kutilmoqda…» while the server waits for the provider (polling every
 * 2 s), the confirmation, failure / expiry with «Qayta yaratish», and «Bekor qilish». Offline the panel says the
 * payment stays pending and the sale is not closed (QT-M01-13). No card or phone data is asked (PCI).
 */
import { useUnit } from "effector-react";
import { CheckCircle2, CircleAlert, Clock3, Loader2, WifiOff } from "lucide-react";
import { useState } from "react";

import { useTranslation } from "@shared/i18n";
import { formatMoney } from "@shared/lib/format";
import type { Money } from "@shared/lib/money";
import { Banner, Button, ConfirmDialog, Icon } from "@shared/ui";

import { errorText, messageText } from "#/shared/lib/i18n-errors.ts";
import { QrCode } from "#/shared/ui/ReceiptPreview.tsx";

import {
  $checkoutView,
  checkoutCancelled,
  checkoutStarted,
  type CheckoutProvider,
  type CheckoutPurpose,
} from "../model/index.ts";

export interface ProviderCheckoutPanelProps {
  provider: CheckoutProvider;
  purpose: CheckoutPurpose;
  amount: Money;
  cashRegisterId: string | null;
  online: boolean;
}

const time = (iso: string | null) => (iso ? new Date(iso).toLocaleTimeString("uz-UZ", { hour: "2-digit", minute: "2-digit" }) : "");

export function ProviderCheckoutPanel({ provider, purpose, amount, cashRegisterId, online }: ProviderCheckoutPanelProps) {
  const { t } = useTranslation("pos");
  const [c, start, cancel] = useUnit([$checkoutView, checkoutStarted, checkoutCancelled]);
  const [confirmCancel, setConfirmCancel] = useState(false);
  const mine = c && c.provider === provider && c.purpose === purpose ? c : null;
  const canStart = online && cashRegisterId !== null;
  const begin = () => {
    if (cashRegisterId) start({ provider, purpose, amount, cashRegisterId });
  };
  const providerName = t(`payment.method.${provider}`);

  if (!mine) {
    return (
      <div className="flex flex-col gap-3" data-testid="checkout-panel">
        {!online ? (
          <Banner tone="warning" icon={WifiOff}>
            {t("payment.onlineOnly")}
          </Banner>
        ) : null}
        <p className="text-[14px]">{t("checkout.intro", { provider: providerName, amount: formatMoney(amount) })}</p>
        <Button size="pos" disabled={!canStart} onClick={begin} data-testid="checkout-start">
          {t("checkout.create")}
        </Button>
      </div>
    );
  }

  const link = mine.qrPayload ?? mine.checkoutUrl;
  return (
    <div className="flex flex-col gap-3" data-testid="checkout-panel" data-phase={mine.phase}>
      {mine.phase === "creating" ? (
        <p className="flex items-center gap-2 text-[14px]">
          <Icon as={Loader2} size="md" className="animate-spin" />
          {t("checkout.creating")}
        </p>
      ) : null}
      {(mine.phase === "pending" || mine.phase === "confirmed") && link ? (
        <div className="flex items-start gap-4">
          <div className="rounded-lg border border-border bg-white p-2">
            <QrCode data={link} size={176} label={t("checkout.qrLabel", { provider: providerName })} />
          </div>
          <div className="flex min-w-0 flex-col gap-1 text-[13px]">
            <span className="text-[22px] font-extrabold">{formatMoney(mine.amount)}</span>
            <span className="text-muted-foreground">{t("checkout.scanHint", { provider: providerName })}</span>
            <span className="break-all text-[12px] text-foreground-secondary" data-testid="checkout-link">
              {link}
            </span>
            {mine.expiresAt ? (
              <span className="flex items-center gap-1 text-muted-foreground">
                <Icon as={Clock3} size="sm" />
                {t("checkout.expiresAt", { time: time(mine.expiresAt) })}
              </span>
            ) : null}
          </div>
        </div>
      ) : null}
      {mine.phase === "pending" ? (
        <Banner tone={mine.offline ? "warning" : "info"} icon={mine.offline ? WifiOff : Loader2} live="polite">
          <span data-testid="checkout-waiting">
            {mine.offline ? t("checkout.offlinePending") : t("checkout.waiting")}
          </span>
        </Banner>
      ) : null}
      {mine.phase === "confirmed" ? (
        <Banner tone="success" icon={CheckCircle2} live="assertive">
          <span data-testid="checkout-confirmed">{t("checkout.confirmed", { provider: providerName })}</span>
        </Banner>
      ) : null}
      {mine.phase === "failed" || mine.phase === "expired" || mine.phase === "error" ? (
        <Banner
          tone="destructive"
          icon={CircleAlert}
          live="assertive"
          action={
            <Button size="sm" variant="secondary" disabled={!canStart} onClick={begin} data-testid="checkout-retry">
              {t("checkout.retry")}
            </Button>
          }
        >
          <span data-testid="checkout-error">
            {mine.phase === "error" && mine.error
              ? mine.error.code.startsWith("validation.")
                ? messageText(mine.error.code, null)
                : errorText(mine.error.code, mine.error.params)
              : t(`checkout.${mine.phase === "expired" ? "expired" : "failed"}`)}
          </span>
        </Banner>
      ) : null}
      {mine.phase === "pending" || mine.phase === "creating" ? (
        <Button variant="secondary" size="pos" onClick={() => setConfirmCancel(true)} data-testid="checkout-cancel">
          {t("checkout.cancel")}
        </Button>
      ) : null}
      {confirmCancel ? (
        <ConfirmDialog
          open
          onOpenChange={(o) => !o && setConfirmCancel(false)}
          title={t("checkout.cancelTitle")}
          description={t("checkout.cancelText")}
          confirmLabel={t("checkout.cancelYes")}
          cancelLabel={t("sale.cancel")}
          onConfirm={() => {
            setConfirmCancel(false);
            cancel();
          }}
        />
      ) : null}
    </div>
  );
}
