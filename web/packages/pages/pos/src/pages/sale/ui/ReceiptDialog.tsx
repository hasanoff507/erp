/**
 * POS-04 «Chek» (07 POS-04, mockup Pos04Chek.dc.html): left — «Chek chop etildi», number / date / cashier,
 * «To'landi», fiscal requisites (pending → «Fiskal belgi kutilmoqda», fiscalized → sign + QR, failed → retry),
 * «Qayta chop etish» (Ctrl+P, «NUSXA»), electronic receipt (reason + QR on screen), printer error → warning +
 * «Uskunalarni sozlash» (POS-16), «Yangi chek» (Enter); right — ReceiptPreview. After a successful print the
 * screen returns to POS-02 in 5 s (06 §1.1); on a printer error it stays.
 */
import { useUnit } from "effector-react";
import { CircleAlert, CircleCheck, Printer, QrCode as QrIcon, RefreshCw, WifiOff } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { useTranslation } from "@shared/i18n";
import { formatMoney } from "@shared/lib/format";
import { $isOnline } from "@shared/state/network";
import {
  Banner,
  Button,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  Icon,
  Kbd,
  StatusChip,
} from "@shared/ui";

import { tashkentDateTime } from "#/shared/lib/dates.ts";
import { dyn, errorText } from "#/shared/lib/i18n-errors.ts";
import { useHotkeys } from "#/shared/lib/use-hotkeys.ts";
import { QrCode, ReceiptPreview } from "#/shared/ui/ReceiptPreview.tsx";

import { $storeInfo } from "../model/context.ts";
import { $lastSale } from "../model/payment.ts";
import {
  $canReprint,
  $electronic,
  $printState,
  $receiptFiscal,
  $reprintCount,
  electronicShown,
  fiscalRetryRequested,
  printFx,
  printRequested,
  receiptDoc,
  receiptOpened,
} from "../model/receipt.ts";

const AUTO_RETURN_MS = 5_000;

