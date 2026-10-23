/**
 * POS-03 «To'lov» (07 POS-03, 06 §6 POS-03 wireframes, mockup Pos03Tolov.dc.html): modal over POS-02 —
 * method grid 4 × 2 (Naqd, Karta, UzQR, Click, Payme, Uzum, Aralash, Nasiya; Click/Payme/Uzum need a provider
 * checkout — not connected, always disabled; UzQR static only online), the chosen method's panel, and the
 * aside: receipt content, «To'lanadigan», split, primary action, «Sotishga qaytish (Esc)». The card panel is
 * features/card-payment's `CardPayment` (embedded as is); while it is locked Esc does nothing.
 * PCI: there is no input that accepts card data on this screen.
 */
import { useUnit } from "effector-react";
import {
  Banknote,
  BookUser,
  CircleAlert,
  CreditCard,
  Layers,
  QrCode,
  Smartphone,
  Trash2,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { useTranslation } from "@shared/i18n";
import { formatMoney, formatPercent } from "@shared/lib/format";
import type { Money } from "@shared/lib/money";
import { $fiscalLadder } from "@shared/offline";
import { $isOnline } from "@shared/state/network";
import {
  Banner,
  Button,
  cn,
  ConfirmDialog,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  Icon,
  Input,
  Kbd,
  Label,
  MoneyInput,
  type LucideIcon,
} from "@shared/ui";

import { $draft, $totals, cmpMoney, isPositive, sumMoney } from "#/entities/receipt-draft/index.ts";
import { $posCashier, cashierCan } from "#/entities/pos-session/index.ts";
import {
  $cardPanelLocked,
  $cardPaymentOutcome,
  $cardPhase,
  CardPayment,
  saleCancelled,
} from "#/features/card-payment/index.ts";
import { errorText } from "#/shared/lib/i18n-errors.ts";
import { posPrinter } from "#/shared/lib/device-runtime.ts";
import { useHotkeys } from "#/shared/lib/use-hotkeys.ts";

import { $fiscalDeviceLocked } from "../model/context.ts";
import type { PaymentPart, PayMethod } from "../model/lib/sale-payload.ts";
import {
  $cardPart,
  $change,
  $payment,
  $paymentError,
  $remaining,
  cardStartRequested,
  cashReceivedChanged,
  completeSaleFx,
  confirmPressed,
  electronicChosen,
  mixedPartAdded,
  mixedPartRemoved,
  modeChosen,
  paymentClosed,
  paymentErrorDismissed,
  partsFor,
  uzqrRefChanged,
  type PayMode,
} from "../model/payment.ts";
import { DebtSalePanel, debtReady, useDebtView } from "./DebtSalePanel.tsx";

interface MethodButton {
  id: PayMode | "click" | "payme" | "uzum";
  icon: LucideIcon;
  hint: string;
  disabled: boolean;
  tone?: "warning";
}

function MethodGrid({
  methods,
  active,
  onPick,
}: {
  methods: MethodButton[];
  active: PayMode | null;
  onPick: (m: PayMode) => void;
}) {
  const { t } = useTranslation("pos");
  return (
    <div className="grid grid-cols-4 gap-2" role="radiogroup" aria-label={t("payment.methodsLabel")}>
      {methods.map((m) => {
        const selected = m.id === active;
        return (
          <button
            key={m.id}
            type="button"
            role="radio"
            aria-checked={selected}
            disabled={m.disabled}
            data-testid={`method-${m.id}`}
            onClick={() => onPick(m.id as PayMode)}
            className={cn(
              "flex h-[76px] flex-col items-start justify-center gap-0.5 rounded-xl border px-3 text-left disabled:opacity-50",
              selected
                ? "border-primary bg-primary-soft"
                : "border-border bg-background hover:border-primary",
              m.tone === "warning" && !selected && "border-warning-border bg-warning-soft/40",
            )}
          >
            <span className="flex items-center gap-2 text-[15px] font-extrabold">
              <Icon as={m.icon} size="lg" />
              {t(`payment.method.${m.id}`)}
            </span>
            <span className="text-[12px] text-muted-foreground">{m.hint}</span>
          </button>
        );
      })}
    </div>
  );
}

function CashPanel({ total }: { total: Money }) {
  const { t } = useTranslation("pos");
  const [p, change, setReceived] = useUnit([$payment, $change, cashReceivedChanged]);
  useEffect(() => {
    if (p && !p.cashReceived) setReceived(total);
  }, [p, total, setReceived]);
  const quick = ["1000", "5000", "10000", "50000", "100000", "200000"];
  return (
    <div className="flex flex-col gap-3">
      <Label htmlFor="pos-cash">{t("payment.cashReceived")}</Label>
      <MoneyInput
        id="pos-cash"
        data-testid="cash-received"
        autoFocus
        value={p?.cashReceived ?? ""}
        onChange={setReceived}
        className="h-16 text-[26px] font-extrabold"
      />
      <div className="flex flex-wrap gap-2">
        {quick.map((q) => (
          <Button key={q} size="sm" variant="secondary" onClick={() => setReceived(`${q}.00`)}>
            {formatMoney(q, { withCurrency: false })}
          </Button>
        ))}
      </div>
      <div className="flex items-baseline justify-between rounded-xl bg-muted px-4 py-3">
        <span className="font-bold">{t("payment.change")}</span>
        <span className="text-[26px] font-extrabold" data-testid="cash-change">
          {change ? formatMoney(change) : t("payment.cashNotEnough")}
        </span>
      </div>
    </div>
  );
}

function UzqrPanel({ online }: { online: boolean }) {
  const { t } = useTranslation("pos");
  const [p, setRef] = useUnit([$payment, uzqrRefChanged]);
  return (
    <div className="flex flex-col gap-3">
      {!online ? (
        <Banner tone="warning" icon={CircleAlert}>
          {t("payment.onlineOnly")}
        </Banner>
      ) : (
        <p className="text-[14px]">{t("payment.uzqrHint")}</p>
      )}
      <Label htmlFor="pos-uzqr-ref">{t("payment.uzqrRef")}</Label>
      <Input
        id="pos-uzqr-ref"
        maxLength={40}
        value={p?.uzqrRef ?? ""}
        onChange={(e) => setRef(e.target.value)}
        className="h-12"
      />
    </div>
  );
}

function MixedPanel({ online }: { online: boolean }) {
  const { t } = useTranslation("pos");
  const [p, remaining, cardPart, cardPhase, add, remove, startCard, draft] = useUnit([
    $payment,
    $remaining,
    $cardPart,
    $cardPhase,
    mixedPartAdded,
    mixedPartRemoved,
    cardStartRequested,
    $draft,
  ]);
  const [method, setMethod] = useState<PayMethod>("cash");
  const [typed, setAmount] = useState<string | null>(null);
  const amount = typed ?? remaining;
  const cardBusy =
    cardPart !== null || (cardPhase !== "idle" && cardPhase !== "declined" && cardPhase !== "voided");
  const valid = isPositive(amount || "0") && cmpMoney(amount || "0", remaining) <= 0;
  const methods: { id: PayMethod; disabled: boolean }[] = [
    { id: "cash", disabled: false },
    { id: "card", disabled: cardBusy },
    { id: "uzqr", disabled: !online },
    { id: "debt", disabled: !draft.customerId },
  ];
  return (
    <div className="flex flex-col gap-3">
      <ul className="flex flex-col gap-1" data-testid="mixed-parts">
        {(p?.parts ?? []).map((part, i) => (
          <li key={i} className="flex items-center gap-2 rounded-lg bg-muted px-3 py-2">
            <span className="flex-1 font-bold">{t(`payment.method.${part.method}`)}</span>
            <span className="font-extrabold">{formatMoney(part.amount)}</span>
            <Button size="sm" variant="ghost" aria-label={t("payment.removePart")} onClick={() => remove(i)}>
              <Icon as={Trash2} size="sm" />
            </Button>
          </li>
        ))}
        {cardPart ? (
          <li className="flex items-center gap-2 rounded-lg bg-muted px-3 py-2">
            <span className="flex-1 font-bold">{t("payment.method.card")}</span>
            <span className="font-extrabold">{formatMoney(cardPart.amount)}</span>
          </li>
        ) : null}
      </ul>
      {isPositive(remaining) ? (
        <div className="flex flex-wrap items-end gap-2">
          <div className="flex gap-1" role="radiogroup" aria-label={t("payment.mixedMethod")}>
            {methods.map((m) => (
              <Button
                key={m.id}
                size="sm"
                role="radio"
                aria-checked={method === m.id}
                variant={method === m.id ? "default" : "secondary"}
                disabled={m.disabled}
                onClick={() => setMethod(m.id)}
              >
                {t(`payment.method.${m.id}`)}
              </Button>
            ))}
          </div>
          <MoneyInput
            aria-label={t("payment.partAmount")}
            data-testid="mixed-amount"
            value={amount}
            onChange={setAmount}
            className="h-11 w-44"
          />
          <Button
            size="default"
            disabled={!valid}
            data-testid="mixed-add"
            onClick={() => {
              const value = (amount || "0") as Money;
              if (method === "card") startCard(value);
              else add({ method, amount: value });
              setAmount(null);
            }}
          >
            {method === "card" ? t("payment.sendToTerminal") : t("payment.addPart")}
          </Button>
        </div>
      ) : null}
      {method === "debt" && !draft.customerId ? (
        <p className="text-[13px] text-muted-foreground">{t("payment.debtNeedsCustomer")}</p>
      ) : null}
    </div>
  );
}

export interface PaymentDialogProps {
  receiptLabel: string;
  onDone: () => void;
}

export function PaymentDialog({ receiptLabel, onDone }: PaymentDialogProps) {
  const { t } = useTranslation("pos");
  const [
    p,
    totals,
    remaining,
    online,
    ladder,
    fiscalLocked,
    cardPart,
    cardOutcome,
    locked,
    error,
    pending,
    cashier,
    draft,
  ] = useUnit([
    $payment,
    $totals,
    $remaining,
    $isOnline,
    $fiscalLadder,
    $fiscalDeviceLocked,
    $cardPart,
    $cardPaymentOutcome,
    $cardPanelLocked,
    $paymentError,
    completeSaleFx.pending,
    $posCashier,
    $draft,
  ]);
  const [uzqrConfirm, setUzqrConfirm] = useState(false);
  const [printerReady, setPrinterReady] = useState<boolean | null>(null);
  useEffect(() => {
    let alive = true;
    void posPrinter()
      .then((port) => port.status())
      .then((s) => alive && setPrinterReady(s.state === "ready"))
      .catch(() => alive && setPrinterReady(false));
    return () => {
      alive = false;
    };
  }, []);

  const blocked = ladder.level === "blocked48" || fiscalLocked;
  const choose = (mode: PayMode) => {
    paymentErrorDismissed();
    modeChosen(mode);
    if (mode === "card" && !blocked) cardStartRequested(totals.total);
  };

  const methods: MethodButton[] = [
    { id: "cash", icon: Banknote, hint: t("payment.hint.cash"), disabled: false },
    { id: "card", icon: CreditCard, hint: t("payment.hint.card"), disabled: blocked },
    { id: "uzqr", icon: QrCode, hint: t("payment.hint.uzqr"), disabled: !online },
    { id: "click", icon: Smartphone, hint: t("payment.hint.provider"), disabled: true },
    { id: "payme", icon: Smartphone, hint: t("payment.hint.provider"), disabled: true },
    { id: "uzum", icon: Smartphone, hint: t("payment.hint.provider"), disabled: true },
    { id: "mixed", icon: Layers, hint: t("payment.hint.mixed"), disabled: false },
    {
      id: "debt",
      icon: BookUser,
      hint: t("payment.hint.debt"),
      disabled: !cashierCan(cashier, "debts.create"),
      tone: "warning",
    },
  ];

  const parts: PaymentPart[] = p ? partsFor(p, totals.total, cardPart) : [];
  // B4 (w-debts): the debt part needs a customer and its over-limit step (approval online / confirm offline)
  const debtPart = sumMoney(parts.filter((x) => x.method === "debt").map((x) => x.amount));
  const debtView = useDebtView(draft.customerId);
  const debtOk =
    !isPositive(debtPart) ||
    debtReady(debtView, debtPart, online, p?.debtApproval != null, p?.debtOverLimitConfirmed === true);
  const cardIntegrated = cardOutcome?.mode === "integrated";
  const canConfirm =
    !!p?.mode &&
    !pending &&
    !(blocked && parts.some((x) => x.method !== "debt")) &&
    !(p.mode === "card" && cardPart === null) &&
    !(p.mode === "mixed" && isPositive(remaining)) &&
    !(p.mode === "uzqr" && !online) &&
    debtOk;
  const close = () => {
    if (locked) return;
    if (cardIntegrated) return; // an approved card must be finished or voided («Sotuvni bekor qilish»)
    paymentClosed();
    onDone();
  };

  // Esc goes through Radix `onEscapeKeyDown` (UX-01); Enter is scoped to this dialog (UX-02)
  const dialogRef = useRef<HTMLDivElement | null>(null);
  useHotkeys(
    [
      {
        key: "Enter",
        allowInInput: true,
        handler: () => {
          if (!canConfirm) return false;
          if (p?.mode === "uzqr") setUzqrConfirm(true);
          else confirmPressed();
          return true;
        },
      },
    ],
    { enabled: !uzqrConfirm, scope: dialogRef },
  );

  if (!p) return null;
  const paidSplit = sumMoney(parts.map((x) => x.amount));

  return (
    <Dialog open onOpenChange={(o) => !o && close()}>
      <DialogContent
        ref={dialogRef}
        hideClose
        onEscapeKeyDown={(e) => {
          e.preventDefault();
          close(); // refuses while the card panel is locked or an approved card waits (07 POS-03)
        }}
        onInteractOutside={(e) => e.preventDefault()}
        className="max-w-[1080px] p-0"
        aria-describedby={undefined}
        data-testid="payment-dialog"
      >
        <div className="flex min-h-[620px]">
          <div className="flex min-w-0 flex-1 flex-col gap-4 p-6">
            <div className="flex items-center gap-3">
              <DialogTitle className="text-[24px] font-extrabold">{t("payment.title")}</DialogTitle>
              <span className="rounded-lg bg-muted px-2 py-1 text-[13px] font-bold">{receiptLabel}</span>
            </div>
            <DialogDescription className="sr-only">{t("payment.description")}</DialogDescription>
            {ladder.level === "blocked48" ? (
              <Banner tone="destructive" icon={CircleAlert} live="assertive">
                {t("fiscalLadder.blockedBanner")}
              </Banner>
            ) : null}
            {fiscalLocked ? (
              <Banner tone="destructive" icon={CircleAlert}>
                {errorText("FISCAL_DEVICE_LOCKED")}
              </Banner>
            ) : null}
            <MethodGrid methods={methods} active={p.mode} onPick={choose} />
            {!online ? <p className="text-[13px] text-muted-foreground">{t("payment.offlineNote")}</p> : null}

            <div className="min-h-0 flex-1">
              {p.mode === "cash" ? <CashPanel total={totals.total} /> : null}
              {p.mode === "uzqr" ? <UzqrPanel online={online} /> : null}
              {p.mode === "debt" ? <DebtSalePanel amount={totals.total} online={online} /> : null}
              {p.mode === "mixed" ? <MixedPanel online={online} /> : null}
              {p.mode === "mixed" && parts.some((x) => x.method === "debt") ? (
                <div className="mt-3">
                  <DebtSalePanel amount={debtPart} online={online} />
                </div>
              ) : null}
              {p.mode === "card" || p.mode === "mixed" ? <CardPayment /> : null}
              {p.mode === null ? <p className="text-muted-foreground">{t("payment.chooseMethod")}</p> : null}
            </div>

            {printerReady === false && !p.electronic ? (
              <Banner
                tone="warning"
                icon={CircleAlert}
                action={
                  <Button size="sm" variant="warning" onClick={() => electronicChosen("printer_failure")}>
                    {t("payment.useElectronic")}
                  </Button>
                }
              >
                {t("payment.printerNotReady")}
              </Banner>
            ) : null}
            <label className="flex items-center gap-2 text-[14px]">
              <input
                type="checkbox"
                className="h-5 w-5"
                checked={p.electronic !== null}
                onChange={(e) =>
                  electronicChosen(
                    e.target.checked
                      ? printerReady === false
                        ? "printer_failure"
                        : "customer_request"
                      : null,
                  )
                }
              />
              {p.electronic === "printer_failure"
                ? t("payment.electronicPrinter")
                : t("payment.electronicCustomer")}
            </label>
          </div>

          <aside className="flex w-[360px] shrink-0 flex-col gap-3 border-l border-border bg-background p-6">
            <h3 className="text-[15px] font-extrabold">{t("payment.composition")}</h3>
            <ul className="flex max-h-[180px] flex-col gap-1 overflow-y-auto text-[13px]">
              {totals.lines.map((l) => (
                <li key={l.id} className="flex justify-between gap-2">
                  <span className="truncate">{l.name}</span>
                  <span className="font-bold">{formatMoney(l.total, { withCurrency: false })}</span>
                </li>
              ))}
            </ul>
            <dl className="flex flex-col gap-1 border-t border-border pt-2 text-[13px]">
              <div className="flex justify-between">
                <dt>{t("sale.subtotal")}</dt>
                <dd>{formatMoney(totals.subtotal, { withCurrency: false })}</dd>
              </div>
              <div className="flex justify-between">
                <dt>{t("sale.discount")}</dt>
                <dd>−{formatMoney(totals.discount, { withCurrency: false })}</dd>
              </div>
              {totals.vat.map((v) => (
                <div key={v.rate} className="flex justify-between">
                  <dt>{t("sale.vatIncluded", { rate: formatPercent(v.rate) })}</dt>
                  <dd>{formatMoney(v.amount, { precision: 2, withCurrency: false })}</dd>
                </div>
              ))}
            </dl>
            <div className="rounded-xl bg-card p-3">
              <div className="text-[13px] text-muted-foreground">{t("payment.due")}</div>
              <div className="text-[32px] font-extrabold leading-tight" data-testid="payment-due">
                {formatMoney(totals.total)}
              </div>
            </div>
            <ul className="flex flex-col gap-1 text-[13px]" data-testid="payment-split">
              {parts.map((x, i) => (
                <li key={i} className="flex justify-between">
                  <span>
                    {t(`payment.split.${x.card?.mode === "integrated" ? "cardTerminal" : x.method}`)}
                  </span>
                  <span className="font-bold">{formatMoney(x.amount, { withCurrency: false })}</span>
                </li>
              ))}
              <li className="flex justify-between border-t border-border pt-1">
                <span>{t("payment.rest")}</span>
                <span className="font-bold">
                  {formatMoney(cmpMoney(paidSplit, totals.total) >= 0 ? "0" : remaining, {
                    withCurrency: false,
                  })}
                </span>
              </li>
            </ul>
            {p.mode === "card" ? (
              <p className="text-[12px] text-foreground-secondary">{t("payment.cardAutoReceipt")}</p>
            ) : null}
            {error ? (
              <Banner tone="destructive" icon={CircleAlert} live="assertive">
                <span data-testid="payment-error">{errorText(error.code, error.params ?? {})}</span>
              </Banner>
            ) : null}
            <div className="grow" />
            {p.mode === "card" && cardPart === null ? (
              <Button size="pos-cta" className="w-full" disabled>
                {locked ? t("payment.waitingBank") : t("payment.confirm")}
              </Button>
            ) : (
              <Button
                size="pos-cta"
                className="w-full"
                disabled={!canConfirm}
                data-testid="payment-confirm"
                onClick={() => (p.mode === "uzqr" ? setUzqrConfirm(true) : confirmPressed())}
              >
                {p.mode === "uzqr" ? t("payment.uzqrReceived") : t("payment.confirm")}
                <Kbd keys="Enter" inverted />
              </Button>
            )}
            {cardIntegrated ? (
              <Button
                size="pos"
                variant="destructive-outline"
                className="w-full"
                onClick={() => saleCancelled()}
              >
                {t("payment.cancelSaleWithCard")}
              </Button>
            ) : (
              <Button
                size="pos"
                variant="secondary"
                className="w-full"
                disabled={locked}
                onClick={close}
                data-testid="payment-back"
              >
                {t("payment.back")}
                <Kbd keys="Esc" />
              </Button>
            )}
          </aside>
        </div>
        {uzqrConfirm ? (
          <ConfirmDialog
            open
            onOpenChange={(o) => !o && setUzqrConfirm(false)}
            title={t("payment.uzqrConfirmTitle")}
            description={t("payment.uzqrConfirmText", { amount: formatMoney(totals.total) })}
            confirmLabel={t("payment.uzqrConfirmYes")}
            cancelLabel={t("sale.cancel")}
            onConfirm={() => {
              setUzqrConfirm(false);
              confirmPressed();
            }}
          />
        ) : null}
      </DialogContent>
    </Dialog>
  );
}
