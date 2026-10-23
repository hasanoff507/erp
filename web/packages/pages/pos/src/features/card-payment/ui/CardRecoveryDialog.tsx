/**
 * SYNC-03 / 16 §12: a card attempt found after a reload (or by the logout blocker) is shown on its own —
 * `unknown` (status query, manager resolution) or `dangling` (an approved purchase no sale took: void it here,
 * or press «Karta» on the receipt of the same amount to attach it). Mounted once by the POS app shell.
 */
import { useUnit } from "effector-react";

import { useTranslation } from "@shared/i18n";
import { Button, Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@shared/ui";

import { $cardPhase, $cardRecoveryOpen, cardPaymentClosed, cardRecoveryClosed } from "../model/index.ts";
import { CardPayment } from "./CardPayment.tsx";
import { dyn } from "./i18n.ts";

/** Phases that may hide the dialog: the attempt stays in `card_attempts` until it is resolved. */
const DISMISSIBLE = new Set(["dangling", "voided", "void_failed", "declined", "idle"]);

export function CardRecoveryDialog() {
  const { t: tt } = useTranslation("pos");
  const t = dyn(tt);
  const [open, phase, dismiss, close] = useUnit([
    $cardRecoveryOpen,
    $cardPhase,
    cardRecoveryClosed,
    cardPaymentClosed,
  ]);
  if (!open) return null;
  const canDismiss = DISMISSIBLE.has(phase);
  const done = () => {
    if (phase === "voided" || phase === "void_failed" || phase === "declined") close();
    dismiss();
  };
  return (
    <Dialog open onOpenChange={(o) => (o || !canDismiss ? undefined : done())}>
      <DialogContent size="lg" hideClose data-testid="card-recovery-dialog" aria-describedby={undefined}>
        <DialogHeader>
          <DialogTitle>{t("cardPayment.title")}</DialogTitle>
        </DialogHeader>
        <CardPayment />
        <DialogFooter>
          <Button variant="secondary" size="lg" disabled={!canDismiss} onClick={done}>
            {t("cardPayment.actions.close")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