export function ReceiptDialog({
  onNewReceipt,
  equipmentPath,
}: {
  onNewReceipt: () => void;
  equipmentPath: string;
}) {
  const { t: tt } = useTranslation("pos");
  const t = dyn(tt);
  const [sale, store, fiscalView, print, electronic, canReprint, reprints, online, printing] = useUnit([
    $lastSale,
    $storeInfo,
    $receiptFiscal,
    $printState,
    $electronic,
    $canReprint,
    $reprintCount,
    $isOnline,
    printFx.pending,
  ]);
  const [askReason, setAskReason] = useState(false);

  useEffect(() => {
    receiptOpened();
  }, []);

  // 06 §1.1: back to the sale 5 s after a successful first print (not after a printer error)
  useEffect(() => {
    if (print.kind !== "printed" || print.copy || electronic) return undefined;
    const timer = setTimeout(onNewReceipt, AUTO_RETURN_MS);
    return () => clearTimeout(timer);
  }, [print, electronic, onNewReceipt]);

  const dialogRef = useRef<HTMLDivElement | null>(null);
  useHotkeys(
    [
      { key: "Enter", handler: onNewReceipt },
      {
        key: "p",
        ctrl: true,
        allowInInput: true,
        handler: () => {
          if (canReprint) printRequested({ copy: true });
        },
      },
    ],
    { scope: dialogRef },
  );

  const doc = useMemo(
    () => (sale ? receiptDoc(sale, store, fiscalView, false) : null),
    [sale, store, fiscalView],
  );
  if (!sale || !doc) return null;

  const status = fiscalView?.status ?? "local";
  const printerError = print.kind === "error" ? print.code : null;
  const showElectronic =
    electronic ?? (sale.delivery === "electronic" ? (sale.deliveryReason ?? "customer_request") : null);
  const paid = sale.totals.total;

  return (
    <Dialog open onOpenChange={(o) => !o && onNewReceipt()}>
      <DialogContent
        ref={dialogRef}
        hideClose
        className="max-w-[1040px] p-0"
        onEscapeKeyDown={(e) => {
          e.preventDefault();
          onNewReceipt(); // Esc = «Yangi chek» (UX-01)
        }}
        data-testid="receipt-dialog"
      >
        <div className="flex max-h-[calc(100dvh-4rem)] min-h-[600px]">
          <div className="flex min-w-0 flex-1 flex-col gap-4 overflow-y-auto p-6">
            <div className="flex items-center gap-3">
              <Icon as={CircleCheck} size="xl" className="text-success-strong" />
              <DialogTitle className="text-[24px] font-extrabold">
                {printerError || showElectronic ? t("receipt.titleSaved") : t("receipt.titlePrinted")}
              </DialogTitle>
              {sale.isOffline || !online ? (
                <StatusChip tone="warning" icon={WifiOff}>
                  {t("receipt.offline")}
                </StatusChip>
              ) : null}
            </div>
            <DialogDescription>
              {t("receipt.meta", {
                number: fiscalView?.number ?? sale.tempNumber,
                seq: sale.receiptSeq ?? "—",
                at: tashkentDateTime(sale.createdAt),
                cashier: sale.cashierName,
              })}
            </DialogDescription>
            <div className="rounded-xl bg-muted p-4">
              <div className="text-[13px] text-muted-foreground">{t("receipt.paid")}</div>
              <div className="text-[34px] font-extrabold" data-testid="receipt-paid">
                {formatMoney(paid)}
              </div>
              {sale.change && sale.change !== "0.00" ? (
                <div className="text-[16px] font-bold">
                  {t("receipt.change", { amount: formatMoney(sale.change) })}
                </div>
              ) : null}
            </div>

            <section aria-label={t("receipt.fiscalTitle")} className="flex flex-col gap-1 text-[14px]">
              <h3 className="font-extrabold">{t("receipt.fiscalTitle")}</h3>
              <div className="flex items-center gap-2" data-testid="fiscal-status">
                <StatusChip
                  tone={status === "fiscalized" ? "success" : status === "failed" ? "destructive" : "warning"}
                  dot
                >
                  {t(`receipt.fiscal.${status}`)}
                </StatusChip>
                {fiscalView?.errorCode ? (
                  <span className="text-destructive">{errorText(fiscalView.errorCode)}</span>
                ) : null}
              </div>
              {status === "fiscalized" && fiscalView ? (
                <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5">
                  <dt className="text-muted-foreground">{t("receipt.fiscalSign")}</dt>
                  <dd className="font-mono">{fiscalView.fiscalSign}</dd>
                  <dt className="text-muted-foreground">{t("receipt.fmReceiptSeq")}</dt>
                  <dd>{String(fiscalView.fmReceiptSeq ?? "")}</dd>
                </dl>
              ) : null}
              {status === "failed" && fiscalView?.fiscalReceiptId ? (
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={!online}
                  onClick={() => fiscalRetryRequested()}
                >
                  <Icon as={RefreshCw} size="sm" />
                  {t("receipt.fiscalRetry")}
                </Button>
              ) : null}
            </section>

            {printerError ? (
              <Banner
                tone="destructive"
                icon={CircleAlert}
                live="assertive"
                action={
                  <Button asChild size="sm" variant="secondary">
                    <Link to={equipmentPath}>{t("receipt.equipment")}</Link>
                  </Button>
                }
              >
                <span data-testid="printer-error">{t(`equipment.printer.errors.${printerError}`)}</span>
              </Banner>
            ) : null}

            <div className="flex flex-wrap gap-2">
              <Button
                size="pos"
                variant="secondary"
                disabled={!canReprint || printing}
                onClick={() => printRequested({ copy: true })}
                data-testid="reprint"
                title={canReprint ? undefined : t("receipt.reprintWaits")}
              >
                <Icon as={Printer} size="lg" />
                {t("receipt.reprint")}
                <Kbd keys="Ctrl+P" />
              </Button>
              <Button
                size="pos"
                variant="secondary"
                onClick={() => setAskReason(true)}
                data-testid="electronic"
              >
                <Icon as={QrIcon} size="lg" />
                {t("receipt.electronic")}
              </Button>
            </div>
            {!canReprint ? (
              <p className="text-[12px] text-muted-foreground">{t("receipt.reprintWaits")}</p>
            ) : null}
            {reprints > 0 ? (
              <p className="text-[12px] text-muted-foreground">{t("receipt.reprinted", { n: reprints })}</p>
            ) : null}

            {askReason ? (
              <div className="flex flex-wrap items-center gap-2 rounded-xl border border-border p-3">
                <span className="text-[14px] font-bold">{t("receipt.electronicReason")}</span>
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => {
                    electronicShown("printer_failure");
                    setAskReason(false);
                  }}
                >
                  {t("receipt.reason.printer_failure")}
                </Button>
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => {
                    electronicShown("customer_request");
                    setAskReason(false);
                  }}
                >
                  {t("receipt.reason.customer_request")}
                </Button>
              </div>
            ) : null}
            {showElectronic ? (
              <div
                className="flex items-center gap-4 rounded-xl border border-border p-3"
                data-testid="electronic-receipt"
              >
                {fiscalView?.qrUrl ? (
                  <QrCode data={fiscalView.qrUrl} size={140} label={t("receipt.electronicQr")} />
                ) : (
                  <p className="text-[14px]">{t("receipt.electronicPending")}</p>
                )}
                <div className="text-[13px]">
                  <div className="font-bold">{t(`receipt.reason.${showElectronic}`)}</div>
                  <div className="text-muted-foreground">{t("receipt.electronicHint")}</div>
                </div>
              </div>
            ) : null}

            <div className="grow" />
            <Button size="pos-cta" className="w-full" onClick={onNewReceipt} data-testid="new-receipt">
              {t("receipt.newReceipt")}
              <Kbd keys="Enter" inverted />
            </Button>
          </div>
          <aside className="w-[460px] shrink-0 overflow-y-auto border-l border-border bg-background p-6">
            <ReceiptPreview doc={doc} />
          </aside>
        </div>
      </DialogContent>
    </Dialog>
  );
}
