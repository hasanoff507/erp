/**
 * POS-06 — Nasiyaga sotish (07, route /pos/sale/credit; mockup Pos06Nasiya.dc.html), an overlay of POS-02
 * opened by NASIYA / F5: customer (pick, or «+ Yangi mijoz» name + phone — offline too, US-M08-05), current
 * debt / this sale / after the sale against the credit limit, promise date (7/14/30 days), comment, and
 * «NASIYAGA RASMIYLASHTIRISH» (Enter): `sale.created` with `payments[{method:"debt", due_date}]`, posted with
 * `fiscal.status='deferred'` — no fiscal receipt now (qaror #30), POS-04 does not open. Over the limit: online
 * a Manager approval, offline the cashier's confirmation (16 §5). Esc → back to the sale.
 */
import { useUnit } from "effector-react";
import { CircleAlert, ReceiptText } from "lucide-react";
import { useEffect, useRef } from "react";

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
  Label,
  Textarea,
} from "@shared/ui";

import { $draft, $totals } from "#/entities/receipt-draft/index.ts";
import { $posCashier, cashierCan } from "#/entities/pos-session/index.ts";
import { errorText } from "#/shared/lib/i18n-errors.ts";
import { useHotkeys } from "#/shared/lib/use-hotkeys.ts";

import {
  $payment,
  $paymentError,
  commentChanged,
  completeSaleFx,
  confirmPressed,
  modeChosen,
  paymentClosed,
  paymentOpened,
} from "../model/payment.ts";
import { DebtSalePanel, debtReady, useDebtView } from "./DebtSalePanel.tsx";

export interface CreditSaleDialogProps {
  receiptLabel: string;
  onDone: () => void;
}

export function CreditSaleDialog({ receiptLabel, onDone }: CreditSaleDialogProps) {
  const { t } = useTranslation("pos");
  const [p, totals, draft, online, error, pending, cashier, setComment] = useUnit([
    $payment,
    $totals,
    $draft,
    $isOnline,
    $paymentError,
    completeSaleFx.pending,
    $posCashier,
    commentChanged,
  ]);
  const view = useDebtView(draft.customerId);
  const opened = useRef(false);
  useEffect(() => {
    if (opened.current) return;
    opened.current = true;
    paymentOpened();
    modeChosen("debt");
  }, []);

  const ready =
    !!p &&
    p.mode === "debt" &&
    !pending &&
    cashierCan(cashier, "debts.create") &&
    draft.lines.length > 0 &&
    debtReady(view, totals.total, online, p.debtApproval !== null, p.debtOverLimitConfirmed);
  const close = () => {
    paymentClosed();
    onDone();
  };
  const dialogRef = useRef<HTMLDivElement | null>(null);
  useHotkeys(
    [
      {
        key: "Enter",
        allowInInput: true,
        handler: () => {
          if (!ready) return false;
          confirmPressed();
          return true;
        },
      },
    ],
    { scope: dialogRef },
  );

  return (
    <Dialog open onOpenChange={(o) => !o && close()}>
      <DialogContent
        ref={dialogRef}
        className="max-w-[920px]"
        onEscapeKeyDown={(e) => {
          e.preventDefault();
          close();
        }}
        onInteractOutside={(e) => e.preventDefault()}
        data-testid="credit-dialog"
      >
        <div className="flex flex-col gap-4 md:flex-row">
          <div className="flex min-w-0 flex-1 flex-col gap-3">
            <div className="flex items-center gap-2">
              <DialogTitle className="text-[22px] font-extrabold">{t("debts.creditTitle")}</DialogTitle>
              <Kbd keys="F5" />
            </div>
            <DialogDescription>{t("debts.creditHint")}</DialogDescription>
            <DebtSalePanel amount={totals.total} online={online} autoPick />
            <Label htmlFor="credit-comment">{t("debts.comment")}</Label>
            <Textarea
              id="credit-comment"
              rows={2}
              maxLength={1000}
              value={p?.comment ?? ""}
              onChange={(e) => setComment(e.target.value)}
            />
          </div>
          <aside className="flex w-full shrink-0 flex-col gap-3 rounded-xl bg-background p-4 md:w-[300px]">
            <span className="rounded-lg bg-muted px-2 py-1 text-[13px] font-bold">{receiptLabel}</span>
            <div>
              <div className="text-[13px] text-muted-foreground">{t("debts.onCredit")}</div>
              <div className="text-[30px] font-extrabold leading-tight" data-testid="credit-total">
                {formatMoney(totals.total)}
              </div>
            </div>
            <Banner tone="info" icon={ReceiptText}>
              <span className="flex flex-col gap-1">
                <span>{t("debts.noReceiptNow")}</span>
                <span className="font-normal">{t("debts.noReceiptWhy")}</span>
              </span>
            </Banner>
            {error ? (
              <Banner tone="destructive" icon={CircleAlert} live="assertive">
                <span data-testid="payment-error">{errorText(error.code, error.params ?? {})}</span>
              </Banner>
            ) : null}
            <div className="grow" />
            <Button
              size="pos-cta"
              className="w-full"
              disabled={!ready}
              onClick={() => confirmPressed()}
              data-testid="credit-confirm"
            >
              <Icon as={ReceiptText} size="lg" />
              {t("debts.creditConfirm")}
              <Kbd keys="Enter" inverted />
            </Button>
            <Button size="pos" variant="secondary" className="w-full" onClick={close}>
              {t("payment.back")}
              <Kbd keys="Esc" />
            </Button>
          </aside>
        </div>
      </DialogContent>
    </Dialog>
  );
}
